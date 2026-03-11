# OpenClaw + Odoo MCP Setup Guide

Connect any OpenClaw instance to the Odoo 18 CRM system in 2 steps.

## Prerequisites

- OpenClaw installed (`openclaw --version`)
- mcporter installed (`mcporter --version`)
  - If not: `npm install -g mcporter`

## Step 1: Get Your API Token

The MCP server requires bearer token authentication. Request a token from your admin.

## Step 2: Connect to Odoo MCP Server

```bash
mcporter config add odoo http://103.72.97.51:8200/sse \
  --header "Authorization=Bearer YOUR_API_TOKEN" --scope home
```

Replace `YOUR_API_TOKEN` with the token provided by your admin.

Verify:
```bash
mcporter list odoo --schema
```

You should see 26 tools (odoo_server_info, odoo_list_models, odoo_model_fields, etc.)

Test:
```bash
mcporter call odoo.odoo_server_info
mcporter call odoo.odoo_crm_stages
```

## Step 3: Install Odoo Skill (teaches agents how to use it)

```bash
# Clone the repo (or just copy the skill folder)
git clone https://github.com/tanthanhkid/trinity-masios-odoo.git /tmp/odoo-setup

# Copy skill to OpenClaw
cp -r /tmp/odoo-setup/deploy/mcp/openclaw-skill ~/.openclaw/skills/odoo-crm

# Verify
openclaw skills list | grep odoo
```

## That's it!

Your OpenClaw agents now have:
- **26 real-time tools** to interact with Odoo
- **Skill documentation** teaching them CRM models, fields, domain syntax, and workflows

## Quick Test

```bash
# Via mcporter directly
mcporter call odoo.odoo_list_models filter=crm
mcporter call odoo.odoo_search_read model=crm.lead fields=name,partner_id,stage_id

# Via OpenClaw agent
openclaw agent --agent YOUR_AGENT --local \
  --message "List all CRM opportunities from Odoo"
```

## What Agents Can Do

| Action | Example |
|--------|---------|
| Discover models | "What models does Odoo CRM have?" |
| Inspect fields | "What fields does crm.lead have?" |
| Query data | "Show me all open opportunities" |
| Create records | "Create a new lead for Acme Corp" |
| Update records | "Move lead #2 to Won stage" |
| Pipeline report | "How many deals are in each stage?" |
| Access control | "Who has write access to crm.lead?" |

## Architecture

```
OpenClaw Agent
  ↓ uses mcporter skill
mcporter CLI
  ↓ HTTP request
Odoo MCP Server (port 8200)
  ↓ XML-RPC
Odoo 18.0 (port 8069)
  ↓ ORM
PostgreSQL 16
```

## Available Tools Reference

### Introspection
- `odoo_server_info` — version, connection info
- `odoo_list_models filter=<keyword>` — find models by name
- `odoo_model_fields model=<name>` — field types, required, relations, selections
- `odoo_model_access model=<name>` — CRUD permissions per group
- `odoo_model_views model=<name>` — view definitions (form/list/kanban)

### CRM Shortcuts
- `odoo_crm_stages` — pipeline stages
- `odoo_crm_lead_summary` — leads overview (filterable by stage/type)

### Generic CRUD
- `odoo_search_read model=<name> domain=<filter> fields=<list>` — query any model
- `odoo_count model=<name> domain=<filter>` — count records
- `odoo_create model=<name> values=<json>` — create record
- `odoo_write model=<name> ids=<list> values=<json>` — update records
- `odoo_delete model=<name> ids=<list>` — delete records
- `odoo_execute model=<name> method=<name> args=<json>` — call any method

## Domain Filter Cheatsheet

```python
# Equals
[["stage_id", "=", 1]]

# Contains (case-insensitive)
[["name", "ilike", "trinity"]]

# In list
[["id", "in", [1, 2, 3]]]

# Date range
[["create_date", ">=", "2024-01-01"]]

# AND (default)
[["stage_id", "=", 1], ["type", "=", "opportunity"]]

# OR
["|", ["stage_id", "=", 1], ["stage_id", "=", 2]]
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `mcporter list odoo` shows nothing | Run `mcporter config add odoo http://103.72.97.51:8200/sse --header "Authorization=Bearer TOKEN" --scope home` |
| Connection refused on 8200 | MCP server not running on remote. Ask admin to check: `systemctl status odoo-mcp` |
| 401 Unauthorized | Missing or malformed Authorization header. Use `--header "Authorization=Bearer TOKEN"` |
| 403 Forbidden | Invalid API token. Request a new token from admin |
| Auth error | Odoo credentials are server-side. Ask admin to verify ODOO_PASSWORD env |
| `openclaw skills list` missing odoo-crm | Copy skill: `cp -r deploy/mcp/openclaw-skill ~/.openclaw/skills/odoo-crm` |
| Tool returns empty | Check if Odoo service is running: `mcporter call odoo.odoo_server_info` |
