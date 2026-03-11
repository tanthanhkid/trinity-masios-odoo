# Trinity Masios Odoo

Self-hosted Odoo 18.0 CRM on Ubuntu, fully managed by AI agents via MCP.

## What This Is

An Odoo deployment with an AI-powered management layer:
- **Odoo 18.0 Community** running on Ubuntu 24.04 (103.72.97.51)
- **MCP Server** (26 tools) — real-time Odoo introspection, CRUD, sales, invoicing, credit control via XML-RPC
- **Claude Code skills** — SSH DevOps, Odoo self-hosting, smart error memory
- **OpenClaw integration** — any OpenClaw agent can manage Odoo via mcporter

## Architecture

```
┌─ Your Machine ─────────────────────┐     ┌─ Ubuntu Server ──────────────┐
│                                     │     │                              │
│  Claude Code ──► .mcp.json (stdio)  │     │  MCP Server (:8200 HTTP)    │
│                                     │     │       │ XML-RPC              │
│  OpenClaw ──► mcporter ─────────────┼────►│  Odoo 18.0 (:8069)          │
│     agents      (HTTP)              │     │       │ ORM                  │
│                                     │     │  PostgreSQL 16               │
│  Browser ───────────────────────────┼────►│  Nginx (:80)                │
└─────────────────────────────────────┘     └──────────────────────────────┘
```

## Quick Start

### Claude Code (this repo)
```bash
git clone https://github.com/tanthanhkid/trinity-masios-odoo.git
cd trinity-masios-odoo
cp .env.example .env.local   # fill in credentials
python3 setup-claude.py      # installs skills, hooks, memory
# Restart Claude Code — MCP server auto-starts via .mcp.json
```

### OpenClaw (any machine)
```bash
mcporter config add odoo http://103.72.97.51:8200/sse \
  --header "Authorization=Bearer YOUR_API_TOKEN" --scope home
cp deploy/mcp/openclaw-skill ~/.openclaw/skills/odoo-crm
# Done — agents can now call mcporter call odoo.<tool>
```

See [openclaw_setup.md](openclaw_setup.md) for detailed guide.

## MCP Tools (26)

| Category | Tools |
|----------|-------|
| **Discover** | `odoo_server_info`, `odoo_list_models`, `odoo_model_fields`, `odoo_model_access`, `odoo_model_views` |
| **CRM** | `odoo_crm_stages`, `odoo_crm_lead_summary`, `odoo_pipeline_by_stage` |
| **Sales** | `odoo_sale_order_summary`, `odoo_create_sale_order`, `odoo_confirm_sale_order`, `odoo_sale_order_pdf` |
| **Invoicing** | `odoo_invoice_summary`, `odoo_create_invoice_from_so`, `odoo_invoice_pdf` |
| **Customers** | `odoo_create_customer`, `odoo_customer_credit_status`, `odoo_customer_set_classification`, `odoo_customers_exceeding_credit` |
| **Dashboard** | `odoo_dashboard_kpis` |
| **CRUD** | `odoo_search_read`, `odoo_count`, `odoo_create`, `odoo_write`, `odoo_delete` |
| **Advanced** | `odoo_execute` (allowlisted methods only) |

## Project Structure

```
├── CLAUDE.md                    # AI agent project guide
├── .mcp.json                    # MCP server config (Claude Code)
├── .env.example                 # Credentials template
├── setup-claude.py              # Cross-platform setup script
├── openclaw_setup.md            # OpenClaw setup guide
├── mcp/odoo-server/server.py    # MCP server (stdio + HTTP)
├── deploy/
│   ├── config/                  # Odoo + systemd configs
│   ├── nginx/                   # Nginx reverse proxy
│   └── mcp/                     # HTTP MCP service + OpenClaw skill
├── custom-addons/               # Odoo custom modules
├── odoo-server/                 # Odoo 18.0 source (git submodule)
└── .claude/
    ├── skills/                  # ssh-devops, odoo-selfhost, smart-memory
    ├── hooks/                   # Error tracking, session context, auto-learn
    └── memory/                  # Persistent project knowledge
```

## Skills

| Skill | What It Does |
|-------|-------------|
| **ssh-devops** | SSH into server, deploy, check logs, monitor services |
| **odoo-selfhost** | Install, configure, develop modules, troubleshoot Odoo |
| **smart-memory** | Track errors in SQLite, learn from past fixes, preserve context |

## Security

- **Bearer token auth** on HTTP endpoint — generate with `python3 server.py --generate-token`
- Credentials stored in `.env.local` (gitignored) or `/etc/odoo-mcp/credentials` (server)
- MCP HTTP binds to `127.0.0.1` by default (use reverse proxy for remote)
- `odoo_execute` restricted to allowlisted methods
- XML-RPC errors return clean JSON, never raw tracebacks
