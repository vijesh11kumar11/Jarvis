"""
backend/brain/computer_control.py
Cross-platform (Windows-first) computer control engine.
"""
import os
import sys
import json
import time
import base64
import asyncio
import subprocess
import webbrowser
import platform
from io import BytesIO
from datetime import datetime
from typing import Optional

try:
    import pyautogui
    pyautogui.FAILSAFE = True
except Exception:
    pyautogui = None

try:
    import pyperclip
except Exception:
    pyperclip = None

try:
    from PIL import ImageGrab, Image
except Exception:
    ImageGrab = None
    Image = None

try:
    import psutil
except Exception:
    psutil = None

try:
    import dateparser
except Exception:
    dateparser = None


IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"


# ─────────── Website map ───────────
SITES = {
    "instagram": "https://instagram.com",
    "youtube": "https://youtube.com",
    "gmail": "https://mail.google.com",
    "whatsapp": "https://web.whatsapp.com",
    "facebook": "https://facebook.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "linkedin": "https://linkedin.com",
    "spotify": "https://open.spotify.com",
    "netflix": "https://netflix.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "github": "https://github.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "google": "https://google.com",
    "amazon": "https://amazon.com",
    "flipkart": "https://flipkart.com",
    "myntra": "https://myntra.com",
    "swiggy": "https://swiggy.com",
    "zomato": "https://zomato.com",
    "uber": "https://uber.com",
    "ola": "https://olacabs.com",
    "reddit": "https://reddit.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "wikipedia": "https://wikipedia.org",
    "twitch": "https://twitch.tv",
    "discord": "https://discord.com",
    "slack": "https://slack.com",
    "notion": "https://notion.so",
    "trello": "https://trello.com",
    "asana": "https://asana.com",
    "figma": "https://figma.com",
    "canva": "https://canva.com",
    "dribbble": "https://dribbble.com",
    "behance": "https://behance.net",
    "medium": "https://medium.com",
    "quora": "https://quora.com",
    "pinterest": "https://pinterest.com",
    "tiktok": "https://tiktok.com",
    "snapchat": "https://snapchat.com",
    "telegram": "https://web.telegram.org",
    "calendar": "https://calendar.google.com",
    "google calendar": "https://calendar.google.com",
    "docs": "https://docs.google.com",
    "google docs": "https://docs.google.com",
    "sheets": "https://sheets.google.com",
    "google sheets": "https://sheets.google.com",
    "meet": "https://meet.google.com",
    "google meet": "https://meet.google.com",
    "zoom": "https://zoom.us",
    "outlook": "https://outlook.live.com",
    "yahoo": "https://yahoo.com",
    "bing": "https://bing.com",
    "duckduckgo": "https://duckduckgo.com",
    "perplexity": "https://perplexity.ai",
    "huggingface": "https://huggingface.co",
    "kaggle": "https://kaggle.com",
}

WIN_APPS = {
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "spotify": "spotify",
    "discord": "discord",
    "zoom": "zoom",
    "slack": "slack",
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "file explorer": "explorer",
    "explorer": "explorer",
    "task manager": "taskmgr",
    "control panel": "control",
    "cmd": "cmd",
    "terminal": "wt",
    "powershell": "powershell",
    "paint": "mspaint",
    "settings": "ms-settings:",
    "snipping tool": "snippingtool",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "obs": "obs64",
    "steam": "steam",
    "epic": "EpicGamesLauncher",
    "vlc": "vlc",
    "audacity": "audacity",
    "blender": "blender",
    "premiere": "Adobe Premiere Pro",
    "photoshop": "Photoshop",
}

MAC_APPS = {
    "chrome": "Google Chrome",
    "firefox": "Firefox",
    "safari": "Safari",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "spotify": "Spotify",
    "discord": "Discord",
    "zoom": "zoom.us",
    "slack": "Slack",
    "notes": "Notes",
    "calculator": "Calculator",
    "finder": "Finder",
    "terminal": "Terminal",
    "preview": "Preview",
    "messages": "Messages",
    "mail": "Mail",
    "calendar": "Calendar",
    "music": "Music",
}


# ─────────── Public functions ───────────
def open_website(name_or_url: str) -> dict:
    key = name_or_url.lower().strip().replace("open ", "")
    url = SITES.get(key)
    if not url:
        if not key.startswith("http"):
            url = f"https://{key}" if "." in key else f"https://google.com/search?q={key}"
        else:
            url = key
    try:
        webbrowser.open(url, new=2)
        return {"success": True, "result": f"Opened {url}"}
    except Exception as e:
        return {"success": False, "result": str(e)}


def open_application(app_name: str) -> dict:
    name = app_name.lower().strip()
    table = WIN_APPS if IS_WIN else MAC_APPS
    cmd = table.get(name, app_name)
    try:
        if IS_WIN:
            if cmd.startswith("ms-settings:"):
                os.startfile(cmd)
            else:
                subprocess.Popen(cmd, shell=True)
        elif IS_MAC:
            subprocess.Popen(["open", "-a", cmd])
        else:
            subprocess.Popen([cmd])
        return {"success": True, "result": f"Launched {app_name}"}
    except Exception as e:
        return {"success": False, "result": f"Could not open {app_name}: {e}"}


def take_screenshot(analyze: bool = False) -> dict:
    if not ImageGrab:
        return {"success": False, "result": "Screenshot unavailable (PIL missing)"}
    try:
        img = ImageGrab.grab()
        buf = BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return {"success": True, "result": "Screenshot captured",
                "screenshot_b64": b64, "analyze": analyze}
    except Exception as e:
        return {"success": False, "result": str(e)}


async def screenshot_and_analyze(router) -> dict:
    shot = take_screenshot()
    if not shot["success"]:
        return shot
    analysis = await router.gemini_vision_call(
        shot["screenshot_b64"],
        "Describe what's on this screen. What app is open? What is the user "
        "doing? Highlight any important information visible. Be concise (3-4 sentences).",
    )
    shot["analysis"] = analysis
    return shot


def send_whatsapp_message(contact: str, message: str) -> dict:
    """Opens WhatsApp Web and types the message. User confirms by pressing Enter
    via UI prompt — for safety we DO NOT auto-press send unless explicitly requested.
    """
    if not pyautogui:
        return {"success": False, "result": "pyautogui unavailable"}
    try:
        webbrowser.open("https://web.whatsapp.com", new=2)
        time.sleep(6)  # let page load
        pyautogui.hotkey("ctrl", "alt", "/" if IS_MAC else "k")  # search
        time.sleep(1.0)
        pyautogui.typewrite(contact, interval=0.05)
        time.sleep(2.0)
        pyautogui.press("enter")
        time.sleep(1.5)
        if pyperclip:
            pyperclip.copy(message)
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.typewrite(message, interval=0.02)
        time.sleep(0.5)
        # Don't auto-send by default; return staged
        return {"success": True,
                "result": f"Message staged in WhatsApp for {contact}. Press Enter to send.",
                "staged": True}
    except Exception as e:
        return {"success": False, "result": str(e)}


def type_text_anywhere(text: str) -> dict:
    if not pyautogui or not pyperclip:
        return {"success": False, "result": "pyautogui/pyperclip unavailable"}
    try:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        return {"success": True, "result": "Text typed."}
    except Exception as e:
        return {"success": False, "result": str(e)}


def set_reminder(title: str, datetime_str: str) -> dict:
    if not dateparser:
        return {"success": False, "result": "dateparser missing"}
    when = dateparser.parse(datetime_str)
    if not when:
        return {"success": False, "result": f"Could not parse time: {datetime_str}"}
    # In-process scheduling via APScheduler is started in main.py
    return {"success": True,
            "result": f"Reminder scheduled: '{title}' at {when.isoformat()}",
            "title": title, "when": when.isoformat()}


def read_file(filepath: str) -> dict:
    if not os.path.isfile(filepath):
        return {"success": False, "result": "File not found"}
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".pdf":
            from PyPDF2 import PdfReader
            r = PdfReader(filepath)
            text = "\n".join((p.extract_text() or "") for p in r.pages)
        elif ext in (".docx",):
            from docx import Document
            d = Document(filepath)
            text = "\n".join(p.text for p in d.paragraphs)
        else:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        return {"success": True, "result": text[:50000]}
    except Exception as e:
        return {"success": False, "result": str(e)}


def control_system(action: str, value: Optional[int] = None) -> dict:
    action = action.lower().replace("-", "_")
    try:
        if IS_WIN:
            if action == "volume_up":
                for _ in range(value or 5):
                    pyautogui.press("volumeup")
            elif action == "volume_down":
                for _ in range(value or 5):
                    pyautogui.press("volumedown")
            elif action == "mute":
                pyautogui.press("volumemute")
            elif action == "lock_screen":
                import ctypes
                ctypes.windll.user32.LockWorkStation()
            elif action in ("brightness_up", "brightness_down"):
                # WMI approach
                import subprocess as sp
                delta = (value or 10) * (1 if action.endswith("_up") else -1)
                sp.run(["powershell", "-Command",
                        f"$b=(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness).CurrentBrightness; "
                        f"(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,[Math]::Max(0,[Math]::Min(100,$b+({delta}))))"
                        ], capture_output=True)
            else:
                return {"success": False, "result": f"Unknown action: {action}"}
        else:
            return {"success": False, "result": "system control limited on this OS"}
        return {"success": True, "result": f"Performed {action}"}
    except Exception as e:
        return {"success": False, "result": str(e)}


def get_system_info() -> dict:
    info = {
        "time": datetime.now().strftime("%H:%M"),
        "date": datetime.now().strftime("%a, %d %b %Y"),
        "platform": platform.system(),
    }
    if psutil:
        try:
            info["cpu_pct"] = psutil.cpu_percent(interval=0.1)
            info["ram_pct"] = psutil.virtual_memory().percent
            bat = psutil.sensors_battery()
            if bat:
                info["battery_pct"] = bat.percent
                info["plugged"] = bat.power_plugged
        except Exception:
            pass
    try:
        if IS_WIN:
            r = subprocess.run(["netsh", "wlan", "show", "interfaces"],
                               capture_output=True, text=True, timeout=2)
            for line in r.stdout.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    info["wifi"] = line.split(":", 1)[-1].strip()
                    break
    except Exception:
        pass
    return info


# ─────────── Natural-language intent parser ───────────
async def parse_computer_command(text: str, router) -> dict:
    """Use Groq for fast intent classification → returns {action, params}."""
    sys_prompt = (
        "You convert a user's spoken command into a JSON action call.\n"
        "Allowed actions: open_website, open_app, send_whatsapp, screenshot, "
        "type_text, search_web, set_reminder, read_file, control_system, none.\n"
        "Return STRICT JSON: {\"action\":\"...\",\"params\":{...},\"speak\":\"short confirm\"}.\n"
        "If the user is just chatting, return {\"action\":\"none\",\"params\":{},\"speak\":\"\"}.\n"
        "Examples:\n"
        "'open youtube' -> {\"action\":\"open_website\",\"params\":{\"name\":\"youtube\"},\"speak\":\"Opening YouTube.\"}\n"
        "'whatsapp mom that I'm coming' -> {\"action\":\"send_whatsapp\",\"params\":{\"contact\":\"mom\",\"message\":\"I'm coming\"},\"speak\":\"Drafting a message to mom.\"}\n"
        "'what is on my screen' -> {\"action\":\"screenshot\",\"params\":{\"analyze\":true},\"speak\":\"Looking at your screen now.\"}\n"
        "'remind me at 6pm to post on instagram' -> {\"action\":\"set_reminder\",\"params\":{\"title\":\"post on instagram\",\"when\":\"6pm\"},\"speak\":\"Reminder set.\"}\n"
        "'turn down volume' -> {\"action\":\"control_system\",\"params\":{\"action\":\"volume_down\"},\"speak\":\"Lowering volume.\"}\n"
        "Output only JSON, no commentary."
    )
    out = ""
    async for tok in router.groq_stream(sys_prompt, text):
        out += tok
    try:
        start = out.find("{")
        end = out.rfind("}")
        if start >= 0 and end > start:
            return json.loads(out[start:end + 1])
    except Exception:
        pass
    return {"action": "none", "params": {}, "speak": ""}


# ─────────── Top-level executor ───────────
async def execute(action: str, params: dict, router=None) -> dict:
    if action == "open_website":
        return open_website(params.get("name") or params.get("url", ""))
    if action == "open_app":
        return open_application(params.get("name", ""))
    if action == "send_whatsapp":
        return send_whatsapp_message(params.get("contact", ""), params.get("message", ""))
    if action == "screenshot":
        if params.get("analyze") and router:
            return await screenshot_and_analyze(router)
        return take_screenshot(analyze=False)
    if action == "type_text":
        return type_text_anywhere(params.get("text", ""))
    if action == "set_reminder":
        return set_reminder(params.get("title", ""), params.get("when", ""))
    if action == "read_file":
        return read_file(params.get("path", ""))
    if action == "control_system":
        return control_system(params.get("action", ""), params.get("value"))
    if action == "search_web":
        from ..services.research import quick_search_summary
        return await quick_search_summary(params.get("query", ""), router)
    return {"success": False, "result": f"Unknown action: {action}"}
