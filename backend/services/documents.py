"""
backend/services/documents.py
Extract text from uploaded documents (PDF/DOCX/TXT/MD/code) and produce
a marketing-oriented analysis through the AI router.
"""
import os
from pathlib import Path

TEXT_EXT = {".txt", ".md", ".markdown", ".py", ".js", ".ts", ".tsx",
            ".jsx", ".json", ".html", ".css", ".yaml", ".yml", ".toml",
            ".csv", ".log", ".rst", ".sh", ".bat", ".java", ".go",
            ".rs", ".cpp", ".c", ".h"}


def extract_text(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            r = PdfReader(str(p))
            return "\n".join((pg.extract_text() or "") for pg in r.pages)
        except Exception as e:
            return f"[Could not read PDF: {e}]"
    if ext in (".docx",):
        try:
            import docx
            d = docx.Document(str(p))
            return "\n".join(par.text for par in d.paragraphs)
        except Exception as e:
            return f"[Could not read DOCX: {e}]"
    if ext in TEXT_EXT or ext == "":
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return f"[Could not read file: {e}]"
    # Fallback: try as text
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"[Unsupported file type: {ext} — {e}]"


async def analyze_for_marketing(text: str, name: str, router) -> str:
    if not text or text.startswith("["):
        return text or "[Empty document]"
    snippet = text[:18000]
    prompt = f"""You are FRIDAY, a senior marketing CMO and friend.
A user just uploaded a document called "{name}". Read it and respond in a
warm, spoken tone (no markdown headings) covering exactly:

1) ONE honest sentence describing what this is.
2) The strongest unfair-advantage angle hiding inside it.
3) The GATEKEEPER play that would make this category-defining (name
   which of: data / distribution / standard / integration / certification
   / curation / co-creation / supply-constrained — and why).
4) The ONE move for this week.

DOCUMENT (truncated):
\"\"\"
{snippet}
\"\"\"
"""
    try:
        return await router.simple_gemini(prompt)
    except Exception as e:
        return f"[Analysis failed: {e}]"
