"""
E2E tests for Masi Bot critical multi-turn conversation flows.

Run: python3 tests/e2e/test_bot_multiturn.py
"""
import sys, os, json, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

API_BASE = "http://103.72.97.51:8300"
CEO_USER_ID = 2048339435

def api_post(endpoint, payload, timeout=60):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{API_BASE}{endpoint}", data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def clear():
    api_post("/api/clear", {"user_id": CEO_USER_ID})

def chat(msg, timeout=60):
    return api_post("/api/chat", {"user_id": CEO_USER_ID, "message": msg}, timeout=timeout)

def contains_any(text, keywords):
    tl = text.lower()
    return any(k.lower() in tl for k in keywords)

def contains_none(text, bad_patterns):
    tl = text.lower()
    return not any(p.lower() in tl for p in bad_patterns)

def run_test(name, steps_checks):
    """steps_checks: list of (message, must_contain_any, must_not_contain)"""
    clear()
    print(f"\n  [{name}]")
    for i, (msg, must_have, must_not) in enumerate(steps_checks):
        resp = chat(msg)
        rt = resp.get("response", "")
        preview = rt[:70].replace("\n", " ")
        print(f"    T{i+1}: '{msg[:40]}' -> '{preview}'")
        if resp.get("error") and not rt:
            print(f"         ❌ API error: {resp['error']}")
            return False
        if must_have and not contains_any(rt, must_have):
            print(f"         ❌ Missing any of {must_have[:3]}")
            return False
        if must_not and not contains_none(rt, must_not):
            for p in must_not:
                if p.lower() in rt.lower():
                    print(f"         ❌ Bad pattern found: '{p}'")
            return False
    return True


MULTI_TURN_TESTS = [
    ("quote_bare_number", [
        ("/quote",  ["so", "sale order", "số", "cho biết", "quote"], []),
        ("1",       ["sale order", "s0", "so#", "order", "customer", "khách", "amount"],
                    ["bạn muốn xem", "không rõ", "lệnh không"]),
    ]),
    ("invoice_bare_number", [
        ("/invoice", ["invoice", "hóa đơn", "số", "cho biết"], []),
        ("2",        ["invoice", "hóa đơn", "tổng", "customer", "khách", "amount", "không tìm"],
                     ["bạn muốn xem", "không rõ"]),
    ]),
    ("findcustomer_drilldown_no_bad_search", [
        ("/findcustomer", ["tên", "khách", "cho biết", "search"], []),
        ("ABC",           ["abc", "khách", "tìm", "partner", "customer", "không tìm"], []),
        # Critical: "lịch sử đơn hàng?" must NOT trigger search for customer named that phrase
        ("lịch sử đơn hàng?",
         ["đơn hàng", "order", "lịch sử", "không có", "purchase", "sale", "mua"],
         ["lịch sử đơn hàng", "tìm thấy khách"]),  # Should NOT search for customer named "lịch sử"
    ]),
    ("ok_guard_no_report", [
        ("/kpi",       ["kpi", "pipeline", "doanh thu"], []),
        ("ok cảm ơn", ["cảm ơn", "dạ", "👍", "nếu cần", "vâng", "ok"],
                      ["hunter", "farmer", "pipeline", "kpi", "doanh thu"]),  # No new report
    ]),
    ("morning_brief_drilldown", [
        ("/morning_brief", ["hunter", "farmer"], []),
        ("hunter hôm nay thế nào?", ["hunter", "lead", "sla", "hôm nay"], []),
    ]),
]

def main():
    print(f"\n{'='*65}")
    print("Masi Bot E2E: Critical Multi-Turn Flows")
    print(f"API: {API_BASE}")
    print(f"{'='*65}")

    try:
        with urllib.request.urlopen(f"{API_BASE}/api/health", timeout=5):
            pass
    except Exception as e:
        print(f"❌ Cannot reach test server: {e}")
        sys.exit(1)

    results = []
    for name, steps in MULTI_TURN_TESTS:
        ok = run_test(name, steps)
        results.append((name, ok))
        print(f"\n  {'✅ PASS' if ok else '❌ FAIL'}  {name}")
        time.sleep(1)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{'='*65}")
    print(f"RESULT: {passed}/{total} PASS")
    print(f"{'='*65}\n")
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
