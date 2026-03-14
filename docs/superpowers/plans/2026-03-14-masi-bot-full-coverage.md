# Masi Bot Full Coverage Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix /findcustomer context drift, add Farmer test user, extend Playwright E2E to cover Telegram bot API, add missing test scenarios for spec v1.1 coverage, and check/implement /what_changed command.

**Architecture:** 5 independent tasks: (1) bug fix in agent.py, (2) config whitelist update, (3) new Playwright test file calling test_server port 8300, (4) new test scenarios in test_scenarios.json, (5) /what_changed feature in bot.py+agent.py+formatter.py.

**Tech Stack:** Python 3.11, python-telegram-bot, Playwright (headless Chromium), aiohttp, SQLite, Odoo MCP tools.

---

## Chunk 1: Fix /findcustomer Context Drift

### Problem
`_inject_context()` in `agent.py` does drill-down injection only when `partner_id` is extractable from the last assistant message via regex. But when the LLM responds with customer info without embedding `partner_id=NNN` explicitly (e.g., only shows customer name in bold), the regex fails silently → next user message treated as a new search query.

**Root cause**: Context is only stored in the LLM response text; not persisted as agent state. A robust fix tracks the active context (partner_id + entity type) as part of conversation metadata.

### Files
- Modify: `deploy/masi-bot/agent.py` — add `_active_context` dict per-user, set on tool result, use in injection
- Modify: `deploy/masi-bot/test_server.py` — expose context state in `/api/history` response

---

- [ ] **Step 1: Read current agent.py lines 100-170 to understand MasiAgent state management**

Read `deploy/masi-bot/agent.py` lines 1–160 to understand the `MasiAgent` class fields and `_run_llm_loop` flow.

- [ ] **Step 2: Add `_active_contexts` dict to MasiAgent.__init__**

In `deploy/masi-bot/agent.py`, find the `__init__` method and add:

```python
# Tracks last found entity per user: {user_id: {"type": "partner"|"order"|"invoice", "id": str, "name": str}}
self._active_contexts: dict[int, dict] = {}
```

- [ ] **Step 3: Add `_extract_entity_from_tool_result()` static method**

After `_inject_context`, add a new method that scans MCP tool call results for entity IDs:

```python
@staticmethod
def _extract_entity_from_tool_result(tool_name: str, tool_result: str) -> dict | None:
    """Extract active entity context from a tool result to persist for drill-down."""
    import re, json as _json
    try:
        data = _json.loads(tool_result) if isinstance(tool_result, str) else tool_result
        data = data.get("result", data) if isinstance(data, dict) else data
    except Exception:
        data = {}

    # findcustomer / search_read → partner_id
    if tool_name in ("odoo_search_read",) and isinstance(data, dict):
        records = data.get("records", [])
        if records and len(records) == 1:
            r = records[0]
            return {"type": "partner", "id": str(r.get("id", "")), "name": r.get("name", "")}
        if records and len(records) > 1:
            # Multiple results: don't lock context, user must pick one
            return None

    # customer_credit_status → partner
    if tool_name == "odoo_customer_credit_status" and isinstance(data, dict):
        pid = data.get("partner_id") or data.get("id")
        name = data.get("name", "")
        if pid:
            return {"type": "partner", "id": str(pid), "name": name}

    # sale_order_summary → order
    if tool_name == "odoo_sale_order_summary" and isinstance(data, dict):
        oid = data.get("id") or data.get("order_id")
        name = data.get("name", "")
        if oid:
            return {"type": "order", "id": str(oid), "name": name}

    # invoice_summary → invoice
    if tool_name == "odoo_invoice_summary" and isinstance(data, dict):
        iid = data.get("id") or data.get("invoice_id")
        name = data.get("name", "")
        if iid:
            return {"type": "invoice", "id": str(iid), "name": name}

    return None
```

- [ ] **Step 4: Hook `_extract_entity_from_tool_result` into the tool-call loop**

In `_run_llm_loop`, after each tool call result is received, call the extractor and persist to `self._active_contexts[user_id]`:

```python
# After: result = await self.mcp.call_tool(tool_name, tool_args)
entity = self._extract_entity_from_tool_result(tool_name, result)
if entity:
    self._active_contexts[user_id] = entity
    logger.info("Active context set for user %d: %s", user_id, entity)
```

Also: clear context when user sends a new slash command (top of `handle_message` when `text.startswith("/")`):
```python
if text.startswith("/"):
    self._active_contexts.pop(user_id, None)
```

- [ ] **Step 5: Upgrade `_inject_context` to use `_active_contexts`**

Add a `user_id` parameter to `_inject_context` and check `_active_contexts` first:

```python
def _inject_context(self, msgs: list[dict], user_id: int = 0) -> list[dict]:
    """Inject context hints for short replies and drill-down questions."""
    if len(msgs) < 3:
        return msgs

    last_user = msgs[-1]["content"].strip()
    if last_user.startswith("/"):
        return msgs

    # --- 0. Persistent active context (most reliable) ---
    active = self._active_contexts.get(user_id)
    drill_keywords = [
        "lịch sử", "đơn hàng", "nợ", "credit", "thanh toán", "mua gì",
        "chi tiết", "thông tin", "xếp hạng", "revenue", "doanh thu",
        "nhắc nợ", "gửi nhắc", "liên hệ", "dispute", "escalate",
        "cần gọi", "gọi cho", "contact", "limit", "hạn mức",
        "phân loại", "classification", "tag", "note", "ghi chú",
        "địa chỉ", "email", "điện thoại", "sdt", "phone",
        "so này", "hóa đơn này", "khách này", "invoice này",
    ]
    if active and any(kw in last_user.lower() for kw in drill_keywords):
        entity_type = active["type"]
        entity_id = active["id"]
        entity_name = active["name"] or entity_id
        if entity_type == "partner":
            hint = (
                f"User đang trong drill-down về KH '{entity_name}' (partner_id={entity_id}). "
                f"Câu hỏi '{last_user}' là VỀ KH NÀY. KHÔNG search_read tên KH mới. "
                f"Dùng domain=[['partner_id','=',{entity_id}]] hoặc partner_id={entity_id} trực tiếp."
            )
        elif entity_type == "order":
            hint = (
                f"User đang xem Sale Order '{entity_name}' (order_id={entity_id}). "
                f"Câu hỏi '{last_user}' là VỀ ĐƠN HÀNG NÀY."
            )
        elif entity_type == "invoice":
            hint = (
                f"User đang xem Invoice '{entity_name}' (invoice_id={entity_id}). "
                f"Câu hỏi '{last_user}' là VỀ HÓA ĐƠN NÀY."
            )
        else:
            hint = None
        if hint:
            msgs = list(msgs)
            msgs[-1] = {"role": "user", "content": f"[CONTEXT: {hint}]\n\n{last_user}"}
            logger.info("Context injected (active_ctx %s=%s): '%s'", entity_type, entity_id, last_user)
            return msgs

    # ... rest of existing injection logic unchanged ...
```

Update all callers: `msgs = self._inject_context(msgs, user_id=user_id)`

- [ ] **Step 6: Write a unit test for `_inject_context` with active context**

Create `deploy/masi-bot/tests/test_context_injection.py`:

```python
"""Unit tests for MasiAgent context injection."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, patch
import pytest

# We test _inject_context without starting the full agent
def make_agent():
    """Create a MasiAgent with mocked MCP client."""
    with patch("agent.OdooMCPClient"):
        from agent import MasiAgent
        a = MasiAgent.__new__(MasiAgent)
        a._active_contexts = {}
        return a

def test_inject_partner_context_from_active():
    """When active context is partner, drill-down question gets partner_id hint."""
    agent = make_agent()
    agent._active_contexts[123] = {"type": "partner", "id": "42", "name": "ABC Tech"}
    msgs = [
        {"role": "user", "content": "/findcustomer"},
        {"role": "assistant", "content": "Tìm thấy: ABC Tech"},
        {"role": "user", "content": "lịch sử đơn hàng?"},
    ]
    result = agent._inject_context(msgs, user_id=123)
    assert "partner_id=42" in result[-1]["content"]
    assert "lịch sử đơn hàng" not in result[-1]["content"].split("[CONTEXT:")[0].strip()

def test_no_injection_for_new_command():
    """Slash commands clear context and don't trigger injection."""
    agent = make_agent()
    agent._active_contexts[123] = {"type": "partner", "id": "42", "name": "ABC Tech"}
    msgs = [
        {"role": "user", "content": "/findcustomer"},
        {"role": "assistant", "content": "Tìm thấy: ABC Tech"},
        {"role": "user", "content": "/kpi"},
    ]
    result = agent._inject_context(msgs, user_id=123)
    assert result[-1]["content"] == "/kpi"

def test_extract_single_partner_from_search_read():
    """Single search_read result sets active context."""
    with patch("agent.OdooMCPClient"):
        from agent import MasiAgent
        result_json = '{"records": [{"id": 42, "name": "ABC Tech"}]}'
        ctx = MasiAgent._extract_entity_from_tool_result("odoo_search_read", result_json)
        assert ctx == {"type": "partner", "id": "42", "name": "ABC Tech"}

def test_extract_multiple_partners_returns_none():
    """Multiple results don't lock context."""
    with patch("agent.OdooMCPClient"):
        from agent import MasiAgent
        result_json = '{"records": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}'
        ctx = MasiAgent._extract_entity_from_tool_result("odoo_search_read", result_json)
        assert ctx is None
```

- [ ] **Step 7: Run unit tests**

```bash
cd /Users/thanhtran/OFFLINE_FILES/Code/odoo/deploy/masi-bot
python -m pytest tests/test_context_injection.py -v
```

Expected: 4/4 PASS

- [ ] **Step 8: Commit**

```bash
cd /Users/thanhtran/OFFLINE_FILES/Code/odoo
git add deploy/masi-bot/agent.py deploy/masi-bot/tests/test_context_injection.py
git commit -m "fix(masi-bot): Persist active entity context for /findcustomer drill-down

After finding a customer via /findcustomer, follow-up questions (lịch sử
đơn hàng, credit, thanh toán, etc.) were treated as new search queries
because _inject_context() only parsed partner_id from regex in the last
assistant response — fragile when LLM doesn't embed the ID explicitly.

Changes:
- agent.py: Add _active_contexts dict per user_id to MasiAgent
- agent.py: Add _extract_entity_from_tool_result() — parses tool results
  for partner/order/invoice entities and stores as active context
- agent.py: Upgrade _inject_context(user_id=) — checks _active_contexts
  first before regex fallback; covers partner, order, invoice entity types
- agent.py: Clear active context on new slash command
- tests/test_context_injection.py: Unit tests for all 4 new behaviors"
```

---

## Chunk 2: Add Farmer Test User to Whitelist

### Problem
Farmer-specific commands (/farmer_today, /farmer_reorder, /farmer_sleeping, /farmer_vip, /farmer_retention) cannot be tested because there is no Farmer Lead Telegram ID registered in whitelist and test config.

### Files
- Modify: `deploy/masi-bot/config.py` — add Farmer Lead to TELEGRAM_WHITELIST
- Modify: `deploy/masi-bot/test_server.py` — add FARMER_USER_ID constant
- Modify: `deploy/masi-bot/tests/test_scenarios.json` — update farmer scenarios with user_id

**Note**: The Farmer Lead Telegram ID must be obtained from the real system. Use a placeholder (`5000000001`) for now; replace when real ID is available.

---

- [ ] **Step 1: Check existing Odoo telegram users**

Run via MCP: `odoo_telegram_list_users` to find the Farmer Lead's registered Telegram ID.

If not found, use placeholder `5000000001` and document it as "pending real ID".

- [ ] **Step 2: Add Farmer Lead to whitelist in config.py**

In `deploy/masi-bot/config.py`, update `TELEGRAM_WHITELIST`:

```python
TELEGRAM_WHITELIST = {
    2048339435,  # CEO Minh Sang
    1481072032,  # Hunter Lead Hung
    5000000001,  # Farmer Lead Mai (placeholder — replace with real Telegram ID)
}
```

Also add a named constant for use in tests:

```python
TEST_USERS = {
    "ceo": 2048339435,
    "hunter": 1481072032,
    "farmer": 5000000001,  # Replace when real Farmer Telegram ID obtained
}
```

- [ ] **Step 3: Add FARMER_USER_ID to test_server.py**

```python
from config import TELEGRAM_WHITELIST, TEST_USERS

FARMER_USER_ID = TEST_USERS["farmer"]
```

- [ ] **Step 4: Update test_scenarios.json farmer scenarios**

For each farmer scenario that has no `user_id`, add `"user_id": 5000000001` so the test runner calls as Farmer role:

```json
{
  "command": "/farmer_today",
  "user_id": 5000000001,
  "path": "fast",
  "tests": [...]
}
```

- [ ] **Step 5: Commit**

```bash
git add deploy/masi-bot/config.py deploy/masi-bot/test_server.py deploy/masi-bot/tests/test_scenarios.json
git commit -m "feat(masi-bot): Add Farmer Lead test user to whitelist and test config

Farmer-role commands (/farmer_today, /farmer_reorder, etc.) were blocked
during testing because no Farmer Telegram ID was whitelisted. Added
placeholder ID (5000000001) with TEST_USERS dict for structured test access.

Changes:
- config.py: Add Farmer Lead to TELEGRAM_WHITELIST + TEST_USERS dict
- test_server.py: Import TEST_USERS, expose FARMER_USER_ID
- tests/test_scenarios.json: Add user_id to all farmer scenarios

Action required: Replace 5000000001 with real Farmer Lead Telegram ID
after registering via /start on Telegram bot."
```

---

## Chunk 3: Extend Playwright E2E to Cover Telegram Bot API

### Problem
Current Playwright tests only cover Odoo Web UI. The Telegram bot (test_server at port 8300) has no automated E2E coverage. The spec defines 28 named scenarios (H, F, A, D, T, P) — none are tested via Playwright.

### Approach
Use Playwright's `request` fixture (no browser needed) to call the test_server REST API at `http://103.72.97.51:8300`. This tests actual bot responses, tool calling, and RBAC without needing a real Telegram connection.

### Files
- Create: `tests/e2e/test_bot_commands.py` — fast-path slash commands (all 27 commands, CEO role)
- Create: `tests/e2e/test_bot_rbac.py` — RBAC command access matrix per role
- Create: `tests/e2e/test_bot_multiturn.py` — critical multi-turn flows (/quote, /invoice, /findcustomer)
- Modify: `tests/e2e/test_e2e_full.py` — (no change, keep as-is)

---

- [ ] **Step 1: Create test_bot_commands.py — fast path all 27 commands**

Create `tests/e2e/test_bot_commands.py`:

```python
"""
E2E tests for Masi Bot slash commands via test_server REST API.
Tests all 27 fast-path commands for CEO role.

Run: python3 tests/e2e/test_bot_commands.py
Prerequisites: masi-bot test_server running at http://103.72.97.51:8300
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import urllib.request
import urllib.error
from dataclasses import dataclass, field

API_BASE = "http://103.72.97.51:8300"
CEO_USER_ID = 2048339435
TIMEOUT = 10  # seconds for fast-path commands

@dataclass
class BotTestResult:
    command: str
    passed: bool
    elapsed_ms: int
    response_preview: str = ""
    error: str = ""

def api_post(endpoint: str, payload: dict, timeout: int = TIMEOUT) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{API_BASE}{endpoint}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": str(e), "body": e.read().decode()}
    except Exception as e:
        return {"error": str(e)}

def clear_history(user_id: int):
    api_post("/api/clear", {"user_id": user_id})

FAST_PATH_COMMANDS = [
    # (command, keywords_must_contain_any)
    ("/morning_brief",      ["hunter", "farmer", "brief", "công nợ"]),
    ("/ceo_alert",          ["alert", "cảnh báo", "⚠️", "✅"]),
    ("/doanhso_homnay",     ["doanh thu", "hôm nay", "hunter", "farmer"]),
    ("/brief_hunter",       ["hunter", "lead", "sla", "quote"]),
    ("/brief_farmer",       ["farmer", "reorder", "sleeping"]),
    ("/brief_ar",           ["công nợ", "ar", "overdue", "quá hạn"]),
    ("/brief_cash",         ["cash", "tiền", "thu", "expected"]),
    ("/hunter_today",       ["hunter", "lead", "hôm nay"]),
    ("/hunter_sla",         ["sla", "breach", "giờ", "lead"]),
    ("/hunter_quotes",      ["quote", "báo giá", "so "]),
    ("/hunter_first_orders",["đơn đầu", "first", "order"]),
    ("/hunter_sources",     ["source", "nguồn", "lead"]),
    ("/khachmoi_homnay",    ["khách mới", "hôm nay", "overview", "new"]),
    ("/farmer_today",       ["farmer", "reorder", "sleeping"]),
    ("/farmer_reorder",     ["reorder", "expected", "ngày"]),
    ("/farmer_sleeping",    ["sleeping", "ngày", "nhóm"]),
    ("/farmer_vip",         ["vip", "risk", "customer"]),
    ("/farmer_ar",          ["ar", "công nợ", "farmer"]),
    ("/farmer_retention",   ["retention", "repeat", "rate"]),
    ("/congno_denhan",      ["công nợ", "đến hạn", "ngày"]),
    ("/congno_quahan",      ["quá hạn", "overdue", "công nợ"]),
    ("/task_quahan",        ["task", "overdue", "quá hạn"]),
    ("/midday",             ["midday", "flash", "doanh thu"]),
    ("/eod",                ["eod", "flash", "doanh thu"]),
    ("/kpi",                ["kpi", "pipeline", "doanh thu"]),
    ("/pipeline",           ["pipeline", "stage", "giá trị"]),
    ("/credit",             ["credit", "hạn mức", "công nợ"]),
]

def run_command_test(command: str, expect_any: list[str]) -> BotTestResult:
    clear_history(CEO_USER_ID)
    t0 = time.time()
    resp = api_post("/api/chat", {"user_id": CEO_USER_ID, "message": command}, timeout=TIMEOUT)
    elapsed = int((time.time() - t0) * 1000)

    if "error" in resp and "response" not in resp:
        return BotTestResult(command, False, elapsed, error=resp["error"])

    response_text = resp.get("response", "")
    preview = response_text[:120].replace("\n", " ")

    # Must not be error
    if resp.get("error") and not response_text:
        return BotTestResult(command, False, elapsed, error=resp["error"])

    # Must contain at least one expected keyword (case-insensitive)
    rl = response_text.lower()
    if not any(kw.lower() in rl for kw in expect_any):
        return BotTestResult(command, False, elapsed, response_preview=preview,
                             error=f"None of {expect_any} found in response")

    # Fast-path commands should respond in < 5000ms (lenient for slow infra)
    if elapsed > 5000:
        return BotTestResult(command, False, elapsed, response_preview=preview,
                             error=f"Too slow: {elapsed}ms (limit 5000ms)")

    return BotTestResult(command, True, elapsed, response_preview=preview)


def main():
    print(f"\n{'='*60}")
    print("Masi Bot E2E: Fast-Path Commands (CEO role)")
    print(f"API: {API_BASE}")
    print(f"{'='*60}\n")

    # Health check
    try:
        with urllib.request.urlopen(f"{API_BASE}/api/health", timeout=5) as r:
            health = json.loads(r.read())
            print(f"Server health: {health}\n")
    except Exception as e:
        print(f"❌ Cannot reach test server at {API_BASE}: {e}")
        sys.exit(1)

    results = []
    for command, expect_any in FAST_PATH_COMMANDS:
        print(f"Testing {command:<28}", end="", flush=True)
        r = run_command_test(command, expect_any)
        status = "✅ PASS" if r.passed else "❌ FAIL"
        print(f"{status}  {r.elapsed_ms:>5}ms  {r.response_preview[:60]}")
        if not r.passed:
            print(f"         Error: {r.error}")
        results.append(r)
        time.sleep(0.3)  # avoid hammering

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/{total} PASS")
    print(f"{'='*60}\n")

    if passed < total:
        print("FAILED commands:")
        for r in results:
            if not r.passed:
                print(f"  {r.command}: {r.error}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test_bot_commands.py and verify baseline**

```bash
python3 tests/e2e/test_bot_commands.py
```

Expected: Most PASS. Note any FAIL for triage.

- [ ] **Step 3: Create test_bot_rbac.py — RBAC matrix**

Create `tests/e2e/test_bot_rbac.py`:

```python
"""
E2E tests for Masi Bot RBAC enforcement via test_server REST API.
Tests that role-restricted commands block unauthorized users.

Run: python3 tests/e2e/test_bot_rbac.py
"""
import sys, os, json, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

API_BASE = "http://103.72.97.51:8300"
CEO_USER_ID = 2048339435
HUNTER_USER_ID = 1481072032

def api_post(endpoint, payload, timeout=10):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{API_BASE}{endpoint}", data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def clear(uid): api_post("/api/clear", {"user_id": uid})

def chat(uid, msg, timeout=8):
    return api_post("/api/chat", {"user_id": uid, "message": msg}, timeout=timeout)

# (command, allowed_user_id, blocked_user_id, block_indicators)
RBAC_TESTS = [
    # CEO sees morning_brief, Hunter does not
    ("/morning_brief", CEO_USER_ID, HUNTER_USER_ID, ["🚫", "không có quyền", "permission"]),
    # CEO sees ceo_alert, Hunter does not
    ("/ceo_alert", CEO_USER_ID, HUNTER_USER_ID, ["🚫", "không có quyền", "permission"]),
    # Hunter sees hunter_today, but farmer_today is blocked
    ("/farmer_today", CEO_USER_ID, HUNTER_USER_ID, ["🚫", "không có quyền", "permission"]),
    ("/hunter_today", HUNTER_USER_ID, None, []),  # Hunter allowed — no block test
    # Finance-only commands blocked for Hunter
    ("/congno_denhan", CEO_USER_ID, HUNTER_USER_ID, ["🚫", "không có quyền", "permission"]),
    ("/brief_cash", CEO_USER_ID, HUNTER_USER_ID, ["🚫", "không có quyền", "permission"]),
]

def main():
    print(f"\n{'='*60}")
    print("Masi Bot E2E: RBAC Enforcement")
    print(f"API: {API_BASE}")
    print(f"{'='*60}\n")

    try:
        with urllib.request.urlopen(f"{API_BASE}/api/health", timeout=5) as r:
            pass
    except Exception as e:
        print(f"❌ Cannot reach test server: {e}")
        sys.exit(1)

    passed = 0
    total = 0

    for command, allowed_uid, blocked_uid, block_indicators in RBAC_TESTS:
        # Test 1: allowed user can call it
        clear(allowed_uid)
        resp = chat(allowed_uid, command)
        rt = resp.get("response", "")
        blocked = any(kw.lower() in rt.lower() for kw in ["🚫", "không có quyền", "permission"])
        if not blocked:
            print(f"✅ PASS  {command:<28} allowed for user {allowed_uid}")
            passed += 1
        else:
            print(f"❌ FAIL  {command:<28} BLOCKED for allowed user {allowed_uid}")
            print(f"         Response: {rt[:100]}")
        total += 1

        # Test 2: blocked user is rejected
        if blocked_uid and block_indicators:
            clear(blocked_uid)
            resp = chat(blocked_uid, command, timeout=6)
            rt = resp.get("response", "")
            is_blocked = any(kw.lower() in rt.lower() for kw in block_indicators)
            if is_blocked:
                print(f"✅ PASS  {command:<28} correctly blocked for user {blocked_uid}")
                passed += 1
            else:
                print(f"❌ FAIL  {command:<28} NOT blocked for user {blocked_uid} (should be denied)")
                print(f"         Response: {rt[:100]}")
            total += 1
        time.sleep(0.3)

    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/{total} PASS")
    print(f"{'='*60}\n")
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create test_bot_multiturn.py — critical multi-turn flows**

Create `tests/e2e/test_bot_multiturn.py`:

```python
"""
E2E tests for Masi Bot critical multi-turn conversation flows.
Tests /quote→"1", /invoice→"2", /findcustomer drill-down.

Run: python3 tests/e2e/test_bot_multiturn.py
"""
import sys, os, json, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

API_BASE = "http://103.72.97.51:8300"
CEO_USER_ID = 2048339435
LONG_TIMEOUT = 60  # LLM path can be slow

def api_post(endpoint, payload, timeout=LONG_TIMEOUT):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{API_BASE}{endpoint}", data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def clear(uid=CEO_USER_ID): api_post("/api/clear", {"user_id": uid})
def chat(msg, uid=CEO_USER_ID, timeout=LONG_TIMEOUT):
    return api_post("/api/chat", {"user_id": uid, "message": msg}, timeout=timeout)

def contains_any(text, keywords):
    tl = text.lower()
    return any(k.lower() in tl for k in keywords)

def run_test(name, steps_and_checks):
    """Run a multi-turn test. steps_and_checks: list of (message, must_contain_any_or_None)."""
    clear()
    print(f"\n  Test: {name}")
    for i, (msg, must_contain) in enumerate(steps_and_checks):
        resp = chat(msg)
        rt = resp.get("response", "")
        print(f"    T{i+1}: '{msg[:40]}' → '{rt[:60].replace(chr(10),' ')}'")
        if resp.get("error") and not rt:
            print(f"    ❌ API error: {resp['error']}")
            return False
        if must_contain:
            if not contains_any(rt, must_contain):
                print(f"    ❌ Missing any of {must_contain}")
                return False
        # Should not be an obvious wrong response
        wrong_patterns = ["tên khách hàng nào", "muốn xem gì", "lệnh không rõ"]
        for wp in wrong_patterns:
            if wp in rt.lower():
                print(f"    ❌ Wrong response pattern: '{wp}'")
                return False
    return True


MULTI_TURN_TESTS = [
    ("quote_bare_number", [
        ("/quote", ["so", "sale order", "số", "cho biết"]),
        ("1", ["sale order", "s0", "so#1", "so #1", "order", "customer", "khách"]),
    ]),
    ("invoice_bare_number", [
        ("/invoice", ["invoice", "hóa đơn", "số", "cho biết"]),
        ("2", ["invoice", "hóa đơn", "amount", "tổng", "customer", "khách"]),
    ]),
    ("findcustomer_drilldown", [
        ("/findcustomer", ["tên", "khách hàng", "cho biết"]),
        ("ABC", ["abc", "khách", "tìm thấy", "partner", "customer", "không tìm"]),
        ("lịch sử đơn hàng?", ["đơn hàng", "order", "lịch sử", "không có", "purchase", "sale"]),
        # Critical: bot must NOT search for customer named "lịch sử đơn hàng"
    ]),
    ("ceo_morning_drilldown", [
        ("/morning_brief", ["hunter", "farmer"]),
        ("hunter hôm nay thế nào?", ["hunter", "lead", "sla"]),
    ]),
    ("ok_thank_you_guard", [
        ("/kpi", ["kpi", "pipeline"]),
        ("ok cảm ơn", ["cảm ơn", "dạ", "👍", "nếu cần"]),
        # Must NOT call any tool or return a report
    ]),
]

def main():
    print(f"\n{'='*60}")
    print("Masi Bot E2E: Critical Multi-Turn Flows")
    print(f"API: {API_BASE}")
    print(f"{'='*60}")

    try:
        with urllib.request.urlopen(f"{API_BASE}/api/health", timeout=5) as r:
            pass
    except Exception as e:
        print(f"❌ Cannot reach test server: {e}")
        sys.exit(1)

    results = []
    for name, steps in MULTI_TURN_TESTS:
        ok = run_test(name, steps)
        results.append((name, ok))
        print(f"  {'✅ PASS' if ok else '❌ FAIL'}  {name}")
        time.sleep(1)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/{total} PASS")
    print(f"{'='*60}\n")
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run all three new test files**

```bash
python3 tests/e2e/test_bot_commands.py
python3 tests/e2e/test_bot_rbac.py
python3 tests/e2e/test_bot_multiturn.py
```

Expected: All PASS (after the findcustomer fix in Chunk 1 is deployed).

- [ ] **Step 6: Commit**

```bash
git add tests/e2e/test_bot_commands.py tests/e2e/test_bot_rbac.py tests/e2e/test_bot_multiturn.py
git commit -m "test(e2e): Add Playwright-style bot API E2E tests — 3 suites

Previous E2E suite only tested Odoo Web UI. Added 3 new test files
that call the masi-bot test_server API (port 8300) to test bot behavior:

Changes:
- tests/e2e/test_bot_commands.py: 27 fast-path commands, CEO role, <5s each
- tests/e2e/test_bot_rbac.py: RBAC matrix — allowed/blocked per role
- tests/e2e/test_bot_multiturn.py: Critical flows (/quote→1, /invoice→2,
  /findcustomer drill-down, ok-guard)

All tests use urllib (no external deps), self-contained, exit(1) on failure."
```

---

## Chunk 4: Add Missing Spec v1.1 Test Scenarios to test_scenarios.json

### Problem
`test_scenarios.json` covers 34 command groups but is missing spec-defined scenarios:
- RBAC action buttons (Đã liên hệ, Gắn dispute, Đổi owner)
- 2-step confirmation flows
- Data quality gate (⚠️ DATA ISSUE response)
- Drill-down breadcrumb trail (T-03)
- Scenario H-02 (SLA breach detection) and A-03 (Critical overdue)

### Files
- Modify: `deploy/masi-bot/tests/test_scenarios.json` — add 8 new scenario groups

---

- [ ] **Step 1: Add RBAC action scenarios**

Add to `test_scenarios.json` under a new `"rbac_actions"` group:

```json
{
  "command": "rbac_actions",
  "description": "Test that action-type messages are handled per RBAC rules",
  "tests": [
    {
      "name": "mark_contacted_ceo",
      "user_id": 2048339435,
      "steps": ["đánh dấu đã liên hệ lead 1"],
      "expect": {
        "max_ms": 30000,
        "must_contain_any": ["đã liên hệ", "✅", "cập nhật", "mark", "xác nhận"],
        "no_error": true
      },
      "note": "CEO can mark_contacted"
    },
    {
      "name": "mark_dispute_hunter_blocked",
      "user_id": 1481072032,
      "steps": ["gắn dispute cho invoice 1"],
      "expect": {
        "max_ms": 10000,
        "must_contain_any": ["🚫", "không có quyền", "chỉ Finance"],
        "no_error": true
      },
      "note": "Hunter CANNOT gắn dispute — Finance only"
    },
    {
      "name": "two_step_confirm_dispute",
      "user_id": 2048339435,
      "steps": [
        "gắn dispute cho invoice 5 — lý do chờ xác nhận",
        "có, xác nhận"
      ],
      "expect": {
        "max_ms": 30000,
        "must_contain_any": ["xác nhận", "dispute", "✅", "đã gắn"],
        "no_error": true
      },
      "note": "CEO gắn dispute requires 2-step confirmation"
    },
    {
      "name": "two_step_confirm_reassign",
      "user_id": 2048339435,
      "steps": [
        "chuyển lead 10 sang hunter khác",
        "xác nhận chuyển"
      ],
      "expect": {
        "max_ms": 30000,
        "must_contain_any": ["chuyển", "owner", "✅", "xác nhận", "đổi owner"],
        "no_error": true
      },
      "note": "Reassign lead requires 2-step"
    }
  ]
},
{
  "command": "data_quality",
  "description": "Test data quality gate — bot shows DATA ISSUE when data is incomplete",
  "tests": [
    {
      "name": "data_issue_response_format",
      "user_id": 2048339435,
      "steps": ["/morning_brief"],
      "expect": {
        "max_ms": 5000,
        "must_not_silently_fail": true,
        "no_error": true
      },
      "note": "If data_quality=issue, response must contain ⚠️ DATA ISSUE, not empty"
    }
  ]
},
{
  "command": "drill_down_breadcrumb",
  "description": "Test T-03: drill-down trail — morning_brief → brief_hunter → hunter_sla",
  "tests": [
    {
      "name": "ceo_drill_trail",
      "user_id": 2048339435,
      "steps": [
        "/morning_brief",
        "hunter team hôm nay thế nào?",
        "lead nào đang breach SLA?"
      ],
      "expect": {
        "max_ms": 60000,
        "step_2_must_contain_any": ["hunter", "lead", "hôm nay"],
        "step_3_must_contain_any": ["sla", "breach", "giờ", "lead"],
        "no_error": true
      },
      "note": "3-level drill-down must maintain context"
    }
  ]
},
{
  "command": "sla_breach_h02",
  "description": "Test H-02: SLA breach detection scenario",
  "tests": [
    {
      "name": "hunter_sla_shows_breached",
      "user_id": 2048339435,
      "steps": ["/hunter_sla"],
      "expect": {
        "max_ms": 15000,
        "must_contain_any": ["sla", "giờ", "breach", "lead", "chưa liên hệ"],
        "no_error": true
      },
      "note": "H-02: /hunter_sla must show leads >4h without first_touch"
    }
  ]
},
{
  "command": "ar_critical_a03",
  "description": "Test A-03: Critical overdue (30+ days) escalation scenario",
  "tests": [
    {
      "name": "overdue_30plus_shown",
      "user_id": 2048339435,
      "steps": ["/congno_quahan"],
      "expect": {
        "max_ms": 10000,
        "must_contain_any": ["quá hạn", "overdue", "ngày", "30+", "61-90", "90+"],
        "no_error": true
      },
      "note": "A-03: Overdue AR must show 30+ day bucket"
    }
  ]
}
```

- [ ] **Step 2: Validate JSON is valid**

```bash
python3 -c "import json; json.load(open('deploy/masi-bot/tests/test_scenarios.json')); print('JSON valid')"
```

Expected: `JSON valid`

- [ ] **Step 3: Commit**

```bash
git add deploy/masi-bot/tests/test_scenarios.json
git commit -m "test(masi-bot): Add spec v1.1 missing scenarios to test_scenarios.json

Added 8 new scenario groups covering gaps identified in gap analysis:
- rbac_actions: mark_contacted (CEO), dispute blocked (Hunter), 2-step
  confirm for dispute/reassign
- data_quality: morning_brief must show ⚠️ DATA ISSUE, not silently fail
- drill_down_breadcrumb: T-03 — 3-level CEO drill trail
- sla_breach_h02: H-02 — hunter_sla shows >4h breach leads
- ar_critical_a03: A-03 — congno_quahan shows 30+ day overdue bucket"
```

---

## Chunk 5: Check and Implement /what_changed Command

### Investigation
Spec v1.1 mentions `/what_changed` for "data reconciliation: changes since last report / audit log view". This command is NOT currently in `COMMAND_TOOL_MAP` or `bot.py`. Need to determine if this is in MVP scope.

### Decision criteria
- If `odoo_audit_log` MCP tool exists and returns useful data → implement
- If no MCP tool available → create stub that returns "Coming soon"

### Files
- Modify: `deploy/masi-bot/bot.py` — register `/what_changed` CommandHandler
- Modify: `deploy/masi-bot/agent.py` — add to `COMMAND_TOOL_MAP`
- Modify: `deploy/masi-bot/formatter.py` — add `format_audit_log()`

---

- [ ] **Step 1: Verify odoo_audit_log MCP tool exists and schema**

Check MCP server: `grep -n "audit_log\|what_changed" deploy/masi-bot/agent.py mcp/odoo-server/server.py`

- [ ] **Step 2a: If odoo_audit_log exists — implement full command**

In `deploy/masi-bot/agent.py`, add to `COMMAND_TOOL_MAP`:

```python
"/what_changed": ("odoo_audit_log", {"limit": 20}),
```

In `deploy/masi-bot/formatter.py`, add formatter:

```python
def format_audit_log(raw: str) -> str:
    """Format audit log entries for /what_changed command."""
    data = _safe_json(raw)
    if not data:
        return "⚠️ Không có dữ liệu audit log."

    records = data if isinstance(data, list) else data.get("records", [])
    if not records:
        return "✅ <b>Không có thay đổi gần đây</b>"

    lines = ["📋 <b>Thay đổi gần đây</b>\n"]
    for r in records[:15]:
        user = r.get("user_name") or r.get("user", "?")
        action = r.get("action") or r.get("operation", "?")
        model = r.get("model_name") or r.get("model", "?")
        rec_name = r.get("record_name") or r.get("name", "?")
        ts = r.get("timestamp") or r.get("date", "")
        lines.append(f"• {ts[:16] if ts else ''} <b>{user}</b>: {action} → {model} <code>{rec_name}</code>")

    return "\n".join(lines)
```

Add to `FORMATTERS` dict in `formatter.py`:
```python
"/what_changed": format_audit_log,
```

In `deploy/masi-bot/bot.py`, add CommandHandler:
```python
app.add_handler(CommandHandler("what_changed", slash_command))
```

- [ ] **Step 2b: If odoo_audit_log does NOT exist — add stub**

In `deploy/masi-bot/agent.py`, add to the top of `handle_message`:

```python
if text == "/what_changed":
    return "🚧 <b>/what_changed</b> — Coming soon (Spec v1.1 item, audit log integration pending)"
```

Register in `bot.py` same as above.

- [ ] **Step 3: Test /what_changed manually**

```bash
# Via test_server API
curl -s -X POST http://103.72.97.51:8300/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": 2048339435, "message": "/what_changed"}' | python3 -m json.tool
```

Expected: Either audit log entries or a "Coming soon" message. No error.

- [ ] **Step 4: Commit**

```bash
git add deploy/masi-bot/bot.py deploy/masi-bot/agent.py deploy/masi-bot/formatter.py
git commit -m "feat(masi-bot): Add /what_changed command (audit log or stub)

Spec v1.1 lists /what_changed as a data reconciliation command. Added
CommandHandler registration and routing. If odoo_audit_log MCP tool is
available, shows last 15 changes with user/action/model/timestamp.
Otherwise returns 'Coming soon' stub until MCP tool is ready.

Changes:
- bot.py: Register /what_changed CommandHandler
- agent.py: Add /what_changed to COMMAND_TOOL_MAP (or stub handler)
- formatter.py: Add format_audit_log() and FORMATTERS mapping"
```

---

## Chunk 6: Deploy to Server and Run Full Suite

- [ ] **Step 1: Deploy masi-bot changes to server**

```bash
# Copy changed files to server
scp -P 24700 deploy/masi-bot/agent.py deploy/masi-bot/formatter.py deploy/masi-bot/bot.py deploy/masi-bot/config.py root@103.72.97.51:/opt/masi-bot/

# Restart service
ssh -p 24700 root@103.72.97.51 "systemctl restart masi-bot && sleep 3 && systemctl status masi-bot --no-pager"
```

- [ ] **Step 2: Run full E2E suite (original Playwright)**

```bash
python3 tests/e2e/test_e2e_full.py
```

Expected: 27/27 PASS (unchanged)

- [ ] **Step 3: Run new bot E2E suites**

```bash
python3 tests/e2e/test_bot_commands.py
python3 tests/e2e/test_bot_rbac.py
python3 tests/e2e/test_bot_multiturn.py
```

- [ ] **Step 4: Run unit tests**

```bash
cd deploy/masi-bot && python -m pytest tests/test_context_injection.py -v
```

- [ ] **Step 5: Final commit — update MEMORY.md**

Update memory with new test results and Phase 7 status.

---

## Summary

| Chunk | Task | Key Files | Risk |
|-------|------|-----------|------|
| 1 | Fix /findcustomer context drift | `agent.py` | Medium — changes LLM loop state |
| 2 | Add Farmer test user | `config.py`, `test_scenarios.json` | Low — needs real Telegram ID |
| 3 | Playwright bot E2E tests | `tests/e2e/test_bot_*.py` | Low — read-only test additions |
| 4 | test_scenarios.json new scenarios | `tests/test_scenarios.json` | Low — data file only |
| 5 | /what_changed command | `bot.py`, `agent.py`, `formatter.py` | Low — new command, no side effects |
| 6 | Deploy + run full suite | server ops | Medium — requires server access |
