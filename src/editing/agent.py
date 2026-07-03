"""
Editing phase entrypoint.

Reads data/runs/<date>_research.json, uses a free tool-calling LLM (Groq)
to curate it, and writes data/runs/<date>_content.json matching the nine
sections in config/newsletter_schema.yaml.

This is the ONLY phase that authors content. The research phase just
gathered; the design phase just renders. Here is where the judgment lives.

Run with:
    python src/editing/agent.py            # uses today's research file
    python src/editing/agent.py 2026-07-03 # or a specific date

Requires GROQ_API_KEY in the environment (or .env). Get a free key at
https://console.groq.com .
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "data" / "runs"
SYSTEM_PROMPT = ROOT / "config" / "prompts" / "editing_agent.md"

load_dotenv(ROOT / ".env")

# Free, strong tool/JSON-capable model on Groq. Override with GROQ_MODEL.
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# The nine sections every newsletter must have (config/newsletter_schema.yaml).
# products and x_posts have no source wired up yet, so they default to empty
# and the template simply omits them.
REQUIRED_SECTIONS = [
    "introduction",
    "big_story",
    "quick_updates",
    "top_papers",
    "top_repos",
    "tutorial",
    "top_products",
    "top_x_posts",
    "closing_notes",
]


def _trim(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def build_candidate_payload(research: dict) -> dict:
    """Compress the raw snapshot into a compact, token-friendly candidate set.

    The editor doesn't need every field or the full abstracts - just enough
    to judge and cite. Trimming here keeps us comfortably inside free-tier
    token limits.
    """
    papers = [
        {
            "title": p.get("title", ""),
            "authors": (p.get("authors") or ["Unknown"])[0]
            + (" et al." if len(p.get("authors") or []) > 1 else ""),
            "summary": _trim(p.get("summary", ""), 400),
            "url": p.get("url", ""),
        }
        for p in research.get("papers", [])[:15]
    ]
    repos = [
        {
            "name": r.get("full_name", ""),
            "description": _trim(r.get("description", ""), 200),
            "language": r.get("language"),
            "stars": r.get("stars", 0),
            "stars_since": r.get("stars_since", 0),
            "url": r.get("url", ""),
        }
        for r in research.get("repos", [])[:15]
    ]
    updates = [
        {
            "source": u.get("source", ""),
            "title": u.get("title", ""),
            "summary": _trim(u.get("summary", ""), 250),
            "url": u.get("url", ""),
        }
        for u in research.get("updates", [])[:20]
    ]
    hackernews = [
        {
            "title": h.get("title", ""),
            "points": h.get("points", 0),
            "url": h.get("url", ""),
        }
        for h in research.get("hackernews", [])[:15]
    ]
    return {
        "papers": papers,
        "repos": repos,
        "blog_posts": updates,
        "hacker_news": hackernews,
    }


def edit(research: dict) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise SystemExit(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add a free "
            "key from https://console.groq.com , then re-run."
        )

    client = Groq(api_key=api_key)
    system = SYSTEM_PROMPT.read_text()
    payload = build_candidate_payload(research)

    user = (
        "Here is today's raw snapshot. Curate it into the newsletter JSON.\n\n"
        + json.dumps(payload, indent=2)
    )

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = json.loads(response.choices[0].message.content)
    return normalize(content, research["date"])


def normalize(content: dict, run_date: str) -> dict:
    """Guarantee all nine sections exist so the template never KeyErrors."""
    normalized = {"date": run_date}
    for key in REQUIRED_SECTIONS:
        value = content.get(key)
        if value is None:
            # list sections default to [], prose sections to ""
            value = [] if key in {
                "quick_updates", "top_papers", "top_repos",
                "top_products", "top_x_posts",
            } else ""
        normalized[key] = value
    return normalized


def resolve_date(argv: list[str]) -> str:
    return argv[1] if len(argv) > 1 else date.today().isoformat()


def main():
    run_date = resolve_date(sys.argv)
    research_path = RUNS_DIR / f"{run_date}_research.json"
    if not research_path.exists():
        raise SystemExit(
            f"No research file at {research_path}. Run the research phase first:\n"
            f"    python src/research/agent.py"
        )

    research = json.loads(research_path.read_text())
    print(f"Editing {run_date} with {MODEL}...")
    content = edit(research)

    out_path = RUNS_DIR / f"{run_date}_content.json"
    out_path.write_text(json.dumps(content, indent=2))
    counts = {
        k: len(v) for k, v in content.items()
        if isinstance(v, list)
    }
    print(f"Wrote {out_path}")
    print(f"  sections: {counts}")


if __name__ == "__main__":
    main()
