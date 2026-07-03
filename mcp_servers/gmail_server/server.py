"""
Gmail MCP Server

Exposes one tool, send_email, which sends an HTML email through the Gmail
API using a previously-authorized OAuth token.

This server does NOT run the interactive OAuth flow - a subprocess talking
stdio can't open a browser. Run the one-time authorization first:

    python mcp_servers/gmail_server/authorize.py

That writes token.json; after that this server can send unattended (the
token auto-refreshes). Paths come from the environment:

    GMAIL_CREDENTIALS_PATH  OAuth client secrets from Google Cloud Console
    GMAIL_TOKEN_PATH        token.json produced by authorize.py

Run standalone for testing:
    python server.py
(it will sit waiting on stdio - meant to be spawned by an MCP client)
"""

import base64
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gmail-server")

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

DEFAULT_TOKEN = Path(__file__).resolve().parent / "token.json"
TOKEN_PATH = Path(os.environ.get("GMAIL_TOKEN_PATH", str(DEFAULT_TOKEN)))


def _load_credentials() -> Credentials:
    if not TOKEN_PATH.exists():
        raise RuntimeError(
            f"No Gmail token at {TOKEN_PATH}. Run authorize.py once to create it."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())  # persist the refreshed token
        else:
            raise RuntimeError(
                "Gmail token is invalid and cannot refresh. Re-run authorize.py."
            )
    return creds


@mcp.tool()
async def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str = "",
) -> dict:
    """
    Send an HTML email via Gmail.

    Args:
        to: recipient address(es), comma-separated for multiple
        subject: email subject line
        html_body: the HTML body of the email
        text_body: optional plain-text fallback (recommended for deliverability)

    Returns:
        A dict with sent (bool), id (Gmail message id), and to fields.
    """
    creds = _load_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    message = MIMEMultipart("alternative")
    message["To"] = to
    message["Subject"] = subject
    # A plain-text part first, then HTML - clients pick the richest they support.
    message.attach(MIMEText(text_body or "View this email in an HTML client.", "plain"))
    message.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )
    return {"sent": True, "id": sent.get("id"), "to": to}


if __name__ == "__main__":
    mcp.run(transport="stdio")
