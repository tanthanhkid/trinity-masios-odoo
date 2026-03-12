#!/usr/bin/env python3
"""
Masi OS Scheduled Alerts - Direct Odoo XML-RPC + Telegram

Alert Codes (spec 7.2):
  H02: Lead chưa chạm sau 4 giờ
  H03: Lead quá SLA 24 giờ
  H05: Quote treo > 3 ngày
  F01: Khách sắp reorder
  F02: Khách quá chu kỳ reorder
  F03: VIP chưa được chạm >10 ngày
  A01: Công nợ đến hạn 7 ngày
  A03: Công nợ rủi ro cao >60 ngày
  A04: Công nợ > 30 ngày
  T03: Task trọng yếu quá hạn
  S03: Workflow lõi gãy

Usage: alert_runner.py [morning|midday|eod|sla|ar|alerts]
"""
import sys
import json
import urllib.request
import urllib.parse
import xmlrpc.client
from datetime import date, datetime, timedelta

# ─── Configuration ───────────────────────────────────────────────────────────

BOT_TOKEN = "6449879315:AAHWnvBNYn6SJVJZj-jbvDb4cjafrmntgaI"
ODOO_URL = "http://103.72.97.51:8069"
ODOO_DB = "odoo"
ODOO_USER = "admin"
ODOO_PASS = "admin"

# ─── Multi-recipient routing ─────────────────────────────────────────────────

RECIPIENTS = {
    "ceo": "2048339435",
    "hunter_lead": "2048339435",   # same person for now
    "farmer_lead": "2048339435",
    "finance": "2048339435",
    "finance_lead": "2048339435",
    "ops": "2048339435",
    "admin_tech": "2048339435",
    # When more users added, update these
}

# ─── Severity indicators ─────────────────────────────────────────────────────

SEV_YELLOW = "\U0001f7e1"   # 🟡 Vàng (Warning)
SEV_ORANGE = "\U0001f7e0"   # 🟠 Cam (Action needed)
SEV_RED = "\U0001f534"      # 🔴 Đỏ (Critical)

# ─── Alert definitions ───────────────────────────────────────────────────────

ALERT_DEFS = {
    "H02": {
        "severity": SEV_YELLOW,
        "label": "Lead chưa chạm sau 4 giờ",
        "recipients": ["hunter_lead"],
        "escalate_ceo": False,
    },
    "H03": {
        "severity": SEV_ORANGE,
        "label": "Lead quá SLA 24 giờ",
        "recipients": ["hunter_lead"],
        "escalate_ceo": "hot_lead",  # escalate when lead is hot
    },
    "H05": {
        "severity": SEV_ORANGE,
        "label": "Báo giá treo > 3 ngày",
        "recipients": ["hunter_lead"],
        "escalate_ceo": False,
    },
    "F01": {
        "severity": SEV_YELLOW,
        "label": "Khách sắp reorder",
        "recipients": ["farmer_lead"],
        "escalate_ceo": "vip",  # escalate when VIP
    },
    "F02": {
        "severity": SEV_ORANGE,
        "label": "Khách quá chu kỳ reorder",
        "recipients": ["farmer_lead"],
        "escalate_ceo": False,
    },
    "F03": {
        "severity": SEV_RED,
        "label": "VIP chưa được chạm >10 ngày",
        "recipients": ["farmer_lead"],
        "escalate_ceo": True,  # always CEO
    },
    "A01": {
        "severity": SEV_YELLOW,
        "label": "Công nợ đến hạn 7 ngày",
        "recipients": ["finance", "farmer_lead"],
        "escalate_ceo": False,
    },
    "A03": {
        "severity": SEV_RED,
        "label": "Công nợ rủi ro cao >60 ngày",
        "recipients": ["finance_lead", "farmer_lead"],
        "escalate_ceo": True,  # always CEO
    },
    "A04": {
        "severity": SEV_RED,
        "label": "Công nợ > 30 ngày",
        "recipients": ["finance_lead"],
        "escalate_ceo": True,  # always CEO
    },
    "T03": {
        "severity": SEV_RED,
        "label": "Task trọng yếu quá hạn",
        "recipients": ["ops"],
        "escalate_ceo": True,  # escalate CEO
    },
    "S03": {
        "severity": SEV_RED,
        "label": "Workflow lõi gãy",
        "recipients": ["admin_tech", "ops"],
        "escalate_ceo": True,  # always CEO
    },
}

# ─── Odoo helpers ─────────────────────────────────────────────────────────────


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
    return models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, model, "search_read", [domain], kw
    )


def sc(models, uid, model, domain):
    return models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, model, "search_count", [domain]
    )


# ─── Telegram helpers ────────────────────────────────────────────────────────


def send_telegram(text, chat_id=None):
    """Gửi tin nhắn Telegram tới một chat_id cụ thể."""
    if chat_id is None:
        chat_id = RECIPIENTS["ceo"]
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode()
    try:
        req = urllib.request.Request(url, data)
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        print(f"Lỗi Telegram (chat_id={chat_id}): {e}")
        return None


def route_alert(code, message, escalate=False):
    """Gửi cảnh báo tới đúng người nhận theo định nghĩa routing."""
    defn = ALERT_DEFS.get(code, {})
    severity = defn.get("severity", SEV_YELLOW)
    label = defn.get("label", code)
    recipients = defn.get("recipients", [])
    escalate_ceo = defn.get("escalate_ceo", False)

    header = f"{severity} <b>[{code}] {label}</b>\n\n"
    full_msg = header + message

    # Collect unique chat_ids to avoid duplicate sends
    sent_ids = set()
    results = []

    for role in recipients:
        cid = RECIPIENTS.get(role)
        if cid and cid not in sent_ids:
            sent_ids.add(cid)
            r = send_telegram(full_msg, chat_id=cid)
            results.append((role, r))

    # CEO escalation
    should_escalate = (
        escalate_ceo is True
        or (escalate_ceo and escalate)
    )
    if should_escalate:
        ceo_id = RECIPIENTS["ceo"]
        if ceo_id not in sent_ids:
            sent_ids.add(ceo_id)
            r = send_telegram(full_msg, chat_id=ceo_id)
            results.append(("ceo", r))

    return results


# ─── Existing alert functions (enhanced) ──────────────────────────────────────


def morning_brief():
    uid, models = get_odoo()
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    stages = sr(models, uid, "crm.stage", [], fields=["name"], limit=20)
    pipeline_lines = []
    for s in stages:
        cnt = sc(
            models, uid, "crm.lead",
            [("stage_id", "=", s["id"]), ("active", "=", True)],
        )
        if cnt > 0:
            pipeline_lines.append(f"  {s['name']}: {cnt}")

    so_y = sr(
        models, uid, "sale.order",
        [
            ("date_order", ">=", yesterday),
            ("date_order", "<", today),
            ("state", "in", ["sale", "done"]),
        ],
        fields=["amount_total"],
    )
    rev_y = sum(s["amount_total"] for s in so_y)

    overdue = sc(
        models, uid, "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("invoice_date_due", "<", today),
        ],
    )

    leads_today = sc(models, uid, "crm.lead", [("create_date", ">=", today)])

    # Count untouched leads (H02/H03 preview)
    cutoff_4h = (datetime.now() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
    untouched_4h = sc(
        models, uid, "crm.lead",
        [
            ("create_date", "<", cutoff_4h),
            ("activity_date_deadline", "=", False),
            ("active", "=", True),
            ("type", "=", "lead"),
        ],
    )

    lines = [
        f"{SEV_YELLOW} <b>Báo cáo buổi sáng — {date.today().strftime('%d/%m/%Y')}</b>",
        "",
        "<b>Pipeline CRM:</b>",
    ]
    lines.extend(pipeline_lines)
    lines.append("")
    lines.append(f"Doanh thu hôm qua: {rev_y:,.0f} VNĐ")
    lines.append(f"Lead mới hôm nay: {leads_today}")
    lines.append(f"Hóa đơn quá hạn: {overdue}")
    if untouched_4h > 0:
        lines.append(f"⚠️ Lead chưa chạm >4h: {untouched_4h}")
    return "\n".join(lines)


def midday_flash():
    uid, models = get_odoo()
    today = date.today().isoformat()

    so = sr(
        models, uid, "sale.order",
        [("date_order", ">=", today), ("state", "in", ["sale", "done"])],
        fields=["amount_total"],
    )
    rev = sum(s["amount_total"] for s in so)
    leads = sc(models, uid, "crm.lead", [("create_date", ">=", today)])
    overdue = sc(
        models, uid, "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("invoice_date_due", "<", today),
        ],
    )

    # Draft quotes count
    draft_quotes = sc(
        models, uid, "sale.order",
        [("state", "=", "draft"), ("create_date", ">=", today)],
    )

    lines = [
        f"{SEV_YELLOW} <b>Báo cáo giữa ngày — {date.today().strftime('%d/%m/%Y')}</b>",
        "",
        f"Doanh thu hôm nay: {rev:,.0f} VNĐ",
        f"Đơn hàng xác nhận: {len(so)}",
        f"Báo giá nháp: {draft_quotes}",
        f"Lead mới: {leads}",
        f"Hóa đơn quá hạn: {overdue}",
    ]
    return "\n".join(lines)


def eod_report():
    uid, models = get_odoo()
    today = date.today().isoformat()

    so = sr(
        models, uid, "sale.order",
        [("date_order", ">=", today), ("state", "in", ["sale", "done"])],
        fields=["amount_total"],
    )
    rev = sum(s["amount_total"] for s in so)
    inv = sr(
        models, uid, "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("invoice_date", ">=", today),
            ("state", "=", "posted"),
        ],
        fields=["amount_total"],
    )
    inv_total = sum(i["amount_total"] for i in inv)

    # Leads created/won today
    leads_created = sc(models, uid, "crm.lead", [("create_date", ">=", today)])
    leads_won = sc(
        models, uid, "crm.lead",
        [("date_closed", ">=", today), ("stage_id.is_won", "=", True)],
    )

    lines = [
        f"{SEV_YELLOW} <b>Báo cáo cuối ngày — {date.today().strftime('%d/%m/%Y')}</b>",
        "",
        f"Doanh thu: {rev:,.0f} VNĐ ({len(so)} đơn)",
        f"Hóa đơn xuất: {inv_total:,.0f} VNĐ ({len(inv)} hóa đơn)",
        f"Lead mới: {leads_created}",
        f"Lead thắng: {leads_won}",
    ]
    return "\n".join(lines)


def sla_alert():
    uid, models = get_odoo()
    cutoff = (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
    breached = sr(
        models, uid, "crm.lead",
        [
            ("type", "=", "opportunity"),
            ("active", "=", True),
            ("stage_id.is_won", "=", False),
            ("create_date", "<", cutoff),
        ],
        fields=["name", "user_id", "create_date"],
        limit=10,
        order="create_date asc",
    )
    if not breached:
        return None
    lines = [
        f"{SEV_ORANGE} <b>Cảnh báo SLA!</b> {len(breached)} lead vượt 48 giờ",
        "",
    ]
    for lead in breached:
        user = lead["user_id"][1] if lead["user_id"] else "Chưa gán"
        lines.append(f"• {lead['name']} ({user})")
    return "\n".join(lines)


def overdue_ar():
    uid, models = get_odoo()
    today = date.today().isoformat()
    invoices = sr(
        models, uid, "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("invoice_date_due", "<", today),
        ],
        fields=["partner_id", "amount_residual", "invoice_date_due"],
        limit=10,
        order="amount_residual desc",
    )
    if not invoices:
        return None
    total = sum(i["amount_residual"] for i in invoices)
    lines = [
        f"{SEV_ORANGE} <b>Công nợ quá hạn</b> — Tổng: {total:,.0f} VNĐ",
        "",
    ]
    for i in invoices[:5]:
        partner = i["partner_id"][1] if i["partner_id"] else "Không xác định"
        days = (date.today() - date.fromisoformat(str(i["invoice_date_due"])[:10])).days
        lines.append(f"• {partner}: {i['amount_residual']:,.0f} VNĐ ({days} ngày)")
    if len(invoices) > 5:
        lines.append(f"  ... và {len(invoices) - 5} hóa đơn khác")
    return "\n".join(lines)


# ─── New alert check functions (H/F/A/T/S) ───────────────────────────────────


def check_h02():
    """H02: Lead chưa chạm sau 4 giờ — Vàng → Hunter owner."""
    uid, models = get_odoo()
    cutoff = (datetime.now() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
    leads = sr(
        models, uid, "crm.lead",
        [
            ("create_date", "<", cutoff),
            ("create_date", ">=", date.today().isoformat()),
            ("activity_date_deadline", "=", False),
            ("active", "=", True),
        ],
        fields=["name", "user_id", "create_date"],
        limit=20,
        order="create_date asc",
    )
    if not leads:
        return 0
    lines = [f"Có {len(leads)} lead tạo hơn 4 giờ chưa được chạm:", ""]
    for lead in leads[:10]:
        user = lead["user_id"][1] if lead["user_id"] else "Chưa gán"
        lines.append(f"• {lead['name']} — {user}")
    if len(leads) > 10:
        lines.append(f"  ... và {len(leads) - 10} lead khác")
    route_alert("H02", "\n".join(lines))
    return len(leads)


def check_h03():
    """H03: Lead quá SLA 24 giờ — Cam → Hunter owner + Hunter Lead, escalate CEO khi lead nóng."""
    uid, models = get_odoo()
    cutoff = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    leads = sr(
        models, uid, "crm.lead",
        [
            ("create_date", "<", cutoff),
            ("activity_date_deadline", "=", False),
            ("active", "=", True),
            ("type", "=", "lead"),
        ],
        fields=["name", "user_id", "create_date", "priority"],
        limit=20,
        order="create_date asc",
    )
    if not leads:
        return 0
    has_hot = any(l.get("priority", "0") in ("2", "3") for l in leads)
    lines = [f"Có {len(leads)} lead quá 24 giờ chưa được chạm:", ""]
    for lead in leads[:10]:
        user = lead["user_id"][1] if lead["user_id"] else "Chưa gán"
        hot_tag = " 🔥" if lead.get("priority", "0") in ("2", "3") else ""
        lines.append(f"• {lead['name']} — {user}{hot_tag}")
    if len(leads) > 10:
        lines.append(f"  ... và {len(leads) - 10} lead khác")
    route_alert("H03", "\n".join(lines), escalate=has_hot)
    return len(leads)


def check_h05():
    """H05: Quote treo > 3 ngày — Cam → Hunter owner + Hunter Lead."""
    uid, models = get_odoo()
    cutoff = (date.today() - timedelta(days=3)).isoformat()
    orders = sr(
        models, uid, "sale.order",
        [
            ("state", "=", "draft"),
            ("create_date", "<", cutoff),
        ],
        fields=["name", "partner_id", "user_id", "amount_total", "create_date"],
        limit=20,
        order="create_date asc",
    )
    if not orders:
        return 0
    total = sum(o["amount_total"] for o in orders)
    lines = [
        f"Có {len(orders)} báo giá nháp treo hơn 3 ngày (tổng {total:,.0f} VNĐ):",
        "",
    ]
    for o in orders[:10]:
        partner = o["partner_id"][1] if o["partner_id"] else "Không xác định"
        user = o["user_id"][1] if o["user_id"] else "Chưa gán"
        days = (date.today() - date.fromisoformat(str(o["create_date"])[:10])).days
        lines.append(f"• {o['name']} — {partner} — {o['amount_total']:,.0f} VNĐ ({days} ngày) — {user}")
    if len(orders) > 10:
        lines.append(f"  ... và {len(orders) - 10} báo giá khác")
    route_alert("H05", "\n".join(lines))
    return len(orders)


def check_f01():
    """F01: Khách sắp reorder (trong 3 ngày tới) — Vàng → Farmer owner, escalate CEO khi VIP."""
    uid, models = get_odoo()
    today = date.today().isoformat()
    future_3d = (date.today() + timedelta(days=3)).isoformat()
    try:
        partners = sr(
            models, uid, "res.partner",
            [
                ("expected_reorder_date", ">=", today),
                ("expected_reorder_date", "<=", future_3d),
                ("customer_rank", ">", 0),
            ],
            fields=["name", "expected_reorder_date", "user_id", "vip_level"],
            limit=20,
            order="expected_reorder_date asc",
        )
    except Exception:
        # Field expected_reorder_date may not exist yet
        return 0
    if not partners:
        return 0
    has_vip = any(p.get("vip_level") not in (False, "none", "") for p in partners)
    lines = [f"Có {len(partners)} khách hàng sắp tới chu kỳ reorder:", ""]
    for p in partners[:10]:
        user = p["user_id"][1] if p["user_id"] else "Chưa gán"
        vip_tag = " ⭐" if p.get("vip_level") not in (False, "none", "") else ""
        lines.append(f"• {p['name']} — hạn {p['expected_reorder_date']} — {user}{vip_tag}")
    if len(partners) > 10:
        lines.append(f"  ... và {len(partners) - 10} khách khác")
    route_alert("F01", "\n".join(lines), escalate=has_vip)
    return len(partners)


def check_f02():
    """F02: Khách quá chu kỳ reorder — Cam → Farmer owner + Farmer Lead."""
    uid, models = get_odoo()
    today = date.today().isoformat()
    try:
        partners = sr(
            models, uid, "res.partner",
            [
                ("expected_reorder_date", "<", today),
                ("customer_rank", ">", 0),
            ],
            fields=["name", "expected_reorder_date", "user_id"],
            limit=20,
            order="expected_reorder_date asc",
        )
    except Exception:
        return 0
    if not partners:
        return 0
    lines = [f"Có {len(partners)} khách hàng đã quá chu kỳ reorder:", ""]
    for p in partners[:10]:
        user = p["user_id"][1] if p["user_id"] else "Chưa gán"
        days = (date.today() - date.fromisoformat(str(p["expected_reorder_date"])[:10])).days
        lines.append(f"• {p['name']} — quá hạn {days} ngày — {user}")
    if len(partners) > 10:
        lines.append(f"  ... và {len(partners) - 10} khách khác")
    route_alert("F02", "\n".join(lines))
    return len(partners)


def check_f03():
    """F03: VIP chưa được chạm >10 ngày — Đỏ → Farmer Lead, always CEO."""
    uid, models = get_odoo()
    cutoff = (date.today() - timedelta(days=10)).isoformat()
    try:
        partners = sr(
            models, uid, "res.partner",
            [
                ("vip_level", "not in", [False, "none"]),
                ("customer_rank", ">", 0),
            ],
            fields=["name", "vip_level", "user_id", "activity_date_deadline"],
            limit=50,
        )
    except Exception:
        return 0
    # Filter: last activity > 10 days ago or no activity at all
    stale = []
    for p in partners:
        last_act = p.get("activity_date_deadline")
        if not last_act or str(last_act)[:10] < cutoff:
            stale.append(p)
    if not stale:
        return 0
    lines = [f"Có {len(stale)} khách VIP chưa được chạm hơn 10 ngày:", ""]
    for p in stale[:10]:
        user = p["user_id"][1] if p["user_id"] else "Chưa gán"
        vip = p.get("vip_level", "N/A")
        lines.append(f"• {p['name']} (VIP: {vip}) — {user}")
    if len(stale) > 10:
        lines.append(f"  ... và {len(stale) - 10} khách khác")
    route_alert("F03", "\n".join(lines))
    return len(stale)


def check_a01():
    """A01: Công nợ đến hạn trong 7 ngày — Vàng → Finance + Farmer."""
    uid, models = get_odoo()
    today = date.today().isoformat()
    future_7d = (date.today() + timedelta(days=7)).isoformat()
    invoices = sr(
        models, uid, "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("invoice_date_due", ">=", today),
            ("invoice_date_due", "<=", future_7d),
        ],
        fields=["partner_id", "amount_residual", "invoice_date_due", "name"],
        limit=20,
        order="invoice_date_due asc",
    )
    if not invoices:
        return 0
    total = sum(i["amount_residual"] for i in invoices)
    lines = [
        f"Có {len(invoices)} hóa đơn sắp đến hạn trong 7 ngày (tổng {total:,.0f} VNĐ):",
        "",
    ]
    for i in invoices[:10]:
        partner = i["partner_id"][1] if i["partner_id"] else "Không xác định"
        lines.append(
            f"• {i['name']} — {partner} — {i['amount_residual']:,.0f} VNĐ — hạn {i['invoice_date_due']}"
        )
    if len(invoices) > 10:
        lines.append(f"  ... và {len(invoices) - 10} hóa đơn khác")
    route_alert("A01", "\n".join(lines))
    return len(invoices)


def check_a03():
    """A03: Công nợ rủi ro cao >60 ngày — Đỏ → Finance Lead + Farmer Lead, always CEO."""
    uid, models = get_odoo()
    cutoff_60d = (date.today() - timedelta(days=60)).isoformat()
    invoices = sr(
        models, uid, "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("invoice_date_due", "<", cutoff_60d),
        ],
        fields=["partner_id", "amount_residual", "invoice_date_due", "name"],
        limit=20,
        order="amount_residual desc",
    )
    if not invoices:
        return 0
    total = sum(i["amount_residual"] for i in invoices)
    lines = [
        f"Có {len(invoices)} hóa đơn quá hạn hơn 60 ngày — RỦI RO CAO (tổng {total:,.0f} VNĐ):",
        "",
    ]
    for i in invoices[:10]:
        partner = i["partner_id"][1] if i["partner_id"] else "Không xác định"
        days = (date.today() - date.fromisoformat(str(i["invoice_date_due"])[:10])).days
        lines.append(
            f"• {i['name']} — {partner} — {i['amount_residual']:,.0f} VNĐ ({days} ngày)"
        )
    if len(invoices) > 10:
        lines.append(f"  ... và {len(invoices) - 10} hóa đơn khác")
    route_alert("A03", "\n".join(lines))
    return len(invoices)


def check_a04():
    """A04: Công nợ > 30 ngày — Đỏ → Finance Lead, always CEO."""
    uid, models = get_odoo()
    cutoff_30d = (date.today() - timedelta(days=30)).isoformat()
    cutoff_60d = (date.today() - timedelta(days=60)).isoformat()
    # Only 30-60 day range (A03 covers >60)
    invoices = sr(
        models, uid, "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("invoice_date_due", "<", cutoff_30d),
            ("invoice_date_due", ">=", cutoff_60d),
        ],
        fields=["partner_id", "amount_residual", "invoice_date_due", "name"],
        limit=20,
        order="amount_residual desc",
    )
    if not invoices:
        return 0
    total = sum(i["amount_residual"] for i in invoices)
    lines = [
        f"Có {len(invoices)} hóa đơn quá hạn 30-60 ngày (tổng {total:,.0f} VNĐ):",
        "",
    ]
    for i in invoices[:10]:
        partner = i["partner_id"][1] if i["partner_id"] else "Không xác định"
        days = (date.today() - date.fromisoformat(str(i["invoice_date_due"])[:10])).days
        lines.append(
            f"• {i['name']} — {partner} — {i['amount_residual']:,.0f} VNĐ ({days} ngày)"
        )
    if len(invoices) > 10:
        lines.append(f"  ... và {len(invoices) - 10} hóa đơn khác")
    route_alert("A04", "\n".join(lines))
    return len(invoices)


def check_t03():
    """T03: Task trọng yếu quá hạn — Đỏ → Lead liên quan, escalate CEO."""
    uid, models = get_odoo()
    today = date.today().isoformat()
    try:
        tasks = sr(
            models, uid, "project.task",
            [
                ("date_deadline", "<", today),
                ("stage_id.fold", "=", False),
                ("priority", "in", ["1", "2"]),  # high/critical priority
            ],
            fields=["name", "user_ids", "project_id", "date_deadline", "priority"],
            limit=20,
            order="date_deadline asc",
        )
    except Exception:
        # project module may not be installed
        return 0
    if not tasks:
        return 0
    lines = [f"Có {len(tasks)} task trọng yếu đã quá hạn:", ""]
    for t in tasks[:10]:
        project = t["project_id"][1] if t["project_id"] else "Không xác định"
        users = ", ".join(
            u[1] if isinstance(u, list) else str(u)
            for u in (t.get("user_ids") or [])
        ) or "Chưa gán"
        days = (date.today() - date.fromisoformat(str(t["date_deadline"])[:10])).days
        prio = "🔥 Quan trọng" if t.get("priority") == "2" else "⚡ Cao"
        lines.append(f"• [{prio}] {t['name']} — {project} — quá hạn {days} ngày — {users}")
    if len(tasks) > 10:
        lines.append(f"  ... và {len(tasks) - 10} task khác")
    route_alert("T03", "\n".join(lines), escalate=True)
    return len(tasks)


def check_s03():
    """S03: Workflow lõi gãy — Đỏ → Admin/Tech + Ops, always CEO.

    Placeholder: kiểm tra các dấu hiệu workflow bất thường.
    - Đơn hàng xác nhận nhưng không có hóa đơn sau 7 ngày
    - Lead won nhưng không có sale order
    """
    uid, models = get_odoo()
    issues = []

    # Check 1: Confirmed SO without invoice for >7 days
    cutoff_7d = (date.today() - timedelta(days=7)).isoformat()
    confirmed_so = sr(
        models, uid, "sale.order",
        [
            ("state", "=", "sale"),
            ("date_order", "<", cutoff_7d),
            ("invoice_count", "=", 0),
        ],
        fields=["name", "partner_id", "date_order", "amount_total"],
        limit=10,
        order="date_order asc",
    )
    if confirmed_so:
        issues.append(f"<b>Đơn hàng xác nhận chưa xuất hóa đơn (&gt;7 ngày):</b>")
        for so in confirmed_so[:5]:
            partner = so["partner_id"][1] if so["partner_id"] else "Không xác định"
            issues.append(f"  • {so['name']} — {partner} — {so['amount_total']:,.0f} VNĐ")

    # Check 2: Won leads without SO
    try:
        won_leads = sr(
            models, uid, "crm.lead",
            [
                ("stage_id.is_won", "=", True),
                ("active", "=", True),
                ("order_ids", "=", False),
            ],
            fields=["name", "user_id", "date_closed"],
            limit=10,
            order="date_closed asc",
        )
        if won_leads:
            issues.append("")
            issues.append("<b>Lead thắng nhưng chưa có đơn hàng:</b>")
            for l in won_leads[:5]:
                user = l["user_id"][1] if l["user_id"] else "Chưa gán"
                issues.append(f"  • {l['name']} — {user}")
    except Exception:
        pass

    if not issues:
        return 0

    header = f"Phát hiện {len(confirmed_so) + len(won_leads if 'won_leads' in dir() else [])} vấn đề workflow:\n\n"
    route_alert("S03", header + "\n".join(issues))
    return len(issues)


def run_all_alerts():
    """Chạy tất cả kiểm tra H/F/A/T/S và route theo quy tắc."""
    checks = [
        ("H02", check_h02),
        ("H03", check_h03),
        ("H05", check_h05),
        ("F01", check_f01),
        ("F02", check_f02),
        ("F03", check_f03),
        ("A01", check_a01),
        ("A03", check_a03),
        ("A04", check_a04),
        ("T03", check_t03),
        ("S03", check_s03),
    ]
    total_alerts = 0
    for code, fn in checks:
        try:
            count = fn()
            if count:
                print(f"  [{code}] Gửi cảnh báo: {count} mục")
                total_alerts += count
            else:
                print(f"  [{code}] Không có cảnh báo")
        except Exception as e:
            print(f"  [{code}] Lỗi: {e}")
    return total_alerts


# ─── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Cách dùng: alert_runner.py [morning|midday|eod|sla|ar|alerts]")
        print("")
        print("  morning  — Báo cáo buổi sáng (pipeline, doanh thu, lead)")
        print("  midday   — Báo cáo giữa ngày")
        print("  eod      — Báo cáo cuối ngày")
        print("  sla      — Cảnh báo SLA (lead vượt 48h)")
        print("  ar       — Công nợ quá hạn")
        print("  alerts   — Chạy tất cả kiểm tra H/F/A/T/S và gửi cảnh báo")
        sys.exit(1)

    cmd = sys.argv[1]

    # Legacy handlers: send to CEO chat directly
    simple_handlers = {
        "morning": morning_brief,
        "midday": midday_flash,
        "eod": eod_report,
        "sla": sla_alert,
        "ar": overdue_ar,
    }

    if cmd == "alerts":
        print("Đang chạy tất cả kiểm tra cảnh báo...")
        total = run_all_alerts()
        print(f"\nHoàn tất. Tổng cảnh báo: {total}")
    elif cmd in simple_handlers:
        msg = simple_handlers[cmd]()
        if msg:
            result = send_telegram(msg)
            print(f"Đã gửi {cmd}: {result}")
        else:
            print(f"Không có cảnh báo cho {cmd}")
    else:
        print(f"Lệnh không hợp lệ: {cmd}")
        sys.exit(1)
