#!/usr/bin/env python3
"""Decode base64 PDF from MCP tool output and send via Telegram Bot API.

Usage:
    mcporter call odoo.odoo_sale_order_pdf order_id=5 > /tmp/pdf_result.json 2>/dev/null
    python3 send_pdf.py CHAT_ID < /tmp/pdf_result.json
    rm -f /tmp/pdf_result.json

If CHAT_ID is omitted, just saves the PDF to /tmp/ without sending.
Requires TELEGRAM_BOT_TOKEN env var for sending.
"""
import sys, json, base64, subprocess, os

data = json.load(sys.stdin)
pdf = base64.b64decode(data["pdf_base64"])
filename = data["filename"]
filepath = f"/tmp/{filename}"

with open(filepath, "wb") as f:
    f.write(pdf)
print(f"Saved: {filepath} ({len(pdf)} bytes)")

if len(sys.argv) > 1:
    chat_id = sys.argv[1]
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    order_or_inv = data.get("order", data.get("invoice", ""))
    partner = data.get("partner", "")
    amount = data.get("amount_total", 0)
    caption = f"\U0001f4c4 {order_or_inv} - {partner} ({amount:,.0f} VND)"
    result = subprocess.run([
        "curl", "-s", "-F", f"chat_id={chat_id}",
        "-F", f"document=@{filepath}",
        "-F", f"caption={caption}",
        f"https://api.telegram.org/bot{token}/sendDocument"
    ], capture_output=True, text=True)
    try:
        resp = json.loads(result.stdout)
        if resp.get("ok"):
            print(f"Telegram: OK (message_id: {resp['result']['message_id']})")
        else:
            print(f"Telegram: FAILED - {resp}")
    except json.JSONDecodeError:
        print(f"Telegram: ERROR - {result.stdout[:200]}", file=sys.stderr)
    os.remove(filepath)
