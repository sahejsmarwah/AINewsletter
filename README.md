# AI Newsletter

A daily AI-industry digest that builds itself. Every day it gathers what's
new across AI (papers, trending code, blog posts, Hacker News), has an LLM
write it up as a newsletter, renders it to HTML, and emails it out.

It runs as a **4-step pipeline**. Each step reads the file the previous one
wrote, so you run them in order:

```
1. Research  →  2. Editing  →  3. Design  →  4. Send
   gather        curate         render        email
```

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your keys
cp .env.example .env        # then open .env and fill in GROQ_API_KEY

# 3. Run the pipeline (from the project root, in this order)
python src/research/agent.py     # → data/runs/<date>_research.json
python src/editing/agent.py      # → data/runs/<date>_content.json
python src/design/formatter.py   # → newsletters/<date>.html

# 4. (optional) email it — needs the one-time Gmail setup below
python src/design/send.py
```

After step 3, open the `newsletters/<date>.html` file it prints in your
browser to see the newsletter. If you only want to *generate* it (not email
it), you're done after step 3.

> **Order matters.** Run one step at a time and let each finish before the
> next — step 2 can't run until step 1 has written its file, and so on.

---

## The four steps in detail

| # | Command | What it does | Needs a key? |
|---|---------|--------------|--------------|
| 1 | `python src/research/agent.py` | Pulls from four sources (arXiv, GitHub trending, RSS blogs, Hacker News) and saves a snapshot to `data/runs/<date>_research.json` | No |
| 2 | `python src/editing/agent.py` | Uses Groq to curate the snapshot into newsletter content at `data/runs/<date>_content.json` | **Yes — `GROQ_API_KEY`** |
| 3 | `python src/design/formatter.py` | Renders the content into `newsletters/<date>.html` (deterministic, no LLM) | No |
| 4 | `python src/design/send.py` | Emails the HTML via Gmail | **Yes — Gmail OAuth** |

**Picking a date.** Every step defaults to today. To re-run an earlier day
from its saved snapshot, pass the date:

```bash
python src/editing/agent.py 2026-07-03
```

---

## Keys and configuration

Copy `.env.example` to `.env` and fill in what you need. The only key
required to generate a newsletter is:

- **`GROQ_API_KEY`** — free at <https://console.groq.com>. Used by step 2.

Everything else is optional (Gmail sending, and future sources). See the
comments in `.env.example`.

### What's configured where

| To change... | Edit |
|--------------|------|
| Which feeds / categories / thresholds are pulled | `config/sources.yaml` |
| The editorial voice and output shape | `config/prompts/editing_agent.md` |
| How the email looks | `src/design/templates/newsletter.html.j2` |

---

## Sending email (one-time Gmail setup)

Only needed for step 4. To generate newsletters without emailing, skip this.

1. In **Google Cloud Console**: enable the Gmail API and create a
   **Desktop app** OAuth client. Download its JSON and point
   `GMAIL_CREDENTIALS_PATH` (in `.env`) at it.
2. Authorize once (opens a browser):
   ```bash
   python mcp_servers/gmail_server/authorize.py
   ```
   This writes `token.json`; after that, sends run unattended.
3. Set `NEWSLETTER_TO` in `.env`, then run `python src/design/send.py`.

---

## Running it automatically every day

`.github/workflows/daily.yml` runs the whole pipeline on a daily cron in
GitHub Actions. Add these repository secrets:

- `GROQ_API_KEY`
- `NEWSLETTER_TO`
- `GMAIL_CREDENTIALS_JSON` and `GMAIL_TOKEN_JSON` (paste the file contents)

---

## How it's built (MCP servers)

Each source is its own small **MCP server** under `mcp_servers/`, and the
research phase talks to all of them:

- `arxiv_server` — recent papers
- `github_server` — trending repositories
- `fetch_server` — RSS blogs + Hacker News
- `gmail_server` — sending the email

You can poke any server on its own (handy when building a new one):

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(
        command="python", args=["mcp_servers/arxiv_server/server.py"]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([t.name for t in tools.tools])

asyncio.run(main())
```


---

## Good to know

- **arXiv rate-limits sometimes.** `export.arxiv.org`'s public API can return
  a **403** from certain hosting providers/IP ranges. It's usually not your
  code — retry, or run from a different network.
- **No X/Twitter section yet.** Read access requires a paid tier, so there's
  no clean free API path. It'll need a search-MCP workaround or a manual step.
