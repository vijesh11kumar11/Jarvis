"""
backend/services/github_repo.py
Fetch a public GitHub repo and produce a structured marketing/positioning brief.
"""
from __future__ import annotations
import re
import json
import base64
import asyncio
from typing import Optional
import httpx


GITHUB_RE = re.compile(r"github\.com[:/]+([\w.-]+)/([\w.-]+?)(?:\.git)?/?$",
                       re.IGNORECASE)


def parse_repo_url(url: str) -> Optional[tuple[str, str]]:
    if not url: return None
    m = GITHUB_RE.search(url.strip())
    if not m: return None
    owner, name = m.group(1), m.group(2)
    return owner, name.removesuffix(".git")


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict:
    try:
        r = await client.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str:
    try:
        r = await client.get(url, timeout=15)
        if r.status_code == 200: return r.text
    except Exception:
        pass
    return ""


async def fetch_repo_data(owner: str, repo: str) -> dict:
    base = f"https://api.github.com/repos/{owner}/{repo}"
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "Friday-Marketing-Jarvis"}
    async with httpx.AsyncClient(headers=headers) as client:
        repo_info, langs, topics_resp, contents = await asyncio.gather(
            _fetch_json(client, base),
            _fetch_json(client, base + "/languages"),
            _fetch_json(client, base + "/topics"),
            _fetch_json(client, base + "/contents"),
        )
        # README
        readme = ""
        rd = await _fetch_json(client, base + "/readme")
        if rd.get("content"):
            try:
                readme = base64.b64decode(rd["content"]).decode("utf-8", errors="ignore")
            except Exception:
                readme = ""
        # branch fallback for raw files
        default_branch = (repo_info.get("default_branch") or "main")
        package_json = await _fetch_text(client, f"{raw_base}/{default_branch}/package.json")
        requirements = await _fetch_text(client, f"{raw_base}/{default_branch}/requirements.txt")

    file_names = [c.get("name") for c in (contents if isinstance(contents, list) else []) if c.get("name")][:30]
    return {
        "owner": owner, "repo": repo,
        "name": repo_info.get("name"),
        "description": repo_info.get("description") or "",
        "stars": repo_info.get("stargazers_count", 0),
        "forks": repo_info.get("forks_count", 0),
        "watchers": repo_info.get("subscribers_count", 0),
        "open_issues": repo_info.get("open_issues_count", 0),
        "homepage": repo_info.get("homepage") or "",
        "license": (repo_info.get("license") or {}).get("name") or "",
        "topics": (topics_resp.get("names") or repo_info.get("topics") or [])[:20],
        "languages": list((langs or {}).keys())[:8],
        "files_root": file_names,
        "readme": readme[:18000],
        "package_json": package_json[:6000],
        "requirements_txt": requirements[:6000],
    }


PROMPT = """You are Friday, {user_name}'s personal CMO. Produce a marketing
positioning brief for this GitHub project.

USER BUSINESS CONTEXT (their day job):
{biz}

REPO DATA:
- name: {name}
- description: {desc}
- stars: {stars}, forks: {forks}, issues: {issues}
- topics: {topics}
- languages: {langs}
- root files: {files}

README EXCERPT:
{readme}

DEPENDENCIES (if any):
{deps}

Return your analysis in EXACTLY this format:

PITCH (10 words max): <headline>

PROBLEM IT SOLVES: <1-2 sentences>

ICP (ideal customer profile): <who would actually use/install this>

POSITIONING (fill in the blanks):
"For <audience> who <struggle>, <product> is a <category> that <key benefit>, unlike <alternative> which <weakness>."

CHANNELS:
1. <channel + why it fits this product>
2. <channel + why>
3. <channel + why>

CONTENT ANGLE: <the storytelling hook that makes devs/users care>

LAUNCH STRATEGY: <Show HN / ProductHunt / Twitter dev / niche subreddit etc + reasoning>

GROWTH MOVE: <one specific tactic to 10x reach this month>

NEXT FEATURE TO BUILD (marketing-led): <feature + why it would unlock distribution>

7-DAY PLAN:
- Day 1-2: <action>
- Day 3-4: <action>
- Day 5-7: <action>

SPOKEN BRIEF: <80-word friend-style spoken summary ready for TTS, no headers>
"""


async def analyze_repo_for_marketing(url_or_owner_repo: str,
                                     user_context: Optional[dict] = None,
                                     user_name: str = "Mr Vijesh") -> dict:
    parsed = parse_repo_url(url_or_owner_repo)
    if not parsed and "/" in url_or_owner_repo:
        owner, repo = url_or_owner_repo.strip().split("/", 1)
    elif parsed:
        owner, repo = parsed
    else:
        return {"error": "Could not parse GitHub URL or owner/repo."}

    data = await fetch_repo_data(owner, repo)
    if not data.get("name"):
        return {"error": f"Repo {owner}/{repo} not found or private."}

    from ..brain.ai_router import get_router
    router = get_router()
    deps = ""
    if data.get("package_json"): deps += "package.json:\n" + data["package_json"][:1500]
    if data.get("requirements_txt"): deps += "\nrequirements.txt:\n" + data["requirements_txt"][:1500]

    prompt = PROMPT.format(
        user_name=user_name,
        biz=json.dumps(user_context or {}, default=str)[:1200],
        name=data["name"], desc=data["description"],
        stars=data["stars"], forks=data["forks"], issues=data["open_issues"],
        topics=", ".join(data["topics"]) or "—",
        langs=", ".join(data["languages"]) or "—",
        files=", ".join(data["files_root"]) or "—",
        readme=(data["readme"] or "(no README)")[:6000],
        deps=deps or "—",
    )
    analysis = ""
    for _call in (
        lambda: router.simple_gemini(prompt, model="gemini-2.0-flash"),
        lambda: router.simple_deepseek(prompt),
        lambda: router.simple_groq(prompt),
    ):
        try:
            analysis = await _call()
            if analysis: break
        except Exception:
            continue
    spoken = ""
    m = re.search(r"SPOKEN BRIEF:\s*(.+)", analysis, re.IGNORECASE | re.DOTALL)
    if m: spoken = m.group(1).strip()[:800]
    return {
        "owner": owner, "repo": repo, "data": data,
        "analysis": analysis, "spoken": spoken,
    }


# Backwards-compat
async def fetch_repo_brief(url: str) -> dict:
    parsed = parse_repo_url(url)
    if not parsed: return {"error": "Bad URL"}
    return await fetch_repo_data(*parsed)
