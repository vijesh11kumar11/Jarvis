"""
backend/db/memory.py
Long-term conversational memory for Jarvis.
"""
from datetime import datetime
from . import database as db


def _human_age(ts: str) -> str:
    try:
        when = datetime.fromisoformat(ts.replace("Z", ""))
    except Exception:
        return "recently"
    delta = datetime.utcnow() - when
    days = delta.days
    if days <= 0:
        hrs = delta.seconds // 3600
        return f"{hrs} hours ago" if hrs else "just now"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        return f"{days // 7} weeks ago"
    return f"{days // 30} months ago"


async def build_memory_context(user_id: str, limit: int = 5) -> str:
    me = await db.get_about_me(user_id)
    parts = []
    me_lines = []
    if me.get("life_story"):
        me_lines.append(f"LIFE STORY:\n{me['life_story'].strip()}")
    if me.get("preferences"):
        me_lines.append(f"PREFERENCES:\n{me['preferences'].strip()}")
    if me.get("facts"):
        me_lines.append(f"FACTS FRIDAY HAS LEARNED:\n{me['facts'].strip()}")
    if me_lines:
        parts.append("ABOUT THE USER (remember and reference naturally):\n" + "\n".join(me_lines))

    summaries = await db.get_recent_summaries(user_id, limit=limit)
    if summaries:
        lines = ["MEMORY FROM PAST SESSIONS:"]
        for s in summaries:
            age = _human_age(s.get("created_at", ""))
            lines.append(f"- [{age}] {s['summary'].strip()}")
            if s.get("action_items"):
                lines.append(f"   Action items: {s['action_items']}")
        parts.append("\n".join(lines))

    attachments = await db.get_recent_attachments(user_id, limit=3)
    if attachments:
        a_lines = ["RECENT ATTACHMENTS USER SHARED:"]
        for a in attachments:
            a_lines.append(f"- ({a['kind']}) {a['name']}: {a.get('summary','')[:300]}")
        parts.append("\n".join(a_lines))

    if not parts:
        return "No previous sessions on record. This is your first conversation."
    return "\n\n".join(parts)


async def summarize_conversation(conversation_id: str, user_id: str,
                                 ai_router) -> str:
    """Use Gemini to summarize a finished conversation."""
    msgs = await db.get_recent_messages(conversation_id, limit=200)
    if not msgs:
        return ""
    transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in msgs)
    prompt = (
        "Summarize this marketing conversation in EXACTLY 3 bullet points "
        "focusing on: decisions made, strategies discussed, action items the "
        "user committed to. Be specific with numbers, names, channels, dates.\n\n"
        f"{transcript}\n\nReturn only the 3 bullet points, no preamble."
    )
    summary = await ai_router.simple_gemini(prompt)
    await db.save_summary(user_id, conversation_id, summary)
    return summary


async def get_user_context(user_id: str) -> dict:
    user = await db.get_user(user_id)
    biz = await db.get_business_context(user_id)
    summaries = await db.get_recent_summaries(user_id, 5)
    research = await db.get_latest_research(user_id)
    return {
        "user": user,
        "business": biz,
        "summaries": summaries,
        "latest_research": research,
    }
