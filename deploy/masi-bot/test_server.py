"""
Masi Bot Test API — structured endpoints for AI agent testing.

Run:  python test_server.py
Base: http://103.72.97.51:8300

Endpoints:
  POST /api/chat        Send message, get structured response
  POST /api/clear       Clear conversation history for a user
  GET  /api/history     Get full conversation history
  GET  /api/commands    List all slash commands with metadata
  GET  /api/tools       List all MCP tools
  GET  /api/health      Server health check
  GET  /                Web UI (for manual testing)
"""

import asyncio
import json
import logging
import time
from aiohttp import web

from agent import MasiAgent, COMMAND_TOOL_MAP, PDF_TOOLS
from config import TELEGRAM_WHITELIST
from mcp_client import OdooMCPClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("test_server")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
mcp_client: OdooMCPClient = None
agent: MasiAgent = None
conversations: dict[int, list] = {}     # user_id -> message history
call_logs: dict[int, list] = {}         # user_id -> tool call log per session
MAX_HISTORY = 20

DEFAULT_USER_ID = 2048339435  # CEO user for testing


def get_history(user_id: int) -> list:
    if user_id not in conversations:
        conversations[user_id] = []
    return conversations[user_id]


def add_to_history(user_id: int, role: str, content: str):
    history = get_history(user_id)
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY:
        conversations[user_id] = history[-MAX_HISTORY:]


# ---------------------------------------------------------------------------
# Monkey-patch agent to capture tool calls
# ---------------------------------------------------------------------------
_original_call_tool = None

async def _logging_call_tool(name, args):
    """Wrapper that logs tool calls for test inspection."""
    t0 = time.time()
    result = await _original_call_tool(name, args)
    elapsed = time.time() - t0

    # Store in current session log
    entry = {
        "tool": name,
        "args": args,
        "elapsed_ms": round(elapsed * 1000),
        "result_len": len(result) if isinstance(result, str) else len(json.dumps(result, default=str)),
        "is_pdf": name in PDF_TOOLS,
    }

    # Append to all active user logs
    for uid in call_logs:
        call_logs[uid].append(entry)

    return result


# ---------------------------------------------------------------------------
# API Handlers
# ---------------------------------------------------------------------------
async def handle_chat(request: web.Request) -> web.Response:
    """
    POST /api/chat
    Body: {"message": "...", "user_id": 2048339435}

    Returns structured response with timing, tool calls, path info.
    Designed for AI agent evaluation.
    """
    data = await request.json()
    text = data.get("message", "").strip()
    user_id = data.get("user_id", DEFAULT_USER_ID)

    if not text:
        return web.json_response({"error": "Empty message"}, status=400)

    # Reset tool call log for this request
    call_logs[user_id] = []

    add_to_history(user_id, "user", text)
    history = get_history(user_id)

    # Detect if this should be fast path
    cmd = text.strip().split()[0] if text.strip() else ""
    if "@" in cmd:
        cmd = cmd.split("@")[0]
    expected_path = "fast" if cmd in COMMAND_TOOL_MAP else "llm"

    t0 = time.time()
    try:
        response = await agent.chat(list(history), telegram_user_id=user_id)
        error = None
    except Exception as e:
        logger.error("Agent error: %s", e, exc_info=True)
        response = f"❌ Error: {e}"
        error = str(e)

    elapsed = time.time() - t0
    add_to_history(user_id, "assistant", response)

    # Collect PDFs
    pdfs = []
    for pdf_data in agent.pop_pending_pdfs():
        pdfs.append({
            "filename": pdf_data.get("filename", "document.pdf"),
            "size_bytes": pdf_data.get("size_bytes", 0),
            "order_name": pdf_data.get("order_name", ""),
            "partner": pdf_data.get("partner", ""),
            "amount_total": pdf_data.get("amount_total", 0),
            # base64 omitted for API — too large. Use /api/chat?include_pdf=1 if needed
            "has_data": bool(pdf_data.get("pdf_base64")),
        })

    # Build structured result
    tool_calls = call_logs.get(user_id, [])
    result = {
        "response": response,
        "elapsed_ms": round(elapsed * 1000),
        "path": expected_path,
        "tool_calls": tool_calls,
        "tool_count": len(tool_calls),
        "pdfs": pdfs,
        "history_len": len(history),
        "user_id": user_id,
        "error": error,
    }

    return web.json_response(result, dumps=lambda x: json.dumps(x, ensure_ascii=False, default=str))


async def handle_clear(request: web.Request) -> web.Response:
    """
    POST /api/clear
    Body: {"user_id": 2048339435}  (optional, defaults to CEO)

    Clears conversation history. Essential between test scenarios.
    """
    data = await request.json()
    user_id = data.get("user_id", DEFAULT_USER_ID)
    old_len = len(get_history(user_id))
    conversations.pop(user_id, None)
    call_logs.pop(user_id, None)
    return web.json_response({"status": "cleared", "messages_removed": old_len})


async def handle_history(request: web.Request) -> web.Response:
    """
    GET /api/history?user_id=2048339435

    Returns full conversation history for inspection.
    """
    user_id = int(request.query.get("user_id", DEFAULT_USER_ID))
    return web.json_response({
        "user_id": user_id,
        "history": get_history(user_id),
        "message_count": len(get_history(user_id)),
    }, dumps=lambda x: json.dumps(x, ensure_ascii=False, default=str))


async def handle_commands(request: web.Request) -> web.Response:
    """
    GET /api/commands

    Lists all registered slash commands with their MCP tool mapping.
    AI agent uses this to know what commands to test.
    """
    fast_commands = []
    for cmd, (tool, args) in COMMAND_TOOL_MAP.items():
        fast_commands.append({
            "command": cmd,
            "mcp_tool": tool,
            "default_args": args,
            "path": "fast",
            "needs_input": False,
        })

    # Commands that need user input (go through LLM)
    llm_commands = [
        {"command": "/masi", "description": "Show menu", "path": "llm", "needs_input": False},
        {"command": "/quote", "description": "View sale order", "path": "llm", "needs_input": True, "input_type": "order_id"},
        {"command": "/invoice", "description": "View invoice", "path": "llm", "needs_input": True, "input_type": "invoice_id"},
        {"command": "/newlead", "description": "Create CRM lead", "path": "llm", "needs_input": True, "input_type": "name, phone"},
        {"command": "/newcustomer", "description": "Create customer", "path": "llm", "needs_input": True, "input_type": "name, phone, email"},
        {"command": "/findcustomer", "description": "Search customer", "path": "llm", "needs_input": True, "input_type": "search_term"},
    ]

    return web.json_response({
        "fast_commands": fast_commands,
        "llm_commands": llm_commands,
        "total_fast": len(fast_commands),
        "total_llm": len(llm_commands),
        "total": len(fast_commands) + len(llm_commands),
    }, dumps=lambda x: json.dumps(x, ensure_ascii=False, default=str))


async def handle_tools(request: web.Request) -> web.Response:
    """
    GET /api/tools

    Lists all MCP tools available from Odoo server.
    """
    tools = mcp_client.get_anthropic_tools()
    tool_list = []
    for t in tools:
        tool_list.append({
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": list(t.get("input_schema", {}).get("properties", {}).keys()),
        })

    return web.json_response({
        "tools": tool_list,
        "total": len(tool_list),
    }, dumps=lambda x: json.dumps(x, ensure_ascii=False, default=str))


async def handle_health(request: web.Request) -> web.Response:
    """
    GET /api/health

    Quick health check — is MCP connected? How many tools?
    """
    return web.json_response({
        "status": "ok",
        "mcp_connected": mcp_client is not None and len(mcp_client.tools) > 0,
        "mcp_tools": len(mcp_client.tools) if mcp_client else 0,
        "active_sessions": len(conversations),
        "llm_model": "qwen3.5-plus",
    })


async def handle_index(request: web.Request) -> web.Response:
    """GET / — redirect to API docs or serve simple UI."""
    return web.Response(text=API_DOCS_HTML, content_type="text/html")


# ---------------------------------------------------------------------------
# Simple API docs page
# ---------------------------------------------------------------------------
API_DOCS_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><title>Masi Bot Test API</title>
<style>
body { font-family: -apple-system, sans-serif; background: #0e1621; color: #e5e5e5; padding: 40px; max-width: 900px; margin: 0 auto; }
h1 { color: #5ec47b; } h2 { color: #5288c1; margin-top: 30px; }
.endpoint { background: #17212b; padding: 16px; border-radius: 8px; margin: 12px 0; border-left: 3px solid #5288c1; }
.method { color: #5ec47b; font-weight: bold; } .path { color: #e5c07b; }
code { background: #1a2332; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
pre { background: #1a2332; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 13px; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-left: 8px; }
.fast { background: #2d5a27; color: #5ec47b; } .llm { background: #5a4a27; color: #e5c07b; }
</style>
</head><body>
<h1>🤖 Masi Bot Test API</h1>
<p>Structured API for AI agent testing. All responses are JSON.</p>

<h2>Endpoints</h2>

<div class="endpoint">
<span class="method">POST</span> <span class="path">/api/chat</span> — Send message, get structured response
<pre>{
  "message": "/kpi",
  "user_id": 2048339435    // optional, defaults to CEO
}</pre>
Response includes: <code>response</code>, <code>elapsed_ms</code>, <code>path</code> (fast/llm), <code>tool_calls[]</code>, <code>pdfs[]</code>, <code>history_len</code>
</div>

<div class="endpoint">
<span class="method">POST</span> <span class="path">/api/clear</span> — Clear conversation history
<pre>{"user_id": 2048339435}   // optional</pre>
⚠️ Call this between test scenarios to reset context.
</div>

<div class="endpoint">
<span class="method">GET</span> <span class="path">/api/history</span> — Get conversation history
<pre>/api/history?user_id=2048339435</pre>
</div>

<div class="endpoint">
<span class="method">GET</span> <span class="path">/api/commands</span> — List all slash commands
<p>Returns <code>fast_commands[]</code> (template, &lt;1s) and <code>llm_commands[]</code> (need args, ~10s)</p>
</div>

<div class="endpoint">
<span class="method">GET</span> <span class="path">/api/tools</span> — List all 51 MCP tools
</div>

<div class="endpoint">
<span class="method">GET</span> <span class="path">/api/health</span> — Health check
</div>

<h2>Testing Patterns</h2>

<h3>1. Fast path command <span class="tag fast">FAST</span></h3>
<pre>POST /api/clear
POST /api/chat  {"message": "/kpi"}
→ Assert: path="fast", elapsed_ms &lt; 2000, tool_count=2 (perm + data)</pre>

<h3>2. Multi-turn conversation <span class="tag llm">LLM</span></h3>
<pre>POST /api/clear
POST /api/chat  {"message": "/quote"}
→ Bot asks for ID
POST /api/chat  {"message": "1"}
→ Assert: bot shows SO 1 details (not "lệnh không rõ ràng")</pre>

<h3>3. PDF download <span class="tag llm">LLM</span></h3>
<pre>POST /api/clear
POST /api/chat  {"message": "tải PDF báo giá 1"}
→ Assert: pdfs[0].filename exists, pdfs[0].has_data=true</pre>

<h3>4. Context continuity <span class="tag llm">LLM</span></h3>
<pre>POST /api/clear
POST /api/chat  {"message": "/kpi"}
POST /api/chat  {"message": "giải thích số pipeline"}
→ Assert: response references pipeline value from KPI</pre>

<h3>5. Free-form Vietnamese <span class="tag llm">LLM</span></h3>
<pre>POST /api/clear
POST /api/chat  {"message": "hôm nay có bao nhiêu lead mới?"}
→ Assert: response contains number, tool_calls includes odoo_* tool</pre>

</body></html>
"""


# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------
async def on_startup(app: web.Application):
    """Initialize MCP client when aiohttp starts."""
    global mcp_client, agent, _original_call_tool
    mcp_client = OdooMCPClient()
    await mcp_client.connect()
    agent = MasiAgent(mcp_client)

    # Patch tool calls for logging
    _original_call_tool = mcp_client.call_tool
    mcp_client.call_tool = _logging_call_tool

    logger.info("Test server initialized with %d MCP tools", len(mcp_client.tools))


def create_app() -> web.Application:
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            resp = web.Response()
        else:
            resp = await handler(request)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    app = web.Application(middlewares=[cors_middleware])
    app.on_startup.append(on_startup)
    app.router.add_get("/", handle_index)
    app.router.add_post("/api/chat", handle_chat)
    app.router.add_post("/api/clear", handle_clear)
    app.router.add_get("/api/history", handle_history)
    app.router.add_get("/api/commands", handle_commands)
    app.router.add_get("/api/tools", handle_tools)
    app.router.add_get("/api/health", handle_health)
    return app


if __name__ == "__main__":
    logger.info("Starting Test API at http://0.0.0.0:8300")
    web.run_app(create_app(), host="0.0.0.0", port=8300)
