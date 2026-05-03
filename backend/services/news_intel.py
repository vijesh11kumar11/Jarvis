"""
backend/services/news_intel.py
News + market-pulse engine for Friday's morning briefings and on-demand queries.

Combines NewsAPI (for headline-volume + global) with Tavily (for fresh,
analytic web results). Uses Gemini Flash to synthesize a spoken-friendly brief.
"""
from __future__ import annotations

import os
import asyncio
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

try:
    from newsapi import NewsApiClient
    _newsapi = NewsApiClient(api_key=os.getenv("NEWS_API_KEY")) \
        if os.getenv("NEWS_API_KEY") else None
except Exception:
    _newsapi = None

try:
    from tavily import TavilyClient
    _tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")) \
        if os.getenv("TAVILY_API_KEY") else None
except Exception:
    _tavily = None


def _safe(coro_factory):
    async def _wrap():
        try:
            return await coro_factory()
        except Exception as e:
            return {"error": str(e)}
    return _wrap()


def _newsapi_call(fn, *args, **kwargs):
    if not _newsapi: return {"articles": []}
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {"articles": [], "error": str(e)}


def _tavily_search(query: str, max_results: int = 5,
                   topic: str = "general") -> dict:
    if not _tavily: return {"results": []}
    try:
        return _tavily.search(query=query, max_results=max_results,
                              topic=topic, search_depth="advanced")
    except Exception as e:
        return {"results": [], "error": str(e)}


# ───────────── synthesis helper ─────────────
async def _synth(prompt: str, max_words: int = 90) -> str:
    from ..brain.ai_router import get_router
    router = get_router()
    full = (
        f"Synthesize the following into a SPOKEN brief of about {max_words} words. "
        "Use short sentences, no bullet markers, no markdown. Open with a friend-style "
        "hook (e.g., 'okay so', 'alright,'). End with one specific takeaway "
        "tied to a marketing or business angle if relevant.\n\n"
        f"{prompt}"
    )
    try:
        return (await router.simple_gemini(full, model="gemini-2.0-flash")).strip()
    except Exception:
        try:
            return (await router.simple_deepseek(full)).strip()
        except Exception:
            return ""


# ───────────── 1. Marketing news ─────────────
async def get_marketing_news(user_context: dict) -> dict:
    industry = (user_context.get("product") or "marketing").split()[0]
    headlines = _newsapi_call(_newsapi.get_top_headlines, category="business",
                              language="en", page_size=10)
    everything = _newsapi_call(_newsapi.get_everything,
                               q=f"{industry} marketing OR campaign OR brand",
                               language="en", sort_by="publishedAt",
                               page_size=10) if industry else {"articles": []}
    items: List[str] = []
    for src in (headlines, everything):
        for a in (src.get("articles") or [])[:8]:
            t = a.get("title") or ""
            d = a.get("description") or ""
            if t: items.append(f"- {t}. {d[:160]}")
    blob = "\n".join(items[:18]) or "No fresh marketing headlines."
    spoken = await _synth(
        f"User runs: {user_context.get('product','')}. Audience: {user_context.get('target_audience','')}.\n"
        f"Marketing headlines today:\n{blob}", max_words=90)
    return {"spoken": spoken, "items": items[:10]}


# ───────────── 2. Financial pulse ─────────────
async def get_financial_snapshot() -> dict:
    queries = [
        "NIFTY 50 today closing", "SENSEX today close", "USD INR rupee today",
        "Bitcoin BTC price today", "India stock market news today",
    ]
    results: List[str] = []
    for q in queries:
        r = _tavily_search(q, max_results=2)
        for item in (r.get("results") or [])[:2]:
            t = item.get("title") or ""
            c = (item.get("content") or "")[:200]
            if t: results.append(f"- {t}: {c}")
    blob = "\n".join(results) or "No market data."
    spoken = await _synth(
        f"Indian market & crypto pulse right now:\n{blob}", max_words=60)
    return {"spoken": spoken, "items": results[:8]}


# ───────────── 3. Industry trends ─────────────
async def get_industry_trends(user_context: dict) -> dict:
    product = user_context.get("product") or "small business"
    location = user_context.get("location") or "Coimbatore"
    q = f"latest trends {product} India {location} 2025"
    r = _tavily_search(q, max_results=6, topic="general")
    items = []
    for item in (r.get("results") or [])[:6]:
        t = item.get("title") or ""
        c = (item.get("content") or "")[:200]
        if t: items.append(f"- {t}: {c}")
    blob = "\n".join(items) or "No industry signal."
    spoken = await _synth(
        f"Trends for {product} in {location}:\n{blob}\n"
        "Tie this back to one practical move he could test this week.",
        max_words=90)
    return {"spoken": spoken, "items": items}


# ───────────── 4. Morning briefing ─────────────
async def generate_morning_briefing(user_context: dict, user_name: str = "Mr Vijesh"
                                    ) -> dict:
    marketing, financial, trends = await asyncio.gather(
        get_marketing_news(user_context),
        get_financial_snapshot(),
        get_industry_trends(user_context),
    )
    hour = datetime.now().hour
    salute = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Hey")
    combo = (
        f"{marketing.get('spoken','')}\n\n"
        f"Markets: {financial.get('spoken','')}\n\n"
        f"Trends for your space: {trends.get('spoken','')}"
    )
    spoken = await _synth(
        f"Open with a warm 1-line greeting to {user_name} — '{salute} {user_name}'. "
        "Then weave the three sections below into ONE flowing 60-90 word spoken "
        "briefing. End with a single question like 'want me to pull deeper on any of these?'.\n\n"
        + combo, max_words=120)
    return {
        "spoken": spoken,
        "marketing": marketing,
        "financial": financial,
        "trends": trends,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ───────────── 5. On-demand search ─────────────
async def search_news_on_demand(query: str, user_context: Optional[dict] = None
                                ) -> dict:
    user_context = user_context or {}
    r = _tavily_search(query, max_results=6)
    items = []
    for item in (r.get("results") or [])[:6]:
        t = item.get("title") or ""
        c = (item.get("content") or "")[:240]
        if t: items.append(f"- {t}: {c}")
    blob = "\n".join(items) or "No results."
    spoken = await _synth(
        f"User asked: '{query}'. Their product: {user_context.get('product','')}.\n"
        f"Search results:\n{blob}\n"
        "Always tie back to how this affects his business or marketing in one line.",
        max_words=90)
    return {"spoken": spoken, "items": items, "query": query}
