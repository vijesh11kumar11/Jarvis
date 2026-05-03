"""
backend/services/research.py
Market intelligence: Tavily searches + Gemini synthesis.
"""
import os
import json
import asyncio
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from dotenv import load_dotenv

from ..db import database as db

load_dotenv()

try:
    from tavily import TavilyClient
    _TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    _tavily = TavilyClient(api_key=_TAVILY_KEY) if _TAVILY_KEY else None
except Exception:
    _tavily = None


@dataclass
class MarketReport:
    demand_level: str = "MEDIUM"
    demand_explanation: str = ""
    competitors: List[dict] = field(default_factory=list)
    pricing: dict = field(default_factory=dict)
    best_channels: List[dict] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    threats: List[str] = field(default_factory=list)
    summary: str = ""
    spoken_brief: str = ""
    sources: List[str] = field(default_factory=list)
    generated_at: str = ""
    location: str = ""
    product: str = ""

    def to_dict(self):
        return asdict(self)


async def _tavily_search(query: str, max_results: int = 5) -> dict:
    if not _tavily:
        return {"query": query, "results": [], "error": "no_tavily_key"}
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(
            None,
            lambda: _tavily.search(query=query, max_results=max_results,
                                   search_depth="basic"),
        )
    except Exception as e:
        return {"query": query, "results": [], "error": str(e)}


async def analyze_market_demand(product: str, location: str,
                                business_type: str, router,
                                user_id: Optional[str] = None) -> MarketReport:
    # Cache check
    if user_id:
        cached = await db.get_cached_research(user_id, product, location)
        if cached:
            r = cached["report"]
            return MarketReport(**{k: r.get(k) for k in MarketReport.__annotations__ if k in r})

    queries = [
        f"{product} market demand {location} 2025 2026",
        f"top {business_type} competitors in {location}",
        f"{product} pricing {location} market average",
        f"{business_type} customer behavior {location}",
        f"best marketing channels {business_type} {location}",
        f"{product} growing or declining trends {location}",
    ]
    results = await asyncio.gather(*(_tavily_search(q) for q in queries))

    # Build context for Gemini
    bundle = []
    sources = []
    for q, r in zip(queries, results):
        items = r.get("results", []) if isinstance(r, dict) else []
        for it in items[:5]:
            bundle.append(f"[{q}] {it.get('title','')}: {it.get('content','')[:400]}")
            if it.get("url"):
                sources.append(it["url"])

    context = "\n\n".join(bundle) if bundle else "(No live search results — Tavily key missing or no internet.)"

    prompt = f"""You are a senior market analyst. Based on these search results,
provide a structured market analysis as STRICT JSON. No prose around it.

Search results:
{context[:18000]}

Return JSON with EXACTLY these fields:
{{
  "demand_level": "HIGH|MEDIUM|LOW",
  "demand_explanation": "2 sentences",
  "competitors": [{{"name":"","strength":"","weakness":""}}],
  "pricing": {{"average":"", "range":"", "model":""}},
  "best_channels": [{{"channel":"","why":""}}],
  "opportunities": ["gap1","gap2","gap3"],
  "threats": ["risk1","risk2"],
  "summary": "200-word executive summary",
  "spoken_brief": "60 words max, written for text-to-speech delivery"
}}

Product: {product}
Location: {location}
Business type: {business_type}
"""
    try:
        raw = await router.simple_gemini(prompt)
    except Exception:
        raw = await router.simple_deepseek(prompt)
    parsed = {}
    try:
        s = raw.find("{"); e = raw.rfind("}")
        parsed = json.loads(raw[s:e + 1]) if s >= 0 else {}
    except Exception:
        parsed = {}

    report = MarketReport(
        demand_level=parsed.get("demand_level", "MEDIUM"),
        demand_explanation=parsed.get("demand_explanation", ""),
        competitors=parsed.get("competitors", []),
        pricing=parsed.get("pricing", {}),
        best_channels=parsed.get("best_channels", []),
        opportunities=parsed.get("opportunities", []),
        threats=parsed.get("threats", []),
        summary=parsed.get("summary", raw[:1200]),
        spoken_brief=parsed.get("spoken_brief", "Market research is ready."),
        sources=list(dict.fromkeys(sources))[:15],
        generated_at=datetime.utcnow().isoformat(),
        location=location,
        product=product,
    )

    if user_id:
        await db.save_market_research(user_id, product, location, report.to_dict())
    return report


async def get_weekly_market_brief(industry: str, router) -> str:
    now = datetime.utcnow()
    q = f"{industry} marketing news this week {now.strftime('%B %Y')}"
    r = await _tavily_search(q, max_results=8)
    items = r.get("results", []) if isinstance(r, dict) else []
    txt = "\n".join(f"- {i.get('title','')}: {i.get('content','')[:300]}" for i in items[:8])
    prompt = (f"Summarize this week's most important {industry} marketing news in "
              f"a 60-word spoken briefing for a busy founder. Conversational tone, "
              f"no bullets:\n\n{txt}")
    try:
        return await router.simple_gemini(prompt) or "No notable industry news this week."
    except Exception:
        return await router.simple_deepseek(prompt) or "No notable industry news this week."


async def competitor_deep_dive(competitor_name: str, location: str, router) -> dict:
    queries = [
        f"{competitor_name} pricing {location}",
        f"{competitor_name} reviews complaints",
        f"{competitor_name} marketing strategy",
        f"{competitor_name} social media presence",
    ]
    results = await asyncio.gather(*(_tavily_search(q) for q in queries))
    bundle = []
    for q, r in zip(queries, results):
        for it in r.get("results", [])[:4]:
            bundle.append(f"[{q}] {it.get('content','')[:300]}")
    prompt = (f"Based on the research below about competitor '{competitor_name}', "
              f"return strict JSON: {{\"strengths\":[],\"weaknesses\":[],\"how_to_beat\":[]}}.\n\n"
              + "\n".join(bundle)[:12000])
    try:
        raw = await router.simple_gemini(prompt)
    except Exception:
        raw = await router.simple_deepseek(prompt)
    try:
        s = raw.find("{"); e = raw.rfind("}")
        return json.loads(raw[s:e + 1])
    except Exception:
        return {"strengths": [], "weaknesses": [], "how_to_beat": [],
                "raw": raw[:2000]}


async def estimate_campaign_budget(goal: str, location: str,
                                   business_type: str, router) -> str:
    prompt = (
        f"As a 15-year marketing strategist, give a SPECIFIC budget recommendation "
        f"for this goal: '{goal}' for a {business_type} in {location}. "
        "Speak as voice (no markdown). Include: minimum viable budget, "
        "recommended budget, expected results, channel allocation percentages, "
        "and estimated CAC. Around 120 words."
    )
    try:
        return await router.simple_gemini(prompt) or ""
    except Exception:
        return await router.simple_deepseek(prompt) or ""


async def quick_search_summary(query: str, router) -> dict:
    r = await _tavily_search(query, max_results=5)
    items = r.get("results", []) if isinstance(r, dict) else []
    if not items:
        return {"success": False, "result": "No results."}
    snippets = "\n".join(f"- {i.get('title','')}: {i.get('content','')[:300]}"
                         for i in items)
    try:
        summary = await router.simple_gemini(
            f"Summarize this in 3 sentences as a briefing for a busy executive:\n{snippets}"
        )
    except Exception:
        summary = await router.simple_deepseek(
            f"Summarize this in 3 sentences as a briefing for a busy executive:\n{snippets}"
        )
    return {"success": True, "result": summary,
            "sources": [i.get("url") for i in items if i.get("url")]}
