"""
One-time Gmail OAuth bootstrap.

Run this once, locally, in a terminal where a browser can open:

    python mcp_servers/gmail_server/authorize.py

Prerequisite: a Google Cloud OAuth client (Desktop app type) with the Gmail
API enabled. Download its client-secret JSON and point GMAIL_CREDENTIALS_PATH
at it (see .env.example). This script opens a browser, you grant the
gmail.send scope, and it writes token.json. After that the Gmail MCP server
runs unattended.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

HERE = Path(__file__).resolve().parent
CREDENTIALS_PATH = Path(
    os.environ.get("GMAIL_CREDENTIALS_PATH", str(HERE / "credentials.json"))
)
TOKEN_PATH = Path(os.environ.get("GMAIL_TOKEN_PATH", str(HERE / "token.json")))


def main():
    if not CREDENTIALS_PATH.exists():
        raise SystemExit(
            f"OAuth client secrets not found at {CREDENTIALS_PATH}.\n"
            "Create a Desktop-app OAuth client in Google Cloud Console, enable "
            "the Gmail API, download the JSON, and set GMAIL_CREDENTIALS_PATH."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json())
    print(f"Authorized. Wrote {TOKEN_PATH}")
    print("The Gmail MCP server can now send unattended.")


if __name__ == "__main__":
    main()
