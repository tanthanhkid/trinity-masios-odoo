---
name: odoo-crm
description: Manage Odoo 18 CRM via MCP — introspect models/fields, create leads, manage pipeline, CRUD on any model. Use when user asks about CRM, leads, customers, sales pipeline, Odoo data, or wants to query/modify Odoo records.
allowed-tools: Bash
metadata:
  {
    "openclaw":
      {
        "emoji": "🏢",
        "requires": { "bins": ["mcporter"] },
      },
  }
---

# Odoo CRM MCP Skill

Interact with a live Odoo 18 instance via the Odoo MCP server. All operations go through `mcporter call odoo.<tool>`.

## Setup (one-time)

If the `odoo` server is not yet configured, add it with your API token:

```bash
mcporter config add odoo http://103.72.97.51:8200/sse \
  --header "Authorization=Bearer YOUR_API_TOKEN" --scope home
```

Replace `YOUR_API_TOKEN` with the token provided by your admin.

Verify with: `mcporter list odoo`

## Available Tools (13)

### Discovery & Introspection

| Command | What it does |
|---------|-------------|
| `mcporter call odoo.odoo_server_info` | Server version and connection info |
| `mcporter call odoo.odoo_list_models filter=crm` | List models matching a name filter |
| `mcporter call odoo.odoo_model_fields model=crm.lead` | All fields with types, required, relations, selections |
| `mcporter call odoo.odoo_model_fields model=crm.lead field_filter=partner` | Filter fields by name |
| `mcporter call odoo.odoo_model_access model=crm.lead` | CRUD permissions per security group |
| `mcporter call odoo.odoo_model_views model=crm.lead` | Form/list/kanban view XML definitions |

### CRM Specific

| Command | What it does |
|---------|-------------|
| `mcporter call odoo.odoo_crm_stages` | Pipeline stages (New, Qualified, Proposition, Won) |
| `mcporter call odoo.odoo_crm_lead_summary` | All leads/opportunities |
| `mcporter call odoo.odoo_crm_lead_summary stage_id=1` | Leads in specific stage |
| `mcporter call odoo.odoo_crm_lead_summary type_filter=opportunity` | Only opportunities |

### Read & Search

| Command | What it does |
|---------|-------------|
| `mcporter call odoo.odoo_search_read model=crm.lead fields=name,partner_id,stage_id,expected_revenue` | Query with specific fields |
| `mcporter call odoo.odoo_search_read model=res.partner 'domain=[["company_type","=","company"]]'` | Query with domain filter |
| `mcporter call odoo.odoo_count model=crm.lead` | Count records |
| `mcporter call odoo.odoo_count model=crm.lead 'domain=[["stage_id","=",4]]'` | Count won deals |

### Create, Update, Delete

| Command | What it does |
|---------|-------------|
| `mcporter call odoo.odoo_create model=crm.lead 'values={"name":"Deal Name","type":"opportunity","partner_name":"Company"}'` | Create lead/opportunity |
| `mcporter call odoo.odoo_create model=res.partner 'values={"name":"John","email":"john@example.com","company_type":"person"}'` | Create contact |
| `mcporter call odoo.odoo_write model=crm.lead 'ids=[1]' 'values={"stage_id":4}'` | Move lead to Won |
| `mcporter call odoo.odoo_delete model=crm.lead 'ids=[5]'` | Delete a lead |

### Advanced

| Command | What it does |
|---------|-------------|
| `mcporter call odoo.odoo_execute model=crm.lead method=action_set_won 'args=[[1]]'` | Call any Odoo method |

## Key Models

| Model | Description | Key Fields |
|-------|-------------|------------|
| `crm.lead` | Leads & Opportunities (110 fields) | name (required), type (lead/opportunity, required), partner_id, stage_id, expected_revenue, probability, user_id, team_id |
| `crm.stage` | Pipeline stages | name, sequence, is_won, fold |
| `crm.team` | Sales teams | name, user_id, member_ids |
| `crm.tag` | Lead tags | name, color |
| `res.partner` | Contacts/Companies | name, email, phone, company_type (person/company) |
| `crm.lost.reason` | Lost reasons | name |

## CRM Pipeline Stages

| ID | Name | Won? |
|----|------|------|
| 1 | New | No |
| 2 | Qualified | No |
| 3 | Proposition | No |
| 4 | Won | Yes |

## Domain Filter Syntax

Odoo uses Polish notation for domain filters:

```
# Simple: field operator value
[["field", "=", value]]

# AND (default when multiple conditions)
[["stage_id", "=", 1], ["type", "=", "opportunity"]]

# OR (prefix with "|")
["|", ["stage_id", "=", 1], ["stage_id", "=", 2]]

# Common operators: =, !=, >, <, >=, <=, like, ilike, in, not in, child_of
[["name", "ilike", "trinity"]]
[["id", "in", [1, 2, 3]]]
[["create_date", ">=", "2024-01-01"]]
```

## Common Workflows

### Add a new customer + opportunity
```bash
# 1. Create contact
mcporter call odoo.odoo_create model=res.partner \
  'values={"name":"Acme Corp","email":"info@acme.com","company_type":"company"}'
# Returns: {"created_id": [10]}

# 2. Create opportunity linked to contact
mcporter call odoo.odoo_create model=crm.lead \
  'values={"name":"Acme - Enterprise Deal","partner_id":10,"type":"opportunity","expected_revenue":50000}'
```

### Move opportunity through pipeline
```bash
# Qualify
mcporter call odoo.odoo_write model=crm.lead 'ids=[2]' 'values={"stage_id":2}'

# Mark as Won
mcporter call odoo.odoo_write model=crm.lead 'ids=[2]' 'values={"stage_id":4}'
```

### Search and report
```bash
# All open opportunities with revenue
mcporter call odoo.odoo_search_read model=crm.lead \
  'domain=[["type","=","opportunity"],["stage_id","!=",4]]' \
  fields=name,partner_id,stage_id,expected_revenue,probability \
  order="expected_revenue desc"

# Count per stage
mcporter call odoo.odoo_count model=crm.lead 'domain=[["stage_id","=",1]]'
mcporter call odoo.odoo_count model=crm.lead 'domain=[["stage_id","=",4]]'
```

## Tips

- Always use `odoo_model_fields` first if unsure about a model's field names or types
- `partner_id` in crm.lead links to `res.partner` — create the partner first, then reference by ID
- Use `odoo_list_models filter=keyword` to discover models (e.g., filter=sale, filter=account, filter=stock)
- The server connects to Odoo's XML-RPC API — same permissions as the configured admin user
