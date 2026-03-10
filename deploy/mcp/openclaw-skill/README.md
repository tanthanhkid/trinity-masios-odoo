# Odoo CRM Skill for OpenClaw

## Install (one command)

```bash
# 1. Add skill
cp -r this-folder ~/.openclaw/skills/odoo-crm

# 2. Add MCP server
mcporter config add odoo http://103.72.97.51:8200/sse \
  --header "Authorization=Bearer YOUR_API_TOKEN" --scope home
```

Done. Your OpenClaw agents can now manage Odoo CRM.

## Test

```bash
mcporter call odoo.odoo_crm_stages
```
