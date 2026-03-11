# AI Agent Guide — Trinity Masios Odoo

## Project Status

| Phase | Mô tả | Trạng thái |
|-------|--------|-----------|
| Phase 0 | Odoo 18 self-hosted + MCP bridge | Done |
| Phase 1 | CRM tools + OpenClaw integration | Done |
| Phase 2 | Sale Order + Invoice tools | Done |
| Phase 3 | Credit Control module + partner classification | Done |
| Phase 4 | CEO Dashboard + full test suite | Done |
| Phase 5 | Hardening (backup, monitoring, alerting) | Pending |

**Test Results:** 10/10 test cases passed, tất cả 24 MCP tools hoạt động.
Xem chi tiết testcase tại `deploy/openclaw/testcase-slides.pptx` và `deploy/openclaw/testcase-slides.html`.

## How to Interact with Odoo

You have access to a live Odoo 18.0 instance via MCP tools. Use them to query, create, and modify records in real-time.

### If you're a Claude Code agent
MCP tools are auto-loaded from `.mcp.json`. Call them directly:
- `odoo_list_models(filter="crm")` — discover models
- `odoo_model_fields(model="crm.lead")` — inspect field types and constraints
- `odoo_search_read(model="crm.lead", fields="name,partner_id,stage_id")` — query data
- `odoo_create(model="res.partner", values='{"name":"..."}')` — create records

### If you're an OpenClaw agent
Use the `mcporter` skill:
```bash
mcporter call odoo.odoo_list_models filter=crm
mcporter call odoo.odoo_model_fields model=crm.lead
mcporter call odoo.odoo_search_read model=crm.lead fields=name,partner_id
```

## Available Skills

### ssh-devops
**When to use:** Server management — deploy code, check logs, monitor services, restart Odoo.
**Trigger:** User asks about server status, deployment, logs, SSH operations.
**Key actions:** SSH via sshpass, systemctl, journalctl, server health checks.

### odoo-selfhost
**When to use:** Odoo-specific tasks — install modules, troubleshoot errors, develop custom addons.
**Trigger:** User asks about Odoo configuration, module development, database issues.
**Key actions:** odoo-bin commands, module scaffolding, database management, Nginx config.

### smart-memory
**When to use:** Automatic — hooks trigger on errors, session start, compaction, and stop.
**What it does:** Logs errors and fixes to SQLite, searches past solutions, preserves project context.
**Manual use:** `python3 smart-memory-db.py search-errors '{"query":"postgresql auth"}'`

## CRM Data Model (Key Models)

| Model | Description | Required Fields |
|-------|-------------|-----------------|
| `crm.lead` | Leads & Opportunities | `name`, `type` (lead/opportunity) |
| `crm.stage` | Pipeline stages | `name` |
| `crm.team` | Sales teams | `name` |
| `crm.tag` | Lead tags | `name` |
| `res.partner` | Contacts/Companies | `name` |
| `crm.lost.reason` | Why deals were lost | `name` |

### Pipeline Stages
1. **New** (id=1) → 2. **Qualified** (id=2) → 3. **Proposition** (id=3) → 4. **Won** (id=4, is_won=true)

### Sale & Invoice Models
- `sale.order` — Sale orders/quotations. Key fields: `name`, `partner_id`, `date_order`, `amount_total`, `state` (draft/sent/sale/done/cancel), `invoice_status`, `order_line`
- `sale.order.line` — Order lines. Key fields: `product_id`, `product_uom_qty`, `price_unit`, `price_subtotal`
- `account.move` — Invoices/bills. Key fields: `name`, `partner_id`, `move_type` (out_invoice), `invoice_date`, `invoice_date_due`, `amount_total`, `amount_residual`, `state` (draft/posted/cancel), `payment_state`

### Credit Control Fields (res.partner)
Custom fields added by `masios_credit_control` module:
- `customer_classification`: Selection (new/old) — mặc định 'new'
- `credit_allowed`: Boolean computed — True khi classification = 'old'
- `credit_limit`: Monetary — hạn mức công nợ
- `outstanding_debt`: Monetary computed — tổng amount_residual hóa đơn chưa thanh toán
- `credit_available`: Monetary computed — credit_limit - outstanding_debt
- `credit_exceeded`: Boolean computed — True khi vượt hạn mức

## Available MCP Tools (24)

### Discovery & Introspection (6)
- `odoo_server_info` — Server version and connection info
- `odoo_list_models` — List models matching a name filter
- `odoo_model_fields` — All fields with types, required, relations, selections
- `odoo_model_access` — CRUD permissions per security group
- `odoo_model_views` — Form/list/kanban view XML definitions
- `odoo_crm_stages` — Pipeline stages

### CRM (1)
- `odoo_crm_lead_summary` — All leads/opportunities with optional filters

### Customer (1)
- `odoo_create_customer` — Tạo khách hàng mới với đầy đủ thông tin (name, email, phone, company_type, classification, credit_limit)

### Generic CRUD (5)
- `odoo_search_read` — Query with specific fields and domain filters
- `odoo_count` — Count records with optional domain
- `odoo_create` — Create records on any model
- `odoo_write` — Update records
- `odoo_delete` — Delete records

### Advanced (1)
- `odoo_execute` — Call any allowlisted Odoo method

### Sale Orders (3)
- `odoo_sale_order_summary` — List sale orders with optional partner/state filter
- `odoo_create_sale_order` — Create quotation with order lines
- `odoo_confirm_sale_order` — Confirm a sale order (triggers credit check)

### Invoices (2)
- `odoo_invoice_summary` — List invoices with optional partner/state filter
- `odoo_create_invoice_from_so` — Create invoice from confirmed sale order

### Credit Control (3)
- `odoo_customer_credit_status` — Credit info for a customer
- `odoo_customer_set_classification` — Set customer classification (new/old)
- `odoo_customers_exceeding_credit` — List customers exceeding credit limit

### Dashboard (2)
- `odoo_dashboard_kpis` — CEO KPIs (revenue, pipeline, invoices, credit)
- `odoo_pipeline_by_stage` — Pipeline data grouped by stage

## Common Workflows

### Look up what fields a model has
```
odoo_model_fields(model="crm.lead", field_filter="partner")
```

### Create a customer + CRM opportunity
```
# 1. Create contact
odoo_create(model="res.partner", values='{"name":"Acme","company_type":"company"}')
# Returns {"created_id": 10}

# 2. Create opportunity linked to contact
odoo_create(model="crm.lead", values='{"name":"Acme Deal","partner_id":10,"type":"opportunity"}')
```

### Query with filters
```
# Odoo domain filter syntax: [["field","operator",value]]
odoo_search_read(model="crm.lead", domain='[["stage_id","=",1]]', fields="name,expected_revenue")
```

### Move deal through pipeline
```
odoo_write(model="crm.lead", ids="[2]", values='{"stage_id":4}')  # Move to Won
```

### Sales Workflow
1. Tạo báo giá: `odoo_create_sale_order(partner_id, order_lines)`
2. Xác nhận: `odoo_confirm_sale_order(order_id)` — triggers credit check
3. Tạo hóa đơn: `odoo_create_invoice_from_so(order_id)`
4. Xem trạng thái: `odoo_sale_order_summary()`, `odoo_invoice_summary()`

### Credit Control Workflow
1. Xem credit status: `odoo_customer_credit_status(partner_id)`
2. Đổi phân loại: `odoo_customer_set_classification(partner_id, 'old')`
3. DS vượt hạn mức: `odoo_customers_exceeding_credit()`

### CEO Dashboard
- KPI tổng hợp: `odoo_dashboard_kpis()`
- Pipeline theo stage: `odoo_pipeline_by_stage()`
- Truy cập web: `/dashboard` (đăng nhập Odoo)

## Authentication

- **Claude Code (stdio)**: No token needed — runs locally via `.mcp.json`
- **HTTP endpoint**: Requires bearer token in `Authorization` header
  - Generate token: `python3 server.py --generate-token`
  - Token stored in `MCP_API_TOKEN` env var on the server
  - mcporter clients pass it via `--header "Authorization=Bearer <token>"`

## Architecture

```
Telegram User
    ↓
OpenClaw Agent (Docker container)
    ↓
mcporter (MCP client)
    ↓
MCP HTTP Server :8200 (bearer token auth)
    ↓
Odoo XML-RPC :8069
```

### Infrastructure

| Machine | IP | User | Vai trò |
|---------|-----|------|---------|
| Odoo Server | 103.72.97.51 (SSH port 24700) | root | Odoo 18 + MCP HTTP server + PostgreSQL |
| Mac Deploy | 100.81.203.48 (Tailscale) | masios | OrbStack/Docker — chạy OpenClaw bots |

### Custom Modules Deployed

| Module | Đường dẫn | Mô tả |
|--------|----------|-------|
| `masios_credit_control` | `custom-addons/masios_credit_control/` | Credit control + partner classification (new/old), credit limit, outstanding debt |
| `masios_dashboard` | `custom-addons/masios_dashboard/` | CEO dashboard tại `/dashboard` — KPIs, pipeline chart, top customers |

## OpenClaw Docker Deployment

OpenClaw agents chạy trong Docker containers trên Mac deploy machine. Config tại `deploy/openclaw/`.

### Cấu trúc thư mục
```
deploy/openclaw/
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── config/
│   ├── openclaw.template.json    # Template OpenClaw config
│   ├── mcporter.template.json    # Template mcporter config
│   ├── exec-approvals.json       # MCP tool auto-approve list
│   └── workspace/                # Agent workspace
├── testcase-slides.pptx          # Test case slides (PowerPoint)
├── testcase-slides.html          # Test case slides (HTML)
└── gen_testcase_slides.py        # Script tạo slides
```

### Telegram Bots

| Bot | Username | Port | Mô tả |
|-----|----------|------|-------|
| Bot 1 | @hdxthanhtt4bot | 18789 | Dev/test bot |
| Bot 2 | @MASIBIO_bot | 18790 | Production bot |

### Deploy lên máy mới
```bash
# 1. Clone repo
git clone <repo-url> && cd trinity-masios-odoo

# 2. Cấu hình env
cd deploy/openclaw/config
cp openclaw.template.json openclaw.json    # Điền Telegram token, model config
cp mcporter.template.json mcporter.json    # Điền MCP server URL + bearer token

# 3. Build & run
cd deploy/openclaw
docker-compose up -d
```

### Model khuyến nghị
**GLM-5** là model tốt nhất cho tool-calling trong OpenClaw. Các model khác có thể gặp lỗi khi gọi MCP tools qua mcporter.

## Safety Rules

- **Never delete** records without explicit user confirmation
- **Always check** field names with `odoo_model_fields` before creating/writing
- `odoo_execute` is restricted to allowlisted methods — don't try arbitrary methods
- Credentials are in `.env.local` (local) or `/etc/odoo-mcp/credentials` (server) — never expose them
- **Never expose** API tokens in logs, chat, or commit history
- For SSH operations, use the ssh-devops skill — never hardcode passwords in commands
