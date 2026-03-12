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

## Mac Deploy Machine (OpenClaw Docker Host)
- **IP**: 100.81.203.48 (Tailscale)
- **User**: masios
- **Password**: (stored in memory/server-config.md)
- **OS**: macOS 26.3, Apple Silicon (ARM64), Mac Studio
- **Docker**: OrbStack v2.0.5, Docker 29.2.0
- **Deploy paths**:
  - Bot 1: `~/openclaw-odoo/` (port 18789) — Telegram bot `@hdxthanhtt4bot`
  - Bot 2: `~/openclaw-odoo-2/` (port 18790) — Telegram bot `@MASIBIO_bot`
- **Telegram whitelist**: `2048339435` (CEO), `1481072032`

## MCP Tools (26 total)
### Existing (13): server_info, list_models, model_fields, model_access, model_views, crm_stages, crm_lead_summary, search_read, count, create, write, delete, execute
### Added (13): sale_order_summary, create_sale_order, confirm_sale_order, invoice_summary, create_invoice_from_so, create_customer, customer_credit_status, customer_set_classification, customers_exceeding_credit, dashboard_kpis, pipeline_by_stage, invoice_pdf, sale_order_pdf

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

## Conventions
- **SSH from Windows: ALWAYS use `paramiko` (Python)** — NEVER use `sshpass` (fails on Windows due to TTY issues, wastes time every session)
  - Odoo server: `paramiko.connect('103.72.97.51', port=24700, username='root')` (no password needed)
  - Mac Studio: `paramiko.connect('100.81.203.48', username='masios', password='19112003', allow_agent=False, look_for_keys=False)`
  - For file transfers: use `sftp = ssh.open_sftp()` then `sftp.put(local, remote)`
- Always backup before destructive operations
- Log errors and fixes to Smart Memory SQLite
- Custom modules go in `/opt/odoo/custom-addons/`
