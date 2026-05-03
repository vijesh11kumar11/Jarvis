"""
backend/brain/ai_router.py
Routes between Gemini (primary brain) and Groq (fast voice replies).
NO Anthropic. NO OpenAI.
"""
import os
import base64
import io
import json
import asyncio
from typing import AsyncGenerator, Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()

# ── Lazy imports so the module imports even when keys missing ──
_gemini_ready = False
_groq_ready = False

try:
    import google.generativeai as genai
    if os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        _gemini_ready = True
except Exception:
    genai = None

try:
    from groq import Groq, AsyncGroq
    if os.getenv("GROQ_API_KEY"):
        _groq_ready = True
except Exception:
    Groq = None
    AsyncGroq = None

# DeepSeek uses an OpenAI-compatible REST API → call via httpx (no SDK needed)
import httpx
_deepseek_ready = bool(os.getenv("DEEPSEEK_API_KEY"))


VISION_KEYWORDS = ["screenshot", "screen", "see this", "look at this",
                   "what's on my screen", "image", "picture", "photo"]
QUICK_KEYWORDS = ["time", "date", "weather", "what is", "define",
                  "open ", "close ", "send ", "type ", "remind "]
DEEP_KEYWORDS = ["analyze code", "review code", "audit", "deep analysis",
                 "github", "repo", "repository", "architecture",
                 "deeply", "think hard", "reason about", "step by step",
                 "long term", "strategy roadmap"]


class AIRouter:
    GEMINI_MODEL = "gemini-2.0-flash"
    GEMINI_VISION = "gemini-1.5-pro-latest"
    GROQ_MODEL = "llama-3.3-70b-versatile"

    def __init__(self):
        self.gemini = None
        self.gemini_vision = None
        self.groq = None
        self.async_groq = None
        if _gemini_ready:
            try:
                self.gemini = genai.GenerativeModel(self.GEMINI_MODEL)
                self.gemini_vision = genai.GenerativeModel(self.GEMINI_VISION)
            except Exception as e:
                print(f"[ai_router] Gemini init failed: {e}")
        if _groq_ready:
            try:
                self.groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
                self.async_groq = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
            except Exception as e:
                print(f"[ai_router] Groq init failed: {e}")

    # ─────────── Task classifier (no API call needed for obvious cases) ───
    def classify_task(self, message: str) -> str:
        m = message.lower().strip()
        if any(k in m for k in VISION_KEYWORDS):
            return "vision"
        if any(k in m for k in DEEP_KEYWORDS):
            return "deep"
        if any(m.startswith(k) or f" {k}" in m for k in QUICK_KEYWORDS):
            return "quick"
        if len(m.split()) < 8:
            return "quick"
        return "strategy"

    # ─────────── GEMINI streaming (text only) ───────────
    async def gemini_stream(self, system_prompt: str, user_message: str,
                            history: Optional[List[Dict]] = None
                            ) -> AsyncGenerator[str, None]:
        if not self.gemini:
            yield "[Gemini unavailable — set GEMINI_API_KEY in backend/.env]"
            return
        # Gemini lacks a true system role — prepend as priming message
        contents = [
            {"role": "user", "parts": [
                f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\n"
                "Acknowledge with a single word and then wait for my real question."]},
            {"role": "model", "parts": ["Ready."]},
        ]
        for h in (history or []):
            role = "model" if h["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [h["content"]]})
        contents.append({"role": "user", "parts": [user_message]})

        loop = asyncio.get_event_loop()

        def _gen():
            return self.gemini.generate_content(
                contents,
                stream=True,
                generation_config={
                    "max_output_tokens": 2048,
                    "temperature": 0.7,
                },
            )

        try:
            stream = await loop.run_in_executor(None, _gen)
            for chunk in stream:
                if hasattr(chunk, "text") and chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"[Gemini error: {e}]"

    # Maps any retired/preview model names to their current equivalents
    _MODEL_REMAP = {
        "gemini-2.0-flash-exp":  "gemini-2.0-flash",
        "gemini-1.5-pro":        "gemini-1.5-pro-latest",
        "gemini-pro":            "gemini-1.5-pro-latest",
    }

    def _remap_model(self, model: Optional[str]) -> str:
        if not model:
            return self.GEMINI_MODEL
        return self._MODEL_REMAP.get(model, model)

    async def simple_gemini(self, prompt: str, model: Optional[str] = None) -> str:
        resolved = self._remap_model(model)
        target = self.gemini
        if resolved != self.GEMINI_MODEL:
            try:
                import google.generativeai as genai
                target = genai.GenerativeModel(resolved)
            except Exception:
                target = self.gemini
        if not target:
            return ""
        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(
                None, lambda: target.generate_content(prompt))
            return resp.text or ""
        except Exception as e:
            print(f"[ai_router] simple_gemini error: {e}")
            return ""

    async def simple_groq(self, prompt: str, model: Optional[str] = None) -> str:
        if not self.async_groq:
            return ""
        try:
            resp = await self.async_groq.chat.completions.create(
                model=model or self.GROQ_MODEL,
                messages=[{"role":"user","content":prompt}],
                max_tokens=512, temperature=0.4,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            print(f"[ai_router] simple_groq error: {e}")
            return ""

    # ─────────── GEMINI vision ───────────
    async def gemini_vision_call(self, prompt_or_b64, image_or_prompt=None) -> str:
        # Flexible signature: (prompt, image_bytes) OR (image_b64, prompt) [legacy]
        if isinstance(prompt_or_b64, (bytes, bytearray)):
            image_data, prompt = prompt_or_b64, image_or_prompt or ""
        elif isinstance(image_or_prompt, (bytes, bytearray)):
            prompt, image_data = prompt_or_b64, image_or_prompt
        else:
            # both str: assume (image_b64, prompt) legacy ordering
            try:
                image_data = base64.b64decode(prompt_or_b64)
                prompt = image_or_prompt or ""
            except Exception:
                # fall back to (prompt, b64-as-str)
                prompt = prompt_or_b64
                image_data = base64.b64decode(image_or_prompt or "") if image_or_prompt else b""
        if not self.gemini_vision:
            return "Vision unavailable — Gemini key missing."
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_data))
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: self.gemini_vision.generate_content([prompt, img]),
            )
            return resp.text or ""
        except Exception as e:
            return f"[Vision error: {e}]"

    # ─────────── GROQ streaming ───────────
    async def groq_stream(self, system_prompt: str, user_message: str,
                          history: Optional[List[Dict]] = None
                          ) -> AsyncGenerator[str, None]:
        if not self.async_groq:
            yield "[Groq unavailable — set GROQ_API_KEY in backend/.env]"
            return
        messages = [{"role": "system", "content": system_prompt}]
        for h in (history or []):
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user_message})
        try:
            stream = await self.async_groq.chat.completions.create(
                model=self.GROQ_MODEL,
                messages=messages,
                stream=True,
                max_tokens=1024,
                temperature=0.7,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            yield f"[Groq error: {e}]"

    # ─────────── Smart router with fallback ───────────
    async def stream_with_fallback(self, system_prompt: str, user_message: str,
                                   history: Optional[List[Dict]] = None,
                                   force_model: Optional[str] = None
                                   ) -> AsyncGenerator[str, None]:
        task = force_model or self.classify_task(user_message)
        if task == "deep":
            primary = "deepseek"
        elif task == "quick":
            primary = "groq"
        else:
            primary = "gemini"

        gen = self._pick(primary, system_prompt, user_message, history)
        produced = False
        try:
            async for tok in gen:
                if tok and not tok.startswith("["):
                    produced = True
                yield tok
        except Exception as e:
            yield f"[{primary} crashed: {e}]"

        if produced:
            return
        # Fallback chain
        for fb in ["gemini", "groq", "deepseek"]:
            if fb == primary:
                continue
            try:
                async for tok in self._pick(fb, system_prompt, user_message, history):
                    yield tok
                return
            except Exception:
                continue
        yield ("I'm having trouble connecting to my brain right now. "
               "Please verify your API keys and try again.")

    def _pick(self, name, system_prompt, user_message, history):
        if name == "groq":
            return self.groq_stream(system_prompt, user_message, history)
        if name == "deepseek":
            return self.deepseek_stream(system_prompt, user_message, history)
        return self.gemini_stream(system_prompt, user_message, history)

    # ─────────── DEEPSEEK streaming ───────────
    async def deepseek_stream(self, system_prompt: str, user_message: str,
                              history: Optional[List[Dict]] = None,
                              model: str = "deepseek-chat"
                              ) -> AsyncGenerator[str, None]:
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            yield "[DeepSeek unavailable — set DEEPSEEK_API_KEY]"
            return
        messages = [{"role": "system", "content": system_prompt}]
        for h in (history or []):
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user_message})
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": 2048,
            "temperature": 0.6,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json=payload,
                ) as r:
                    async for line in r.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                            delta = obj["choices"][0]["delta"].get("content")
                            if delta:
                                yield delta
                        except Exception:
                            continue
        except Exception as e:
            yield f"[DeepSeek error: {e}]"

    async def simple_deepseek(self, prompt: str,
                              model: str = "deepseek-chat") -> str:
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            return ""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={"model": model,
                          "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 2048, "temperature": 0.6},
                )
                j = r.json()
                return j["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[ai_router] simple_deepseek error: {e}")
            return ""
router_instance: Optional[AIRouter] = None

def get_router() -> AIRouter:
    global router_instance
    if router_instance is None:
        router_instance = AIRouter()
    return router_instance
