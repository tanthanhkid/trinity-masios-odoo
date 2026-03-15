"""
E2E tests for Masi Bot RBAC enforcement via test_server REST API.

Permission matrix per MASI-OS-Telegram-Command-Center-Spec-v1.1:
  CEO (*):           all commands
  Hunter Lead:       hunter_*, doanhso_homnay, brief_hunter, task_quahan,
                     kpi, pipeline, newlead, newcustomer, quote, credit, findcustomer
  Farmer Lead:       farmer_*, congno_quahan, brief_ar, brief_farmer, task_quahan,
                     kpi, pipeline, newcustomer, credit, findcustomer
  Finance:           congno_denhan, congno_quahan, brief_ar, brief_cash, farmer_ar,
                     task_quahan, kpi, invoice, credit, findcustomer
  Ops/PM:            task_quahan, midday, eod, doanhso_homnay, kpi, pipeline
  Admin/Tech:        ceo_alert, kpi, pipeline

Run: python3 tests/e2e/test_bot_rbac.py
Prerequisites: masi-bot test_server running at http://103.72.97.51:8300
"""
import sys, os, json, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

API_BASE = os.environ.get("TEST_API_BASE", "http://103.72.97.51:8300")
TEST_API_TOKEN = os.environ.get("TEST_API_TOKEN", "")
CEO_USER_ID    = 2048339435  # CEO — all commands
HUNTER_USER_ID = 1481072032  # Hunter Lead
FARMER_USER_ID = 5001000001  # Farmer Lead


def api_post(endpoint, payload, timeout=8):
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if TEST_API_TOKEN:
        headers["Authorization"] = f"Bearer {TEST_API_TOKEN}"
    req = urllib.request.Request(f"{API_BASE}{endpoint}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def clear(uid): api_post("/api/clear", {"user_id": uid})
def chat(uid, msg, timeout=8): return api_post("/api/chat", {"user_id": uid, "message": msg}, timeout=timeout)
def is_blocked(text): return any(k in text.lower() for k in ["🚫", "không có quyền", "permission", "access denied"])
def has_content(text): return len(text.strip()) > 20 and not is_blocked(text)


# (label, command, allowed_uid, blocked_uid)
RBAC_TESTS = [
    # --- CEO-only commands ---
    ("morning_brief: CEO allowed",     "/morning_brief",  CEO_USER_ID,    None),
    ("morning_brief: Hunter blocked",  "/morning_brief",  None,           HUNTER_USER_ID),
    ("morning_brief: Farmer blocked",  "/morning_brief",  None,           FARMER_USER_ID),

    # --- CEO + Admin only (ceo_alert) ---
    ("ceo_alert: CEO allowed",         "/ceo_alert",      CEO_USER_ID,    None),
    ("ceo_alert: Hunter blocked",      "/ceo_alert",      None,           HUNTER_USER_ID),
    ("ceo_alert: Farmer blocked",      "/ceo_alert",      None,           FARMER_USER_ID),

    # --- Hunter-only ---
    ("brief_hunter: Hunter allowed",   "/brief_hunter",   HUNTER_USER_ID, None),
    ("hunter_today: Hunter allowed",   "/hunter_today",   HUNTER_USER_ID, None),
    ("hunter_sla: Hunter allowed",     "/hunter_sla",     HUNTER_USER_ID, None),
    ("farmer_today: Hunter blocked",   "/farmer_today",   None,           HUNTER_USER_ID),

    # --- Farmer-only ---
    ("brief_farmer: Farmer allowed",   "/brief_farmer",   FARMER_USER_ID, None),
    ("farmer_today: Farmer allowed",   "/farmer_today",   FARMER_USER_ID, None),
    ("farmer_reorder: Farmer allowed", "/farmer_reorder", FARMER_USER_ID, None),
    ("congno_quahan: Farmer allowed",  "/congno_quahan",  FARMER_USER_ID, None),
    ("congno_denhan: Farmer blocked",  "/congno_denhan",  None,           FARMER_USER_ID),
    ("brief_hunter: Farmer blocked",   "/brief_hunter",   None,           FARMER_USER_ID),

    # --- Finance-only ---
    ("brief_cash: Hunter blocked",     "/brief_cash",     CEO_USER_ID,    HUNTER_USER_ID),
    ("congno_denhan: Hunter blocked",  "/congno_denhan",  CEO_USER_ID,    HUNTER_USER_ID),

    # --- Midday/EOD: Ops/PM + CEO, not Hunter/Farmer ---
    ("midday: Hunter blocked",         "/midday",         CEO_USER_ID,    HUNTER_USER_ID),
    ("eod: Hunter blocked",            "/eod",            CEO_USER_ID,    HUNTER_USER_ID),

    # --- task_quahan: all roles ---
    ("task_quahan: Hunter allowed",    "/task_quahan",    HUNTER_USER_ID, None),
    ("task_quahan: Farmer allowed",    "/task_quahan",    FARMER_USER_ID, None),
    ("task_quahan: CEO allowed",       "/task_quahan",    CEO_USER_ID,    None),
]


def main():
    print(f"\n{'='*65}")
    print("Masi Bot E2E: RBAC Enforcement (per Spec v1.1)")
    print(f"API: {API_BASE}")
    print(f"{'='*65}\n")

    try:
        with urllib.request.urlopen(f"{API_BASE}/api/health", timeout=5):
            pass
    except Exception as e:
        print(f"❌ Cannot reach test server: {e}")
        sys.exit(1)

    passed = total = 0

    for label, cmd, allowed_uid, blocked_uid in RBAC_TESTS:
        # Test: allowed user gets content
        if allowed_uid:
            clear(allowed_uid)
            resp = chat(allowed_uid, cmd)
            rt = resp.get("response", "")
            ok = has_content(rt)
            status = "✅" if ok else "❌"
            print(f"  {status} ALLOW  {label:<45} {'OK' if ok else f'WRONG: {rt[:50]}'}")
            passed += ok; total += 1
            time.sleep(0.2)

        # Test: blocked user gets denial
        if blocked_uid:
            clear(blocked_uid)
            resp = chat(blocked_uid, cmd, timeout=6)
            rt = resp.get("response", "")
            ok = is_blocked(rt)
            status = "✅" if ok else "❌"
            print(f"  {status} BLOCK  {label:<45} {'DENIED OK' if ok else f'WRONG (got content): {rt[:50]}'}")
            passed += ok; total += 1
            time.sleep(0.2)

    print(f"\n{'='*65}")
    print(f"RESULT: {passed}/{total} PASS")
    print(f"{'='*65}\n")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
