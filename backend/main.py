"""
backend/main.py
Marketing Jarvis backend (FastAPI). Gemini + Groq only.
Run:  python -m uvicorn backend.main:app --reload --port 8000
Or:   python backend/main.py
"""
import os
import json
import asyncio
import tempfile
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Allow running both as `python backend/main.py` and as a module
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.db import database as db
from backend.db import memory as mem
from backend.brain.ai_router import get_router
from backend.brain.marketing_brain import build_marketing_brain
from backend.brain import computer_control as cc
from backend.services import research as rs
from backend.services import voice_pipeline as vp
from backend.services import documents as doc_svc
from backend.services import github_repo as gh_svc

load_dotenv()
DEFAULT_JARVIS_NAME = os.getenv("DEFAULT_JARVIS_NAME", "Friday")
DEFAULT_USER_NAME = os.getenv("DEFAULT_USER_NAME", "Mr Vijesh")
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "Coimbatore, India")
PORT = int(os.getenv("APP_PORT", "8000"))

# Keep references to background listeners
_clap_listener: Optional[vp.DoubleClapDetector] = None
_wake_listener: Optional[vp.PorcupineListener] = None
# Wake event subscribers (SSE)
_wake_subscribers: List[asyncio.Queue] = []


def _wake_event(source: str):
    payload = json.dumps({"source": source})
    for q in list(_wake_subscribers):
        try:
            q.put_nowait(payload)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_database()
    print(f"[jarvis] database ready at {os.getenv('DB_PATH')}")
    print(f"[jarvis] backend listening on http://localhost:{PORT}")
    yield
    if _clap_listener:
        _clap_listener.stop()
    if _wake_listener:
        _wake_listener.stop()


app = FastAPI(title="Marketing Jarvis", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════ Models ═══════════════════════
class ChatRequest(BaseModel):
    user_id: Optional[str] = None
    jarvis_name: str = "Friday"
    user_name: str = "Mr Vijesh"
    message: str
    business_context: Optional[dict] = None
    conversation_id: Optional[str] = None
    use_model: Optional[str] = None  # "gemini" | "groq" | "deepseek" | None=auto
    attached_context: Optional[str] = None


class SpeakRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None


class ResearchRequest(BaseModel):
    user_id: Optional[str] = None
    query: str
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


# ═══════════════════════ Routes ═══════════════════════
@app.get("/health")
async def health():
    return {"ok": True, "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY")),
            "tavily": bool(os.getenv("TAVILY_API_KEY")),
            "porcupine": bool(os.getenv("PORCUPINE_ACCESS_KEY"))}


# ── CHAT (SSE streaming) ──
@app.post("/chat")
async def chat(req: ChatRequest):
    router = get_router()

    # Ensure conversation exists
    user_id = req.user_id or "anonymous"
    if user_id != "anonymous" and not await db.get_user(user_id):
        await db.create_user(req.user_name, req.jarvis_name)
    conv_id = req.conversation_id
    if not conv_id and user_id != "anonymous":
        conv_id = await db.start_conversation(user_id)

    biz = req.business_context or (await db.get_business_context(user_id) if user_id != "anonymous" else None)
    research = await db.get_latest_research(user_id) if user_id != "anonymous" else None
    memory = await mem.build_memory_context(user_id) if user_id != "anonymous" else ""

    me = await db.get_about_me(user_id) if user_id != "anonymous" else {}
    about_me_text = "\n".join([
        me.get("life_story", "") or "",
        me.get("preferences", "") or "",
        me.get("facts", "") or "",
    ]).strip()
    sys_prompt = build_marketing_brain(
        jarvis_name=req.jarvis_name,
        user_name=req.user_name,
        business_context=biz,
        market_research=research,
        user_location=(biz or {}).get("location", DEFAULT_LOCATION),
        memory_context=memory,
        about_me=about_me_text,
        attached_context=req.attached_context or "",
    )

    history = await db.get_recent_messages(conv_id, 10) if conv_id else []
    if conv_id:
        await db.add_message(conv_id, "user", req.message)

    async def streamer():
        full = []
        try:
            async for tok in router.stream_with_fallback(
                    sys_prompt, req.message, history, force_model=req.use_model):
                full.append(tok)
                yield f"data: {json.dumps({'delta': tok})}\n\n"
            text = "".join(full).strip()
            if conv_id and text:
                await db.add_message(conv_id, "assistant", text,
                                     model_used=req.use_model or "auto")
            yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(streamer(), media_type="text/event-stream")


# ── SPEAK (audio stream) ──
@app.post("/speak")
async def speak(req: SpeakRequest):
    async def gen():
        async for chunk in vp.speak_streaming(req.text, req.voice_id):
            if chunk:
                yield chunk
    return StreamingResponse(gen(), media_type="audio/mpeg")


# ── LISTEN (transcribe upload) ──
@app.post("/listen")
async def listen(audio: UploadFile = File(...)):
    suffix = os.path.splitext(audio.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(await audio.read())
        path = f.name
    try:
        result = await vp.transcribe_audio(path)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
    return result


# ── RESEARCH ──
@app.post("/research")
async def research_endpoint(req: ResearchRequest):
    router = get_router()
    report = await rs.analyze_market_demand(
        product=req.product, location=req.location,
        business_type=req.business_type, router=router,
        user_id=req.user_id,
    )
    return report.to_dict()


@app.get("/research/weekly/{user_id}")
async def weekly(user_id: str, industry: str = "marketing"):
    router = get_router()
    return {"brief": await rs.get_weekly_market_brief(industry, router)}


# ── COMPUTER ──
@app.post("/computer/execute")
async def computer_execute(req: ComputerRequest):
    router = get_router()
    if req.natural_command and not req.action:
        intent = await cc.parse_computer_command(req.natural_command, router)
        action = intent.get("action")
        params = intent.get("params", {})
        speak = intent.get("speak", "")
    else:
        action = req.action
        params = req.params or {}
        speak = ""

    if not action or action == "none":
        return {"success": False, "result": "No actionable command detected.",
                "speak": speak}

    result = await cc.execute(action, params, router=router)
    if req.user_id:
        await db.log_computer_action(req.user_id, action, params,
                                     result.get("success", False),
                                     str(result.get("result", ""))[:1000])
    result["speak"] = speak or result.get("result", "")
    result["action"] = action
    return result


@app.get("/system/info")
async def system_info():
    return cc.get_system_info()


# ── USER ──
@app.post("/user")
async def create_user(req: UserCreate):
    user = await db.create_user(req.name, req.jarvis_name, req.email)
    return user


@app.get("/user/{user_id}")
async def get_user(user_id: str):
    u = await db.get_user(user_id)
    if not u:
        raise HTTPException(404, "Not found")
    biz = await db.get_business_context(user_id)
    return {"user": u, "business": biz}


@app.post("/business")
async def update_business(req: BusinessUpdate):
    fields = {k: v for k, v in req.model_dump().items()
              if k != "user_id" and v is not None}
    return await db.upsert_business_context(req.user_id, **fields)


# ── MEMORY ──
@app.post("/memory/save/{conversation_id}")
async def save_memory(conversation_id: str, user_id: str):
    router = get_router()
    return {"summary": await mem.summarize_conversation(conversation_id, user_id, router)}


@app.get("/memory/{user_id}")
async def get_memory(user_id: str):
    return {"context": await mem.build_memory_context(user_id)}


# ── WAKE WORD CONTROL ──
@app.post("/wake-word/start")
async def wake_start(keyword: str = "jarvis"):
    global _wake_listener, _clap_listener
    if _wake_listener:
        _wake_listener.stop()
    _wake_listener = vp.PorcupineListener(keyword,
                                          lambda: _wake_event("porcupine"),
                                          float(os.getenv("WAKE_SENSITIVITY", "0.7")))
    _wake_listener.start()
    if _clap_listener:
        _clap_listener.stop()
    _clap_listener = vp.DoubleClapDetector(lambda: _wake_event("clap"))
    _clap_listener.start()
    return {"started": True, "keyword": keyword}


@app.post("/wake-word/stop")
async def wake_stop():
    global _wake_listener, _clap_listener
    if _wake_listener:
        _wake_listener.stop(); _wake_listener = None
    if _clap_listener:
        _clap_listener.stop(); _clap_listener = None
    return {"stopped": True}


@app.get("/wake-word/events")
async def wake_events(request: Request):
    q: asyncio.Queue = asyncio.Queue()
    _wake_subscribers.append(q)

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {item}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            try:
                _wake_subscribers.remove(q)
            except ValueError:
                pass
    return StreamingResponse(gen(), media_type="text/event-stream")


# ── USAGE ──
@app.get("/usage/{user_id}")
async def usage(user_id: str):
    return await db.get_usage_summary(user_id)


# ── ABOUT-ME (life story memory) ──
@app.get("/about-me/{user_id}")
async def get_about_me(user_id: str):
    return await db.get_about_me(user_id)


@app.post("/about-me")
async def save_about_me(req: AboutMeUpdate):
    return await db.upsert_about_me(req.user_id,
                                    life_story=req.life_story or "",
                                    preferences=req.preferences or "",
                                    facts=req.facts or "")


# ── DOCUMENT UPLOAD + ANALYSIS ──
@app.post("/upload/document")
async def upload_document(user_id: str = "anonymous",
                          file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "doc.txt")[1] or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(await file.read())
        path = f.name
    try:
        text = doc_svc.extract_text(path)
        router = get_router()
        analysis = await doc_svc.analyze_for_marketing(text,
                                                      file.filename or "doc",
                                                      router)
    finally:
        try: os.remove(path)
        except Exception: pass
    if user_id and user_id != "anonymous":
        await db.save_attachment(user_id, "document",
                                 file.filename or "document",
                                 analysis[:2000], text[:50000])
    return {"name": file.filename, "chars": len(text), "analysis": analysis}


# ── GITHUB REPO ANALYSIS ──
@app.post("/analyze/github")
async def analyze_github(req: GithubAnalyzeRequest):
    router = get_router()
    result = await gh_svc.analyze_repo_for_marketing(req.url, router)
    if req.user_id and req.user_id != "anonymous" and not result.get("error"):
        b = result.get("brief", {})
        name = f"{b.get('owner','?')}/{b.get('repo','?')}"
        await db.save_attachment(req.user_id, "github", name,
                                 result.get("analysis", "")[:2000],
                                 b.get("readme", "")[:50000])
    return result


# ── VISION CHAT (image + prompt → marketing read) ──
@app.post("/vision/chat")
async def vision_chat(req: VisionChatRequest):
    router = get_router()
    biz = await db.get_business_context(req.user_id) if req.user_id else None
    me = await db.get_about_me(req.user_id) if req.user_id else {}
    sys_prompt = build_marketing_brain(
        jarvis_name=req.jarvis_name, user_name=req.user_name,
        business_context=biz, market_research=None,
        user_location=(biz or {}).get("location", DEFAULT_LOCATION),
        memory_context="", about_me=(me or {}).get("life_story", ""),
        attached_context="(User has attached an image. See vision output.)",
    )
    full_prompt = f"{sys_prompt}\n\nUSER MESSAGE: {req.prompt}"
    answer = await router.gemini_vision_call(req.image_b64, full_prompt)
    if req.user_id and req.user_id != "anonymous":
        await db.save_attachment(req.user_id, "image",
                                 "image-upload",
                                 answer[:2000], "")
    return {"answer": answer}


# ── SPOKEN WAKE (openWakeWord) ──
@app.post("/wake/spoken/start")
async def wake_spoken_start(model: Optional[str] = None):
    global _wake_listener, _clap_listener
    name = model or os.getenv("WAKE_WORD_MODEL", "alexa")
    sens = float(os.getenv("WAKE_SENSITIVITY", "0.55"))
    if _wake_listener:
        _wake_listener.stop()
    if hasattr(vp, "OpenWakeWordListener"):
        _wake_listener = vp.OpenWakeWordListener(
            name, lambda: _wake_event("openwakeword"), sens)
    else:
        _wake_listener = vp.PorcupineListener(
            name, lambda: _wake_event("porcupine"), sens)
    _wake_listener.start()
    if _clap_listener:
        _clap_listener.stop()
    _clap_listener = vp.DoubleClapDetector(lambda: _wake_event("clap"))
    _clap_listener.start()
    return {"started": True, "model": name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=PORT, reload=False)
