"""
backend/brain/idea_engine.py
Friday's Marketing Ideas Lab — generate, evaluate, remix campaign ideas.
Spoken-friendly outputs with concrete execution steps.
"""
from __future__ import annotations
import json
import re
from typing import Optional


def _safe_json(text: str) -> dict:
    if not text: return {}
    m = re.search(r"\{[\s\S]*\}", text)
    if not m: return {}
    try: return json.loads(m.group(0))
    except Exception: return {}


class IdeaEngine:
    MODES = {
        "viral": "high-shareability, hook-driven, designed to spread on Reels/Shorts.",
        "community": "build a real audience over 90 days through events, WhatsApp groups, local meetups.",
        "content": "evergreen content engine — blog/video/podcast that compounds.",
        "partnership": "co-marketing collabs with non-competing brands or influencers.",
        "guerrilla": "low-budget, on-the-ground stunts that earn press and word of mouth.",
    }

    def __init__(self, ai_router):
        self.ai = ai_router

    async def generate_ideas(self, topic: str, user_context: dict,
                             friend_context: str = "", mode: str = "viral",
                             count: int = 5) -> list:
        mode_desc = self.MODES.get(mode, self.MODES["viral"])
        prompt = f"""You are a senior marketing strategist generating {count} {mode} ideas.
Mode: {mode} — {mode_desc}

USER BUSINESS CONTEXT:
- product: {user_context.get('product','')}
- audience: {user_context.get('target_audience','')}
- location: {user_context.get('location','Coimbatore')}
- budget: {user_context.get('budget_range','small')}
- brand voice: {user_context.get('brand_voice','')}
- what worked: {user_context.get('what_worked','')}
- what failed: {user_context.get('what_failed','')}

FRIEND CONTEXT (use if relevant):
{friend_context[:1200]}

Return ONLY valid JSON in this exact shape:
{{"ideas":[
  {{
    "name": "<short punchy name>",
    "tagline": "<1-line pitch>",
    "the_insight": "<1-2 sentence why this works for THIS user>",
    "execution": ["<step 1>","<step 2>","<step 3>"],
    "what_makes_it_different": "<1 sentence>",
    "success_metric": "<concrete numeric goal>",
    "time_to_first_results": "<e.g. 2 weeks>",
    "spoken_pitch": "<friend-style 30-40 word pitch he can hear and instantly get>"
  }}
]}}"""
        raw = ""
        try:
            raw = await self.ai.simple_gemini(prompt, model="gemini-2.0-flash")
        except Exception:
            try:
                raw = await self.ai.simple_deepseek(prompt)
            except Exception:
                raw = ""
        parsed = _safe_json(raw)
        return (parsed.get("ideas") or [])[:count]

    async def evaluate_idea(self, idea: dict, user_context: dict) -> dict:
        prompt = f"""Evaluate this marketing idea for the user. Score 1-10 on each dimension.
USER: product={user_context.get('product','')}, audience={user_context.get('target_audience','')}, budget={user_context.get('budget_range','')}.
IDEA: {json.dumps(idea)}
Return ONLY valid JSON:
{{"scores":{{"fit":1-10,"feasibility":1-10,"originality":1-10,"speed_to_value":1-10,"risk":1-10}},
  "verdict":"GREEN|YELLOW|RED",
  "why":"<1-2 sentences>",
  "fix_if_yellow":"<1 sentence or empty>",
  "spoken_verdict":"<friend-style 25-35 word verbal opinion>"}}"""
        try:
            raw = await self.ai.simple_gemini(prompt, model="gemini-2.0-flash")
        except Exception:
            raw = await self.ai.simple_deepseek(prompt)
        return _safe_json(raw) or {"verdict": "YELLOW", "why": "Couldn't evaluate.",
                                   "spoken_verdict": ""}

    async def remix_idea(self, original_idea: dict, constraint: str,
                         user_context: dict) -> dict:
        prompt = f"""Remix this idea to satisfy a new constraint.
ORIGINAL: {json.dumps(original_idea)}
CONSTRAINT: {constraint}
USER: {json.dumps({k: user_context.get(k,'') for k in ('product','audience','budget_range','location')})}
Return ONLY valid JSON in the same shape as a single idea (with name, tagline,
the_insight, execution[], what_makes_it_different, success_metric,
time_to_first_results, spoken_pitch)."""
        try:
            raw = await self.ai.simple_gemini(prompt, model="gemini-2.0-flash")
        except Exception:
            raw = await self.ai.simple_deepseek(prompt)
        parsed = _safe_json(raw)
        return parsed if parsed.get("name") else {"error": "remix failed"}
