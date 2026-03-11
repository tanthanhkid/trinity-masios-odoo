# OpenClaw Agent for Odoo — Docker Deployment

AI Agent kết nối Odoo 18 qua MCP, chat qua Telegram. Deploy được trên bất kỳ máy nào có Docker.

## Quick Start

```bash
# 1. Copy env file
cp .env.example .env

# 2. Fill in credentials
nano .env

# 3. Build & run
docker compose up -d

# 4. Check logs
docker compose logs -f openclaw
```

## Architecture

```
Telegram User → OpenClaw Agent (Docker) → mcporter → MCP HTTP :8200 → Odoo XML-RPC
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALIBABA_API_KEY` | Yes | API key for LLM (Qwen/GLM-5/Kimi/MiniMax) |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token from @BotFather |
| `OPENCLAW_GATEWAY_TOKEN` | Yes | Gateway auth token (generate any random string) |
| `ODOO_MCP_TOKEN` | Yes | Bearer token for Odoo MCP server |
| `ODOO_MCP_URL` | No | MCP server URL (default: `http://103.72.97.51:8200/sse`) |
| `OPENCLAW_PORT` | No | Host port (default: `18789`) |

## Multi-bot Deployment

Run multiple bots on the same machine with different ports and tokens:

```bash
# Bot 1
cp .env.example .env
# Edit .env with bot 1 credentials
docker compose up -d

# Bot 2 (separate directory)
mkdir ../openclaw-bot2 && cp -r . ../openclaw-bot2/ && cd ../openclaw-bot2
cp .env.example .env
# Edit .env with bot 2 credentials + different port
echo "OPENCLAW_PORT=18790" >> .env
docker compose -p openclaw-bot2 up -d
```

## What's Included

- **Model**: GLM-5 (via Alibaba Coding API) — best tool-calling performance
- **Skill**: `odoo-crm` — 24 MCP tools for sales, invoices, credit control, dashboard
- **Channel**: Telegram bot with auto tool execution
- **Exec approvals**: Pre-approved `mcporter` commands
- **mcporter**: Installed globally for MCP server communication

## How It Works

1. `entrypoint.sh` injects env vars into config templates at container startup
2. OpenClaw gateway starts with Telegram channel enabled
3. User sends message via Telegram → Agent uses `mcporter call odoo.*` → MCP server → Odoo
4. Agent responds with formatted Vietnamese text

## Customization

### Change default model
Set in `.env` or edit `config/openclaw.template.json`:
```json
"model": {"primary": "alibaba-coding/kimi-k2.5"}
```

### Add more skills
Drop SKILL.md files into `config/workspace/skills/<skill-name>/`

### Enable WhatsApp
Add to `config/openclaw.template.json` under `channels`:
```json
"whatsapp": {"enabled": true, "dmPolicy": "pairing"}
```

## Test Results

All 10/10 end-to-end test cases passed:
1. Server info & connection
2. Model listing & filtering
3. Model field introspection
4. CRM pipeline stages
5. Lead search & read
6. Lead creation
7. Lead update
8. Credit control fields
9. Dashboard data
10. Multi-step workflow

Test evidence slides for customer delivery: `testcase-slides.pptx` (PowerPoint) and `testcase-slides.html` (web) in this directory.

## Troubleshooting

- **"no such file or directory" for entrypoint.sh**: CRLF line endings. Fix with `dos2unix entrypoint.sh` or ensure LF endings.
- **Telegram 409 conflict**: Another instance is using the same bot token. Stop the other instance first.
- **Agent won't run Bash/mcporter**: Ensure `tools.elevated.enabled: true` and `tools.elevated.allowFrom.telegram` is set in openclaw config.
- **`openclaw chat` not found**: OpenClaw v2026.3.2 removed `chat`. Use `openclaw agent --session-id X --message "..."` instead.
