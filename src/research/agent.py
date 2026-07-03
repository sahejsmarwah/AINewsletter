"""
Research phase entrypoint.

Connects to all configured MCP servers, gathers raw candidates for
each newsletter section, and writes data/runs/<date>_research.json.

This phase does NOT judge or write anything - it only collects.
The editing phase is what decides what's good enough to include.

What to gather is declared in config/sources.yaml, not here, so tuning
the newsletter's inputs never means touching code.

Run with:
    python src/research/agent.py
"""

import asyncio
import json
from datetime import date
from pathlib import Path

import yaml

from mcp_client import MCPToolbox

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "runs"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SOURCES = ROOT / "config" / "sources.yaml"


def load_sources() -> dict:
    return yaml.safe_load(SOURCES.read_text()) or {}


async def _gather(toolbox, label, server, tool, arguments):
    """Call one source, returning [] (not raising) if it fails.

    A dead source should cost us that one section, never the whole run.
    """
    try:
        result = await toolbox.call(server, tool, arguments)
        count = len(result) if isinstance(result, list) else "?"
        print(f"  {label}: {count} items")
        return result if isinstance(result, list) else []
    except Exception as exc:  # noqa: BLE001 - want to survive any source failure
        print(f"  {label}: FAILED - {exc}")
        return []


async def run_research(sources: dict) -> dict:
    toolbox = MCPToolbox()
    await toolbox.connect_all()

    arxiv = sources.get("arxiv", {})
    github = sources.get("github", {})
    rss = sources.get("rss", {})
    hn = sources.get("hackernews", {})

    try:
        papers = await _gather(
            toolbox, "arxiv", "arxiv", "search_papers",
            {
                "categories": arxiv.get("categories", "cs.AI,cs.CL,cs.LG"),
                "max_results": arxiv.get("max_results", 20),
                "days_back": arxiv.get("days_back", 2),
            },
        )
        repos = await _gather(
            toolbox, "github", "github", "search_trending_repos",
            {
                "since": github.get("since", "daily"),
                "language": github.get("language", ""),
                "limit": github.get("limit", 15),
            },
        )
        updates = await _gather(
            toolbox, "rss", "fetch", "fetch_rss",
            {
                "feeds": rss.get("feeds", []),
                "max_per_feed": rss.get("max_per_feed", 5),
            },
        )
        hackernews = await _gather(
            toolbox, "hackernews", "fetch", "fetch_hackernews",
            {
                "query": hn.get("query", "AI OR LLM"),
                "min_points": hn.get("min_points", 80),
                "limit": hn.get("limit", 15),
            },
        )
    finally:
        await toolbox.close()

    return {
        "date": date.today().isoformat(),
        "papers": papers,
        "repos": repos,
        "updates": updates,
        "hackernews": hackernews,
        # Filled in as their MCP servers get built:
        # "products": [],   # product_hunt_server
        # "x_posts": [],    # search_server or custom scraper
    }


def main():
    sources = load_sources()
    print(f"Research run for {date.today().isoformat()}:")
    result = asyncio.run(run_research(sources))
    out_path = OUT_DIR / f"{result['date']}_research.json"
    out_path.write_text(json.dumps(result, indent=2))
    total = sum(len(v) for v in result.values() if isinstance(v, list))
    print(f"Wrote {out_path} ({total} total items)")


if __name__ == "__main__":
    main()
