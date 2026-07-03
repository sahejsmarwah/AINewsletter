"""
Design phase entrypoint.

Reads data/runs/<date>_content.json, renders it through
src/design/templates/newsletter.html.j2, and saves the result to
newsletters/<date>.html. No LLM calls - this phase is deterministic.

The actual send is a separate step (the Gmail MCP server); keeping render
and send apart means you can eyeball newsletters/<date>.html in a browser
before anything goes out.

Run with:
    python src/design/formatter.py            # today's content
    python src/design/formatter.py 2026-07-03 # a specific date
"""

import json
import sys
from datetime import date
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "data" / "runs"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
OUT_DIR = ROOT / "newsletters"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_NAME = "newsletter.html.j2"

# Minimal HTML document shell wrapped around the rendered body so the file
# opens standalone in a browser and as an email.
DOCUMENT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The AI Digest &middot; {date}</title>
</head>
<body style="margin:0;padding:0;">
{body}
</body>
</html>
"""


def paragraphs(text: str) -> Markup:
    """Turn plain prose into escaped <p> blocks (blank line = new paragraph).

    The editing agent emits plain text; this keeps it readable in HTML without
    trusting it as markup.
    """
    if not text:
        return Markup("")
    blocks = [b.strip() for b in str(text).split("\n\n") if b.strip()]
    html = "".join(
        f'<p style="margin:0 0 12px 0;">{escape(block).replace(chr(10), "<br>")}</p>'
        for block in blocks
    )
    return Markup(html)


def section_label(text: str) -> Markup:
    """Render a small uppercase section heading consistently."""
    return Markup(
        '<div style="font-size:12px;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.8px;color:#3b82f6;margin-bottom:2px;">'
        f"{escape(str(text))}</div>"
    )


def build_environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["paragraphs"] = paragraphs
    env.filters["section_label"] = section_label
    return env


def render(content: dict) -> str:
    """Render a content dict to a full standalone HTML document string."""
    env = build_environment()
    template = env.get_template(TEMPLATE_NAME)
    body = template.render(**content)
    return DOCUMENT.format(date=escape(content.get("date", "")), body=body)


def resolve_date(argv: list[str]) -> str:
    return argv[1] if len(argv) > 1 else date.today().isoformat()


def main():
    run_date = resolve_date(sys.argv)
    content_path = RUNS_DIR / f"{run_date}_content.json"
    if not content_path.exists():
        raise SystemExit(
            f"No content file at {content_path}. Run the editing phase first:\n"
            f"    python src/editing/agent.py {run_date}"
        )

    content = json.loads(content_path.read_text())
    html = render(content)

    out_path = OUT_DIR / f"{run_date}.html"
    out_path.write_text(html)
    print(f"Wrote {out_path} ({len(html):,} bytes)")
    print(f"  open it: file://{out_path}")


if __name__ == "__main__":
    main()
