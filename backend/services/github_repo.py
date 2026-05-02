"""
backend/services/github_repo.py
Fetch a GitHub repo via REST API (no clone) and produce a marketing brief
biased toward gatekeeper strategy. Uses DeepSeek for code reasoning.
"""
import os
import re
import base64
import httpx

GH_API = "https://api.github.com"


def parse_repo_url(url: str):
    url = url.strip().rstrip("/")
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?$", url)
    if m:
        return m.group(1), m.group(2)
    parts = url.split("/")
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, None


def _headers():
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    tok = os.getenv("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


async def fetch_repo_brief(url: str) -> dict:
    owner, repo = parse_repo_url(url)
    if not owner or not repo:
        return {"error": "Could not parse GitHub URL."}
    async with httpx.AsyncClient(timeout=30.0, headers=_headers()) as cli:
        meta = (await cli.get(f"{GH_API}/repos/{owner}/{repo}")).json()
        if meta.get("message") and "Not Found" in meta["message"]:
            return {"error": f"Repo not found: {owner}/{repo}"}
        # README
        readme_text = ""
        try:
            r = await cli.get(f"{GH_API}/repos/{owner}/{repo}/readme")
            if r.status_code == 200:
                j = r.json()
                readme_text = base64.b64decode(j.get("content", "")).decode(
                    "utf-8", errors="ignore")
        except Exception:
            pass
        # Top-level tree
        tree = []
        try:
            t = await cli.get(
                f"{GH_API}/repos/{owner}/{repo}/git/trees/{meta.get('default_branch','main')}?recursive=0")
            if t.status_code == 200:
                tree = [n["path"] for n in t.json().get("tree", [])][:50]
        except Exception:
            pass
        # A couple of key files
        key_blobs = {}
        for fname in ("package.json", "pyproject.toml", "requirements.txt",
                      "Cargo.toml", "go.mod"):
            try:
                f = await cli.get(
                    f"{GH_API}/repos/{owner}/{repo}/contents/{fname}")
                if f.status_code == 200:
                    j = f.json()
                    key_blobs[fname] = base64.b64decode(
                        j.get("content", "")).decode("utf-8", errors="ignore")[:4000]
            except Exception:
                pass
    return {
        "owner": owner,
        "repo": repo,
        "description": meta.get("description", ""),
        "stars": meta.get("stargazers_count", 0),
        "language": meta.get("language", ""),
        "topics": meta.get("topics", []),
        "homepage": meta.get("homepage", ""),
        "readme": readme_text[:12000],
        "tree": tree,
        "key_files": key_blobs,
    }


async def analyze_repo_for_marketing(url: str, router) -> dict:
    brief = await fetch_repo_brief(url)
    if brief.get("error"):
        return brief
    context = f"""REPO: {brief['owner']}/{brief['repo']} (★{brief['stars']}, {brief['language']})
DESCRIPTION: {brief['description']}
TOPICS: {', '.join(brief['topics'])}
TOP-LEVEL FILES: {', '.join(brief['tree'][:30])}

README (truncated):
\"\"\"
{brief['readme']}
\"\"\"

KEY FILES:
{chr(10).join(f"--- {k} ---{chr(10)}{v}" for k,v in brief['key_files'].items())}
"""
    prompt = f"""You are FRIDAY, marketing CMO and friend.
Analyse this GitHub repository for Mr Vijesh and respond in a warm, spoken
tone (no markdown headings) covering exactly:

1) ONE honest sentence on what this product really is.
2) Who would pay for it tomorrow morning (target audience, sharp).
3) The GATEKEEPER play that would make this unfair (name which of:
   data / distribution / standard / integration / certification /
   curation / co-creation / supply-constrained — and why).
4) Three concrete launch moves (no budget talk).
5) The ONE move for this week.

{context}
"""
    try:
        analysis = await router.simple_deepseek(prompt) if hasattr(
            router, "simple_deepseek") else await router.simple_gemini(prompt)
    except Exception as e:
        analysis = f"[Repo analysis failed: {e}]"
    return {"brief": brief, "analysis": analysis}
