# AI Agent Guide — Trinity Masios Odoo

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

## Available MCP Tools (23)

### Discovery & Introspection (6)
- `odoo_server_info` — Server version and connection info
- `odoo_list_models` — List models matching a name filter
- `odoo_model_fields` — All fields with types, required, relations, selections
- `odoo_model_access` — CRUD permissions per security group
- `odoo_model_views` — Form/list/kanban view XML definitions
- `odoo_crm_stages` — Pipeline stages

### CRM (1)
- `odoo_crm_lead_summary` — All leads/opportunities with optional filters

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

## Safety Rules

- **Never delete** records without explicit user confirmation
- **Always check** field names with `odoo_model_fields` before creating/writing
- `odoo_execute` is restricted to allowlisted methods — don't try arbitrary methods
- Credentials are in `.env.local` (local) or `/etc/odoo-mcp/credentials` (server) — never expose them
- **Never expose** API tokens in logs, chat, or commit history
- For SSH operations, use the ssh-devops skill — never hardcode passwords in commands
