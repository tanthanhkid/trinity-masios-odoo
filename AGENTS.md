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

## Safety Rules

- **Never delete** records without explicit user confirmation
- **Always check** field names with `odoo_model_fields` before creating/writing
- `odoo_execute` is restricted to allowlisted methods — don't try arbitrary methods
- Credentials are in `.env.local` (local) or `/etc/odoo-mcp/credentials` (server) — never expose them
- For SSH operations, use the ssh-devops skill — never hardcode passwords in commands
