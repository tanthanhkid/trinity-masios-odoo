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
            team = item.get('team', item.get('order_type', '?'))
            amount = item.get('amount', item.get('revenue', 0))
            lines.append(f"  • {team}: {_money(amount)} VND ({item.get('count', 0)} đơn)")

    _dq(lines, d)
    return "\n".join(lines)


def format_brief_hunter(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["🎯 <b>BRIEF HUNTER</b>", ""]

    period = d.get("period", "")
    if period:
        lines.append(f"📅 Kỳ: <b>{period}</b>")
        lines.append("")

    lines.append(f"• Leads mới: <b>{d.get('leads_new', 0)}</b>")
    lines.append(f"• Leads đang mở: <b>{d.get('leads_open', 0)}</b>")
    lines.append(f"• SLA OK: <b>{d.get('sla_ok', 0)}</b>")
    lines.append(f"• SLA breach: <b>{d.get('sla_breached', 0)}</b>")
    lines.append(f"• Báo giá chờ: <b>{d.get('quotes_pending', 0)}</b>")
    lines.append(f"• Đơn đầu tiên: <b>{d.get('first_orders_count', 0)}</b> ({_money(d.get('first_orders_revenue', 0))} VND)")
    lines.append(f"• Leads won: <b>{d.get('leads_won', 0)}</b>")
    lines.append(f"• Tỷ lệ chuyển đổi: <b>{_pct(d.get('conversion_rate_pct', 0))}</b>")

    _dq(lines, d)
    return "\n".join(lines)


def format_brief_farmer(raw: str) -> str:
    d = _safe_json(raw)
    lines = ["🌾 <b>BRIEF FARMER</b>", ""]

    period = d.get("period", "")
    if period:
        lines.append(f"📅 Kỳ: <b>{period}</b>")
        lines.append("")

    lines.append(f"• Đơn tái mua: <b>{d.get('repeat_orders_count', 0)}</b> ({_money(d.get('repeat_orders_revenue', 0))} VND)")

    buckets = d.get("sleeping_buckets", {})
    total_sleeping = d.get("total_sleeping", 0)
    lines.append(f"• KH ngủ đông: <b>{total_sleeping}</b>")
    if buckets:
        lines.append(f"  - 30-60 ngày: {buckets.get('30_60d', 0)}")
        lines.append(f"  - 60-90 ngày: {buckets.get('60_90d', 0)}")
        lines.append(f"  - 90+ ngày: {buckets.get('90d_plus', 0)}")

    lines.append(f"• Farmer AR: <b>{_money(d.get('farmer_ar_total', 0))} VND</b>")

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
        if isinstance(aging, dict):
            # MCP returns aging_buckets as dict: {current, 1_30, 31_60, 61_90, 90_plus}
            bucket_labels = [("current", "Hiện tại"), ("1_30", "1-30 ngày"), ("31_60", "31-60 ngày"),
                             ("61_90", "61-90 ngày"), ("90_plus", "90+ ngày")]
            for key, label in bucket_labels:
                val = aging.get(key, 0)
                if val:
                    lines.append(f"  • {label}: {_money(val)} VND")
        else:
            # Fallback: list of dicts [{bucket, amount, count}, ...]
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

    period = d.get("period", "")
    if period:
        lines.append(f"📅 Kỳ: <b>{period}</b>")
        lines.append("")

    lines.append(f"💰 Đã thu: <b>{_money(d.get('collected', 0))}</b> VND")
    lines.append(f"📅 Dự kiến 7 ngày: <b>{_money(d.get('expected_7d', 0))}</b> VND")
    lines.append(f"🔴 Quá hạn: <b>{_money(d.get('overdue_amount', 0))}</b> VND")
    lines.append(f"📑 Tổng hóa đơn: <b>{_money(d.get('total_invoiced', 0))}</b> VND")
    lines.append(f"📊 Tỷ lệ thu: <b>{_pct(d.get('collection_rate_pct', 0))}</b>")

    top_pending = d.get("top_pending", [])
    if top_pending:
        lines.append("")
        lines.append("📋 <b>Top chờ thu:</b>")
        for inv in top_pending[:5]:
            if isinstance(inv, dict):
                name = inv.get("invoice", inv.get("name", "?"))
                partner = inv.get("partner", "?")
                amt = _money(inv.get("amount", 0))
                due = inv.get("due_date", "")
                lines.append(f"  • {name} — {partner}: {amt} VND (hạn: {due})")

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


def format_hunter_today(raw: str, section_override: str = "") -> str:
    """Dedicated formatter for odoo_hunter_today.
    Handles sections: all, overview, sla, quotes, first_orders, sources.
    """
    d = _safe_json(raw)
    section = section_override or d.get("section", "all")
    lines = ["🎯 <b>HUNTER TODAY</b> — " + d.get("date", ""), ""]

    if section in ("all", "overview"):
        ov = d.get("overview", {})
        lines.append("📋 <b>Tổng quan</b>")
        lines.append(f"  • Leads tạo hôm nay: <b>{ov.get('leads_created_today', 0)}</b>")
        lines.append(f"  • Activities đến hạn: <b>{ov.get('activities_due_today', 0)}</b>")
        lines.append("")

    if section in ("all", "sla"):
        sla = d.get("sla", {})
        lines.append("⏱️ <b>SLA</b>")
        lines.append(f"  • OK (trong 48h): <b>{sla.get('ok', 0)}</b>")
        lines.append(f"  • Vi phạm (>48h): <b>{sla.get('breached', 0)}</b>")
        lines.append("")

    if section in ("all", "quotes"):
        qt = d.get("quotes", {})
        lines.append(f"📝 <b>Báo giá</b> ({qt.get('count', 0)} đơn)")
        records = qt.get("records", [])
        for q in records[:8]:
            if isinstance(q, dict):
                name = q.get("name", "?")
                partner = q.get("partner", "?")
                amount = _money(q.get("amount", 0))
                state = q.get("state", "")
                state_vn = {"draft": "Nháp", "sent": "Đã gửi"}.get(state, state)
                lines.append(f"  • <b>{name}</b> — {partner}: {amount} VND ({state_vn})")
        if len(records) > 8:
            lines.append(f"  ... +{len(records) - 8} khác")
        lines.append("")

    if section in ("all", "first_orders"):
        fo = d.get("first_orders", {})
        lines.append("🆕 <b>Đơn đầu tiên hôm nay</b>")
        lines.append(f"  • Số đơn: <b>{fo.get('count', 0)}</b>")
        lines.append(f"  • Doanh thu: <b>{_money(fo.get('revenue', 0))}</b> VND")
        lines.append("")

    if section in ("all", "sources"):
        sources = d.get("sources", [])
        lines.append(f"📊 <b>Nguồn lead tháng này</b> ({len(sources)} nguồn)")
        for s in sources[:10]:
            if isinstance(s, dict):
                src = s.get("source", "Unknown")
                cnt = s.get("count", 0)
                lines.append(f"  • {src}: <b>{cnt}</b>")
        if len(sources) > 10:
            lines.append(f"  ... +{len(sources) - 10} khác")
        lines.append("")

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


def format_farmer_today(raw: str, section_override: str = "") -> str:
    """Dedicated formatter for odoo_farmer_today.
    Handles sections: all, overview, reorder, sleeping, vip, retention.
    """
    d = _safe_json(raw)
    section = section_override or d.get("section", "all")
    lines = ["🌾 <b>FARMER TODAY</b> — " + d.get("date", ""), ""]

    if section in ("all", "overview"):
        ov = d.get("overview", {})
        lines.append("📋 <b>Tổng quan</b>")
        lines.append(f"  • Đơn hàng hôm nay: <b>{ov.get('orders_today', 0)}</b>")
        lines.append(f"  • Doanh thu hôm nay: <b>{_money(ov.get('revenue_today', 0))}</b> VND")
        lines.append(f"  • Tổng KH cũ: <b>{ov.get('total_customers', 0)}</b>")
        lines.append("")

    if section in ("all", "reorder"):
        rd = d.get("reorder_due", {})
        lines.append(f"🔄 <b>Cần tái mua</b> ({rd.get('count', 0)} KH)")
        custs = rd.get("customers", [])
        for c in custs[:10]:
            if isinstance(c, dict):
                name = c.get("name", "?")
                lo = c.get("last_order", "?")
                lines.append(f"  • {name} — đơn cuối: {lo}")
        if len(custs) > 10:
            lines.append(f"  ... +{len(custs) - 10} khác")
        lines.append("")

    if section in ("all", "sleeping"):
        sl = d.get("sleeping", {})
        b30 = sl.get("30_60d", {})
        b60 = sl.get("60_90d", {})
        b90 = sl.get("90d_plus", {})
        total_sleeping = b30.get("count", 0) + b60.get("count", 0) + b90.get("count", 0)
        lines.append(f"😴 <b>KH ngủ đông</b> ({total_sleeping} KH)")
        lines.append(f"  • 30-60 ngày: <b>{b30.get('count', 0)}</b>")
        for c in b30.get("customers", [])[:3]:
            if isinstance(c, dict):
                lines.append(f"    - {c.get('name', '?')} ({c.get('days_since', '?')} ngày)")
        lines.append(f"  • 60-90 ngày: <b>{b60.get('count', 0)}</b>")
        for c in b60.get("customers", [])[:3]:
            if isinstance(c, dict):
                lines.append(f"    - {c.get('name', '?')} ({c.get('days_since', '?')} ngày)")
        lines.append(f"  • 90+ ngày: <b>{b90.get('count', 0)}</b>")
        for c in b90.get("customers", [])[:3]:
            if isinstance(c, dict):
                lines.append(f"    - {c.get('name', '?')} ({c.get('days_since', '?')} ngày)")
        lines.append("")

    if section in ("all", "vip"):
        vip = d.get("vip_at_risk", {})
        lines.append(f"⭐ <b>VIP gặp rủi ro</b> ({vip.get('count', 0)} KH)")
        for c in vip.get("customers", [])[:10]:
            if isinstance(c, dict):
                name = c.get("name", "?")
                lo = c.get("last_order", "Chưa mua")
                days = c.get("days_since")
                days_str = f" ({days} ngày)" if days is not None else ""
                lines.append(f"  • {name} — đơn cuối: {lo}{days_str}")
        lines.append("")

    if section in ("all", "retention"):
        rt = d.get("retention", {})
        lines.append("📊 <b>Retention</b>")
        lines.append(f"  • KH active (<30 ngày): <b>{rt.get('active_customers', 0)}</b>")
        lines.append(f"  • Tổng KH: <b>{rt.get('total_customers', 0)}</b>")
        lines.append(f"  • Tỷ lệ giữ chân: <b>{_pct(rt.get('retention_rate_pct', 0))}</b>")
        lines.append("")

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
    """Dedicated formatter for odoo_flash_report (midday/eod).
    Keys: revenue_today, orders_today, leads_today, collections_today,
    open_issues.{overdue_invoices, sla_breached_leads, overdue_tasks},
    EOD adds: delta_vs_yesterday.{revenue, leads, collections}
    """
    d = _safe_json(raw)
    rtype = report_type or d.get("report_type", "midday")
    title = "EOD REPORT" if rtype == "eod" else "MIDDAY REPORT"
    icon = "🌙" if rtype == "eod" else "☀️"
    lines = [f"{icon} <b>{title} — {d.get('date', '')}</b>", ""]

    # Main metrics
    lines.append("💰 <b>Doanh thu hôm nay:</b> " + _money(d.get("revenue_today", 0)) + " VND")
    lines.append(f"🛒 <b>Đơn hàng:</b> {d.get('orders_today', 0)}")
    lines.append(f"🎯 <b>Leads mới:</b> {d.get('leads_today', 0)}")
    lines.append("💵 <b>Thu hồi nợ:</b> " + _money(d.get("collections_today", 0)) + " VND")
    lines.append("")

    # Open issues
    issues = d.get("open_issues", {})
    lines.append("⚠️ <b>Vấn đề cần xử lý</b>")
    lines.append(f"  • HĐ quá hạn: <b>{issues.get('overdue_invoices', 0)}</b>")
    lines.append(f"  • Leads vi phạm SLA: <b>{issues.get('sla_breached_leads', 0)}</b>")
    lines.append(f"  • Task quá hạn: <b>{issues.get('overdue_tasks', 0)}</b>")

    # EOD delta
    delta = d.get("delta_vs_yesterday")
    if delta and isinstance(delta, dict):
        lines.append("")
        lines.append("📈 <b>So với hôm qua</b>")
        rev_delta = delta.get("revenue", 0)
        rev_icon = "🔼" if rev_delta >= 0 else "🔽"
        lines.append(f"  {rev_icon} Doanh thu: {'+' if rev_delta >= 0 else ''}{_money(rev_delta)} VND")
        leads_delta = delta.get("leads", 0)
        leads_icon = "🔼" if leads_delta >= 0 else "🔽"
        lines.append(f"  {leads_icon} Leads: {'+' if leads_delta >= 0 else ''}{leads_delta}")
        coll_delta = delta.get("collections", 0)
        coll_icon = "🔼" if coll_delta >= 0 else "🔽"
        lines.append(f"  {coll_icon} Thu hồi nợ: {'+' if coll_delta >= 0 else ''}{_money(coll_delta)} VND")

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


def format_pending_approvals(raw: str) -> str:
    d = _safe_json(raw)
    pending_count = d.get("pending_count", 0)
    requests = d.get("requests", [])

    lines = [f"📋 <b>YÊU CẦU PHÊ DUYỆT CÔNG NỢ</b> ({pending_count} chờ duyệt)", ""]

    if not requests:
        lines.append("✅ Không có yêu cầu nào chờ duyệt.")
        return "\n".join(lines)

    for req in requests[:10]:
        if isinstance(req, dict):
            name = req.get("name", "?")
            so = req.get("sale_order_id", [0, "?"])
            so_name = so[1] if isinstance(so, list) and len(so) > 1 else str(so)
            partner = req.get("partner_id", [0, "?"])
            partner_name = partner[1] if isinstance(partner, list) and len(partner) > 1 else str(partner)
            amount = _money(req.get("amount_total", 0))
            debt = _money(req.get("outstanding_debt", 0))
            new_total = _money(req.get("new_total_debt", 0))

            lines.append(f"📋 <b>{name}</b>")
            lines.append(f"  • Đơn: {so_name} — KH: {partner_name}")
            lines.append(f"  • Giá trị: {amount} VND | Nợ hiện tại: {debt} VND")
            lines.append(f"  • Tổng nợ mới: {new_total} VND")
            lines.append("")

    if len(requests) > 10:
        lines.append(f"  ... +{len(requests) - 10} yêu cầu khác")

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
    "/hunter_quotes": lambda raw: format_hunter_today(raw, section_override="quotes"),
    "/hunter_first_orders": lambda raw: format_hunter_today(raw, section_override="first_orders"),
    "/hunter_sources": lambda raw: format_hunter_today(raw, section_override="sources"),
    "/khachmoi_homnay": lambda raw: format_hunter_today(raw, section_override="overview"),
    "/farmer_today": format_farmer_today,
    "/farmer_reorder": lambda raw: format_farmer_today(raw, section_override="reorder"),
    "/farmer_sleeping": lambda raw: format_farmer_today(raw, section_override="sleeping"),
    "/farmer_vip": lambda raw: format_farmer_today(raw, section_override="vip"),
    "/farmer_ar": format_farmer_ar,
    "/farmer_retention": lambda raw: format_farmer_today(raw, section_override="retention"),
    "/congno_denhan": lambda raw: format_congno(raw, "due_soon"),
    "/congno_quahan": lambda raw: format_congno(raw, "overdue"),
    "/task_quahan": format_task_overdue,
    "/midday": lambda raw: format_flash_report(raw, "midday"),
    "/eod": lambda raw: format_flash_report(raw, "eod"),
    "/kpi": format_kpi,
    "/pipeline": format_pipeline,
    "/credit": format_credit,
    "/pending_approvals": format_pending_approvals,
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
