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
- 26 tools: introspect models/fields/access/views, CRUD, CRM helpers, sales/invoicing, credit control, dashboard, execute (allowlisted)
- Use `odoo_model_fields` to get field types, constraints, relations for any model
- Use `odoo_list_models` with filter to discover models (e.g. filter="crm")
- Requires `uv` (Python package runner) — no global install needed
- Inside Docker containers, `mcporter` CLI must be installed for OpenClaw agents to call MCP tools

### Authentication
- **stdio mode** (Claude Code): No token needed — runs locally
- **HTTP mode** (OpenClaw/remote): Bearer token required
  - Token stored in `MCP_API_TOKEN` env var (in `/etc/odoo-mcp/credentials` on server)
  - Generate: `uv run --with mcp python3 mcp/odoo-server/server.py --generate-token`
  - Without token: server warns but still starts (NO auth — dev only)
  - With token: all HTTP requests must include `Authorization: Bearer <token>` header
  - Auth errors: 401 (missing header), 403 (wrong token)

### OpenClaw Integration
- Registered in mcporter: `~/.mcporter/mcporter.json` (home scope)
- OpenClaw agents use `mcporter` skill to call Odoo tools
- Call pattern: `mcporter call odoo.<tool_name> key=value`
- Examples:
  - `mcporter call odoo.odoo_server_info`
  - `mcporter call odoo.odoo_list_models filter=crm`
  - `mcporter call odoo.odoo_model_fields model=crm.lead`
  - `mcporter call odoo.odoo_crm_stages`
  - `mcporter call odoo.odoo_search_read model=crm.lead domain='[]' limit=10`
- Env vars (ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD) stored in mcporter config
- HTTP mode: `server.py --http --port 8200` (for remote OpenClaw instances)
- Systemd: `deploy/mcp/odoo-mcp.service` → runs on server as HTTP
- New OpenClaw setup: see `openclaw_setup.md`
- Skill for agents: `deploy/mcp/openclaw-skill/SKILL.md`
- mcporter with auth: `mcporter config add odoo http://server:8200/sse --header "Authorization=Bearer <token>" --scope home`

#### Exec Approvals
- `exec-approvals.json` only works for LOCAL/CLI mode — has no effect in Telegram gateway
- For Telegram gateway: set `agents.defaults.elevatedDefault: "full"` + `tools.exec.security: "full"`
- These keys are set via `openclaw config set` in `entrypoint.sh` (template validation strips them)
- Test Telegram flow with: `openclaw agent --channel telegram --session-id X --message "..."`

### Docker Deployment (`deploy/openclaw/`)
- Dockerized OpenClaw bots with template-based configuration
- Config templates: `config/openclaw.template.json`, `config/mcporter.template.json`
- `entrypoint.sh` injects env vars (TELEGRAM_BOT_TOKEN, ODOO_URL, etc.) at container startup via `sed` replacement
- Environment variables passed through `docker-compose.yml` and `.env` file
- GLM-5 is the best-performing model for tool-calling tasks with OpenClaw

### Modes
- **stdio** (Claude Code): `.mcp.json` → `uv run` → local process (no token needed)
- **HTTP** (OpenClaw remote): `http://server:8200/sse` → mcporter connects (bearer token required)

## Masi Telegram Bot v2 (`deploy/masi-bot/`)
Lightweight Telegram bot replacing OpenClaw — direct MCP integration, template-based formatting.

- **Architecture**: python-telegram-bot → Anthropic SDK (Qwen 3.5 Plus via Alibaba) → MCP SSE client → Odoo
- **Deploy**: Systemd service on Odoo server (`/opt/masi-bot/`, `masi-bot.service`)
- **Model**: Qwen 3.5 Plus via Alibaba Anthropic-compatible API
- **Telegram Bot**: `@hdxthanhtt4bot` (Bot 1)
- **Whitelist**: `2048339435` (CEO), `1481072032` (Hunter Lead), `5001000001` (Farmer Lead)
- **Performance**: Slash commands < 1s (template formatter), free-form chat ~10s (LLM)
- **Files**:
  - `bot.py` — Telegram handler, RBAC, conversation memory, HTML formatting
  - `agent.py` — LLM tool-calling loop + fast path (direct MCP → template)
  - `mcp_client.py` — MCP SSE client, tool discovery, persistent connection
  - `formatter.py` — Python template formatters for 27 slash commands (no LLM)
  - `config.py` — env vars, system prompt, whitelist, TEST_USERS dict
- **34 slash commands** registered in Telegram menu (includes `/what_changed` stub)
- **51 MCP tools** auto-discovered at startup
- **Context injection**: `_active_contexts` dict per user persists entity (partner/order/invoice) across turns — fixes /findcustomer drill-down context drift

### How it works
1. **Slash commands** (`/kpi`, `/morning_brief`, etc.): Permission check → MCP tool call → Python template format → Telegram HTML. No LLM needed. Sub-second response.
2. **Free-form chat**: Permission check → Qwen 3.5 Plus with 51 tools → tool-calling loop → Telegram HTML. ~10s response.

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
  - Bot 1: **REPLACED** by Masi Bot v2 on Odoo server (was `~/openclaw-odoo/` port 18789)
  - Bot 2: `~/openclaw-bot2-native/` (port 18790) — Telegram `@MASIBIO_bot` (native macOS, **disconnected from Odoo** — clean OpenClaw instance, no Odoo skills/MCP)
- **Telegram whitelist**: `2048339435` (CEO), `1481072032`

## MCP Tools (51 total)
### Core (13): server_info, list_models, model_fields, model_access, model_views, crm_stages, crm_lead_summary, search_read, count, create, write, delete, execute
### Sales & Invoice (7): sale_order_summary, create_sale_order, confirm_sale_order, invoice_summary, create_invoice_from_so, sale_order_pdf, invoice_pdf
### Customer & Credit (4): create_customer, customer_credit_status, customer_set_classification, customers_exceeding_credit
### Dashboard (2): dashboard_kpis, pipeline_by_stage
### Command Center (14): morning_brief, ceo_alert, revenue_today, brief_hunter, brief_farmer, brief_ar, brief_cash, hunter_today, hunter_sla_details, farmer_today, farmer_ar, congno, task_overdue, flash_report
### Actions (7): mark_contacted, mark_collection, set_dispute, change_owner, escalate, complete_task, audit_log
### Telegram RBAC (4): telegram_check_permission, telegram_get_menu, telegram_list_users, telegram_register_user

## Custom Modules Deployed
- `masios_credit_control` — Customer classification (new/old), credit limits, debt tracking
- `masios_dashboard` — CEO dashboard at `/dashboard` with KPIs, pipeline, orders, invoices

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
4. **Scope**: component affected (e.g. `mcp`, `credit-control`, `dashboard`, `openclaw`, `deploy`)
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
- deploy/openclaw/config/workspace/send_pdf.py: Telegram Bot API PDF sender

Trade-off: base64 encoding doubles payload size but avoids binary in JSON.
File-based approach (/tmp) used to handle large payloads.
```

```
fix(openclaw): Resolve Telegram gateway ignoring exec-approvals.json

exec-approvals.json only works in LOCAL/CLI mode. Telegram gateway uses
a separate approval path that requires elevated permissions config.

Changes:
- deploy/openclaw/entrypoint.sh: Add openclaw config set for elevatedDefault and exec.security
- CLAUDE.md: Document two-tier approval architecture (CLI vs gateway)
- AGENTS.md: Add exec approvals section with testing instructions

Root cause: OpenClaw template validation strips non-standard keys from JSON,
so these must be set via CLI after config generation.
```

## E2E Test Suite

### Odoo Web UI Tests (Playwright headless browser)
- `tests/e2e/test_e2e_full.py` — 27 tests across 6 suites
- `tests/__init__.py`, `tests/e2e/__init__.py` — package markers

| Suite | Tests | Coverage |
|-------|-------|----------|
| 1 — Welcome Page | 6 | Each role sees role badge, feature cards, quick links |
| 2 — RBAC Menu Visibility | 6 | Each role sees only their allowed Odoo app menus |
| 3 — RBAC URL Blocking | 4 | Forbidden URL access → AccessError dialog or redirect |
| 4 — Credit Control | 5 | Phân loại KH field, Công nợ tab, outstanding_debt, credit_limit |
| 5 — Dashboard KPIs | 3 | CEO sees /dashboard, non-CEO redirected to /welcome |
| 6 — Command Center | 3 | Command Center menu visibility, masios.telegram_user accessible |

```bash
# Requires: pip install playwright && python -m playwright install chromium
python3 tests/e2e/test_e2e_full.py
```
**Note:** Run after 45s+ gap — Odoo workers (2 CPU, 3.8GB) need cooldown. Screenshots → `test_screenshots/` on failure.

### Telegram Bot API Tests (test_server port 8300)
Three additional suites calling the masi-bot REST API directly (no browser, stdlib urllib only):

| File | Tests | Coverage |
|------|-------|----------|
| `tests/e2e/test_bot_commands.py` | 27 | All fast-path commands, CEO role, keyword + timing check |
| `tests/e2e/test_bot_rbac.py` | 27 | Full RBAC matrix per spec v1.1 (allowed + blocked per role) |
| `tests/e2e/test_bot_multiturn.py` | 5 | /quote→number, /invoice→number, /findcustomer drill-down, ok-guard, morning_brief drill |

```bash
python3 tests/e2e/test_bot_commands.py
python3 tests/e2e/test_bot_rbac.py
python3 tests/e2e/test_bot_multiturn.py
```
**Prerequisite:** masi-bot service running on server (port 8300 accessible).

### Unit Tests
- `deploy/masi-bot/tests/test_context_injection.py` — 6 unit tests for `_inject_context` + `_extract_entity_from_tool_result`
```bash
cd deploy/masi-bot && python -m pytest tests/test_context_injection.py -v
```

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
