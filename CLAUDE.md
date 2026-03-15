# Trinity Masios Odoo - Project Guide

## Project Overview
Self-hosted Odoo deployment on Ubuntu server with custom module development capabilities.

## Server Details
- **IP**: 103.72.97.51
- **SSH Port**: 24700
- **User**: root
- **OS**: Ubuntu 24.04 LTS
- **Odoo Version**: 18.0 (Community)
- **Odoo Port**: 8069 (HTTP), 8072 (longpolling)

## Architecture
- Odoo installed at `/opt/odoo/odoo-server/`
- Custom addons at `/opt/odoo/custom-addons/`
- Config at `/etc/odoo.conf`
- Logs at `/var/log/odoo/odoo-server.log`
- Nginx reverse proxy on port 80/443
- PostgreSQL 16 local

## Skills Available
- **ssh-devops**: SSH operations, server management
- **odoo-selfhost**: Odoo install, deploy, module dev, troubleshoot
- **smart-memory**: Error learning via SQLite, project context persistence

## Odoo MCP Server
- Real-time bridge to Odoo via XML-RPC (`.mcp.json` → `mcp/odoo-server/server.py`)
- Credentials in `.env.local` (gitignored), template in `.env.example`
- Server-side creds: `/etc/odoo-mcp/credentials` (chmod 600)
- 55 tools: introspect models/fields/access/views, CRUD, CRM helpers, sales/invoicing, credit control, credit approval, dashboard, execute (allowlisted)
- Use `odoo_model_fields` to get field types, constraints, relations for any model
- Use `odoo_list_models` with filter to discover models (e.g. filter="crm")
- Requires `uv` (Python package runner) — no global install needed

### Authentication
- **stdio mode** (Claude Code): No token needed — runs locally
- **HTTP mode** (remote): Bearer token required
  - Token stored in `MCP_API_TOKEN` env var (in `/etc/odoo-mcp/credentials` on server)
  - Generate: `uv run --with mcp python3 mcp/odoo-server/server.py --generate-token`
  - With token: all HTTP requests must include `Authorization: Bearer <token>` header
  - Auth errors: 401 (missing header), 403 (wrong token)

### Modes
- **stdio** (Claude Code): `.mcp.json` → `uv run` → local process (no token needed)
- **HTTP** (remote): `http://server:8200/sse` → bearer token required

## Masi Telegram Bot v2 (`deploy/masi-bot/`)
Lightweight Telegram bot — direct MCP integration, template-based formatting.

- **Architecture**: python-telegram-bot → **OpenAI SDK (Gemini 3.1 Flash Lite via OpenRouter)** → MCP SSE client → Odoo
- **Deploy**: Systemd service on Odoo server (`/opt/masi-bot/`, `masi-bot.service`)
- **Model**: `google/gemini-3.1-flash-lite-preview` via OpenRouter ($0.25/M input, $1.50/M output)
- **Telegram Bot**: `@hdxthanhtt4bot` (Bot 1)
- **Whitelist**: `2048339435` (CEO), `1481072032` (Hunter Lead), `5001000001` (Farmer Lead)
- **Performance**: Slash commands < 1s (template formatter), free-form chat ~3-10s (LLM)
- **Files**:
  - `bot.py` — Telegram handler, RBAC, conversation memory, HTML formatting, inline button callbacks
  - `agent.py` — OpenAI SDK tool-calling loop + fast path (direct MCP → template)
  - `mcp_client.py` — MCP SSE client, tool discovery, persistent connection
  - `formatter.py` — Python template formatters for 28 slash commands (no LLM)
  - `config.py` — env vars, system prompt, whitelist, TEST_USERS dict, LLM backend config
- **37 slash commands** registered in Telegram menu
- **55 MCP tools** auto-discovered at startup
- **Context injection**: `_active_contexts` dict per user persists entity (partner/order/invoice) across turns
- **Credit approval callbacks**: `CallbackQueryHandler` handles inline Approve/Reject buttons from CEO

### How it works
1. **Slash commands** (`/kpi`, `/morning_brief`, `/pending_approvals`, etc.): Permission check → MCP tool call → Python template format → Telegram HTML. No LLM needed. Sub-second response.
2. **Free-form chat** (`/approve`, `/reject`, create order, etc.): Permission check → Gemini Flash Lite with 55 tools → tool-calling loop → Telegram HTML. ~3-10s response.
3. **Credit approval buttons**: CEO receives inline buttons → `CallbackQueryHandler` → MCP approve/reject → update Telegram message.

### Deploy commands
```bash
# On Odoo server (103.72.97.51)
systemctl status masi-bot    # Check status
systemctl restart masi-bot   # Restart
journalctl -u masi-bot -f    # Tail logs
```

## Mac Deploy Machine (OpenClaw Host — legacy)
- **IP**: 100.81.203.48 (Tailscale)
- **User**: masios
- **Password**: (stored in memory/server-config.md)
- **OS**: macOS 26.3, Apple Silicon (ARM64), Mac Studio
- **Docker**: OrbStack v2.0.5, Docker 29.2.0
- **Deploy paths**:
  - Bot 1: **REPLACED** by Masi Bot v2 on Odoo server
  - Bot 2: `~/openclaw-bot2-native/` (port 18790) — Telegram `@MASIBIO_bot` (native macOS, **disconnected from Odoo**)
- **Telegram whitelist**: `2048339435` (CEO), `1481072032`

## MCP Tools (55 total)
### Core (13): server_info, list_models, model_fields, model_access, model_views, crm_stages, crm_lead_summary, search_read, count, create, write, delete, execute
### Sales & Invoice (7): sale_order_summary, create_sale_order, confirm_sale_order, invoice_summary, create_invoice_from_so, sale_order_pdf, invoice_pdf
### Customer & Credit (4): create_customer, customer_credit_status, customer_set_classification, customers_exceeding_credit
### Credit Approval (4): pending_approvals, approve_credit, reject_credit, approval_history
### Dashboard (2): dashboard_kpis, pipeline_by_stage
### Command Center (14): morning_brief, ceo_alert, revenue_today, brief_hunter, brief_farmer, brief_ar, brief_cash, hunter_today, hunter_sla_details, farmer_today, farmer_ar, congno, task_overdue, flash_report
### Actions (7): mark_contacted, mark_collection, set_dispute, change_owner, escalate, complete_task, audit_log
### Telegram RBAC (4): telegram_check_permission, telegram_get_menu, telegram_list_users, telegram_register_user

## Custom Modules Deployed
- `masios_credit_control` — Customer classification (new/old), credit limits, debt tracking
- `masios_dashboard` — CEO dashboard at `/dashboard` with KPIs, pipeline, orders, invoices
- `masios_credit_approval` — CEO approval workflow for orders exceeding debt threshold

### Credit Approval Workflow
When a sale order is confirmed and customer's total outstanding debt exceeds a configurable threshold (default 20M VND):
1. **Hold**: SO stays in draft, `credit.approval.request` record created
2. **Notify**: Telegram notification sent to CEO with inline ✅ Duyệt / ❌ Từ chối buttons
3. **Approve**: CEO taps Duyệt → SO auto-confirmed, Telegram message updated
4. **Reject**: CEO taps Từ chối → bot asks for reason → SO stays draft, reason logged
5. **History**: Full audit trail in Odoo web (Sales → Phê duyệt công nợ)
6. **Config**: Settings → Sales → Phê duyệt công nợ (threshold, Telegram bot token, CEO chat ID)

Technical details:
- Uses `self.pool.cursor()` autonomous cursor to persist approval request despite UserError rollback
- `bypass_credit_approval` + `bypass_credit_check` context flags for approved orders
- Odoo model calls Telegram Bot API directly via `urllib.request` (no bot dependency)
- System params: `masios_credit_approval.threshold`, `.telegram_bot_token`, `.telegram_ceo_chat_id`

## Git Commit Rules (MANDATORY)
Every commit MUST have a detailed, well-documented message. Never use vague messages like "fix bug", "update code", or "misc changes".

### Commit Message Format
```
<type>(<scope>): <short summary - what changed>

<detailed description - WHY this change was made>

Changes:
- <specific change 1 with file/function names>
- <specific change 2 with file/function names>
- <specific change 3 with file/function names>

<optional: context, trade-offs, or related issues>
```

### Types
- `feat` — new feature or capability
- `fix` — bug fix
- `refactor` — code restructuring without behavior change
- `docs` — documentation only
- `deploy` — deployment, infrastructure, config changes
- `security` — security fixes or hardening
- `test` — test additions or fixes
- `chore` — maintenance, cleanup, dependencies

### Rules
1. **Subject line**: max 72 chars, imperative mood ("Add X" not "Added X")
2. **Body**: explain WHY, not just WHAT. Include context, reasoning, trade-offs
3. **Changes list**: enumerate every significant file/function modified
4. **Scope**: component affected (e.g. `mcp`, `credit-control`, `dashboard`, `credit-approval`, `masi-bot`)
5. **No empty bodies**: every commit must have a description beyond the subject line
6. **Reference issues**: mention related bugs, features, or decisions when applicable

### Examples
```
feat(mcp): Add PDF generation tools for sale orders and invoices

Odoo HTTP report engine generates PDFs but requires session-based auth
(not XML-RPC). Added two new MCP tools that authenticate via /web/session
and download reports as base64-encoded PDFs.

Changes:
- mcp/odoo-server/server.py: Add odoo_sale_order_pdf() and odoo_invoice_pdf()
- mcp/odoo-server/server.py: Add _get_session_and_pdf() helper for HTTP auth

Trade-off: base64 encoding doubles payload size but avoids binary in JSON.
```

## Test Suite

### Unit Tests (137 tests, <1.3s)
```bash
cd deploy/masi-bot && python -m pytest tests/ -v
```

| File | Tests | Coverage |
|------|:-----:|----------|
| `tests/test_agent_helpers.py` | 34 | `_quick_reply`, `_trim_history`, `_extract_pdf`, `_pdf_summary`, `_mcp_tools_to_openai` |
| `tests/test_formatter_helpers.py` | 30 | `_safe_json`, `_money`, `_pct`, `_val`, `_dq` |
| `tests/test_formatter_commands.py` | 21 | `format_command` router + 8 key `format_*` functions |
| `tests/test_md_to_html.py` | 20 | Markdown→Telegram HTML (bold, code, tables, XSS) |
| `tests/test_mcp_parsers.py` | 20 | `_parse_json`, `_parse_domain`, `_parse_ids`, `_parse_values` |
| `tests/test_context_injection.py` | 6 | `_inject_context`, `_extract_entity_from_tool_result` |
| `tests/test_openrouter_hallucination.py` | 3 | Gemini tool-calling accuracy (standalone, calls OpenRouter API) |

### E2E Tests — Odoo Web UI (Playwright)
- `tests/e2e/test_e2e_full.py` — 27 tests across 6 suites

| Suite | Tests | Coverage |
|-------|-------|----------|
| 1 — Welcome Page | 6 | Each role sees role badge, feature cards, quick links |
| 2 — RBAC Menu Visibility | 6 | Each role sees only their allowed Odoo app menus |
| 3 — RBAC URL Blocking | 4 | Forbidden URL access → AccessError dialog or redirect |
| 4 — Credit Control | 5 | Phân loại KH field, Công nợ tab, outstanding_debt, credit_limit |
| 5 — Dashboard KPIs | 3 | CEO sees /dashboard, non-CEO redirected to /welcome |
| 6 — Command Center | 3 | Command Center menu visibility, masios.telegram_user accessible |

```bash
python3 tests/e2e/test_e2e_full.py
```

### E2E Tests — Telegram Bot API (test_server port 8300)

| File | Tests | Coverage |
|------|-------|----------|
| `tests/e2e/test_bot_commands.py` | 27 | All fast-path commands, CEO role, keyword + timing check |
| `tests/e2e/test_bot_rbac.py` | 27 | Full RBAC matrix per spec v1.1 (allowed + blocked per role) |
| `tests/e2e/test_bot_multiturn.py` | 5 | /quote→number, /invoice→number, /findcustomer drill-down, ok-guard |

```bash
python3 tests/e2e/test_bot_commands.py
python3 tests/e2e/test_bot_rbac.py
python3 tests/e2e/test_bot_multiturn.py
```
**Prerequisite:** masi-bot service running on server (port 8300 accessible).

### RBAC Permission Matrix (per Spec v1.1)
| Command | CEO | Hunter | Farmer | Finance | Ops/PM | Admin |
|---------|:---:|:------:|:------:|:-------:|:------:|:-----:|
| morning_brief | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| ceo_alert | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| doanhso_homnay | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| brief_hunter | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| brief_farmer | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| brief_ar | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| brief_cash | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| hunter_today/sla/quotes/etc | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| farmer_today/reorder/etc | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| congno_denhan | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| congno_quahan | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| task_quahan | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| midday / eod | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| pending_approvals | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

Stored in Odoo: `masios.telegram_role` records (id 1-6).

### Test Users
| Role | Login | Password |
|------|-------|----------|
| CEO | admin | (set via ODOO_ADMIN_PASSWORD env var) |
| Hunter Lead | hung.hunter@masibio.vn | (set via ODOO_TEST_PASSWORD env var) |
| Farmer Lead | mai.farmer@masibio.vn | (set via ODOO_TEST_PASSWORD env var) |
| Finance | phuc.finance@masibio.vn | (set via ODOO_TEST_PASSWORD env var) |
| Ops/PM | dat.ops@masibio.vn | (set via ODOO_TEST_PASSWORD env var) |
| Admin/Tech | tung.admin@masibio.vn | (set via ODOO_TEST_PASSWORD env var) |

## Conventions
- **SSH platform rules**:
  - **macOS**: Use `sshpass` + `ssh` (native, fast) — install via `brew install hudochenkov/sshpass/sshpass`
  - **Windows**: Use `paramiko` (Python) — `sshpass` fails on Windows due to TTY issues
  - Odoo server: `ssh -p 24700 root@103.72.97.51` (no password needed)
  - Mac Studio: `sshpass -p '$MAC_STUDIO_PASSWORD' ssh masios@100.81.203.48` (macOS) or `paramiko.connect('100.81.203.48', username='masios', password=os.environ['MAC_STUDIO_PASSWORD'])` (Windows)
  - For file transfers: `scp` (macOS) or `sftp = ssh.open_sftp()` (Windows/paramiko)
- Always backup before destructive operations
- Log errors and fixes to Smart Memory SQLite
- Custom modules go in `/opt/odoo/custom-addons/`
