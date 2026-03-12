#!/usr/bin/env python3
"""Masi OS Scheduled Alerts - Direct Odoo XML-RPC + Telegram"""
import sys, json, urllib.request, urllib.parse, xmlrpc.client
from datetime import date, timedelta

BOT_TOKEN = "6449879315:AAHWnvBNYn6SJVJZj-jbvDb4cjafrmntgaI"
CHAT_ID = "2048339435"
ODOO_URL = "http://103.72.97.51:8069"
ODOO_DB = "odoo"
ODOO_USER = "admin"
ODOO_PASS = "admin"


def get_odoo():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models


def sr(models, uid, model, domain, fields=None, limit=0, order=""):
    kw = {}
    if fields:
        kw["fields"] = fields
    if limit:
        kw["limit"] = limit
    if order:
        kw["order"] = order
    return models.execute_kw(ODOO_DB, uid, ODOO_PASS, model, "search_read", [domain], kw)


def sc(models, uid, model, domain):
    return models.execute_kw(ODOO_DB, uid, ODOO_PASS, model, "search_count", [domain])


def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }).encode()
    try:
        req = urllib.request.Request(url, data)
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        print(f"Telegram error: {e}")
        return None


def morning_brief():
    uid, models = get_odoo()
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    stages = sr(models, uid, "crm.stage", [], fields=["name"], limit=20)
    pipeline_lines = []
    for s in stages:
        cnt = sc(models, uid, "crm.lead", [("stage_id", "=", s["id"]), ("active", "=", True)])
        if cnt > 0:
            pipeline_lines.append(f"  {s['name']}: {cnt}")

    so_y = sr(models, uid, "sale.order",
              [("date_order", ">=", yesterday), ("date_order", "<", today),
               ("state", "in", ["sale", "done"])],
              fields=["amount_total"])
    rev_y = sum(s["amount_total"] for s in so_y)

    overdue = sc(models, uid, "account.move",
                 [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                  ("amount_residual", ">", 0), ("invoice_date_due", "<", today)])

    leads_today = sc(models, uid, "crm.lead", [("create_date", ">=", today)])

    lines = ["<b>Báo cáo buổi sáng</b>", "", "<b>Pipeline CRM:</b>"]
    lines.extend(pipeline_lines)
    lines.append("")
    lines.append(f"Doanh thu hôm qua: {rev_y:,.0f} VND")
    lines.append(f"Lead mới hôm nay: {leads_today}")
    lines.append(f"Hóa đơn quá hạn: {overdue}")
    return "\n".join(lines)


def midday_flash():
    uid, models = get_odoo()
    today = date.today().isoformat()

    so = sr(models, uid, "sale.order",
            [("date_order", ">=", today), ("state", "in", ["sale", "done"])],
            fields=["amount_total"])
    rev = sum(s["amount_total"] for s in so)
    leads = sc(models, uid, "crm.lead", [("create_date", ">=", today)])
    overdue = sc(models, uid, "account.move",
                 [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                  ("amount_residual", ">", 0), ("invoice_date_due", "<", today)])

    lines = [
        "<b>Báo cáo giữa ngày</b>", "",
        f"Doanh thu hôm nay: {rev:,.0f} VND",
        f"Đơn hàng: {len(so)}",
        f"Lead mới: {leads}",
        f"Hóa đơn quá hạn: {overdue}",
    ]
    return "\n".join(lines)


def eod_report():
    uid, models = get_odoo()
    today = date.today().isoformat()

    so = sr(models, uid, "sale.order",
            [("date_order", ">=", today), ("state", "in", ["sale", "done"])],
            fields=["amount_total"])
    rev = sum(s["amount_total"] for s in so)
    inv = sr(models, uid, "account.move",
             [("move_type", "=", "out_invoice"), ("invoice_date", ">=", today),
              ("state", "=", "posted")],
             fields=["amount_total"])
    inv_total = sum(i["amount_total"] for i in inv)

    lines = [
        "<b>Báo cáo cuối ngày</b>", "",
        f"Doanh thu: {rev:,.0f} VND ({len(so)} đơn)",
        f"Hóa đơn xuất: {inv_total:,.0f} VND ({len(inv)} hóa đơn)",
    ]
    return "\n".join(lines)


def sla_alert():
    uid, models = get_odoo()
    cutoff = (date.today() - timedelta(hours=48)).isoformat()
    breached = sr(models, uid, "crm.lead",
                  [("type", "=", "opportunity"), ("active", "=", True),
                   ("stage_id.is_won", "=", False), ("create_date", "<", cutoff)],
                  fields=["name", "user_id", "create_date"], limit=5,
                  order="create_date asc")
    if not breached:
        return None
    lines = [f"<b>SLA Alert!</b> {len(breached)} leads vượt 48h", ""]
    for l in breached:
        user = l["user_id"][1] if l["user_id"] else "N/A"
        lines.append(f"- {l['name']} ({user})")
    return "\n".join(lines)


def overdue_ar():
    uid, models = get_odoo()
    today = date.today().isoformat()
    invoices = sr(models, uid, "account.move",
                  [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                   ("amount_residual", ">", 0), ("invoice_date_due", "<", today)],
                  fields=["partner_id", "amount_residual", "invoice_date_due"],
                  limit=10, order="amount_residual desc")
    if not invoices:
        return None
    total = sum(i["amount_residual"] for i in invoices)
    lines = [f"<b>Công nợ quá hạn</b> - Tổng: {total:,.0f} VND", ""]
    for i in invoices[:5]:
        partner = i["partner_id"][1] if i["partner_id"] else "N/A"
        days = (date.today() - date.fromisoformat(str(i["invoice_date_due"])[:10])).days
        lines.append(f"- {partner}: {i['amount_residual']:,.0f} VND ({days} ngày)")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: alert_runner.py [morning|midday|eod|sla|ar]")
        sys.exit(1)

    handlers = {
        "morning": morning_brief,
        "midday": midday_flash,
        "eod": eod_report,
        "sla": sla_alert,
        "ar": overdue_ar,
    }

    handler = handlers.get(sys.argv[1])
    if not handler:
        print(f"Unknown: {sys.argv[1]}")
        sys.exit(1)

    msg = handler()
    if msg:
        result = send_telegram(msg)
        print(f"Sent {sys.argv[1]}: {result}")
    else:
        print(f"No alert needed for {sys.argv[1]}")
