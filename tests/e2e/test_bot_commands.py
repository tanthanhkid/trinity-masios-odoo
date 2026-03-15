"""
E2E tests for Masi Bot slash commands via test_server REST API.
Tests all 27 fast-path commands for CEO role.

Run: python3 tests/e2e/test_bot_commands.py
Prerequisites: masi-bot test_server running at http://103.72.97.51:8300
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import urllib.request
import urllib.error
from dataclasses import dataclass

API_BASE = os.environ.get("TEST_API_BASE", "http://103.72.97.51:8300")
TEST_API_TOKEN = os.environ.get("TEST_API_TOKEN", "")
CEO_USER_ID = 2048339435
TIMEOUT = 8

@dataclass
class BotTestResult:
    command: str
    passed: bool
    elapsed_ms: int
    response_preview: str = ""
    error: str = ""

def api_post(endpoint: str, payload: dict, timeout: int = TIMEOUT) -> dict:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if TEST_API_TOKEN:
        headers["Authorization"] = f"Bearer {TEST_API_TOKEN}"
    req = urllib.request.Request(
        f"{API_BASE}{endpoint}", data=data, headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}

def clear_history(user_id: int):
    api_post("/api/clear", {"user_id": user_id})

FAST_PATH_COMMANDS = [
    ("/morning_brief",       ["hunter", "farmer", "brief", "công nợ"]),
    ("/ceo_alert",           ["alert", "cảnh báo", "⚠️", "✅", "không có"]),
    ("/doanhso_homnay",      ["doanh thu", "hôm nay", "hunter", "farmer", "revenue"]),
    ("/brief_hunter",        ["hunter", "lead", "sla", "quote"]),
    ("/brief_farmer",        ["farmer", "reorder", "sleeping", "vip"]),
    ("/brief_ar",            ["công nợ", "ar", "overdue", "quá hạn", "aging"]),
    ("/brief_cash",          ["cash", "tiền", "thu", "expected", "collected"]),
    ("/hunter_today",        ["hunter", "lead", "hôm nay", "sla"]),
    ("/hunter_sla",          ["sla", "breach", "giờ", "lead", "chưa"]),
    ("/hunter_quotes",       ["quote", "báo giá", "so ", "ngày"]),
    ("/hunter_first_orders", ["đơn đầu", "first", "order", "chuyển đổi"]),
    ("/hunter_sources",      ["source", "nguồn", "lead"]),
    ("/khachmoi_homnay",     ["khách mới", "hôm nay", "overview", "new", "khách"]),
    ("/farmer_today",        ["farmer", "reorder", "sleeping", "vip"]),
    ("/farmer_reorder",      ["reorder", "expected", "ngày", "dự kiến"]),
    ("/farmer_sleeping",     ["sleeping", "ngày", "nhóm", "30"]),
    ("/farmer_vip",          ["vip", "risk", "customer", "khách"]),
    ("/farmer_ar",           ["ar", "công nợ", "farmer", "aging"]),
    ("/farmer_retention",    ["retention", "repeat", "rate", "khách"]),
    ("/congno_denhan",       ["công nợ", "đến hạn", "ngày", "invoice"]),
    ("/congno_quahan",       ["quá hạn", "overdue", "công nợ", "ngày"]),
    ("/task_quahan",         ["task", "overdue", "quá hạn", "ngày"]),
    ("/midday",              ["midday", "flash", "doanh thu", "hôm nay"]),
    ("/eod",                 ["eod", "flash", "doanh thu", "hôm nay"]),
    ("/kpi",                 ["kpi", "pipeline", "doanh thu", "leads"]),
    ("/pipeline",            ["pipeline", "stage", "giá trị", "lead"]),
    ("/credit",              ["credit", "hạn mức", "công nợ", "khách"]),
]

def run_command_test(command: str, expect_any: list) -> BotTestResult:
    clear_history(CEO_USER_ID)
    t0 = time.time()
    resp = api_post("/api/chat", {"user_id": CEO_USER_ID, "message": command}, timeout=TIMEOUT)
    elapsed = int((time.time() - t0) * 1000)

    if "error" in resp and "response" not in resp:
        return BotTestResult(command, False, elapsed, error=resp["error"])

    response_text = resp.get("response", "")
    preview = response_text[:100].replace("\n", " ")

    rl = response_text.lower()
    if not any(kw.lower() in rl for kw in expect_any):
        return BotTestResult(command, False, elapsed, response_preview=preview,
                             error=f"None of {expect_any[:3]} found")

    return BotTestResult(command, True, elapsed, response_preview=preview)


def main():
    print(f"\n{'='*65}")
    print("Masi Bot E2E: Fast-Path Commands (CEO role)")
    print(f"API: {API_BASE}")
    print(f"{'='*65}\n")

    try:
        with urllib.request.urlopen(f"{API_BASE}/api/health", timeout=5) as r:
            health = json.loads(r.read())
            print(f"Server health: {health}\n")
    except Exception as e:
        print(f"❌ Cannot reach test server at {API_BASE}: {e}")
        print("   Start test_server first: cd deploy/masi-bot && python test_server.py")
        sys.exit(1)

    results = []
    for command, expect_any in FAST_PATH_COMMANDS:
        print(f"  {command:<30}", end="", flush=True)
        r = run_command_test(command, expect_any)
        status = "✅" if r.passed else "❌"
        print(f"{status}  {r.elapsed_ms:>5}ms  {r.response_preview[:55]}")
        if not r.passed:
            print(f"         Error: {r.error}")
        results.append(r)
        time.sleep(0.2)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n{'='*65}")
    print(f"RESULT: {passed}/{total} PASS")
    print(f"{'='*65}\n")
    if passed < total:
        print("FAILED:")
        for r in results:
            if not r.passed:
                print(f"  {r.command}: {r.error}")
        sys.exit(1)

if __name__ == "__main__":
    main()
