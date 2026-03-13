# Trinity Masios Odoo - Project Memory

## Server
- IP: 103.72.97.51, Port: 24700, User: root, OS: Ubuntu 24.04 LTS
- 2 CPUs, 3.8GB RAM, 20GB disk (88% used - monitor closely)
- Other services: Docker (port 3000), Node app (port 3001)

## Odoo Setup
- Version: 18.0 Community (branch 18.0 from github.com/odoo/odoo)
- Install: /opt/odoo/odoo-server/ (source install, not package)
- Custom addons: /opt/odoo/custom-addons/
- Config: /etc/odoo.conf (3 workers, 1 cron thread)
- Service: systemd `odoo.service`, runs as user `odoo`
- Logs: /var/log/odoo/odoo-server.log
- DB: PostgreSQL 16, database name `odoo`, user `odoo` (md5 auth)
- Nginx reverse proxy on port 80 -> 8069 (HTTP) + 8072 (websocket)
- Default login: admin/admin (NEEDS CHANGING)

## Known Issues & Fixes
- PostgreSQL auth: Odoo needs `db_password` in config + md5 in pg_hba.conf (not peer)
- Fresh install: must run `odoo-bin -i base --stop-after-init` to init DB
- pip cryptography: use `--ignore-installed` flag on Ubuntu 24.04
- Disk space tight: clean apt cache and old logs regularly

## Project Structure
- GitHub: github.com/tanthanhkid/trinity-masios-odoo
- odoo-server/ = git submodule (odoo/odoo)
- custom-addons/ = custom modules
- deploy/ = server configs (sanitized)
- .claude/skills/ = 3 skills (ssh-devops, odoo-selfhost, smart-memory)
- .claude/hooks/ = smart memory hooks (copied from plugin)

## Masi Telegram Bot v2
- Replaced OpenClaw Bot 1 (@hdxthanhtt4bot) on 2026-03-13
- Runs on Odoo server as systemd service `masi-bot.service`
- Stack: python-telegram-bot + Anthropic SDK (Qwen 3.5 Plus) + MCP SSE client
- 33 slash commands, 51 MCP tools, template formatting (<1s response)
- Code: /opt/masi-bot/ on server, deploy/masi-bot/ in repo
- Free-form chat uses LLM, slash commands use Python templates

## Plugin Location
- Global: ~/.claude/plugins/local/devops-ssh/
- Skills: ssh-devops, odoo-selfhost, smart-memory
- Hooks: session-start, error-tracker, compact, stop (auto-learn)
- SQLite DB: ~/.claude/smart-memory.db

## Topic Files
- [server-config.md](server-config.md) - detailed server configuration
- [odoo-patterns.md](odoo-patterns.md) - Odoo development patterns
