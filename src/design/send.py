"""
Send step of the design phase.

Reads the rendered newsletters/<date>.html (rendering it first if needed),
spawns the Gmail MCP server over stdio, and calls its send_email tool.

Kept separate from formatter.py on purpose: rendering is safe to run any
time, but sending is an outward action, so it's an explicit, deliberate step.

Run with:
    python src/design/send.py            # today
    python src/design/send.py 2026-07-03 # a specific date

Requires:
    NEWSLETTER_TO   comma-separated recipient address(es) in .env
    a Gmail token   (run mcp_servers/gmail_server/authorize.py once)
"""

import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import formatter as fmt  # same directory

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "data" / "runs"
OUT_DIR = ROOT / "newsletters"
GMAIL_SERVER = ROOT / "mcp_servers" / "gmail_server" / "server.py"

load_dotenv(ROOT / ".env")


def resolve_date(argv: list[str]) -> str:
    return argv[1] if len(argv) > 1 else date.today().isoformat()


def subject_for(content: dict, run_date: str) -> str:
    big = (content.get("big_story") or {}).get("title")
    lead = f": {big}" if big else ""
    return f"The AI Digest · {run_date}{lead}"


async def send(run_date: str, html: str, subject: str, recipients: str):
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(GMAIL_SERVER)],
        env=os.environ.copy(),  # pass GMAIL_TOKEN_PATH etc. through to the server
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "send_email",
                {
                    "to": recipients,
                    "subject": subject,
                    "html_body": html,
                    "text_body": f"The AI Digest for {run_date}. "
                    "Open in an HTML-capable client to read.",
                },
            )
    if result.isError:
        detail = result.content[0].text if result.content else "(no detail)"
        raise SystemExit(f"Send failed: {detail}")
    return result.structuredContent or {}


def main():
    run_date = resolve_date(sys.argv)

    recipients = os.environ.get("NEWSLETTER_TO", "").strip()
    if not recipients:
        raise SystemExit(
            "NEWSLETTER_TO is not set. Add comma-separated recipient(s) to .env."
        )

    content_path = RUNS_DIR / f"{run_date}_content.json"
    if not content_path.exists():
        raise SystemExit(
            f"No content file at {content_path}. Run the editing phase first."
        )
    content = json.loads(content_path.read_text())

    # Render fresh so the sent email always matches current content/template.
    html = fmt.render(content)
    out_path = OUT_DIR / f"{run_date}.html"
    out_path.write_text(html)

    subject = subject_for(content, run_date)
    print(f"Sending '{subject}' to {recipients} ...")
    info = asyncio.run(send(run_date, html, subject, recipients))
    print(f"Sent. Gmail message id: {info.get('id')}")


if __name__ == "__main__":
    main()
