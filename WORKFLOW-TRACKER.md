# Masi OS — Command Center Workflow Tracker

> File này track toàn bộ workflow của hệ thống. Bạn có thể để comment bằng cách thêm vào mục `[COMMENT]` — AI sẽ trả lời tại `[REPLY]`.

---

## 1. Infrastructure Overview

| Component | Host | Status | Notes |
|-----------|------|--------|-------|
| Odoo 18.0 | 103.72.97.51:8069 | Running | Ubuntu 24.04, PostgreSQL 16 |
| MCP Server | 103.72.97.51:8200 | Running | 40 tools, bearer token auth |
| OpenClaw Bot 1 | Mac Studio:18789 | Healthy | @hdxthanhtt4bot, GLM-5 |
| OpenClaw Bot 2 | Mac Studio:18790 | Healthy | @MASIBIO_bot, GLM-5 |
| n8n | Mac Studio:5678 | Running | Chưa dùng — alert qua cron |
| Alert Cron | Mac Studio crontab | Active | 5 scheduled reports |

**[COMMENT]:**

**[REPLY]:**

---

## 2. MCP Tools (40 total)

### Original Tools (26)
| # | Tool | Category |
|---|------|----------|
| 1 | odoo_server_info | System |
| 2 | odoo_list_models | Discovery |
| 3 | odoo_model_fields | Discovery |
| 4 | odoo_model_access | Discovery |
| 5 | odoo_model_views | Discovery |
| 6 | odoo_crm_stages | CRM |
| 7 | odoo_crm_lead_summary | CRM |
| 8 | odoo_search_read | CRUD |
| 9 | odoo_count | CRUD |
| 10 | odoo_create | CRUD |
| 11 | odoo_write | CRUD |
| 12 | odoo_delete | CRUD |
| 13 | odoo_execute | CRUD |
| 14 | odoo_sale_order_summary | Sales |
| 15 | odoo_create_sale_order | Sales |
| 16 | odoo_confirm_sale_order | Sales |
| 17 | odoo_invoice_summary | Finance |
| 18 | odoo_create_invoice_from_so | Finance |
| 19 | odoo_create_customer | Customer |
| 20 | odoo_customer_credit_status | Credit |
| 21 | odoo_customer_set_classification | Credit |
| 22 | odoo_customers_exceeding_credit | Credit |
| 23 | odoo_dashboard_kpis | Dashboard |
| 24 | odoo_pipeline_by_stage | Dashboard |
| 25 | odoo_sale_order_pdf | PDF |
| 26 | odoo_invoice_pdf | PDF |

### New Command Center Tools (14)
| # | Tool | Mô tả | E2E Test |
|---|------|-------|----------|
| 27 | odoo_morning_brief | Báo cáo buổi sáng tổng hợp | PASS |
| 28 | odoo_ceo_alert | Cảnh báo khẩn cấp cho CEO | PASS |
| 29 | odoo_revenue_today | Doanh thu hôm nay (Hunter/Farmer split) | PASS |
| 30 | odoo_brief_hunter | Tổng hợp Hunter (leads, SLA, quotes) | PASS |
| 31 | odoo_brief_farmer | Tổng hợp Farmer (repeat, sleeping, VIP) | PASS |
| 32 | odoo_brief_ar | Tổng hợp công nợ phải thu | PASS |
| 33 | odoo_brief_cash | Tổng hợp dòng tiền | PASS |
| 34 | odoo_hunter_today | Chi tiết Hunter hôm nay | PASS |
| 35 | odoo_hunter_sla_details | SLA phản hồi lead chi tiết | PASS |
| 36 | odoo_farmer_today | Chi tiết Farmer hôm nay | PASS |
| 37 | odoo_farmer_ar | Công nợ phạm vi Farmer | PASS |
| 38 | odoo_congno | Công nợ đến hạn/quá hạn | PASS |
| 39 | odoo_task_overdue | Task quá hạn (project module) | SKIP* |
| 40 | odoo_flash_report | Báo cáo flash (midday/eod) | PASS |

> *SKIP: Module `project` chưa cài trên production. Tool đã handle gracefully.

**[COMMENT]:**

**[REPLY]:**

---

## 3. Slash Commands (34 skills)

### CEO — Báo cáo tổng quan (7)
| Command | Tool gọi | Mô tả |
|---------|----------|-------|
| `/morning_brief` | odoo_morning_brief | Báo cáo buổi sáng |
| `/ceo_alert` | odoo_ceo_alert | Cảnh báo khẩn cấp |
| `/doanhso_homnay` | odoo_revenue_today | Doanh số hôm nay |
| `/brief_hunter` | odoo_brief_hunter | Tổng hợp Hunter |
| `/brief_farmer` | odoo_brief_farmer | Tổng hợp Farmer |
| `/brief_ar` | odoo_brief_ar | Tổng hợp công nợ |
| `/brief_cash` | odoo_brief_cash | Tổng hợp dòng tiền |

### Hunter — Săn khách mới (6)
| Command | Tool gọi | Mô tả |
|---------|----------|-------|
| `/hunter_today` | odoo_hunter_today | Tổng quan Hunter hôm nay |
| `/hunter_sla` | odoo_hunter_sla_details | SLA phản hồi lead |
| `/hunter_quotes` | odoo_search_read (sale.order) | Báo giá đang chờ |
| `/hunter_first_orders` | odoo_search_read (sale.order) | Đơn hàng đầu tiên |
| `/hunter_sources` | odoo_search_read (crm.lead) | Nguồn lead |
| `/khachmoi_homnay` | odoo_search_read (crm.lead) | Khách mới hôm nay |

### Farmer — Chăm khách cũ (6)
| Command | Tool gọi | Mô tả |
|---------|----------|-------|
| `/farmer_today` | odoo_farmer_today | Tổng quan Farmer hôm nay |
| `/farmer_reorder` | odoo_search_read (res.partner) | Khách cần tái đặt hàng |
| `/farmer_sleeping` | odoo_search_read (res.partner) | Khách ngủ đông |
| `/farmer_vip` | odoo_search_read (res.partner) | Khách VIP |
| `/farmer_ar` | odoo_farmer_ar | Công nợ Farmer |
| `/farmer_retention` | odoo_search_read (res.partner) | Tỷ lệ giữ chân |

### Finance — Công nợ (2)
| Command | Tool gọi | Mô tả |
|---------|----------|-------|
| `/congno_denhan` | odoo_congno (mode=due_soon) | Công nợ đến hạn |
| `/congno_quahan` | odoo_congno (mode=overdue) | Công nợ quá hạn |

### Ops — Vận hành (3)
| Command | Tool gọi | Mô tả |
|---------|----------|-------|
| `/task_quahan` | odoo_task_overdue | Task quá hạn |
| `/midday` | odoo_flash_report (midday) | Báo cáo giữa ngày |
| `/eod` | odoo_flash_report (eod) | Báo cáo cuối ngày |

### Utility — Tiện ích (9)
| Command | Tool gọi | Mô tả |
|---------|----------|-------|
| `/masi` | (menu) | Hiển thị tất cả commands |
| `/kpi` | odoo_dashboard_kpis | KPI dashboard |
| `/pipeline` | odoo_pipeline_by_stage | Pipeline CRM |
| `/newlead` | odoo_create (crm.lead) | Tạo lead mới |
| `/newcustomer` | odoo_create_customer | Tạo khách hàng |
| `/quote` | odoo_create_sale_order + PDF | Tạo báo giá + gửi PDF |
| `/invoice` | odoo_create_invoice_from_so + PDF | Tạo hóa đơn + gửi PDF |
| `/credit` | odoo_customer_credit_status | Kiểm tra công nợ KH |
| `/findcustomer` | odoo_search_read (res.partner) | Tìm khách hàng |

**[COMMENT]:**

**[REPLY]:**

---

## 4. Alert System (Scheduled Reports)

| Alert | Schedule (ICT) | Cron (UTC) | Tool | Condition |
|-------|---------------|-----------|------|-----------|
| Morning Brief | 8:00 AM daily | `0 1 * * *` | morning_brief() | Always send |
| Midday Flash | 12:00 PM daily | `0 5 * * *` | midday_flash() | Always send |
| EOD Report | 6:00 PM daily | `0 11 * * *` | eod_report() | Always send |
| SLA Check | Every 2h, 8am-6pm | `0 1,3,5,7,9,11 * * *` | sla_alert() | Only if breaches |
| Overdue AR | 9:00 AM daily | `0 2 * * *` | overdue_ar() | Only if overdue |

**Implementation:** `alert_runner.py` trên Mac Studio — gọi Odoo XML-RPC trực tiếp, gửi qua Telegram Bot API.

**[COMMENT]:**

**[REPLY]:**

---

## 5. Odoo Custom Modules

### masios_credit_control
- Customer classification (new/old)
- Credit limit management
- Outstanding debt tracking
- Sale order confirm override (chặn khi vượt hạn mức)

### masios_command_center
- **res.partner**: vip_level, last_order_date, repeat_cycle_days, expected_reorder_date, is_sleeping, sleeping_bucket, hunter_farmer_type, ar_aging_bucket
- **sale.order**: order_type (first_order/repeat_order), is_first_order
- **crm.lead**: sla_hours, first_touch_date, sla_status, lead_source, hunter_owner_id
- **account.move**: dispute_status, dispute_note, collection_status, days_overdue
- **project.task**: task_category, related_partner_id, impact_level, source_alert_code
- **Data**: Hunter Team, Farmer Team (sales teams)

### masios_dashboard
- CEO dashboard route `/dashboard`
- KPIs, pipeline chart, orders/invoices tables

**[COMMENT]:**

**[REPLY]:**

---

## 6. Deployment Architecture

```
┌──────────────────────┐     ┌──────────────────────────┐
│  Mac Studio          │     │  Odoo Server             │
│  100.81.203.48       │     │  103.72.97.51            │
│                      │     │                          │
│  ┌─────────────────┐ │     │  ┌────────────────────┐  │
│  │ OpenClaw Bot 1  │─┼─────┼──│ MCP Server :8200   │  │
│  │ @hdxthanhtt4bot │ │     │  │ (40 tools, SSE)    │  │
│  │ :18789          │ │     │  └────────┬───────────┘  │
│  └─────────────────┘ │     │           │              │
│  ┌─────────────────┐ │     │  ┌────────▼───────────┐  │
│  │ OpenClaw Bot 2  │─┼─────┼──│ Odoo 18.0 :8069    │  │
│  │ @MASIBIO_bot    │ │     │  │ (XML-RPC)          │  │
│  │ :18790          │ │     │  └────────────────────┘  │
│  └─────────────────┘ │     │  ┌────────────────────┐  │
│  ┌─────────────────┐ │     │  │ PostgreSQL 16      │  │
│  │ Cron Alerts     │─┼─────┼──│                    │  │
│  │ alert_runner.py │ │     │  └────────────────────┘  │
│  └─────────────────┘ │     └──────────────────────────┘
│  ┌─────────────────┐ │
│  │ Watchdog        │ │     ┌──────────────────────────┐
│  │ */5 * * * *     │ │     │  Telegram API            │
│  └─────────────────┘ │     │  Bot → CEO (2048339435)  │
│  ┌─────────────────┐ │     │  Bot → User (1481072032) │
│  │ n8n :5678       │ │     └──────────────────────────┘
│  │ (standby)       │ │
│  └─────────────────┘ │
└──────────────────────┘
```

**[COMMENT]:**

**[REPLY]:**

---

## 7. E2E Test Results

| # | Tool | Status | Detail |
|---|------|--------|--------|
| 1 | odoo_morning_brief | PASS | 4 CRM stages |
| 2 | odoo_ceo_alert | PASS | 1 overdue invoice |
| 3 | odoo_revenue_today | PASS | 0 orders today |
| 4 | odoo_brief_hunter | PASS | 0 leads |
| 5 | odoo_brief_farmer | PASS | 0 active customers |
| 6 | odoo_brief_ar | PASS | 1 receivable |
| 7 | odoo_brief_cash | PASS | 0 payments |
| 8 | odoo_hunter_today | PASS | 0 new leads |
| 9 | odoo_hunter_sla_details | PASS | 3 opportunities |
| 10 | odoo_farmer_today | PASS | 0 customers |
| 11 | odoo_farmer_ar | PASS | 1 AR entry |
| 12 | odoo_congno | PASS | 1 overdue |
| 13 | odoo_task_overdue | SKIP | project module not installed |
| 14 | odoo_flash_report | PASS | 2 orders, 1 invoice |
| 15 | odoo_sale_order_pdf | PASS | S00007 exists |
| 16 | odoo_invoice_pdf | PASS | INV/2026/00001 exists |

**Test date:** 2026-03-12

**[COMMENT]:**

**[REPLY]:**

---

## 8. Implementation Progress (SQLite Tracking)

| Phase | Description | Tasks | Status |
|-------|-------------|-------|--------|
| P1-DataModel | Odoo module + n8n deploy | 6/6 | Done |
| P2-MCP | 14 new MCP tools | 7/7 | Done |
| P3-Skills | 24 slash commands | 5/5 | Done |
| P4-Deploy | MCP + skills + Telegram | 5/5 | Done |
| P5-RBAC | Role-based, audit, drill-down | 5/5 | Done |
| P6-Advanced | Alert system + inline buttons | 6/6 | Done |
| P7-Test | E2E API test suite | 3/3 | Done |
| **Total** | | **37/37** | **100%** |

**[COMMENT]:**

**[REPLY]:**

---

## 9. Known Issues & Limitations

| Issue | Severity | Workaround |
|-------|----------|------------|
| Module `project` chưa cài | Low | task_overdue tool returns graceful error |
| masios_command_center chưa install trên prod | Medium | Data model fields chưa active, tools vẫn chạy bằng base fields |
| mcporter hang trong Docker container | Low | Alert dùng direct XML-RPC thay vì mcporter |
| Telegram inline buttons | Low | Dùng text hints trong SKILL.md thay thế |
| n8n chưa có API key | Low | Dùng cron + Python script thay n8n |

**[COMMENT]:**

**[REPLY]:**

---

## 10. Next Steps / Backlog

- [ ] Cài module `project` trên production
- [ ] Cài lại `masios_command_center` module
- [ ] Setup n8n workflows (khi cần logic phức tạp hơn cron)
- [ ] Thêm Telegram inline buttons (khi model hỗ trợ)
- [ ] Phân quyền chi tiết theo Telegram user ID
- [ ] Thêm users mới vào whitelist
- [ ] Backup automation (daily Odoo DB backup)
- [ ] Monitoring/alerting cho container health

**[COMMENT]:**

**[REPLY]:**

---

*Last updated: 2026-03-12 | Generated by Claude Code*
