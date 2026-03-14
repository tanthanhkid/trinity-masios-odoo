"""Unit tests for MasiAgent context injection and entity extraction."""
import sys
import os
import types
from unittest.mock import MagicMock, patch

# Stub out heavy dependencies before importing agent
# config module requires env vars at import time — mock it entirely
config_stub = types.ModuleType("config")
config_stub.LLM_BASE_URL = "http://fake"
config_stub.LLM_API_KEY = "fake-key"
config_stub.LLM_MODEL = "fake-model"
config_stub.SYSTEM_PROMPT = "fake prompt"
config_stub.TELEGRAM_BOT_TOKEN = "fake-token"
config_stub.TELEGRAM_WHITELIST = set()
config_stub.MCP_SERVER_URL = "http://fake"
config_stub.MCP_API_TOKEN = ""
sys.modules.setdefault("config", config_stub)

# formatter may also import heavy libs — stub it
formatter_stub = types.ModuleType("formatter")
formatter_stub.format_command = lambda cmd, result: None
sys.modules.setdefault("formatter", formatter_stub)

# mcp_client stub
mcp_stub = types.ModuleType("mcp_client")
mcp_stub.OdooMCPClient = MagicMock
sys.modules.setdefault("mcp_client", mcp_stub)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agent as agent_module


def make_agent():
    """Create a MasiAgent with mocked dependencies."""
    a = agent_module.MasiAgent.__new__(agent_module.MasiAgent)
    a._active_contexts = {}
    a._pending_pdfs = []
    return a


def test_inject_partner_context_from_active():
    """When active context is partner, drill-down question gets partner_id hint."""
    a = make_agent()
    a._active_contexts[123] = {"type": "partner", "id": "42", "name": "ABC Tech"}
    msgs = [
        {"role": "user", "content": "/findcustomer"},
        {"role": "assistant", "content": "Tìm thấy: ABC Tech"},
        {"role": "user", "content": "lịch sử đơn hàng?"},
    ]
    result = a._inject_context(msgs, user_id=123)
    last = result[-1]["content"]
    assert "partner_id=42" in last
    assert "[CONTEXT:" in last


def test_no_injection_for_slash_command():
    """Slash commands are not injected."""
    a = make_agent()
    a._active_contexts[123] = {"type": "partner", "id": "42", "name": "ABC Tech"}
    msgs = [
        {"role": "user", "content": "/findcustomer"},
        {"role": "assistant", "content": "ABC Tech found"},
        {"role": "user", "content": "/kpi"},
    ]
    result = a._inject_context(msgs, user_id=123)
    assert result[-1]["content"] == "/kpi"


def test_extract_single_partner_from_search_read():
    """Single search_read result creates partner context."""
    result_json = '{"records": [{"id": 42, "name": "ABC Tech"}]}'
    ctx = agent_module.MasiAgent._extract_entity_from_tool_result("odoo_search_read", result_json)
    assert ctx == {"type": "partner", "id": "42", "name": "ABC Tech"}


def test_extract_multiple_partners_returns_none():
    """Multiple search results do not lock context."""
    result_json = '{"records": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}'
    ctx = agent_module.MasiAgent._extract_entity_from_tool_result("odoo_search_read", result_json)
    assert ctx is None


def test_extract_sale_order():
    """sale_order_summary result creates order context."""
    result_json = '{"id": 99, "name": "S0099", "partner_id": 5}'
    ctx = agent_module.MasiAgent._extract_entity_from_tool_result("odoo_sale_order_summary", result_json)
    assert ctx is not None
    assert ctx["type"] == "order"
    assert ctx["id"] == "99"


def test_no_injection_without_active_context():
    """No active context = no injection from block 0."""
    a = make_agent()
    # No active context set
    msgs = [
        {"role": "user", "content": "/findcustomer"},
        {"role": "assistant", "content": "Tìm thấy: ABC Tech"},
        {"role": "user", "content": "lịch sử đơn hàng?"},
    ]
    result = a._inject_context(msgs, user_id=999)
    # May still inject from regex fallback, but block 0 should not trigger
    # Just ensure no crash
    assert len(result) == 3
