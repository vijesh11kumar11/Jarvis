"""
backend/db/memory.py
Friend-mode memory: builds the rich context block Friday uses to talk
to Mr Vijesh like someone who actually knows him.
"""
from __future__ import annotations

import json
import re
from typing import Optional
from datetime import datetime

from . import database as db
from ..brain.ai_router import get_router


# ────────────── Build the spoken-friendly memory context ──────────────
def _bullet(label: str, value: str) -> str:
    if not value: return ""
    return f"- {label}: {value.strip()}"


async def build_friend_memory_context(user_id: str,
                                      include_today: bool = True) -> str:
    """Returns a compact text block that prompts Friday with everything
    she should remember about the user. Spoken-style, no markdown noise."""
    user = await db.get_user(user_id) or {}
    about = await db.get_about_me(user_id) or {}
    profile = await db.get_friend_profile(user_id) or {}
    mems = await db.get_personal_memories(user_id, limit=40)
    today = await db.get_todays_context(user_id) if include_today else None
    summaries = await db.get_recent_summaries(user_id, limit=3)

    lines = [f"=== WHAT I KNOW ABOUT {user.get('name','my friend').upper()} ==="]

    # Identity / story
    if about.get("life_story"):
        lines.append("\n[life story]")
        lines.append(about["life_story"][:1200])

    # Categorized memories
    if mems:
        by_cat: dict[str, list[str]] = {}
        for m in mems:
            by_cat.setdefault(m["category"], []).append(m["content"])
        priority = ["family", "goal", "dream", "fear", "project",
                    "preference", "habit", "relationship", "milestone",
                    "health", "finance", "other"]
        for cat in priority:
            items = by_cat.get(cat, [])
            if not items: continue
            lines.append(f"\n[{cat}]")
            for c in items[:6]:
                lines.append(f"- {c.strip()}")

    # Friend profile
    if profile:
        prof_lines = []
        for k in ("favorite_topics", "inside_jokes", "triggers_to_avoid",
                  "motivation_style", "communication_preferences",
                  "energy_pattern"):
            v = profile.get(k) or ""
            if v: prof_lines.append(_bullet(k.replace("_", " "), v))
        if prof_lines:
            lines.append("\n[how to talk to him]")
            lines.extend(prof_lines)

    # Today's context
    if today:
        bits = []
        if today.get("mood"): bits.append(f"mood: {today['mood']}")
        if today.get("energy_level"): bits.append(f"energy {today['energy_level']}/10")
        if today.get("focus_area"): bits.append(f"focused on {today['focus_area']}")
        if today.get("wins"): bits.append(f"wins: {today['wins']}")
        if today.get("challenges"): bits.append(f"struggling with: {today['challenges']}")
        if bits:
            lines.append("\n[today]")
            lines.append("- " + "; ".join(bits))

    # Recent conversation summaries
    if summaries:
        lines.append("\n[recent conversations]")
        for s in summaries[:3]:
            txt = (s.get("summary") or "")[:280]
            if txt: lines.append(f"- {txt}")

    lines.append("\n=== END ===")
    return "\n".join(lines)


# Backwards-compatible name used by older code paths
async def build_memory_context(user_id: str) -> str:
    return await build_friend_memory_context(user_id)


# ────────────── Memory extraction (background after each turn) ──────────────
EXTRACT_PROMPT = """You are an expert listener. Extract NEW personal facts about the user from this conversation snippet.
Return ONLY valid JSON in the form:
{"memories":[{"category":"family|goal|preference|fear|dream|habit|relationship|milestone|project|health|finance|other","content":"<short fact, first-person rewrite e.g. 'has a daughter named X who is 4'>","importance":1-10}]}
Skip generic statements. Skip things you can't be sure about. If nothing to extract, return {"memories":[]}.
Conversation:
USER: {user_msg}
ASSISTANT: {assistant_msg}
"""


def _safe_json(text: str) -> dict:
    if not text: return {}
    m = re.search(r"\{[\s\S]*\}", text)
    if not m: return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


async def extract_memories_from_conversation(user_id: str,
                                             user_message: str,
                                             assistant_message: str) -> list:
    """Background task — runs after every chat turn."""
    if not user_message or len(user_message) < 8:
        return []
    router = get_router()
    prompt = EXTRACT_PROMPT.format(
        user_msg=user_message[:1500],
        assistant_msg=(assistant_message or "")[:1500],
    )
    try:
        raw = await router.simple_gemini(prompt, model="gemini-2.0-flash-exp")
    except Exception:
        try:
            raw = await router.simple_deepseek(prompt)
        except Exception:
            return []
    parsed = _safe_json(raw)
    saved = []
    for m in (parsed.get("memories") or [])[:6]:
        cat = (m.get("category") or "other").lower()
        content = (m.get("content") or "").strip()
        importance = int(m.get("importance") or 5)
        if not content or len(content) < 4: continue
        try:
            mid = await db.save_personal_memory(user_id, cat, content,
                                                max(1, min(10, importance)))
            saved.append({"id": mid, "category": cat, "content": content,
                          "importance": importance})
        except Exception:
            continue
    return saved


# ────────────── Conversation summarizer (for /memory/save endpoint) ──────────────
async def summarize_conversation(conversation_id: str, user_id: str,
                                 router=None) -> str:
    msgs = await db.get_recent_messages(conversation_id, 50)
    if not msgs: return ""
    transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in msgs)
    prompt = (
        "Summarize this conversation in 4 short sentences. Then list key decisions, "
        "action items, and topics on separate lines as 'Decisions:', 'Actions:', 'Topics:'.\n\n"
        + transcript[:8000]
    )
    if router is None:
        router = get_router()
    try:
        text = await router.simple_gemini(prompt)
    except Exception:
        text = await router.simple_deepseek(prompt)
    if text:
        await db.save_summary(user_id, conversation_id, text[:2000])
    return text
