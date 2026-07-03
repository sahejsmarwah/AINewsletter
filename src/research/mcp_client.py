"""
Shared MCP client utilities for the research phase.

Spawns each configured MCP server as a subprocess over stdio and
exposes a single call() method so agent.py doesn't need to know
about MCP session/transport plumbing.

Add new servers here as you build them (github, fetch, product_hunt,
gmail is used in the design phase instead, not here).
"""

import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]

# name -> how to launch that server as a subprocess
SERVERS = {
    "arxiv": {
        "command": sys.executable,
        "args": [str(ROOT / "mcp_servers" / "arxiv_server" / "server.py")],
    },
    "github": {
        "command": sys.executable,
        "args": [str(ROOT / "mcp_servers" / "github_server" / "server.py")],
    },
    "fetch": {
        "command": sys.executable,
        "args": [str(ROOT / "mcp_servers" / "fetch_server" / "server.py")],
    },
    # "product_hunt": {"command": ..., "args": [...]},
}


class MCPToolbox:
    """Connects to all configured MCP servers and exposes a unified call interface."""

    def __init__(self):
        self._stack = AsyncExitStack()
        self.sessions: dict[str, ClientSession] = {}

    async def connect_all(self):
        for name, cfg in SERVERS.items():
            params = StdioServerParameters(command=cfg["command"], args=cfg["args"])
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[name] = session

    async def call(self, server: str, tool: str, arguments: dict):
        """Call a tool on a connected server and return its parsed result.

        Raises RuntimeError if the tool reported an error, so callers can
        decide per-source whether to skip or abort - an error string must
        never be mistaken for data.
        """
        session = self.sessions[server]
        result = await session.call_tool(tool, arguments)

        if result.isError:
            text = result.content[0].text if result.content else "(no detail)"
            raise RuntimeError(f"{server}.{tool} failed: {text}")

        # FastMCP returns structured output when the tool has a typed return.
        # A non-object return (e.g. list[dict]) is wrapped as {"result": ...};
        # unwrap that so callers get the value the tool actually returned.
        structured = result.structuredContent
        if structured is not None:
            if isinstance(structured, dict) and set(structured) == {"result"}:
                return structured["result"]
            return structured

        # Fallback for servers that only emit text content blocks. A tool that
        # returns a list yields one block per item, so collect them all.
        parsed = []
        for block in result.content:
            if block.type == "text":
                try:
                    parsed.append(json.loads(block.text))
                except json.JSONDecodeError:
                    parsed.append(block.text)
        if len(parsed) == 1:
            return parsed[0]
        return parsed

    async def close(self):
        await self._stack.aclose()
