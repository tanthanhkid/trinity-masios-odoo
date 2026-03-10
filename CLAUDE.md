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
- 13 tools: introspect models/fields/access/views, CRUD, CRM helpers, execute (allowlisted)
- Use `odoo_model_fields` to get field types, constraints, relations for any model
- Use `odoo_list_models` with filter to discover models (e.g. filter="crm")
- Requires `uv` (Python package runner) — no global install needed

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

### Modes
- **stdio** (Claude Code): `.mcp.json` → `uv run` → local process (no token needed)
- **HTTP** (OpenClaw remote): `http://server:8200/sse` → mcporter connects (bearer token required)

## Conventions
- Use `sshpass` for SSH connections to this server
- Always backup before destructive operations
- Log errors and fixes to Smart Memory SQLite
- Custom modules go in `/opt/odoo/custom-addons/`
