"""
backend/services/voice_pipeline.py
Voice I/O for Friday: openWakeWord + double-clap + faster-whisper +
ElevenLabs streaming TTS (with pyttsx3 fallback) + filler sounds +
silence-detection recorder.

Designed for a continuous, voice-only conversation. All optional pieces
degrade gracefully when keys/libraries are missing.
"""
from __future__ import annotations

import os
import io
import time
import wave
import random
import asyncio
import threading
from typing import AsyncGenerator, Callable, Optional, List
from dotenv import load_dotenv

load_dotenv()

# ── Optional imports ──
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
    from elevenlabs.client import ElevenLabs
    _eleven = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY")) \
        if os.getenv("ELEVENLABS_API_KEY") else None
except Exception:
    _eleven = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None


# ════════════════ AUDIO CHIMES ════════════════
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
    elif kind == "confirm":
        t = np.linspace(0, 0.18, int(sr * 0.18), False)
        wave_data = 0.28 * np.sin(2 * np.pi * np.linspace(660, 990, t.size) * t)
    else:  # error
        t = np.linspace(0, 0.30, int(sr * 0.30), False)
        wave_data = 0.3 * np.sin(2 * np.pi * np.linspace(440, 220, t.size) * t)
    pcm = (wave_data * 32767).astype("int16").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm)
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
            sd.play(audio, sr); sd.wait()
        except Exception:
            pass
    threading.Thread(target=_p, daemon=True).start()


# ════════════════ NOISE FLOOR CALIBRATION ════════════════
class NoiseFloor:
    """Adaptive ambient-noise floor used by both clap + silence detection."""
    def __init__(self):
        self.value: float = 0.02
        self.last_calibrated: float = 0.0

    def calibrate(self, duration_s: float = 1.0, sr: int = 16000):
        if not (sd and np):
            return
        try:
            buf = sd.rec(int(sr * duration_s), samplerate=sr,
                         channels=1, dtype="int16")
            sd.wait()
            arr = buf.flatten().astype("float32") / 32768.0
            rms = float(np.sqrt(np.mean(arr ** 2)) or 0.005)
            self.value = max(0.005, rms)
            self.last_calibrated = time.time()
            print(f"[noise] calibrated floor = {self.value:.4f}")
        except Exception as e:
            print(f"[noise] calibration failed: {e}")


_noise = NoiseFloor()


# ════════════════ SECTION 1 — DOUBLE-CLAP DETECTION ════════════════
class DoubleClapDetector(threading.Thread):
    """
    Listens for two claps within 150–900 ms.
    Adaptive threshold = max(0.6, noise_floor * 3.0).
    Re-calibrates the noise floor every 5 minutes.
    """
    SR = 16000
    BLOCK = 1024
    GAP_MIN_MS = 150
    GAP_MAX_MS = 900
    WINDOW_S = 1.5
    COOLDOWN_S = 2.5
    RECAL_INTERVAL_S = 300

    def __init__(self, callback: Callable):
        super().__init__(daemon=True)
        self.callback = callback
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        if not (sd and np):
            print("[clap] sounddevice/numpy missing — clap disabled")
            return
        if _noise.last_calibrated == 0:
            _noise.calibrate()
        threshold = max(0.6, _noise.value * 3.0)
        last_trigger = 0.0
        clap_times: List[float] = []
        try:
            with sd.InputStream(samplerate=self.SR, channels=1,
                                dtype="int16", blocksize=self.BLOCK) as stream:
                while not self._stop.is_set():
                    pcm, _ = stream.read(self.BLOCK)
                    arr = pcm.flatten().astype("float32") / 32768.0
                    rms = float(np.sqrt(np.mean(arr ** 2) + 1e-9))
                    now = time.time()

                    # Re-calibrate periodically
                    if now - _noise.last_calibrated > self.RECAL_INTERVAL_S:
                        _noise.calibrate()
                        threshold = max(0.6, _noise.value * 3.0)

                    if rms > threshold:
                        clap_times.append(now)

                    # Drop old claps
                    clap_times = [t for t in clap_times if now - t <= self.WINDOW_S]

                    if len(clap_times) >= 2 and now - last_trigger > self.COOLDOWN_S:
                        gap_ms = (clap_times[-1] - clap_times[0]) * 1000
                        if self.GAP_MIN_MS <= gap_ms <= self.GAP_MAX_MS:
                            last_trigger = now
                            clap_times.clear()
                            play_chime_async("wake")
                            try:
                                self.callback()
                            except Exception:
                                pass
        except Exception as e:
            print(f"[clap] stream error: {e}")


def start_double_clap_listener(callback: Callable,
                               stop_event: Optional[threading.Event] = None
                               ) -> DoubleClapDetector:
    det = DoubleClapDetector(callback)
    if stop_event is not None:
        # bind external event
        det._stop = stop_event
    det.start()
    return det


# ════════════════ SECTION 2 — OPENWAKEWORD ════════════════
class OpenWakeWordListener(threading.Thread):
    SR = 16000
    BLOCK = 1280  # 80 ms
    COOLDOWN_S = 3.0

    def __init__(self, wake_word: str, callback: Callable,
                 sensitivity: float = 0.5):
        super().__init__(daemon=True)
        self.wake_word = wake_word or "hey_jarvis"
        self.callback = callback
        self.sensitivity = sensitivity
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        if not (sd and np):
            print("[wake] sounddevice/numpy missing — spoken wake disabled")
            return
        try:
            from openwakeword.model import Model as OWWModel
        except Exception as e:
            print(f"[wake] openwakeword unavailable ({e}) — using clap only")
            return
        try:
            try:
                model = OWWModel(wakeword_models=[self.wake_word],
                                 inference_framework="onnx")
            except Exception:
                # First run may need to download models
                import openwakeword
                openwakeword.utils.download_models()
                model = OWWModel(wakeword_models=[self.wake_word],
                                 inference_framework="onnx")
        except Exception as e:
            print(f"[wake] OpenWakeWord model load failed: {e}")
            return
        last_trigger = 0.0
        try:
            with sd.InputStream(samplerate=self.SR, channels=1,
                                dtype="int16", blocksize=self.BLOCK) as stream:
                while not self._stop.is_set():
                    pcm, _ = stream.read(self.BLOCK)
                    pcm = pcm.flatten().astype("int16")
                    scores = model.predict(pcm)
                    if any(v >= self.sensitivity for v in scores.values()):
                        now = time.time()
                        if now - last_trigger > self.COOLDOWN_S:
                            last_trigger = now
                            play_chime_async("wake")
                            try:
                                self.callback()
                            except Exception:
                                pass
        except Exception as e:
            print(f"[wake] OpenWakeWord stream error: {e}")


def start_spoken_wake_listener(wake_word: str, callback: Callable,
                               stop_event: Optional[threading.Event] = None
                               ) -> OpenWakeWordListener:
    det = OpenWakeWordListener(wake_word, callback,
                               float(os.getenv("WAKE_SENSITIVITY", "0.5")))
    if stop_event is not None:
        det._stop = stop_event
    det.start()
    return det


# ════════════════ SECTION 3 — COMBINED WAKE SYSTEM ════════════════
def start_all_wake_listeners(callback: Callable,
                             wake_word: str = "hey_jarvis") -> dict:
    """Start clap + spoken wake simultaneously. Returns handles."""
    stop_event = threading.Event()
    clap = start_double_clap_listener(callback, stop_event)
    voice = start_spoken_wake_listener(wake_word, callback, stop_event)
    return {"clap_thread": clap, "voice_thread": voice, "stop_event": stop_event}


# ════════════════ SECTION 4 — TRANSCRIPTION (faster-whisper) ════════════════
def _ensure_whisper():
    global _whisper_model
    if _whisper_model is None and WhisperModel:
        size = os.getenv("WHISPER_MODEL", "base")
        _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
    return _whisper_model


_TRANSCRIPT_NOISE = {"thank you.", "you", ".", "thanks for watching."}


async def transcribe_audio(audio_path_or_bytes,
                           language: Optional[str] = None) -> dict:
    """
    Accepts either a file path (str) or raw audio bytes.
    Returns {text, language, language_prob, duration}.
    """
    model = _ensure_whisper()
    if not model:
        return {"text": "", "language": "en", "language_prob": 0,
                "duration": 0, "error": "faster-whisper not installed"}

    cleanup_path = None
    if isinstance(audio_path_or_bytes, (bytes, bytearray)):
        import tempfile
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tf.write(audio_path_or_bytes); tf.flush(); tf.close()
        path = tf.name
        cleanup_path = path
    else:
        path = audio_path_or_bytes

    loop = asyncio.get_event_loop()

    def _do():
        kwargs = dict(beam_size=5, vad_filter=True)
        if language:
            kwargs["language"] = language
        segments, info = model.transcribe(path, **kwargs)
        text = " ".join(s.text for s in segments).strip()
        return {
            "text": text,
            "language": info.language,
            "language_prob": float(info.language_probability or 0),
            "duration": float(info.duration or 0),
        }

    try:
        result = await loop.run_in_executor(None, _do)
    finally:
        if cleanup_path:
            try: os.remove(cleanup_path)
            except Exception: pass

    txt = (result["text"] or "").strip()
    if len(txt) < 3 or txt.lower() in _TRANSCRIPT_NOISE:
        result["text"] = ""
    return result


# ════════════════ SECTION 5 — TTS (ElevenLabs → pyttsx3 → silence) ════════════════
async def speak_streaming(text: str,
                          voice_id: Optional[str] = None
                          ) -> AsyncGenerator[bytes, None]:
    voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID",
                                     "21m00Tcm4TlvDq8ikWAM")
    if _eleven and text:
        try:
            stream = _eleven.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_turbo_v2_5",
                voice_settings={
                    "stability": 0.71, "similarity_boost": 0.85,
                    "style": 0.35, "use_speaker_boost": True,
                },
            )
            for chunk in stream:
                if chunk:
                    yield chunk
            return
        except Exception as e:
            print(f"[voice] ElevenLabs failed, falling back: {e}")

    # Fallback: pyttsx3
    if pyttsx3 and text:
        try:
            tmp_path = os.path.join(os.path.dirname(__file__), "_tts_tmp.wav")
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            for v in engine.getProperty("voices"):
                if "female" in (v.name or "").lower() or "zira" in (v.id or "").lower():
                    engine.setProperty("voice", v.id); break
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            with open(tmp_path, "rb") as f:
                data = f.read()
            try: os.remove(tmp_path)
            except Exception: pass
            yield data
            return
        except Exception as e:
            print(f"[voice] pyttsx3 also failed: {e}")
    yield b""


# Backwards-compatible alias for the prompt's signature
async def speak_text(text: str,
                     voice_id: str = "21m00Tcm4TlvDq8ikWAM"
                     ) -> AsyncGenerator[bytes, None]:
    async for chunk in speak_streaming(text, voice_id):
        yield chunk


# ════════════════ SECTION 6 — FILLER SOUNDS ════════════════
_FILLERS = [
    "Hmm.", "Let me think...", "One moment.",
    "Okay, give me a second.", "Mhm, let me check.",
]
_filler_cache: dict[str, bytes] = {}


async def play_thinking_filler() -> bytes:
    """Returns one filler audio clip (cached). Empty bytes if synth fails."""
    text = random.choice(_FILLERS)
    if text in _filler_cache:
        return _filler_cache[text]
    chunks: List[bytes] = []
    async for c in speak_streaming(text):
        if c:
            chunks.append(c)
    audio = b"".join(chunks)
    if audio:
        _filler_cache[text] = audio
    return audio


# ════════════════ SECTION 7 — RECORD UNTIL SILENCE ════════════════
def record_until_silence(silence_threshold_seconds: float = 1.8,
                         max_duration_seconds: float = 60.0,
                         on_amplitude: Optional[Callable[[float], None]] = None
                         ) -> bytes:
    """
    Blocks the calling thread. Returns recorded WAV bytes.
    Yields amplitude (0..1) to on_amplitude callback ~10x per second.
    """
    if not (sd and np):
        return b""
    sr = 16000
    block = int(sr * 0.1)  # 100 ms
    if _noise.last_calibrated == 0:
        _noise.calibrate(0.5, sr)
    silence_floor = max(_noise.value * 1.5, 0.012)

    frames: List[bytes] = []
    rolling: List[float] = []
    start = time.time()
    silence_start: Optional[float] = None
    try:
        with sd.InputStream(samplerate=sr, channels=1,
                            dtype="int16", blocksize=block) as stream:
            while True:
                pcm, _ = stream.read(block)
                pcm_i16 = pcm.flatten().astype("int16")
                frames.append(pcm_i16.tobytes())
                arr = pcm_i16.astype("float32") / 32768.0
                rms = float(np.sqrt(np.mean(arr ** 2) + 1e-9))
                if on_amplitude:
                    try: on_amplitude(min(1.0, rms * 3))
                    except Exception: pass
                rolling.append(rms)
                rolling = rolling[-5:]  # last 500 ms
                rolling_rms = sum(rolling) / len(rolling)

                now = time.time()
                if rolling_rms < silence_floor:
                    if silence_start is None:
                        silence_start = now
                    elif now - silence_start >= silence_threshold_seconds:
                        break
                else:
                    silence_start = None

                if now - start >= max_duration_seconds:
                    break
    except Exception as e:
        print(f"[record] stream error: {e}")

    pcm_all = b"".join(frames)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2)
        w.setframerate(sr); w.writeframes(pcm_all)
    return buf.getvalue()


# ════════════════ Backwards compat (PorcupineListener stub) ════════════════
class PorcupineListener(OpenWakeWordListener):
    """Kept as alias so older code still imports without breaking."""
    pass
