# QA Session — Production Readiness Report

**Date:** 2026-03-11
**Auditor:** Claude Opus 4.6 (5 parallel sub-agents)
**Scope:** Full system audit for SME production deployment
**Target Users:** Sales Team, Customer Service, COO/CEO

---

## OVERALL VERDICT

**The system is NOT production-ready.** It is a solid Phase 4 prototype (POC → MVP) with working Telegram-to-Odoo bridge and good CRM/Sales/Credit foundations. There are **12 CRITICAL** and **16 HIGH** priority issues across 5 audit areas that must be resolved before real business use.

## FIX STATUS (Updated 2026-03-11)

Phase 5A local fixes have been applied and deployed. The following items from this report are now RESOLVED:
- MCP server: read_group aggregation, ProtocolError, timeout, logging, delete blocklist, PDF magic bytes, limit caps
- OpenClaw: Telegram allowlist (dmPolicy=allowlist), exec-approvals tightened, send_pdf error handling, delete confirmation
- Custom module: Security access rules added
- Company: Name, country, address updated
- Backup: Daily cron installed

Items still OPEN: Currency USD→VND, test data purge, admin password, user accounts, e-invoice

---

## TABLE OF CONTENTS

1. [Odoo Modules vs MCP Alignment](#1-odoo-modules-vs-mcp-alignment)
2. [Data Quality Assessment](#2-data-quality-assessment)
3. [MCP Server Code Quality](#3-mcp-server-code-quality)
4. [Business Workflow Completeness](#4-business-workflow-completeness)
5. [OpenClaw Bot & PDF Output](#5-openclaw-bot--pdf-output)
6. [Consolidated Action Plan](#6-consolidated-action-plan)

---

## 1. Odoo Modules vs MCP Alignment

### Problem: Only CRM module installed, but MCP tools require Sales + Invoicing + Custom modules

| Model | Required Module | Installed? | Impact |
|-------|----------------|-----------|--------|
| `ir.model`, `ir.ui.view`, `res.partner` | `base` | YES | OK |
| `crm.lead`, `crm.stage` | `crm` | YES | OK |
| `sale.order`, `sale.order.line` | `sale_management` | **NO** | **5 tools CRASH** |
| `account.move` | `account` (Invoicing) | **NO** | **3 tools CRASH** |
| `product.product` | `product` (via sales) | **NO** | Cannot reference products |
| Custom credit fields on `res.partner` | `masios_credit_control` | **NO** | **4 tools CRASH** |
| Dashboard `/dashboard` | `masios_dashboard` | **NO** | Dashboard inaccessible |

### Tool Status Scorecard

| Status | Count | Tools |
|--------|-------|-------|
| Working (CRM only) | 8 (31%) | server_info, list_models, model_fields, model_access, model_views, crm_stages, crm_lead_summary, pipeline_by_stage |
| CRASHING | 12 (46%) | sale_order_summary, create_sale_order, confirm_sale_order, create_invoice_from_so, sale_order_pdf, invoice_summary, invoice_pdf, create_customer, customer_credit_status, customer_set_classification, customers_exceeding_credit, dashboard_kpis (partial) |
| Generic (depends) | 5 | search_read, count, create, write, delete |
| Advanced | 1 | execute (depends on model) |

### REQUIRED ACTION
Install modules in order:
1. `sale_management` (auto-installs `account`, `product`)
2. `masios_credit_control` (depends on sale_management + account)
3. `masios_dashboard` (depends on all above + `website`)

---

## 2. Data Quality Assessment

**Status: ALL MOCK/TEST DATA — not production-ready**

| Area | Rating | Key Issues |
|------|--------|-----------|
| Company Setup | **MOCK** | Name = "My Company", Country = US, Currency = USD (should be VND) |
| CRM Leads | **MOCK** | 3 test leads, all revenue = 0, all in "New" stage |
| Customers | **MOCK** | 11 records: 3 named "test", duplicate entries, fake emails (example.com), reused phone numbers |
| Products | **NEEDS CLEANUP** | 3 products with reasonable VND pricing, but too few and wrong currency |
| Sale Orders | **MOCK** | 7 orders all from same day, 2 customers, amounts in "USD" but VND-scale (98.9M) |
| Invoices | **MOCK** | 1 invoice, NULL date, no payment recorded |
| Credit Control | **MOCK** | Only 1 partner has credit limit set |
| Dashboard KPIs | **MOCK** | Pipeline value = 0, revenue booked = 0, no real business activity |

### CRITICAL: Currency Misconfiguration
All monetary amounts are recorded as USD but are clearly VND values (e.g., 98,900,000 "USD"). This must be fixed BEFORE entering real data — changing currency retroactively is extremely difficult.

### REQUIRED ACTIONS
1. Fix company: name, country = Vietnam, currency = VND, address, tax ID
2. Purge ALL test data (customers, leads, orders, invoices)
3. Set up proper product catalog with categories and VND pricing
4. Configure Vietnamese chart of accounts and VAT rates (8%/10%)
5. Change admin password from default (admin/admin)
6. Create named user accounts per employee

---

## 3. MCP Server Code Quality

### CRITICAL Issues (1)

| Issue | Detail |
|-------|--------|
| Dashboard KPIs silently wrong when >500 records | `odoo_dashboard_kpis` and `odoo_pipeline_by_stage` use `limit=500` then sum client-side. Beyond 500 records, revenue/pipeline/debt numbers are INCORRECT with no warning. Must use `read_group` aggregation. |

### HIGH Issues (5)

| Issue | Detail |
|-------|--------|
| `ProtocolError` not caught | Odoo restart/502/503 causes unhandled exception crash. Add `xmlrpc.client.ProtocolError` to error decorator. |
| N+1 queries in `pipeline_by_stage` | Fetches all stages then queries each separately. Use `read_group` instead. |
| No logging/audit trail | Zero use of Python `logging`. Cannot debug, monitor, or audit in production. |
| No XML-RPC timeout | Hung Odoo = hung MCP server. `ServerProxy` has no timeout set. |
| Dashboard uses client-side sums | 4 separate XML-RPC calls with limit=500, summing in Python. Should be Postgres-side via `read_group`. |

### MEDIUM Issues (11)

| Issue | Detail |
|-------|--------|
| WebSocket auth bypass risk | Bearer token middleware only checks `scope["type"] == "http"`, SSE may use websocket scope |
| `odoo_delete` no safeguards | Can delete any model's records including system tables (ir.*, res.users) |
| `fields_get_cached` no invalidation | LRU cache stale after module install/upgrade until server restart |
| No rate limiting | Unlimited requests per caller |
| No health check endpoint | No `/health` for monitoring |
| Fragile PDF detection | Checks for `<title>` instead of PDF magic bytes `%PDF-` |
| `odoo_execute` args not validated | `args` and `kwargs` not checked for correct types (list/dict) |
| `crm_lead_summary` limit uncapped | No upper bound, can pull entire CRM database |
| Multi-step operation no rollback | Create succeeds but read-back fails = confusing UX |
| Global mutable `_client` state | Not thread-safe for concurrent requests |
| Domain filter cost injection | Expensive domain expressions not validated |

### TOP 3 FIXES (impact/effort)
1. Replace `limit=500 + sum()` with `read_group` (~30 min)
2. Add `ProtocolError` to error decorator + XML-RPC timeout (~10 min)
3. Add Python `logging` module (~1 hour)

---

## 4. Business Workflow Completeness

### Sales Team

| Requirement | Status | Priority |
|-------------|--------|----------|
| Lead/opportunity management | PARTIAL — CRM tools exist, no Telegram workflow | MEDIUM |
| Quotation → Confirm → Invoice | YES | — |
| Product catalog / pricelist | PARTIAL — products queryable, no management via MCP | HIGH |
| Customer management | YES | — |
| PDF quotations via Telegram | YES | — |
| **Sales reporting / targets / commissions** | **NO** | **CRITICAL** |
| **Email integration (send quotes)** | **NO** | **HIGH** |
| **Payment tracking/registration** | **PARTIAL** — no payment recording tool | **HIGH** |

### Customer Service

| Requirement | Status | Priority |
|-------------|--------|----------|
| Customer lookup (phone/email/name) | YES | — |
| Order status check | YES | — |
| Invoice/payment status | YES | — |
| Credit limit check | YES | — |
| **Complaint/ticket management** | **NO** — no helpdesk module | **CRITICAL** |
| Customer history (360 view) | PARTIAL — requires multiple queries | MEDIUM |

### COO/CEO

| Requirement | Status | Priority |
|-------------|--------|----------|
| Revenue dashboard | YES — `/dashboard` + MCP tool | — |
| Pipeline overview | YES | — |
| Outstanding debt/AR aging | PARTIAL — no 30/60/90 day aging | HIGH |
| **Sales team performance** | **NO** | **CRITICAL** |
| Customer acquisition metrics | PARTIAL — lead count only | HIGH |
| Top customers report | NO | MEDIUM |
| Monthly/quarterly trends | NO | HIGH |
| Export to Excel/PDF | NO | MEDIUM |

### Cross-Cutting Concerns

| Requirement | Status | Priority |
|-------------|--------|----------|
| Vietnamese language | PARTIAL — custom modules in VN, Odoo UI not confirmed | MEDIUM |
| **Vietnamese e-invoice (hóa đơn điện tử)** | **NO** — legally required | **CRITICAL** |
| **Multi-user access control** | **NO** — empty security CSV, single admin credential | **CRITICAL** |
| Approval workflows | PARTIAL — credit check on confirm, no discount/override approval | HIGH |
| Notification/alert system | PARTIAL — dashboard only, no proactive push | HIGH |
| Mobile accessibility | PARTIAL — Telegram works, dashboard not optimized | LOW |
| **Data backup/recovery** | **NO** — disk at 88%, Phase 5 not started | **CRITICAL** |

### Completely Missing Workflows

1. **Purchase/Procurement** — no supplier management, no purchase orders
2. **Inventory/Warehouse** — no stock tracking, no delivery orders
3. **Payment Registration** — cannot record customer payments
4. **Refund/Credit Notes** — no returns workflow
5. **Bank Reconciliation** — no bank statement matching
6. **Tax Configuration** — no VAT setup for Vietnam
7. **User/Role Management** — single admin account for everything

### User Training Materials

| Area | Status | Priority |
|------|--------|----------|
| Sales team user guide | NO | HIGH |
| Customer service guide | NO | HIGH |
| COO dashboard guide | NO | MEDIUM |
| Telegram bot usage guide | PARTIAL — SKILL.md is technical, not end-user | HIGH |

---

## 5. OpenClaw Bot & PDF Output

### CRITICAL Issues (3)

| Issue | Detail |
|-------|--------|
| **No Telegram whitelist** | `allowFrom: ["*"]` — ANY Telegram user can access the bot, query all data, create/modify/delete records |
| **Elevated access to ALL users** | `elevated.allowFrom.telegram: ["*"]` + `elevatedDefault: full` + `exec.security: full` = unlimited shell access |
| **exec-approvals too broad** | `python3 *` allows running ANY Python code; `cat *` can read any file including tokens/credentials |

### HIGH Issues (4)

| Issue | Detail |
|-------|--------|
| No conversation audit logging | Financial operations (orders, invoices, credit) with no audit trail |
| No rate limiting per user | Can spam bot with unlimited requests |
| No /help or welcome message | First-time users get zero guidance |
| No delete confirmation | User can say "delete all customers" and bot will execute |

### MEDIUM Issues (7)

| Issue | Detail |
|-------|--------|
| `send_pdf.py` no error handling | No try/except — empty stdin, missing keys, corrupt base64 = raw Python traceback |
| No delete safeguard in SKILL.md | Bot can delete records without confirmation workflow |
| No log rotation | Logs grow unbounded, server disk at 88% |
| No admin commands | No way to check bot status, block users, restart without SSH |
| No user onboarding flow | No `/start` handler |
| Ambiguous request handling | LLM-dependent, no explicit disambiguation instructions |
| No error message templates | Raw JSON/tracebacks may leak to user |

### REQUIRED ACTIONS
1. Lock `allowFrom` to specific Telegram user IDs: `["2048339435", "1481072032"]`
2. Restrict exec-approvals: `python3 /home/openclaw/.openclaw/workspace/send_pdf.py *` instead of `python3 *`
3. Add try/except to `send_pdf.py`
4. Add delete confirmation workflow in SKILL.md
5. Add `/help` message to IDENTITY.md or agent system prompt

---

## 6. Consolidated Action Plan

### Phase 5A: CRITICAL (Must fix before any real use)

| # | Action | Area | Effort |
|---|--------|------|--------|
| 1 | Install `sale_management` module (pulls in account, product) | Odoo | 30 min |
| 2 | Install `masios_credit_control` + `masios_dashboard` custom modules | Odoo | 30 min |
| 3 | Fix company: name, country=VN, currency=VND, address, tax ID | Odoo | 1 hr |
| 4 | Purge ALL test/mock data | Odoo | 1 hr |
| 5 | Change admin password, create user accounts per employee | Odoo | 1 hr |
| 6 | Lock Telegram bot `allowFrom` to whitelisted user IDs | OpenClaw | 15 min |
| 7 | Restrict `exec-approvals.json` patterns | OpenClaw | 15 min |
| 8 | Set up automated database backup (pg_dump cron) | Server | 2 hr |
| 9 | Fix MCP `dashboard_kpis` — use `read_group` instead of `limit=500 + sum()` | MCP | 1 hr |
| 10 | Add `ProtocolError` to MCP error decorator + XML-RPC timeout | MCP | 15 min |
| 11 | Fill `ir.model.access.csv` in `masios_credit_control` | Custom Module | 30 min |
| 12 | Add error handling to `send_pdf.py` | OpenClaw | 30 min |

### Phase 5B: HIGH (Should fix for meaningful production)

| # | Action | Area | Effort |
|---|--------|------|--------|
| 13 | Add Python logging to MCP server | MCP | 2 hr |
| 14 | Configure Vietnamese chart of accounts + VAT (8%/10%) | Odoo | 4 hr |
| 15 | Add payment registration MCP tool | MCP | 2 hr |
| 16 | Add email sending capability (outgoing mail server) | Odoo | 2 hr |
| 17 | Create AR aging report (30/60/90 days) | MCP/Dashboard | 3 hr |
| 18 | Add sales team performance tracking | Dashboard | 4 hr |
| 19 | Add approval workflow for credit limit overrides | Custom Module | 4 hr |
| 20 | Create end-user guides for each department | Docs | 8 hr |
| 21 | Add Telegram bot /help and onboarding flow | OpenClaw | 2 hr |
| 22 | Add conversation audit logging | OpenClaw | 3 hr |
| 23 | Add delete confirmation workflow | SKILL.md | 1 hr |
| 24 | Add proactive notifications (overdue invoices, credit alerts) | MCP/Bot | 4 hr |
| 25 | Investigate Vietnamese e-invoice integration (MISA/VNPT/SInvoice) | Odoo | 8+ hr |
| 26 | Set up disk monitoring + cleanup automation | Server | 2 hr |
| 27 | Product catalog expansion + pricelist management | Odoo | 4 hr |
| 28 | Add MCP health check endpoint | MCP | 1 hr |

### Phase 5C: MEDIUM (Nice to have)

| # | Action | Effort |
|---|--------|--------|
| 29 | Vietnamese language pack installation | 1 hr |
| 30 | Top customers report on dashboard | 2 hr |
| 31 | Unified customer 360 view | 4 hr |
| 32 | Dashboard export to Excel/PDF | 3 hr |
| 33 | Monthly/quarterly trend charts | 4 hr |
| 34 | Lead management workflow in Telegram | 2 hr |
| 35 | MCP cache invalidation mechanism | 2 hr |
| 36 | Rate limiting on MCP server | 2 hr |
| 37 | Mobile-optimized dashboard | 4 hr |

---

## Appendix: Module Dependency Tree

```
base (always installed)
├── crm (installed) ← CRM tools work
├── sale_management (NOT installed) ← 5 tools broken
│   ├── sale
│   ├── account ← 3 tools broken
│   └── product
├── masios_credit_control (NOT installed) ← 4 tools broken
│   ├── sale_management
│   └── account
└── masios_dashboard (NOT installed) ← dashboard broken
    ├── masios_credit_control
    ├── crm
    └── website
```

---

*Report generated by 5 parallel QA agents analyzing: module dependencies, live data quality, code security, business workflows, and bot deployment.*
