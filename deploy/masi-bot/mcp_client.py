"""
MCP SSE Client for Odoo MCP Server.

Connects to the Odoo MCP server via SSE transport, discovers tools,
and provides async call_tool() + Anthropic-format tool schemas.
"""

import asyncio
import logging
from contextlib import AsyncExitStack

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

from config import MCP_API_TOKEN, MCP_SERVER_URL

logger = logging.getLogger(__name__)


class OdooMCPClient:
    def __init__(self):
        self.tools: dict = {}
        self.anthropic_tools: list[dict] = []
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._connected = False
        self._lock = asyncio.Lock()

    async def connect(self):
        """Connect to MCP server via SSE, discover tools."""
        async with self._lock:
            if self._connected and self._session:
                return

            await self._close_existing()

            stack = AsyncExitStack()
            try:
                headers = {"Authorization": f"Bearer {MCP_API_TOKEN}"}
                transport = await stack.enter_async_context(
                    sse_client(url=MCP_SERVER_URL, headers=headers)
                )
                read_stream, write_stream = transport

                session = await stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()

                self._exit_stack = stack
                self._session = session
                self._connected = True

                await self._discover_tools()
                logger.info(
                    "MCP connected — %d tools discovered", len(self.tools)
                )
            except Exception:
                await stack.aclose()
                raise

    async def _close_existing(self):
        """Tear down any existing connection."""
        self._session = None
        self._connected = False
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception as e:
                logger.warning("Error closing MCP connection: %s", e)
            self._exit_stack = None

    async def disconnect(self):
        """Gracefully disconnect from MCP server."""
        async with self._lock:
            await self._close_existing()
            logger.info("MCP disconnected")

    async def _discover_tools(self):
        """Fetch tool list from server and build caches."""
        result = await self._session.list_tools()
        self.tools = {}
        self.anthropic_tools = []

        for tool in result.tools:
            self.tools[tool.name] = tool

            schema = tool.inputSchema if tool.inputSchema else {
                "type": "object",
                "properties": {},
            }

            self.anthropic_tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": schema,
            })

    async def _ensure_connected(self):
        """Reconnect if the session was lost."""
        if self._connected and self._session:
            return
        logger.info("MCP session lost — reconnecting")
        await self.connect()

    async def call_tool(self, name: str, arguments: dict | None = None) -> str:
        """Call an MCP tool by name. Reconnects automatically on failure."""
        if arguments is None:
            arguments = {}

        try:
            await self._ensure_connected()
            result = await self._session.call_tool(name, arguments)
        except Exception as exc:
            logger.warning("Tool call failed (%s), reconnecting: %s", name, exc)
            self._connected = False
            try:
                await self.connect()
            except Exception as conn_err:
                raise ConnectionError(
                    f"MCP server unreachable after reconnect: {conn_err}"
                ) from conn_err
            if not self._session:
                raise ConnectionError("MCP session not established after reconnect")
            result = await self._session.call_tool(name, arguments)

        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts)

    def get_anthropic_tools(self) -> list[dict]:
        """Return tools formatted for the Anthropic API."""
        return self.anthropic_tools
