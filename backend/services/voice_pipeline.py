"""
backend/services/voice_pipeline.py
Wake word, double-clap, faster-whisper transcription, ElevenLabs TTS.
All optional pieces degrade gracefully when keys/libraries are missing.
"""
import os
import io
import time
import wave
import asyncio
import threading
from typing import AsyncGenerator, Callable, Optional
from dotenv import load_dotenv

load_dotenv()

# Optional imports
try:
    import numpy as np
except Exception:
    np = None

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    from faster_whisper import WhisperModel
    _whisper_model: Optional[WhisperModel] = None
except Exception:
    WhisperModel = None
    _whisper_model = None

try:
    import pvporcupine
except Exception:
    pvporcupine = None

try:
    from elevenlabs.client import ElevenLabs
    _eleven = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY")) \
        if os.getenv("ELEVENLABS_API_KEY") else None
except Exception:
    _eleven = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None


# ─────────── Whisper transcription ───────────
def _ensure_whisper():
    global _whisper_model
    if _whisper_model is None and WhisperModel:
        size = os.getenv("WHISPER_MODEL", "base")
        _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
    return _whisper_model


async def transcribe_audio(audio_path: str) -> dict:
    model = _ensure_whisper()
    if not model:
        return {"text": "", "language": "en", "confidence": 0,
                "duration_seconds": 0,
                "error": "faster-whisper not installed"}
    loop = asyncio.get_event_loop()

    def _do():
        segments, info = model.transcribe(audio_path, beam_size=5,
                                          vad_filter=True)
        text = " ".join(s.text for s in segments).strip()
        return {
            "text": text,
            "language": info.language,
            "confidence": float(info.language_probability or 0),
            "duration_seconds": float(info.duration or 0),
        }
    return await loop.run_in_executor(None, _do)


# ─────────── ElevenLabs streaming TTS (with pyttsx3 fallback) ───────────
async def speak_streaming(text: str, voice_id: Optional[str] = None
                          ) -> AsyncGenerator[bytes, None]:
    voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID",
                                     "21m00Tcm4TlvDq8ikWAM")
    if _eleven:
        try:
            stream = _eleven.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_turbo_v2_5",
                voice_settings={
                    "stability": 0.71,
                    "similarity_boost": 0.85,
                    "style": 0.35,
                    "use_speaker_boost": True,
                },
            )
            for chunk in stream:
                if chunk:
                    yield chunk
            return
        except Exception as e:
            print(f"[voice] ElevenLabs failed, falling back: {e}")

    # Fallback: pyttsx3 → render to WAV in memory
    if pyttsx3:
        try:
            tmp_path = os.path.join(os.path.dirname(__file__), "_tts_tmp.wav")
            engine = pyttsx3.init()
            engine.setProperty("rate", 185)
            # Try to pick a female voice
            for v in engine.getProperty("voices"):
                if "female" in (v.name or "").lower() or "zira" in (v.id or "").lower():
                    engine.setProperty("voice", v.id)
                    break
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            with open(tmp_path, "rb") as f:
                data = f.read()
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            yield data
            return
        except Exception as e:
            print(f"[voice] pyttsx3 also failed: {e}")
    yield b""


# ─────────── Audio chime generator ───────────
def generate_chime(kind: str = "wake") -> bytes:
    if not np:
        return b""
    sr = 22050
    if kind == "wake":
        t = np.linspace(0, 0.30, int(sr * 0.30), False)
        wave_data = 0.3 * np.sin(2 * np.pi * np.linspace(440, 880, t.size) * t)
    elif kind == "listen":
        t = np.linspace(0, 0.10, int(sr * 0.10), False)
        wave_data = 0.25 * np.sin(2 * np.pi * 660 * t)
    else:  # error
        t = np.linspace(0, 0.30, int(sr * 0.30), False)
        wave_data = 0.3 * np.sin(2 * np.pi * np.linspace(440, 220, t.size) * t)
    pcm = (wave_data * 32767).astype("int16").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return buf.getvalue()


def play_chime_async(kind: str = "wake") -> None:
    if not (sd and np):
        return
    data = generate_chime(kind)
    if not data:
        return

    def _p():
        try:
            with wave.open(io.BytesIO(data), "rb") as w:
                audio = np.frombuffer(w.readframes(w.getnframes()), dtype="int16")
                sr = w.getframerate()
            sd.play(audio, sr)
            sd.wait()
        except Exception:
            pass
    threading.Thread(target=_p, daemon=True).start()


# ─────────── Double-clap detection ───────────
class DoubleClapDetector(threading.Thread):
    THRESHOLD = 0.45     # RMS threshold
    MIN_GAP_MS = 150
    MAX_GAP_MS = 1000
    COOLDOWN_S = 2.0

    def __init__(self, callback: Callable):
        super().__init__(daemon=True)
        self.callback = callback
        self._stop = threading.Event()
        self._last_clap = 0.0
        self._last_trigger = 0.0

    def stop(self):
        self._stop.set()

    def run(self):
        if not (sd and np):
            print("[clap] sounddevice/numpy missing, double-clap disabled")
            return
        sr = 16000
        block = int(sr * 0.05)  # 50ms

        def _cb(indata, frames, time_info, status):
            if self._stop.is_set():
                raise sd.CallbackStop()
            rms = float(np.sqrt(np.mean(indata.astype("float32") ** 2)))
            now = time.time()
            if rms > self.THRESHOLD:
                gap_ms = (now - self._last_clap) * 1000
                self._last_clap = now
                if self.MIN_GAP_MS < gap_ms < self.MAX_GAP_MS:
                    if now - self._last_trigger > self.COOLDOWN_S:
                        self._last_trigger = now
                        play_chime_async("wake")
                        try:
                            self.callback()
                        except Exception:
                            pass
        try:
            with sd.InputStream(samplerate=sr, channels=1, blocksize=block,
                                callback=_cb, dtype="float32"):
                while not self._stop.is_set():
                    sd.sleep(100)
        except Exception as e:
            print(f"[clap] stream error: {e}")


# ─────────── Porcupine wake word ───────────
class PorcupineListener(threading.Thread):
    def __init__(self, keyword: str, callback: Callable,
                 sensitivity: float = 0.7):
        super().__init__(daemon=True)
        self.keyword = keyword
        self.callback = callback
        self.sensitivity = sensitivity
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        access = os.getenv("PORCUPINE_ACCESS_KEY")
        if not (pvporcupine and access and sd and np):
            print("[wake] Porcupine missing/no key — skipping wake word")
            return
        try:
            keyword = self.keyword.lower() if self.keyword.lower() in pvporcupine.KEYWORDS else "jarvis"
            handle = pvporcupine.create(access_key=access,
                                        keywords=[keyword],
                                        sensitivities=[self.sensitivity])
            sr = handle.sample_rate
            frame_len = handle.frame_length

            with sd.InputStream(samplerate=sr, channels=1,
                                dtype="int16", blocksize=frame_len) as stream:
                while not self._stop.is_set():
                    pcm, _ = stream.read(frame_len)
                    pcm = pcm.flatten().astype("int16")
                    if handle.process(pcm) >= 0:
                        play_chime_async("wake")
                        try:
                            self.callback()
                        except Exception:
                            pass
                        time.sleep(1.0)
            handle.delete()
        except Exception as e:
            print(f"[wake] porcupine error: {e}")


# ─────────── openWakeWord (open-source spoken wake) ───────────
class OpenWakeWordListener(threading.Thread):
    def __init__(self, model_name: str, callback: Callable,
                 sensitivity: float = 0.55):
        super().__init__(daemon=True)
        self.model_name = model_name or "alexa"
        self.callback = callback
        self.sensitivity = sensitivity
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        if not (sd and np):
            print("[wake] sounddevice/numpy missing — skip openwakeword")
            return
        try:
            from openwakeword.model import Model as OWWModel
        except Exception as e:
            print(f"[wake] openwakeword not installed ({e}) — falling back")
            return
        try:
            model = OWWModel(wakeword_models=[self.model_name],
                             inference_framework="onnx")
        except Exception as e:
            print(f"[wake] openwakeword model load failed: {e}")
            return
        sr = 16000
        frame = 1280  # 80 ms @16k as per openwakeword examples
        try:
            with sd.InputStream(samplerate=sr, channels=1,
                                dtype="int16", blocksize=frame) as stream:
                last_fire = 0.0
                while not self._stop.is_set():
                    pcm, _ = stream.read(frame)
                    pcm = pcm.flatten().astype("int16")
                    scores = model.predict(pcm)
                    if any(v >= self.sensitivity for v in scores.values()):
                        now = time.time()
                        if now - last_fire > 1.5:
                            last_fire = now
                            play_chime_async("wake")
                            try:
                                self.callback()
                            except Exception:
                                pass
        except Exception as e:
            print(f"[wake] openwakeword stream error: {e}")
