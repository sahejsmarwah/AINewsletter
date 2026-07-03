# AI Newsletter

A daily AI-industry digest, built as an MCP-driven agent pipeline in three phases:
**research → editing → design**, delivered by email.

## Status

The full pipeline is built. **research → editing → design** all run:

- **Research** gathers from four MCP servers (arXiv, GitHub trending,
  RSS blogs, Hacker News) into `data/runs/<date>_research.json`. Runs with
  no API keys.
- **Editing** curates that snapshot with Groq into
  `data/runs/<date>_content.json` (needs a free `GROQ_API_KEY`).
- **Design** renders the content into `newsletters/<date>.html` (deterministic)
  and can send it via the Gmail MCP server (needs a one-time OAuth setup).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
```

## Running the pipeline

```bash
# 1. Research - no keys needed
python src/research/agent.py

# 2. Editing - needs GROQ_API_KEY (free at https://console.groq.com)
python src/editing/agent.py

# 3. Design - render to newsletters/<date>.html (no keys)
python src/design/formatter.py

# 4. Send - needs Gmail OAuth + NEWSLETTER_TO (see below)
python src/design/send.py
```

Each step defaults to today's date; pass a date (e.g. `2026-07-03`) to
re-run an earlier day from its saved snapshot.

### What's configured where

- **Sources** (which feeds, categories, thresholds): `config/sources.yaml`
- **Editorial voice / output shape**: `config/prompts/editing_agent.md`
- **Email look**: `src/design/templates/newsletter.html.j2`

### Sending email (one-time Gmail setup)

1. In Google Cloud Console: enable the Gmail API and create a **Desktop app**
   OAuth client. Download its JSON and point `GMAIL_CREDENTIALS_PATH` at it.
2. Authorize once (opens a browser):
   ```bash
   python mcp_servers/gmail_server/authorize.py
   ```
   This writes `token.json`; after that sends run unattended.
3. Set `NEWSLETTER_TO` in `.env`, then `python src/design/send.py`.

### Automated daily run

`.github/workflows/daily.yml` runs the whole pipeline on a daily cron.
Add these repository secrets: `GROQ_API_KEY`, `NEWSLETTER_TO`,
`GMAIL_CREDENTIALS_JSON`, `GMAIL_TOKEN_JSON` (paste the file contents).

## Testing an MCP server on its own

Each server can be poked independently without going through the full agent -
useful when you're building a new one:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python", args=["mcp_servers/arxiv_server/server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([t.name for t in tools.tools])

asyncio.run(main())
```

## Roadmap

- [x] arXiv MCP server + research phase wiring
- [x] GitHub MCP server (trending repos)
- [x] Fetch/web MCP server (RSS blogs + Hacker News)
- [x] Editing phase (Groq tool-calling agent)
- [x] Design phase (Jinja2 template + local archive)
- [x] Gmail MCP server (send) + one-time OAuth flow
- [x] GitHub Actions daily trigger
- [ ] Product Hunt MCP server (top_products section) — needs a token
- [ ] Search MCP server / X posts (top_x_posts section) — no free API path
- [ ] SQLite dedup store (skip items already featured)

## Notes

- `export.arxiv.org`'s public API occasionally rate-limits or blocks
  requests from certain hosting providers/IP ranges. If `search_papers`
  returns a 403, it's usually not your code - retry, or run from a
  different network.
- The X/Twitter section has no clean free API path (read access requires
  a paid tier). Plan for a search-MCP-based workaround or a manual step
  for that section specifically.
