#!/usr/bin/env python3
"""
Quick test: Does Gemini 3.1 Flash Lite hallucinate on approve/reject commands?
Uses OpenRouter API (OpenAI-compatible) with the same tools as masi-bot.
"""

import json
import urllib.request
import sys

API_KEY = "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"
MODEL = "google/gemini-3.1-flash-lite-preview"
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Subset of MCP tools relevant to approval flow
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "odoo_approve_credit",
            "description": "Approve a credit approval request. Auto-confirms the sale order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "integer", "description": "ID of the credit.approval.request record"},
                    "approved_by": {"type": "string", "description": "Name of person approving", "default": "CEO"},
                },
                "required": ["request_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "odoo_reject_credit",
            "description": "Reject a credit approval request. Sale order stays in draft.",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "integer", "description": "ID of the credit.approval.request record"},
                    "reason": {"type": "string", "description": "Reason for rejection"},
                    "rejected_by": {"type": "string", "description": "Name of person rejecting", "default": "CEO"},
                },
                "required": ["request_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "odoo_pending_approvals",
            "description": "List pending credit approval requests waiting for CEO decision.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "odoo_approval_history",
            "description": "View credit approval history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "Filter: pending, approved, rejected"},
                    "limit": {"type": "integer", "description": "Max records", "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "odoo_search_read",
            "description": "Search and read records from any Odoo model.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string"},
                    "domain": {"type": "string", "default": "[]"},
                    "fields": {"type": "string", "default": ""},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["model"],
            },
        },
    },
]

SYSTEM = """Bạn là trợ lý AI của Masi OS, kết nối Odoo 18.
Trả lời tiếng Việt. Gọi tool ngay khi có thể, KHÔNG bịa số liệu.
Khi user yêu cầu duyệt/từ chối phê duyệt → GỌI TOOL tương ứng NGAY, không hỏi lại.
Telegram user ID: 2048339435"""

TESTS = [
    {
        "name": "Approve request #3",
        "message": "/approve 3",
        "expect_tool": "odoo_approve_credit",
    },
    {
        "name": "Reject request #5 with reason",
        "message": "Từ chối yêu cầu phê duyệt #5, lý do: khách nợ quá nhiều",
        "expect_tool": "odoo_reject_credit",
    },
    {
        "name": "Natural approve command",
        "message": "duyệt yêu cầu phê duyệt số 10",
        "expect_tool": "odoo_approve_credit",
    },
]


def call_openrouter(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "max_tokens": 1024,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"  HTTP {e.code}: {body[:300]}")
        return None


def run_test(test):
    print(f"\nTEST: {test['name']}")
    print(f"  Input: {test['message']}")

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": test["message"]},
    ]

    result = call_openrouter(messages)
    if not result:
        print("  FAIL: API error")
        return False

    choice = result.get("choices", [{}])[0]
    message = choice.get("message", {})
    tool_calls = message.get("tool_calls", [])
    content = message.get("content", "")
    finish = choice.get("finish_reason", "")

    if tool_calls:
        names = [tc["function"]["name"] for tc in tool_calls]
        args = [tc["function"].get("arguments", "") for tc in tool_calls]
        print(f"  Tools called: {names}")
        print(f"  Args: {args}")
        if test["expect_tool"] in names:
            print(f"  PASS ✅ — called {test['expect_tool']}")
            return True
        else:
            print(f"  FAIL ❌ — expected {test['expect_tool']}, got {names}")
            return False
    else:
        print(f"  Response (no tools): {content[:200]}")
        print(f"  finish_reason: {finish}")
        print(f"  FAIL ❌ — HALLUCINATED (no tool call)")
        return False


def main():
    print("=" * 50)
    print(f"Hallucination Test — {MODEL}")
    print("=" * 50)

    passed = 0
    failed = 0

    for test in TESTS:
        if run_test(test):
            passed += 1
        else:
            failed += 1

    # Token usage
    print(f"\n{'=' * 50}")
    print(f"RESULTS: {passed} PASS, {failed} FAIL / {len(TESTS)} total")
    print("=" * 50)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
