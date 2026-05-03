#!/usr/bin/env python3
"""
setup.py — One-shot installer for Marketing Jarvis.
Run:  python setup.py
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GREEN = "\033[92m"; YEL = "\033[93m"; RED = "\033[91m"; CYAN = "\033[96m"; END = "\033[0m"


def step(msg): print(f"{CYAN}▶ {msg}{END}")
def ok(msg):   print(f"{GREEN}✓ {msg}{END}")
def warn(msg): print(f"{YEL}! {msg}{END}")
def err(msg):  print(f"{RED}✗ {msg}{END}")


def check_python():
    step("Checking Python version…")
    if sys.version_info < (3, 10):
        err(f"Python 3.10+ required (found {sys.version.split()[0]})")
        sys.exit(1)
    ok(f"Python {sys.version.split()[0]}")


def install_python_deps():
    step("Installing Python packages…")
    pip = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    subprocess.check_call(pip, cwd=ROOT)
    ok("Python dependencies installed")


def ensure_env():
    step("Setting up backend/.env…")
    env = ROOT / "backend" / ".env"
    sample = ROOT / "backend" / ".env.example"
    if not env.exists() and sample.exists():
        shutil.copy(sample, env)
        ok("Created backend/.env from example")
    else:
        ok("backend/.env exists")


def npm_install():
    step("Installing Node packages (npm install)…")
    if not (ROOT / "node_modules").exists():
        try:
            subprocess.check_call(["npm", "install"], cwd=ROOT, shell=os.name == "nt")
            ok("Node packages installed")
        except Exception as e:
            warn(f"npm install failed ({e}). Run it manually: npm install")
    else:
        ok("node_modules present")


def init_db():
    step("Initializing SQLite DB…")
    sys.path.insert(0, str(ROOT))
    try:
        import asyncio
        from backend.db.database import init_database
        asyncio.run(init_database())
        ok("Database initialized")
    except Exception as e:
        warn(f"DB init deferred ({e})")


def test_keys():
    step("Probing API keys…")
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
    g = os.getenv("GEMINI_API_KEY")
    q = os.getenv("GROQ_API_KEY")
    if g:
        try:
            import google.generativeai as gen
            gen.configure(api_key=g)
            m = gen.GenerativeModel("gemini-2.0-flash")
            m.generate_content("ping")
            ok("Gemini key works")
        except Exception as e:
            warn(f"Gemini key test failed: {e}")
    else:
        warn("No GEMINI_API_KEY set")
    if q:
        try:
            from groq import Groq
            Groq(api_key=q).chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=4)
            ok("Groq key works")
        except Exception as e:
            warn(f"Groq key test failed: {e}")
    else:
        warn("No GROQ_API_KEY set")


def main():
    print(f"{CYAN}\n=== Marketing Jarvis Setup ==={END}")
    check_python()
    install_python_deps()
    ensure_env()
    init_db()
    npm_install()
    test_keys()
    print(f"\n{GREEN}All done.{END} Launch with:")
    print(f"  Windows:  {CYAN}start.bat{END}")
    print(f"  Mac/Linux: {CYAN}./start.sh{END}\n")


if __name__ == "__main__":
    main()
