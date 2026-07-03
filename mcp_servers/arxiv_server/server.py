"""
arXiv MCP Server

Exposes one tool, search_papers, which queries the public arXiv API
for recently submitted papers in a given set of categories.

Run standalone for testing:
    python server.py
(it will sit waiting on stdio - that's expected, it's meant to be
spawned by an MCP client, not run interactively)
"""

from datetime import datetime, timedelta, timezone

import feedparser
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("arxiv-server")

ARXIV_API = "https://export.arxiv.org/api/query"


@mcp.tool()
async def search_papers(
    categories: str = "cs.AI,cs.CL,cs.LG",
    max_results: int = 15,
    days_back: int = 1,
) -> list[dict]:
    """
    Search arXiv for recently submitted papers in the given categories.

    Args:
        categories: comma-separated arXiv category codes,
            e.g. "cs.AI,cs.CL,cs.LG"
        max_results: maximum number of papers to fetch before date filtering
        days_back: only keep papers submitted within this many days

    Returns:
        A list of dicts, each with title, authors, summary, url,
        and published (ISO date) fields.
    """
    cat_query = " OR ".join(f"cat:{c.strip()}" for c in categories.split(","))
    params = {
        "search_query": cat_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(ARXIV_API, params=params)
        response.raise_for_status()

    feed = feedparser.parse(response.text)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    papers = []
    for entry in feed.entries:
        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if published < cutoff:
            continue
        papers.append(
            {
                "title": entry.title.replace("\n", " ").strip(),
                "authors": [a.name for a in entry.authors]
                if hasattr(entry, "authors")
                else [],
                "summary": entry.summary.replace("\n", " ").strip(),
                "url": entry.link,
                "published": published.isoformat(),
            }
        )

    return papers


if __name__ == "__main__":
    mcp.run(transport="stdio")
