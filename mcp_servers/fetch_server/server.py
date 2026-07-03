"""
Web / RSS Fetch MCP Server

Gathers general web signal for the newsletter's quick-updates and
big-story sections. Two tools:

    fetch_rss         - parse a set of RSS/Atom feeds (AI blogs, etc.)
    fetch_hackernews  - recent HN stories via the free Algolia API

Neither needs authentication.

Run standalone for testing:
    python server.py
(it will sit waiting on stdio - that's expected, it's meant to be
spawned by an MCP client, not run interactively)
"""

import re
from datetime import datetime, timezone

import feedparser
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fetch-server")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ai-newsletter/1.0)"}
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str, limit: int = 500) -> str:
    """Strip HTML tags and collapse whitespace from a feed summary."""
    text = TAG_RE.sub("", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


@mcp.tool()
async def fetch_rss(feeds: list[dict], max_per_feed: int = 5) -> list[dict]:
    """
    Fetch and parse RSS/Atom feeds.

    Args:
        feeds: list of {"name": <source name>, "url": <feed url>} dicts
        max_per_feed: max items to keep from each feed

    Returns:
        A flat list of dicts, each with source, title, url, summary,
        and published (ISO date or None) fields.
    """
    items = []
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        for feed in feeds:
            name = feed.get("name") or feed.get("url", "")
            url = feed.get("url")
            if not url:
                continue
            try:
                resp = await client.get(url, headers=HEADERS)
                resp.raise_for_status()
            except httpx.HTTPError:
                # A single unreachable feed shouldn't drop the others.
                continue

            parsed = feedparser.parse(resp.text)
            for entry in parsed.entries[:max_per_feed]:
                published = None
                if getattr(entry, "published_parsed", None):
                    published = datetime(
                        *entry.published_parsed[:6], tzinfo=timezone.utc
                    ).isoformat()
                items.append(
                    {
                        "source": name,
                        "title": _clean(entry.get("title", ""), 300),
                        "url": entry.get("link", ""),
                        "summary": _clean(entry.get("summary", "")),
                        "published": published,
                    }
                )
    return items


@mcp.tool()
async def fetch_hackernews(
    query: str = "AI OR LLM",
    min_points: int = 80,
    limit: int = 15,
) -> list[dict]:
    """
    Fetch recent Hacker News stories matching a query, most recent first.

    Args:
        query: Algolia full-text query (supports OR and quoted phrases)
        min_points: only keep stories with at least this many points
        limit: max stories to return

    Returns:
        A list of dicts, each with title, url, hn_url, points,
        num_comments, and published (ISO date) fields.
    """
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"points>={min_points}",
        "hitsPerPage": max(limit * 2, 20),
    }
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        resp = await client.get(HN_SEARCH, params=params, headers=HEADERS)
        resp.raise_for_status()

    stories = []
    for hit in resp.json().get("hits", []):
        object_id = hit.get("objectID")
        created = hit.get("created_at")  # already ISO 8601 from Algolia
        stories.append(
            {
                "title": hit.get("title") or hit.get("story_title") or "",
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                "hn_url": f"https://news.ycombinator.com/item?id={object_id}",
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
                "published": created,
            }
        )
        if len(stories) >= limit:
            break
    return stories


if __name__ == "__main__":
    mcp.run(transport="stdio")
