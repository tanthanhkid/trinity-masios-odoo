"""
E2E tests for Masi Bot RBAC enforcement via test_server REST API.

Role permissions are defined in masios.telegram_role records in Odoo:
  CEO (2048339435):       all commands (*)
  Hunter Lead (1481072032): morning_brief, ceo_alert, hunter_*, khachmoi_homnay,
                            doanhso_homnay, brief_hunter, kpi, pipeline, newlead,
                            newcustomer, quote, credit, findcustomer, midday, eod
  Hunter Lead NOT allowed: farmer_today, congno_denhan, congno_quahan, brief_cash,
                            brief_ar, farmer_ar, brief_farmer, task_quahan

Run: python3 tests/e2e/test_bot_rbac.py
"""
import sys, os, json, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

API_BASE = "http://103.72.97.51:8300"
CEO_USER_ID = 2048339435
HUNTER_USER_ID = 1481072032

def api_post(endpoint, payload, timeout=8):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{API_BASE}{endpoint}", data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def clear(uid):
    api_post("/api/clear", {"user_id": uid})

def chat(uid, msg, timeout=8):
    return api_post("/api/chat", {"user_id": uid, "message": msg}, timeout=timeout)

def blocked(text):
    return any(k in text.lower() for k in ["🚫", "không có quyền", "permission", "access denied"])

def has_content(text):
    return len(text.strip()) > 20 and not blocked(text)

RBAC_TESTS = [
    # (label, cmd, allowed_uid, blocked_uid)
    # morning_brief and ceo_alert are allowed for BOTH CEO and Hunter Lead (per Odoo role config)
    ("morning_brief CEO-ok",    "/morning_brief",   CEO_USER_ID,    None),
    ("morning_brief hunter-ok", "/morning_brief",   HUNTER_USER_ID, None),
    ("ceo_alert CEO-ok",        "/ceo_alert",        CEO_USER_ID,    None),
    ("ceo_alert hunter-ok",     "/ceo_alert",        HUNTER_USER_ID, None),
    # farmer_today: CEO allowed, Hunter blocked
    ("farmer_today not-hunter", "/farmer_today",     CEO_USER_ID,    HUNTER_USER_ID),
    # congno_denhan: CEO allowed, Hunter blocked
    ("congno_denhan not-hunter","/congno_denhan",    CEO_USER_ID,    HUNTER_USER_ID),
    # brief_cash: CEO allowed, Hunter blocked
    ("brief_cash not-hunter",   "/brief_cash",       CEO_USER_ID,    HUNTER_USER_ID),
    # hunter_today and hunter_sla: Hunter allowed
    ("hunter_today hunter-ok",  "/hunter_today",     HUNTER_USER_ID, None),
    ("hunter_sla hunter-ok",    "/hunter_sla",       HUNTER_USER_ID, None),
]

def main():
    print(f"\n{'='*65}")
    print("Masi Bot E2E: RBAC Enforcement")
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
        # allowed user should get content
        clear(allowed_uid)
        resp = chat(allowed_uid, cmd)
        rt = resp.get("response", "")
        ok_allowed = has_content(rt)
        status = "✅" if ok_allowed else "❌"
        print(f"  {status} ALLOWED  {cmd:<28} user={allowed_uid} {'OK' if ok_allowed else 'BLOCKED (WRONG)'}")
        passed += ok_allowed; total += 1

        # blocked user should get denial
        if blocked_uid:
            clear(blocked_uid)
            resp = chat(blocked_uid, cmd, timeout=6)
            rt = resp.get("response", "")
            ok_blocked = blocked(rt)
            status = "✅" if ok_blocked else "❌"
            print(f"  {status} BLOCKED  {cmd:<28} user={blocked_uid} {'DENIED (correct)' if ok_blocked else 'GOT CONTENT (wrong)'}")
            if not ok_blocked:
                print(f"           Response: {rt[:80]}")
            passed += ok_blocked; total += 1

        time.sleep(0.3)

    print(f"\n{'='*65}")
    print(f"RESULT: {passed}/{total} PASS")
    print(f"{'='*65}\n")
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
