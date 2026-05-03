"""
backend/main.py
Marketing Jarvis (Friday) — voice-only friend backend.
Run: python backend/main.py
"""
from __future__ import annotations
import os
import json
import asyncio
import tempfile
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.db import database as db
from backend.db import memory as mem
from backend.brain.ai_router import get_router
from backend.brain.marketing_brain import build_marketing_brain
from backend.brain.idea_engine import IdeaEngine
from backend.brain import computer_control as cc
from backend.services import research as rs
from backend.services import voice_pipeline as vp
from backend.services import documents as doc_svc
from backend.services import github_repo as gh_svc
from backend.services import news_intel as news

load_dotenv()
DEFAULT_JARVIS_NAME = os.getenv("DEFAULT_JARVIS_NAME", "Friday")
DEFAULT_USER_NAME = os.getenv("DEFAULT_USER_NAME", "Mr Vijesh")
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "Coimbatore, India")
PORT = int(os.getenv("APP_PORT", "8000"))

_clap_listener = None
_wake_listener = None
_wake_subscribers: List[asyncio.Queue] = []
_pending_actions: dict[str, dict] = {}


def _wake_event(source: str):
    payload = json.dumps({"source": source})
    for q in list(_wake_subscribers):
        try: q.put_nowait(payload)
        except Exception: pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_database()
    print(f"[jarvis] database ready at {os.getenv('DB_PATH')}")
    print(f"[jarvis] backend listening on http://localhost:{PORT}")
    yield
    if _clap_listener: _clap_listener.stop()
    if _wake_listener: _wake_listener.stop()


app = FastAPI(title="Friday — Marketing Jarvis", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# ═══ Models ═══
class ChatRequest(BaseModel):
    user_id: Optional[str] = None
    jarvis_name: str = "Friday"
    user_name: str = "Mr Vijesh"
    message: str
    business_context: Optional[dict] = None
    conversation_id: Optional[str] = None
    use_model: Optional[str] = None
    attached_context: Optional[str] = None
    mode: Optional[str] = None


class SpeakRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None


class ResearchRequest(BaseModel):
    user_id: Optional[str] = None
    query: str = ""
    location: str
    business_type: str
    product: str


class ComputerRequest(BaseModel):
    user_id: Optional[str] = None
    action: Optional[str] = None
    params: Optional[dict] = None
    natural_command: Optional[str] = None
    require_confirmation: bool = False


class UserCreate(BaseModel):
    name: str
    jarvis_name: str = "Friday"
    email: Optional[str] = None


class AboutMeUpdate(BaseModel):
    user_id: str
    life_story: Optional[str] = ""
    preferences: Optional[str] = ""
    facts: Optional[str] = ""


class GithubAnalyzeRequest(BaseModel):
    user_id: Optional[str] = None
    url: str


class VisionChatRequest(BaseModel):
    user_id: Optional[str] = None
    jarvis_name: str = "Friday"
    user_name: str = "Mr Vijesh"
    image_b64: str
    prompt: str = "What do you see, and how would a marketing CMO read this?"


class BusinessUpdate(BaseModel):
    user_id: str
    business_name: Optional[str] = None
    product: Optional[str] = None
    target_audience: Optional[str] = None
    location: Optional[str] = None
    budget_range: Optional[str] = None
    competitors: Optional[str] = None
    brand_voice: Optional[str] = None
    what_worked: Optional[str] = None
    what_failed: Optional[str] = None


class DailyContextUpdate(BaseModel):
    user_id: str
    mood: Optional[str] = ""
    energy_level: Optional[int] = 5
    focus_area: Optional[str] = ""
    wins: Optional[str] = ""
    challenges: Optional[str] = ""


class FriendProfileUpdate(BaseModel):
    user_id: str
    favorite_topics: Optional[str] = None
    inside_jokes: Optional[str] = None
    triggers_to_avoid: Optional[str] = None
    motivation_style: Optional[str] = None
    communication_preferences: Optional[str] = None
    energy_pattern: Optional[str] = None


class MemorySave(BaseModel):
    user_id: str
    category: str
    content: str
    importance: int = 5


class MemoryExtract(BaseModel):
    user_id: str
    user_message: str
    assistant_message: str = ""


class IdeaGenRequest(BaseModel):
    user_id: Optional[str] = None
    topic: str
    mode: str = "viral"
    count: int = 5


class IdeaEvalRequest(BaseModel):
    user_id: Optional[str] = None
    idea: dict


class IdeaRemixRequest(BaseModel):
    user_id: Optional[str] = None
    idea: dict
    constraint: str


class NewsSearchRequest(BaseModel):
    user_id: Optional[str] = None
    query: str


class ConfirmActionRequest(BaseModel):
    action_id: str
    confirm: bool


# ═══ Helpers ═══
async def _full_context(user_id: str) -> dict:
    biz = await db.get_business_context(user_id) if user_id != "anonymous" else None
    biz = biz or {}
    return {
        "user": await db.get_user(user_id) if user_id != "anonymous" else {},
        "business": biz,
        "product": biz.get("product", ""),
        "target_audience": biz.get("target_audience", ""),
        "location": biz.get("location", DEFAULT_LOCATION),
        "budget_range": biz.get("budget_range", ""),
        "brand_voice": biz.get("brand_voice", ""),
        "what_worked": biz.get("what_worked", ""),
        "what_failed": biz.get("what_failed", ""),
    }


MODE_PHRASES = {
    "advisor": ["be more direct", "advisor mode", "executive mode", "cut to it"],
    "critic":  ["be more critical", "stress test", "tear it apart", "be brutal"],
    "friend":  ["just help me", "talk like a friend", "friend mode", "be chill"],
}


def _detect_mode_switch(message: str) -> Optional[str]:
    m = (message or "").lower()
    for mode, triggers in MODE_PHRASES.items():
        if any(t in m for t in triggers):
            return mode
    return None


# ═══ Routes ═══
@app.get("/health")
async def health():
    return {"ok": True,
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
            "elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY")),
            "tavily": bool(os.getenv("TAVILY_API_KEY")),
            "newsapi": bool(os.getenv("NEWS_API_KEY"))}


@app.post("/chat")
async def chat(req: ChatRequest):
    router = get_router()
    user_id = req.user_id or "anonymous"

    if user_id != "anonymous" and not await db.get_user(user_id):
        await db.create_user(req.user_name, req.jarvis_name)
    conv_id = req.conversation_id
    if not conv_id and user_id != "anonymous":
        conv_id = await db.start_conversation(user_id)

    new_mode = _detect_mode_switch(req.message)
    user_record = await db.get_user(user_id) if user_id != "anonymous" else {}
    current_mode = req.mode or (user_record or {}).get("current_mode") or "friend"
    if new_mode and user_id != "anonymous":
        try: await db.update_user(user_id, current_mode=new_mode)
        except Exception: pass
        current_mode = new_mode

    biz = req.business_context or (await db.get_business_context(user_id) if user_id != "anonymous" else None)
    research = await db.get_latest_research(user_id) if user_id != "anonymous" else None
    me = await db.get_about_me(user_id) if user_id != "anonymous" else {}
    friend_ctx = await mem.build_friend_memory_context(user_id) if user_id != "anonymous" else ""

    sys_prompt = build_marketing_brain(
        jarvis_name=req.jarvis_name,
        user_name=req.user_name,
        business_context=biz,
        market_research=research,
        user_location=(biz or {}).get("location", DEFAULT_LOCATION),
        memory_context="",
        about_me=me,
        attached_context=req.attached_context or "",
        friend_context=friend_ctx,
        mode=current_mode,
    )

    history = await db.get_recent_messages(conv_id, 10) if conv_id else []
    if conv_id:
        await db.add_message(conv_id, "user", req.message)

    user_msg = req.message

    async def streamer():
        full = []
        try:
            _error_prefixes = ("[gemini error", "[groq error", "[deepseek error")
            async for tok in router.stream_with_fallback(
                    sys_prompt, req.message, history, force_model=req.use_model):
                # Last-resort guard: never send raw API error tokens to the frontend
                if tok and tok.lower().lstrip().startswith(_error_prefixes):
                    continue
                if tok and ("quota exceeded" in tok.lower() or "429" in tok):
                    continue
                full.append(tok)
                yield f"data: {json.dumps({'delta': tok})}\n\n"
            text = "".join(full).strip()
            if conv_id and text:
                await db.add_message(conv_id, "assistant", text,
                                     model_used=req.use_model or "auto")

            # ── Detect JSON action block in response ──────────────────────
            import re as _re, uuid as _uuid
            done_payload: dict = {"done": True, "conversation_id": conv_id,
                                  "mode": current_mode}
            _NO_CONFIRM = {"open_website", "open_app", "screenshot", "search_web"}
            _action_m = _re.search(r'\{[^{}]*"action"\s*:[^{}]*\}', text, _re.DOTALL)
            if _action_m:
                try:
                    _aj = json.loads(_action_m.group())
                    _act = _aj.get("action", "")
                    _speak = _aj.get("speak", "")
                    _params = {k: v for k, v in _aj.items()
                               if k not in ("action", "speak")}
                    if _act in _NO_CONFIRM:
                        _res = await cc.execute(_act, _params, router=router)
                        done_payload["action_executed"] = {
                            "action": _act, "result": _res, "speak": _speak}
                        done_payload["speak"] = _speak
                        if req.user_id:
                            await db.log_computer_action(
                                req.user_id, _act, _params,
                                _res.get("success", False),
                                str(_res.get("result", ""))[:500])
                    elif _act:
                        _aid = str(_uuid.uuid4())
                        _pending_actions[_aid] = {
                            "action": _act, "params": _params,
                            "user_id": req.user_id, "speak": _speak}
                        done_payload["requires_confirmation"] = True
                        done_payload["action_id"] = _aid
                        done_payload["action"] = _act
                        done_payload["speak"] = _speak
                except Exception:
                    pass  # not valid JSON — treat as plain conversation

            yield f"data: {json.dumps(done_payload)}\n\n"
            if user_id != "anonymous" and text:
                asyncio.create_task(
                    mem.extract_memories_from_conversation(user_id, user_msg, text))
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(streamer(), media_type="text/event-stream")


@app.post("/speak")
async def speak(req: SpeakRequest):
    async def gen():
        async for chunk in vp.speak_streaming(req.text, req.voice_id):
            if chunk: yield chunk
    return StreamingResponse(gen(), media_type="audio/mpeg")


@app.post("/listen")
async def listen(audio: UploadFile = File(...)):
    raw = await audio.read()
    return await vp.transcribe_audio(raw)


@app.post("/research")
async def research_endpoint(req: ResearchRequest):
    router = get_router()
    report = await rs.analyze_market_demand(
        product=req.product, location=req.location,
        business_type=req.business_type, router=router,
        user_id=req.user_id,
    )
    return report.to_dict() if hasattr(report, "to_dict") else report


@app.get("/research/weekly/{user_id}")
async def weekly(user_id: str, industry: str = "marketing"):
    return {"brief": await rs.get_weekly_market_brief(industry, get_router())}


@app.post("/computer/execute")
async def computer_execute(req: ComputerRequest):
    router = get_router()
    if req.natural_command and not req.action:
        intent = await cc.parse_computer_command(req.natural_command, router)
        action = intent.get("action"); params = intent.get("params", {})
        speak = intent.get("speak", "")
    else:
        action, params, speak = req.action, req.params or {}, ""

    if not action or action == "none":
        return {"success": False, "result": "No actionable command detected.",
                "speak": speak}

    if req.require_confirmation:
        import uuid
        aid = str(uuid.uuid4())
        _pending_actions[aid] = {"action": action, "params": params,
                                 "user_id": req.user_id, "speak": speak}
        return {"requires_confirmation": True, "action_id": aid,
                "action": action, "params": params,
                "speak": speak or f"I'm about to {action}. Should I go ahead?"}

    result = await cc.execute(action, params, router=router)
    if req.user_id:
        await db.log_computer_action(req.user_id, action, params,
                                     result.get("success", False),
                                     str(result.get("result", ""))[:1000])
    result["speak"] = speak or result.get("result", "")
    result["action"] = action
    return result


@app.post("/computer/confirm")
async def computer_confirm(req: ConfirmActionRequest):
    pending = _pending_actions.pop(req.action_id, None)
    if not pending:
        return {"success": False, "result": "Action expired or unknown."}
    if not req.confirm:
        return {"success": True, "result": "Cancelled.", "cancelled": True}
    router = get_router()
    result = await cc.execute(pending["action"], pending["params"], router=router)
    if pending.get("user_id"):
        await db.log_computer_action(pending["user_id"], pending["action"],
                                     pending["params"],
                                     result.get("success", False),
                                     str(result.get("result", ""))[:1000])
    return result


@app.get("/system/info")
async def system_info():
    return cc.get_system_info()


@app.post("/user")
async def create_user(req: UserCreate):
    return await db.create_user(req.name, req.jarvis_name, req.email)


@app.get("/user/{user_id}")
async def get_user(user_id: str):
    u = await db.get_user(user_id)
    if not u: raise HTTPException(404, "Not found")
    return {"user": u, "business": await db.get_business_context(user_id)}


@app.post("/business")
async def update_business(req: BusinessUpdate):
    fields = {k: v for k, v in req.model_dump().items() if k != "user_id" and v is not None}
    return await db.upsert_business_context(req.user_id, **fields)


@app.post("/memory/save/{conversation_id}")
async def save_memory(conversation_id: str, user_id: str):
    return {"summary": await mem.summarize_conversation(conversation_id, user_id)}


@app.get("/memory/{user_id}")
async def get_memory(user_id: str):
    return {"context": await mem.build_friend_memory_context(user_id)}


@app.post("/memory/save-fact")
async def save_fact(req: MemorySave):
    mid = await db.save_personal_memory(req.user_id, req.category,
                                        req.content, req.importance)
    return {"id": mid}


@app.get("/memory/list/{user_id}")
async def list_memories(user_id: str, category: Optional[str] = None):
    return {"memories": await db.get_personal_memories(user_id, category)}


@app.post("/memory/extract")
async def memory_extract(req: MemoryExtract):
    saved = await mem.extract_memories_from_conversation(
        req.user_id, req.user_message, req.assistant_message)
    return {"saved": saved}


@app.post("/daily-context")
async def daily_context_save(req: DailyContextUpdate):
    cid = await db.save_daily_context(req.user_id, req.mood or "",
                                      req.energy_level or 5,
                                      req.focus_area or "",
                                      req.wins or "", req.challenges or "")
    return {"id": cid}


@app.get("/daily-context/{user_id}")
async def daily_context_get(user_id: str):
    return await db.get_todays_context(user_id) or {}


@app.get("/friend-profile/{user_id}")
async def friend_profile_get(user_id: str):
    return await db.get_friend_profile(user_id)


@app.post("/friend-profile/update")
async def friend_profile_update(req: FriendProfileUpdate):
    fields = {k: v for k, v in req.model_dump().items()
              if k != "user_id" and v is not None}
    return await db.update_friend_profile(req.user_id, **fields)


@app.post("/wake-word/start")
async def wake_start(keyword: str = "hey_jarvis"):
    global _wake_listener, _clap_listener
    if _wake_listener: _wake_listener.stop()
    if _clap_listener: _clap_listener.stop()
    handles = vp.start_all_wake_listeners(lambda: _wake_event("any"), keyword)
    _wake_listener = handles.get("voice_thread")
    _clap_listener = handles.get("clap_thread")
    return {"started": True, "keyword": keyword}


@app.post("/wake-word/stop")
async def wake_stop():
    global _wake_listener, _clap_listener
    if _wake_listener: _wake_listener.stop(); _wake_listener = None
    if _clap_listener: _clap_listener.stop(); _clap_listener = None
    return {"stopped": True}


@app.get("/wake-word/events")
async def wake_events(request: Request):
    q: asyncio.Queue = asyncio.Queue()
    _wake_subscribers.append(q)

    async def gen():
        try:
            while True:
                if await request.is_disconnected(): break
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {item}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            try: _wake_subscribers.remove(q)
            except ValueError: pass
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/wake/spoken/start")
async def wake_spoken_start(model: Optional[str] = None):
    return await wake_start(model or os.getenv("WAKE_WORD_MODEL", "hey_jarvis"))


@app.get("/usage/{user_id}")
async def usage(user_id: str):
    return await db.get_usage_summary(user_id)


@app.get("/about-me/{user_id}")
async def get_about_me(user_id: str):
    return await db.get_about_me(user_id)


@app.post("/about-me")
async def save_about_me(req: AboutMeUpdate):
    return await db.upsert_about_me(req.user_id,
                                    life_story=req.life_story or "",
                                    preferences=req.preferences or "",
                                    facts=req.facts or "")


@app.post("/upload/document")
@app.post("/analyze/document")
async def analyze_document(user_id: str = Form("anonymous"),
                           file: UploadFile = File(...)):
    file_bytes = await file.read()
    ctx = await _full_context(user_id) if user_id != "anonymous" else {}
    friend_ctx = await mem.build_friend_memory_context(user_id) if user_id != "anonymous" else ""
    result = await doc_svc.analyze_document_for_marketing(
        file_bytes, file.filename or "doc",
        user_context=ctx, friend_context=friend_ctx,
        user_name=DEFAULT_USER_NAME,
    )
    if user_id and user_id != "anonymous" and not result.get("error"):
        await db.save_attachment(user_id, "document",
                                 file.filename or "document",
                                 (result.get("analysis") or "")[:2000],
                                 (result.get("extract_preview") or "")[:50000])
    return result


@app.post("/analyze/github")
async def analyze_github(req: GithubAnalyzeRequest):
    ctx = await _full_context(req.user_id or "anonymous")
    result = await gh_svc.analyze_repo_for_marketing(req.url,
                                                     user_context=ctx,
                                                     user_name=DEFAULT_USER_NAME)
    if req.user_id and req.user_id != "anonymous" and not result.get("error"):
        d = result.get("data", {})
        name = f"{d.get('owner','?')}/{d.get('repo','?')}"
        await db.save_attachment(req.user_id, "github", name,
                                 (result.get("analysis") or "")[:2000],
                                 (d.get("readme") or "")[:50000])
    return result


@app.get("/analyze/github/cached/{user_id}")
async def analyze_github_cached(user_id: str):
    rows = await db.get_recent_attachments(user_id, 10)
    return [r for r in rows if r.get("kind") == "github"]


@app.post("/vision/chat")
async def vision_chat(req: VisionChatRequest):
    router = get_router()
    biz = await db.get_business_context(req.user_id) if req.user_id else None
    me = await db.get_about_me(req.user_id) if req.user_id else {}
    sys_prompt = build_marketing_brain(
        jarvis_name=req.jarvis_name, user_name=req.user_name,
        business_context=biz, market_research=None,
        user_location=(biz or {}).get("location", DEFAULT_LOCATION),
        memory_context="", about_me=me,
        attached_context="(User has attached an image. See vision output.)",
    )
    full_prompt = f"{sys_prompt}\n\nUSER MESSAGE: {req.prompt}"
    answer = await router.gemini_vision_call(req.image_b64, full_prompt)
    if req.user_id and req.user_id != "anonymous":
        await db.save_attachment(req.user_id, "image",
                                 "image-upload", answer[:2000], "")
    return {"answer": answer}


@app.get("/news/morning-brief/{user_id}")
async def news_morning(user_id: str):
    ctx = await _full_context(user_id)
    user = (await db.get_user(user_id)) or {}
    return await news.generate_morning_briefing(ctx, user.get("name", DEFAULT_USER_NAME))


@app.get("/news/today/{user_id}")
async def news_today(user_id: str):
    return await news.get_marketing_news(await _full_context(user_id))


@app.get("/news/market-pulse")
async def news_market():
    return await news.get_financial_snapshot()


@app.get("/news/industry/{user_id}")
async def news_industry(user_id: str):
    return await news.get_industry_trends(await _full_context(user_id))


@app.post("/news/search")
async def news_search(req: NewsSearchRequest):
    return await news.search_news_on_demand(
        req.query, await _full_context(req.user_id or "anonymous"))


@app.post("/ideas/generate")
async def ideas_generate(req: IdeaGenRequest):
    ctx = await _full_context(req.user_id or "anonymous")
    friend_ctx = await mem.build_friend_memory_context(req.user_id) \
        if req.user_id and req.user_id != "anonymous" else ""
    engine = IdeaEngine(get_router())
    ideas = await engine.generate_ideas(req.topic, ctx, friend_ctx,
                                        req.mode, req.count)
    return {"ideas": ideas, "topic": req.topic, "mode": req.mode}


@app.post("/ideas/evaluate")
async def ideas_evaluate(req: IdeaEvalRequest):
    ctx = await _full_context(req.user_id or "anonymous")
    return await IdeaEngine(get_router()).evaluate_idea(req.idea, ctx)


@app.post("/ideas/remix")
async def ideas_remix(req: IdeaRemixRequest):
    ctx = await _full_context(req.user_id or "anonymous")
    return await IdeaEngine(get_router()).remix_idea(req.idea, req.constraint, ctx)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=PORT, reload=False)
