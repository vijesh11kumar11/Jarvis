"""
backend/db/database.py
SQLite database with async aiosqlite.
"""
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional
import aiosqlite
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "./jarvis.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT,
    jarvis_name TEXT DEFAULT 'Aria',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);
CREATE TABLE IF NOT EXISTS business_context (
    user_id TEXT PRIMARY KEY,
    business_name TEXT,
    product TEXT,
    target_audience TEXT,
    location TEXT,
    budget_range TEXT,
    competitors TEXT,
    brand_voice TEXT,
    what_worked TEXT,
    what_failed TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    message_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    role TEXT CHECK(role IN ('user','assistant')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_used TEXT
);
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    conversation_id TEXT,
    summary TEXT NOT NULL,
    key_decisions TEXT,
    action_items TEXT,
    topics TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS market_research (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    product TEXT,
    location TEXT,
    report_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS computer_actions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    action_type TEXT,
    params_json TEXT,
    success BOOLEAN,
    result TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS usage_log (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    model TEXT,
    tokens INTEGER,
    cost REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS about_me (
    user_id TEXT PRIMARY KEY,
    life_story TEXT,
    preferences TEXT,
    facts TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    kind TEXT,
    name TEXT,
    summary TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_database():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

# ───────── USERS ─────────
async def create_user(name: str, jarvis_name: str = "Aria",
                      email: Optional[str] = None) -> dict:
    uid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (id,name,email,jarvis_name,last_active) VALUES (?,?,?,?,?)",
            (uid, name, email, jarvis_name, datetime.utcnow().isoformat()),
        )
        await db.commit()
    return {"id": uid, "name": name, "jarvis_name": jarvis_name, "email": email}

async def get_user(user_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def update_user(user_id: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields.keys())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {cols} WHERE id = ?",
                         (*fields.values(), user_id))
        await db.commit()

# ───────── BUSINESS CONTEXT ─────────
async def upsert_business_context(user_id: str, **fields) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT user_id FROM business_context WHERE user_id = ?", (user_id,))
        existing = await cur.fetchone()
        if existing:
            cols = ", ".join(f"{k} = ?" for k in fields.keys())
            await db.execute(
                f"UPDATE business_context SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (*fields.values(), user_id),
            )
        else:
            keys = ["user_id"] + list(fields.keys())
            placeholders = ",".join("?" * len(keys))
            await db.execute(
                f"INSERT INTO business_context ({','.join(keys)}) VALUES ({placeholders})",
                (user_id, *fields.values()),
            )
        await db.commit()
    return await get_business_context(user_id)

async def get_business_context(user_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM business_context WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

# ───────── CONVERSATIONS / MESSAGES ─────────
async def start_conversation(user_id: str) -> str:
    cid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO conversations (id,user_id) VALUES (?,?)", (cid, user_id))
        await db.commit()
    return cid

async def add_message(conversation_id: str, role: str, content: str,
                      model_used: Optional[str] = None) -> str:
    mid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (id,conversation_id,role,content,model_used) VALUES (?,?,?,?,?)",
            (mid, conversation_id, role, content, model_used),
        )
        await db.execute(
            "UPDATE conversations SET message_count = message_count + 1 WHERE id = ?",
            (conversation_id,),
        )
        await db.commit()
    return mid

async def get_recent_messages(conversation_id: str, limit: int = 20) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp DESC LIMIT ?",
            (conversation_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in reversed(rows)]

# ───────── SUMMARIES ─────────
async def save_summary(user_id: str, conversation_id: str, summary: str,
                       key_decisions: str = "", action_items: str = "",
                       topics: str = "") -> str:
    sid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversation_summaries (id,user_id,conversation_id,summary,key_decisions,action_items,topics) VALUES (?,?,?,?,?,?,?)",
            (sid, user_id, conversation_id, summary, key_decisions, action_items, topics),
        )
        await db.commit()
    return sid

async def get_recent_summaries(user_id: str, limit: int = 5) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM conversation_summaries WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

# ───────── MARKET RESEARCH CACHE ─────────
async def save_market_research(user_id: str, product: str, location: str,
                               report: dict, ttl_days: int = 7) -> str:
    rid = str(uuid.uuid4())
    expires = (datetime.utcnow() + timedelta(days=ttl_days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO market_research (id,user_id,product,location,report_json,expires_at) VALUES (?,?,?,?,?,?)",
            (rid, user_id, product, location, json.dumps(report), expires),
        )
        await db.commit()
    return rid

async def get_cached_research(user_id: str, product: str, location: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM market_research WHERE user_id = ? AND product = ? AND location = ? AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
            (user_id, product, location, datetime.utcnow().isoformat()),
        )
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["report"] = json.loads(d["report_json"])
        return d

async def get_latest_research(user_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM market_research WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["report"] = json.loads(d["report_json"])
        return d

# ───────── COMPUTER ACTIONS ─────────
async def log_computer_action(user_id: str, action_type: str, params: dict,
                              success: bool, result: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO computer_actions (id,user_id,action_type,params_json,success,result) VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), user_id, action_type, json.dumps(params), success, result),
        )
        await db.commit()

# ───────── USAGE ─────────
async def log_usage(user_id: str, model: str, tokens: int, cost: float = 0.0) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO usage_log (id,user_id,model,tokens,cost) VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), user_id, model, tokens, cost),
        )
        await db.commit()

async def get_usage_summary(user_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT model, SUM(tokens), SUM(cost) FROM usage_log WHERE user_id = ? GROUP BY model",
            (user_id,),
        )
        rows = await cur.fetchall()
        return {r[0]: {"tokens": r[1], "cost": r[2]} for r in rows}


# ───────── ABOUT-ME (life story) ─────────
async def get_about_me(user_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM about_me WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else {"user_id": user_id, "life_story": "",
                                      "preferences": "", "facts": ""}


async def upsert_about_me(user_id: str, life_story: str = "",
                          preferences: str = "", facts: str = "") -> dict:
    existing = await get_about_me(user_id)
    has = bool(existing.get("life_story") or existing.get("preferences") or existing.get("facts"))
    async with aiosqlite.connect(DB_PATH) as db:
        if has and existing.get("user_id"):
            await db.execute(
                "UPDATE about_me SET life_story = ?, preferences = ?, facts = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (life_story or existing.get("life_story", ""),
                 preferences or existing.get("preferences", ""),
                 facts or existing.get("facts", ""),
                 user_id),
            )
        else:
            await db.execute(
                "INSERT OR REPLACE INTO about_me (user_id, life_story, preferences, facts) VALUES (?,?,?,?)",
                (user_id, life_story, preferences, facts),
            )
        await db.commit()
    return await get_about_me(user_id)


async def append_facts(user_id: str, new_facts: str) -> None:
    me = await get_about_me(user_id)
    combined = (me.get("facts", "") or "") + "\n" + new_facts.strip()
    await upsert_about_me(user_id, life_story=me.get("life_story", ""),
                          preferences=me.get("preferences", ""),
                          facts=combined.strip())


# ───────── ATTACHMENTS ─────────
async def save_attachment(user_id: str, kind: str, name: str,
                          summary: str, content: str = "") -> str:
    aid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO attachments (id,user_id,kind,name,summary,content) VALUES (?,?,?,?,?,?)",
            (aid, user_id, kind, name, summary, content[:200000]),
        )
        await db.commit()
    return aid


async def get_recent_attachments(user_id: str, limit: int = 5) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM attachments WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
