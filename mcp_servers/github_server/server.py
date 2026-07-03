"""
GitHub Trending MCP Server

Exposes one tool, search_trending_repos, which scrapes github.com/trending
(there is no official trending API) for repositories gaining stars.

Run standalone for testing:
    python server.py
(it will sit waiting on stdio - that's expected, it's meant to be
spawned by an MCP client, not run interactively)
"""

import re

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("github-server")

TRENDING_URL = "https://github.com/trending"
# GitHub returns a plain 403 to obviously-scripted clients; a browser UA is enough.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ai-newsletter/1.0)"}


def _stars_today(article) -> int:
    """Pull the '1,234 stars today' count off a trending row, or 0 if absent."""
    node = article.find(string=re.compile(r"star(s)? (today|this week|this month)"))
    if not node:
        return 0
    match = re.search(r"([\d,]+)", node)
    return int(match.group(1).replace(",", "")) if match else 0


@mcp.tool()
async def search_trending_repos(
    since: str = "daily",
    language: str = "",
    limit: int = 15,
) -> list[dict]:
    """
    Fetch repositories currently trending on GitHub.

    Args:
        since: trending window - one of "daily", "weekly", "monthly"
        language: optional language slug to filter by, e.g. "python"
            (leave empty for all languages)
        limit: maximum number of repositories to return

    Returns:
        A list of dicts, each with full_name, url, description, language,
        stars (total), and stars_since (gained within the window) fields.
    """
    since = since if since in {"daily", "weekly", "monthly"} else "daily"
    url = TRENDING_URL
    if language.strip():
        url = f"{TRENDING_URL}/{language.strip().lower()}"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url, params={"since": since}, headers=HEADERS)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    repos = []
    for article in soup.select("article.Box-row")[:limit]:
        anchor = article.select_one("h2 a")
        if not anchor or not anchor.get("href"):
            continue
        full_name = anchor["href"].strip("/")

        desc_el = article.select_one("p")
        lang_el = article.select_one('[itemprop="programmingLanguage"]')
        stars_el = article.select_one('a[href$="/stargazers"]')

        repos.append(
            {
                "full_name": full_name,
                "url": f"https://github.com/{full_name}",
                "description": desc_el.get_text(strip=True) if desc_el else "",
                "language": lang_el.get_text(strip=True) if lang_el else None,
                "stars": int(stars_el.get_text(strip=True).replace(",", ""))
                if stars_el
                else 0,
                "stars_since": _stars_today(article),
            }
        )

    return repos


if __name__ == "__main__":
    mcp.run(transport="stdio")
