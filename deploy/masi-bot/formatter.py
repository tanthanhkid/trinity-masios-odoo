"""
Template-based formatters for slash commands.
No LLM needed — pure Python string formatting.
Handles actual Odoo MCP response structures.
"""
import json
import logging

logger = logging.getLogger(__name__)


def _safe_json(raw: str):
    try:
        d = json.loads(raw)
        # MCP sometimes wraps response as {"result": "{json_string}"}
        if isinstance(d, dict) and "result" in d and isinstance(d["result"], str):
            try:
                return json.loads(d["result"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d
    except (json.JSONDecodeError, TypeError) as e:
        preview = (raw[:100] + "...") if raw and len(raw) > 100 else raw
        logger.error("JSON parse failed (len=%d, preview=%s): %s",
                     len(raw) if raw else 0, preview, e)
        return {}


def _money(amount) -> str:
    if amount is None:
        return "0"
    try:
        n = float(amount)
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.1f} tỷ"
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f} triệu"
        if n >= 1_000:
            return f"{n/1_000:.0f}K"
        return f"{n:,.0f}"
    except (ValueError, TypeError):
        return "0"


def _pct(val) -> str:
    try:
        return f"{float(val):.1f}%"
    except (ValueError, TypeError):
        return str(val)


def _dq(lines: list, d):
    """Append data quality warning."""
    if not isinstance(d, dict):
        return
    q = d.get("data_quality", "ok")
    issues = d.get("data_issues", [])
    if q != "ok" and issues:
        lines.append("")
        lines.append("⚠️ <b>DATA ISSUE:</b>")
        for i in issues:
            lines.append(f"  • {i}")


def _val(d, *keys, default=None):
    """Get nested value from dict by trying multiple keys."""
    for k in keys:
        if isinstance(d, dict) and k in d:
            return d[k]
    return default


def format_morning_brief(raw: str) -> str:
    d = _safe_json(raw)
    if not d:
        return "🌅 <b>MORNING BRIEF</b>\n\n📭 Không có dữ liệu."

    lines = [f"🌅 <b>MORNING BRIEF — {d.get('date', '')}</b>", ""]

    # Hunter KPIs — always show section even if empty/zero
    h = d.get("hunter_kpis", {}) or {}
    lines.append("🎯 <b>Hunter</b>")
    lines.append(f"  • Leads mới tháng: <b>{h.get('leads_new_this_month', 0)}</b>")
    lines.append(f"  • Leads won: <b>{h.get('leads_won_this_month', 0)}</b>")
    lines.append(f"  • DT đơn đầu: <b>{_money(h.get('first_order_revenue', 0))}</b> VND")
    lines.append("")

    # Farmer KPIs — always show section even if empty/zero
    f = d.get("farmer_kpis", {}) or {}
    lines.append("🌾 <b>Farmer</b>")
    lines.append(f"  • DT tái mua: <b>{_money(f.get('repeat_order_revenue', 0))}</b> VND")
    lines.append(f"  • KH ngủ đông: <b>{f.get('sleeping_customers_90d', 0)}</b>")
    lines.append("")

    # AR summary — always show section even if empty/zero
    ar = d.get("ar_task_summary", {}) or {}
    lines.append("💰 <b>Công nợ</b>")
    lines.append(f"  • Tổng phải thu: <b>{_money(ar.get('total_receivable', 0))}</b> VND")
    lines.append(f"  • HĐ quá hạn: <b>{ar.get('overdue_invoices', 0)}</b>")
    lines.append(f"  • Đến hạn 7 ngày: <b>{ar.get('due_within_7d', 0)}</b>")
    lines.append("")

    # Alerts
    alerts = d.get("top_alerts", [])
    if alerts:
        lines.append(f"🚨 <b>Alerts ({len(alerts)})</b>")
        for a in alerts[:5]:
            msg = a.get("message", str(a)) if isinstance(a, dict) else str(a)
            lines.append(f"  ⚠️ {msg[:100]}")

    _dq(lines, d)
    return "\n".join(lines)


def format_ceo_alert(raw: str) -> str:
    d = _safe_json(raw)
    if not d:
        return "🚨 <b>CEO ALERTS</b>\n\n✅ Không có cảnh báo."

    alerts = d.get("alerts", d.get("top_alerts", []))
    if not alerts and isinstance(d, dict):
        # Try flat structure
        alerts = [v for v in d.values() if isinstance(v, list)]
        alerts = alerts[0] if alerts else []

    lines = [f"🚨 <b>CEO ALERTS</b> ({len(alerts)} vấn đề)", ""]

    for a in alerts:
        if isinstance(a, dict):
            sev = a.get("severity", a.get("type", "info"))
            icon = "🔴" if "critical" in str(sev) else "🟡" if "warning" in str(sev) else "⚠️"
            msg = a.get("summary", a.get("message", a.get("title", a.get("detail", ""))))
            if not msg:
                msg = str(a)
            lines.append(f"{icon} {msg[:150]}")
        else:
            lines.append(f"⚠️ {a}")

    _dq(lines, d)
    return "\n".join(lines)


def format_revenue_today(raw: str) -> str:
    d = _safe_json(raw)
    if not d:
        return "📊 <b>Doanh số hôm nay</b>\n\n📭 Không có dữ liệu."
    lines = [f"📊 <b>Doanh số hôm nay — {d.get('date', '')}</b>", ""]

    total = d.get("total_revenue", 0)
    breakdown = d.get("breakdown", [])

    if not total and not breakdown:
        lines.append("📭 Chưa có dữ liệu doanh số hôm nay.")
    else:
        lines.append(f"💰 <b>Tổng:</b> {_money(total)} VND")
        for item in breakdown:
            lines.append(f"  • {item.get('team', '?')}: {_money(item.get('amount', 0))} VND ({item.get('count', 0)} đơn)")

    _dq(lines, d)
    return "\n".join(lines)


def format_brief_hunter(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["🎯 <b>BRIEF HUNTER</b>", ""]

    summary = d.get("summary", {}) if isinstance(d.get("summary"), dict) else {}
    seen_labels = set()
    for key, label in [
        ("new_leads", "Leads mới"),
        ("leads_new_this_month", "Leads mới tháng"),
        ("sla_breached", "SLA breach"),
        ("sla_breaches", "SLA breach"),
        ("pending_quotes", "Báo giá chờ"),
        ("pending_quotations", "Báo giá chờ"),
        ("first_orders", "Đơn đầu tiên"),
        ("first_order_count", "Đơn đầu tiên"),
        ("conversion_rate", "Tỷ lệ chuyển đổi"),
    ]:
        val = _val(d, key) if _val(d, key) is not None else summary.get(key)
        if val is None:
            continue  # key not present in data at all — skip duplicate alias
        if label in seen_labels:
            continue  # already displayed via another alias
        seen_labels.add(label)
        default_val = "0.0%" if "rate" in key else "0"
        display = _pct(val) if "rate" in key else str(val)
        lines.append(f"• {label}: <b>{display}</b>")

    # If no fields were found at all, show defaults so report isn't empty
    if not seen_labels:
        for label, default_val in [("Leads mới", "0"), ("SLA breach", "0"),
                                    ("Báo giá chờ", "0"), ("Đơn đầu tiên", "0"),
                                    ("Tỷ lệ chuyển đổi", "0.0%")]:
            lines.append(f"• {label}: <b>{default_val}</b>")

    _dq(lines, d)
    return "\n".join(lines)


def format_brief_farmer(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["🌾 <b>BRIEF FARMER</b>", ""]

    summary = d.get("summary", {}) if isinstance(d.get("summary"), dict) else {}
    seen_labels = set()
    for key, label in [
        ("repeat_orders", "Đơn tái mua"),
        ("repeat_order_count", "Đơn tái mua"),
        ("sleeping_customers", "KH ngủ đông"),
        ("sleeping_customers_90d", "KH ngủ đông"),
        ("vip_at_risk", "VIP cần chú ý"),
        ("vip_count", "VIP cần chú ý"),
        ("retention_rate", "Tỷ lệ giữ chân"),
        ("active_customers", "KH active"),
    ]:
        val = _val(d, key) if _val(d, key) is not None else summary.get(key)
        if val is None:
            continue  # key not present in data at all — skip duplicate alias
        if label in seen_labels:
            continue  # already displayed via another alias
        seen_labels.add(label)
        display = _pct(val) if "rate" in key else str(val)
        lines.append(f"• {label}: <b>{display}</b>")

    # If no fields were found at all, show defaults so report isn't empty
    if not seen_labels:
        for label, default_val in [("Đơn tái mua", "0"), ("KH ngủ đông", "0"),
                                    ("VIP cần chú ý", "0"), ("Tỷ lệ giữ chân", "0.0%"),
                                    ("KH active", "0")]:
            lines.append(f"• {label}: <b>{default_val}</b>")

    _dq(lines, d)
    return "\n".join(lines)


def format_brief_ar(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["💰 <b>BÁO CÁO AR AGING</b>", ""]

    total = _val(d, "total_receivable", "total", default=0)
    lines.append(f"📊 Tổng phải thu: <b>{_money(total)}</b> VND")
    lines.append("")

    aging = _val(d, "aging", "aging_buckets", "buckets", default=[])
    if aging:
        lines.append("📅 <b>Theo tuổi nợ:</b>")
        for b in aging:
            if isinstance(b, dict):
                name = _val(b, "bucket", "label", "name", default="?")
                amt = _money(_val(b, "amount", "total", default=0))
                cnt = _val(b, "count", "invoice_count", default=0)
                lines.append(f"  • {name}: {amt} VND ({cnt} HĐ)")
        lines.append("")

    debtors = _val(d, "top_debtors", "top_customers", default=[])
    if debtors:
        lines.append("🏢 <b>Top nợ nhiều:</b>")
        for db in debtors[:5]:
            if isinstance(db, dict):
                name = _val(db, "name", "partner", default="?")
                amt = _money(_val(db, "amount", "amount_residual", "total", default=0))
                lines.append(f"  • {name}: {amt} VND")

    _dq(lines, d)
    return "\n".join(lines)


def format_brief_cash(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["💵 <b>DÒNG TIỀN</b>", ""]

    seen_labels = set()
    for key, label in [
        ("collected", "💰 Đã thu"),
        ("payments_received", "💰 Đã thu"),
        ("total_receivable", "📑 Tổng phải thu"),
        ("overdue", "🔴 Quá hạn"),
        ("overdue_amount", "🔴 Quá hạn"),
        ("expected_7d", "📅 Dự kiến 7 ngày"),
        ("due_within_7d", "📅 Đến hạn 7 ngày"),
        ("collection_rate", "📊 Tỷ lệ thu"),
    ]:
        val = _val(d, key)
        if val is None:
            continue  # key not in data — skip duplicate alias
        if label in seen_labels:
            continue  # already displayed via another alias
        seen_labels.add(label)
        if "rate" in key:
            lines.append(f"{label}: <b>{_pct(val)}</b>")
        else:
            lines.append(f"{label}: <b>{_money(val)}</b> VND")

    # If no fields found, show defaults so report isn't empty
    if not seen_labels:
        for label, default_val in [("💰 Đã thu", "0 VND"), ("📑 Tổng phải thu", "0 VND"),
                                    ("🔴 Quá hạn", "0 VND"), ("📅 Dự kiến 7 ngày", "0 VND"),
                                    ("📊 Tỷ lệ thu", "0.0%")]:
            lines.append(f"{label}: <b>{default_val}</b>")

    _dq(lines, d)
    return "\n".join(lines)


def format_kpi(raw: str) -> str:
    d = _safe_json(raw)
    lines = [f"📊 <b>KPI DASHBOARD</b>", ""]

    period = d.get("period", "")
    if period:
        lines.append(f"📅 {period}")
        lines.append("")

    seen_labels = set()
    for key, label, is_money in [
        ("monthly_revenue", "💰 Doanh thu tháng", True),
        ("revenue", "💰 Doanh thu", True),
        ("pipeline_value", "📈 Pipeline", True),
        ("total_debt", "💳 Tổng nợ", True),
        ("total_receivable", "💳 Phải thu", True),
        ("overdue_receivable", "⚠️ Quá hạn", True),
        ("new_leads", "🎯 Leads mới", False),
        ("orders", "🛒 Đơn hàng", False),
        ("collection_rate", "📊 Tỷ lệ thu", False),
    ]:
        val = d.get(key)
        if val is None:
            continue  # key not in data — skip
        if label in seen_labels:
            continue  # already displayed via another alias
        seen_labels.add(label)
        if is_money:
            lines.append(f"{label}: <b>{_money(val)} VND</b>")
        elif "rate" in key:
            lines.append(f"{label}: <b>{_pct(val)}</b>")
        else:
            lines.append(f"{label}: <b>{val}</b>")

    # If no fields found, show defaults so report isn't empty
    if not seen_labels:
        for label, default_val in [("💰 Doanh thu", "0 VND"), ("📈 Pipeline", "0 VND"),
                                    ("💳 Phải thu", "0 VND"), ("⚠️ Quá hạn", "0 VND"),
                                    ("🎯 Leads mới", "0"), ("🛒 Đơn hàng", "0"),
                                    ("📊 Tỷ lệ thu", "0.0%")]:
            lines.append(f"{label}: <b>{default_val}</b>")

    _dq(lines, d)
    return "\n".join(lines)


def format_pipeline(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["📈 <b>CRM PIPELINE</b>", ""]

    stages = d if isinstance(d, list) else d.get("stages", [])

    total_count = 0
    total_value = 0
    for s in stages:
        if isinstance(s, dict):
            name = _val(s, "stage", "name", default="?")
            count = _val(s, "count", default=0) or 0
            value = _val(s, "value", "expected_revenue", default=0) or 0
            total_count += count
            total_value += value
            lines.append(f"• {name}: <b>{count}</b> leads — {_money(value)} VND")

    if stages:
        lines.append("")
        lines.append(f"📊 <b>Tổng: {total_count} leads — {_money(total_value)} VND</b>")
    else:
        lines.append("📭 Không có dữ liệu pipeline.")

    return "\n".join(lines)


def format_congno(raw: str, mode: str = "") -> str:
    d = _safe_json(raw)
    title = "CÔNG NỢ QUÁ HẠN" if mode == "overdue" else "CÔNG NỢ ĐẾN HẠN"
    icon = "🔴" if mode == "overdue" else "📅"
    lines = [f"{icon} <b>{title}</b>", ""]

    invoices = _val(d, "records", "invoices", "details", default=[])
    total = _val(d, "total_amount", "total", default=0)
    if not total and d.get("count"):
        total = sum(inv.get("amount_residual", 0) for inv in invoices if isinstance(inv, dict))

    lines.append(f"📊 Tổng: <b>{len(invoices)}</b> hóa đơn — {_money(total)} VND")
    lines.append("")

    for inv in invoices[:10]:
        if isinstance(inv, dict):
            name = _val(inv, "partner", "partner_name", "customer", default="?")
            amt = _money(_val(inv, "amount", "amount_residual", default=0))
            days = _val(inv, "days_overdue", "days", default="")
            inv_num = _val(inv, "number", "name", "invoice", default="")
            day_str = f" ({days} ngày)" if days else ""
            lines.append(f"  • <b>{name}</b>: {amt} VND{day_str}")
            if inv_num:
                lines.append(f"    <code>{inv_num}</code>")

    if len(invoices) > 10:
        lines.append(f"  ... và {len(invoices) - 10} HĐ khác")

    _dq(lines, d)
    return "\n".join(lines)


def format_hunter_today(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["🎯 <b>HUNTER TODAY</b>", ""]
    _format_generic(lines, d)
    _dq(lines, d)
    return "\n".join(lines)


def format_hunter_sla(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["🚨 <b>HUNTER SLA</b>", ""]

    leads = _val(d, "records", "leads", "details", "breached", default=[])
    if not leads:
        lines.append("✅ Không có lead vi phạm SLA.")
        return "\n".join(lines)

    threshold = d.get("sla_threshold_hours", 48)
    lines.append(f"📊 Tổng: <b>{len(leads)}</b> leads vi phạm (SLA: {threshold}h)")
    lines.append("")
    for lead in leads[:10]:
        if isinstance(lead, dict):
            name = _val(lead, "name", "lead_name", default="?")
            hours = _val(lead, "sla_hours", "hours", "hours_since_creation", default="?")
            owner = _val(lead, "owner", "user", "user_id", default="?")
            if isinstance(owner, list):
                owner = owner[1] if len(owner) > 1 else owner[0]
            revenue = _val(lead, "expected_revenue", default=0)
            lines.append(f"  • <b>{name}</b>")
            rev_str = f" | {_money(revenue)} VND" if revenue else ""
            lines.append(f"    Owner: {owner} | {hours}h{rev_str}")

    _dq(lines, d)
    return "\n".join(lines)


def format_farmer_today(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["🌾 <b>FARMER TODAY</b>", ""]
    _format_generic(lines, d)
    _dq(lines, d)
    return "\n".join(lines)


def format_farmer_ar(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["🌾 <b>FARMER AR</b>", ""]

    customers = _val(d, "top_debtors", "customers", "details", default=[])
    total = _val(d, "total_receivable", "total", "total_amount", default=0)
    if total:
        lines.append(f"💰 Tổng phải thu: <b>{_money(total)}</b> VND")
        lines.append("")

    # Aging buckets
    aging = d.get("aging_buckets", {})
    if aging and isinstance(aging, dict):
        lines.append("📅 <b>Theo tuổi nợ:</b>")
        bucket_labels = [("current", "Hiện tại"), ("1_30", "1-30 ngày"), ("31_60", "31-60 ngày"),
                         ("61_90", "61-90 ngày"), ("90_plus", "90+ ngày")]
        for key, label in bucket_labels:
            val = aging.get(key, 0)
            if val:
                lines.append(f"  • {label}: {_money(val)} VND")
        lines.append("")

    if customers:
        lines.append("🏢 <b>Top nợ nhiều:</b>")
    for c in customers[:10]:
        if isinstance(c, dict):
            name = _val(c, "name", "partner", default="?")
            amt = _money(_val(c, "amount", "amount_residual", default=0))
            lines.append(f"  • {name}: <b>{amt}</b> VND")

    if not customers and not total:
        lines.append("📭 Không có dữ liệu.")

    _dq(lines, d)
    return "\n".join(lines)


def format_task_overdue(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["📋 <b>TASK QUÁ HẠN</b>", ""]

    tasks = _val(d, "records", "tasks", "details", default=[])
    if not tasks:
        msg = d.get("message", "")
        if msg:
            lines.append(f"ℹ️ {msg}")
        else:
            lines.append("✅ Không có task quá hạn.")
        return "\n".join(lines)

    lines.append(f"📊 Tổng: <b>{len(tasks)}</b> task")
    lines.append("")
    for t in tasks[:10]:
        if isinstance(t, dict):
            name = _val(t, "name", "task_name", default="?")
            days = _val(t, "days_overdue", "days", default="?")
            project_raw = _val(t, "project", "project_id", "assigned_to", default="")
            project = project_raw[1] if isinstance(project_raw, (list, tuple)) and len(project_raw) > 1 else (project_raw or "")
            lines.append(f"  • <b>{name}</b>")
            proj_str = f"{project} | " if project else ""
            lines.append(f"    {proj_str}Quá hạn: {days} ngày")

    _dq(lines, d)
    return "\n".join(lines)


def format_flash_report(raw: str, report_type: str = "") -> str:
    d = _safe_json(raw)
    title = "EOD REPORT" if report_type == "eod" else "MIDDAY REPORT"
    icon = "🌙" if report_type == "eod" else "☀️"
    lines = [f"{icon} <b>{title} — {d.get('date', '')}</b>", ""]
    _format_generic(lines, d)
    _dq(lines, d)
    return "\n".join(lines)


def format_credit(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["🚨 <b>KHÁCH VƯỢT CREDIT LIMIT</b>", ""]

    # MCP returns a plain array or dict with customers key
    if isinstance(d, list):
        customers = d
    else:
        customers = _val(d, "customers", "details", default=[])
    if not customers:
        lines.append("✅ Không có khách vượt hạn mức.")
        return "\n".join(lines)

    lines.append(f"📊 <b>{len(customers)}</b> khách vượt hạn mức")
    lines.append("")
    for c in customers[:10]:
        if isinstance(c, dict):
            name = _val(c, "name", "partner", default="?")
            limit_v = _money(_val(c, "credit_limit", default=0))
            debt = _money(_val(c, "outstanding_debt", "debt", "total_debt", default=0))
            exceeded = _val(c, "credit_available", "exceeded_by", "over", default=0)
            over = _money(abs(exceeded)) if exceeded else "0"
            lines.append(f"  • <b>{name}</b>")
            lines.append(f"    Hạn mức: {limit_v} | Nợ: {debt} | Vượt: {over}")

    _dq(lines, d)
    return "\n".join(lines)


def _format_generic(lines: list, d):
    """Generic formatter — iterate dict keys and render values."""
    if not isinstance(d, dict):
        lines.append(str(d)[:500])
        return
    for key, val in d.items():
        if key in ("data_quality", "data_issues", "date"):
            continue
        label = key.replace("_", " ").title()
        if isinstance(val, (int, float)):
            if val >= 10000:
                lines.append(f"• {label}: <b>{_money(val)}</b>")
            else:
                lines.append(f"• {label}: <b>{val}</b>")
        elif isinstance(val, str):
            lines.append(f"• {label}: {val}")
        elif isinstance(val, list):
            if not val:
                lines.append(f"• {label}: (trống)")
                continue
            lines.append(f"<b>{label}:</b>")
            for item in val[:8]:
                if isinstance(item, dict):
                    parts = []
                    for k, v in list(item.items())[:4]:
                        if k == "id":
                            continue
                        if isinstance(v, (int, float)) and v >= 10000:
                            parts.append(f"{k}: {_money(v)}")
                        elif isinstance(v, list) and len(v) == 2:
                            parts.append(f"{k}: {v[1]}")
                        else:
                            parts.append(f"{k}: {v}")
                    lines.append(f"  • {' | '.join(parts)}")
                else:
                    lines.append(f"  • {item}")
            if len(val) > 8:
                lines.append(f"  ... +{len(val) - 8} khác")
            lines.append("")
        elif isinstance(val, dict):
            lines.append(f"<b>{label}:</b>")
            for k, v in val.items():
                if isinstance(v, (int, float)) and v >= 10000:
                    lines.append(f"  • {k}: <b>{_money(v)}</b>")
                else:
                    lines.append(f"  • {k}: <b>{v}</b>")
            lines.append("")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
FORMATTERS = {
    "/morning_brief": format_morning_brief,
    "/ceo_alert": format_ceo_alert,
    "/doanhso_homnay": format_revenue_today,
    "/brief_hunter": format_brief_hunter,
    "/brief_farmer": format_brief_farmer,
    "/brief_ar": format_brief_ar,
    "/brief_cash": format_brief_cash,
    "/hunter_today": format_hunter_today,
    "/hunter_sla": format_hunter_sla,
    "/hunter_quotes": format_hunter_today,
    "/hunter_first_orders": format_hunter_today,
    "/hunter_sources": format_hunter_today,
    "/khachmoi_homnay": format_hunter_today,
    "/farmer_today": format_farmer_today,
    "/farmer_reorder": format_farmer_today,
    "/farmer_sleeping": format_farmer_today,
    "/farmer_vip": format_farmer_today,
    "/farmer_ar": format_farmer_ar,
    "/farmer_retention": format_farmer_today,
    "/congno_denhan": lambda raw: format_congno(raw, "due_soon"),
    "/congno_quahan": lambda raw: format_congno(raw, "overdue"),
    "/task_quahan": format_task_overdue,
    "/midday": lambda raw: format_flash_report(raw, "midday"),
    "/eod": lambda raw: format_flash_report(raw, "eod"),
    "/kpi": format_kpi,
    "/pipeline": format_pipeline,
    "/credit": format_credit,
}


def format_command(cmd: str, raw_data: str) -> str | None:
    fn = FORMATTERS.get(cmd)
    if fn is None:
        return None
    try:
        return fn(raw_data)
    except Exception as e:
        logger.error("Formatter error for %s: %s", cmd, e, exc_info=True)
        return f"⚠️ Lỗi format dữ liệu cho {cmd}. Đang chuyển sang format AI..."
