# Trinity Masios Odoo

Self-hosted Odoo 18.0 CRM on Ubuntu, fully managed by AI agents via MCP.

## What This Is

An Odoo deployment with an AI-powered management layer:
- **Odoo 18.0 Community** running on Ubuntu 24.04 (103.72.97.51)
- **MCP Server** (51 tools) — real-time Odoo introspection, CRUD, sales, invoicing, credit control, command center via XML-RPC
- **Masi Telegram Bot v2** — lightweight bot with direct MCP integration, sub-second slash commands
- **Claude Code skills** — SSH DevOps, Odoo self-hosting, smart error memory

## Architecture

```
┌─ Your Machine ─────────────────────┐     ┌─ Ubuntu Server (103.72.97.51) ─┐
│                                     │     │                                │
│  Claude Code ──► .mcp.json (stdio)  │     │  Masi Bot v2 (systemd)        │
│                                     │     │    │ Anthropic SDK (Qwen 3.5)  │
│  Browser ───────────────────────────┼────►│    │ MCP SSE client            │
│                                     │     │    ▼                           │
│  Telegram ──────────────────────────┼────►│  MCP Server (:8200 HTTP)      │
│     @hdxthanhtt4bot                 │     │    │ XML-RPC                   │
│                                     │     │  Odoo 18.0 (:8069)            │
│                                     │     │    │ ORM                       │
│                                     │     │  PostgreSQL 16                │
│                                     │     │  Nginx (:80)                  │
└─────────────────────────────────────┘     └────────────────────────────────┘
```

## Quick Start

### Claude Code (this repo)
```bash
git clone https://github.com/tanthanhkid/trinity-masios-odoo.git
cd trinity-masios-odoo
cp .env.example .env.local   # fill in credentials
bash setup-claude.sh         # installs skills, hooks, memory
# Restart Claude Code — MCP server auto-starts via .mcp.json
```

### Telegram Bot
The bot runs on the Odoo server as a systemd service. See `deploy/masi-bot/`.

## MCP Tools (51)

| Category | Count | Tools |
|----------|-------|-------|
| **Discovery** | 5 | server_info, list_models, model_fields, model_access, model_views |
| **CRM** | 2 | crm_stages, crm_lead_summary |
| **CRUD** | 5 | search_read, count, create, write, delete |
| **Execute** | 1 | execute (allowlisted) |
| **Sales** | 3 | sale_order_summary, create_sale_order, confirm_sale_order |
| **Invoicing** | 3 | invoice_summary, create_invoice_from_so, invoice_pdf |
| **Customers** | 4 | create_customer, customer_credit_status, customer_set_classification, customers_exceeding_credit |
| **Dashboard** | 2 | dashboard_kpis, pipeline_by_stage |
| **PDF** | 2 | sale_order_pdf, invoice_pdf |
| **Command Center** | 14 | morning_brief, ceo_alert, revenue_today, brief_hunter/farmer/ar/cash, hunter/farmer_today, hunter_sla_details, farmer_ar, congno, task_overdue, flash_report |
| **Actions** | 7 | mark_contacted, mark_collection, set_dispute, change_owner, escalate, complete_task, audit_log |
| **Telegram RBAC** | 4 | telegram_check_permission, telegram_get_menu, telegram_list_users, telegram_register_user |

## Project Structure

```
├── CLAUDE.md                    # AI agent project guide
├── AGENTS.md                    # Agent interaction guide
├── WORKFLOW-TRACKER.md          # System workflow tracker
├── .mcp.json                    # MCP server config (Claude Code)
├── .env.example                 # Credentials template
├── setup-claude.sh              # Setup script
├── mcp/odoo-server/server.py    # MCP server (stdio + HTTP, 51 tools)
├── deploy/
│   ├── masi-bot/                # Telegram bot v2 (replaces OpenClaw)
│   │   ├── bot.py               # Telegram handler + RBAC
│   │   ├── agent.py             # LLM tool-calling + fast path
│   │   ├── mcp_client.py        # MCP SSE client
│   │   ├── formatter.py         # Template formatters (27 commands)
│   │   └── config.py            # Configuration
│   ├── openclaw/                # OpenClaw (legacy, replaced by masi-bot)
│   ├── config/                  # Odoo + systemd configs
│   ├── nginx/                   # Nginx reverse proxy
│   └── mcp/                     # HTTP MCP service
├── custom-addons/               # Odoo custom modules
├── odoo-server/                 # Odoo 18.0 source (git submodule)
└── .claude/
    ├── skills/                  # ssh-devops, odoo-selfhost, smart-memory
    ├── hooks/                   # Error tracking, auto-learn
    └── memory/                  # Persistent project knowledge
```

## Telegram Bot v2

Lightweight replacement for OpenClaw with direct MCP integration.

| Feature | Detail |
|---------|--------|
| **Bot** | @hdxthanhtt4bot |
| **Model** | Qwen 3.5 Plus (Alibaba API) |
| **Slash Commands** | 33 registered commands |
| **Performance** | Slash commands < 1s, chat ~10s |
| **RBAC** | Managed in Odoo (Command Center > Telegram) |
| **Deploy** | systemd on Odoo server (`masi-bot.service`) |

### Why not OpenClaw?
- OpenClaw had poor skill compliance and slow tool calling
- Masi Bot v2 is 48-421x faster for slash commands (template formatting vs LLM)
- Direct MCP connection (no mcporter middleman)
- Zero personality engine overhead

## Security

- **Bearer token auth** on HTTP endpoint — generate with `python3 server.py --generate-token`
- Credentials stored in `.env.local` (gitignored) or `/etc/odoo-mcp/credentials` (server)
- `odoo_execute` restricted to allowlisted methods
- Telegram whitelist: only approved user IDs can interact with bot
- RBAC managed in Odoo with per-command/per-action permission checks
