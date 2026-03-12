#!/bin/bash
set -e

CONFIG_DIR="$HOME/.openclaw"
MCPORTER_DIR="$HOME/.mcporter"

# --- Inject env vars into openclaw config ---
cp "$CONFIG_DIR/openclaw.template.json" "$CONFIG_DIR/openclaw.json"
sed -i "s|__ALIBABA_API_KEY__|${ALIBABA_API_KEY}|g" "$CONFIG_DIR/openclaw.json"
sed -i "s|__TELEGRAM_BOT_TOKEN__|${TELEGRAM_BOT_TOKEN}|g" "$CONFIG_DIR/openclaw.json"
sed -i "s|__OPENCLAW_GATEWAY_TOKEN__|${OPENCLAW_GATEWAY_TOKEN}|g" "$CONFIG_DIR/openclaw.json"

# --- Inject env vars into mcporter config ---
cp "$MCPORTER_DIR/mcporter.template.json" "$MCPORTER_DIR/mcporter.json"
sed -i "s|__ODOO_MCP_URL__|${ODOO_MCP_URL:-http://103.72.97.51:8200/sse}|g" "$MCPORTER_DIR/mcporter.json"
sed -i "s|__ODOO_MCP_TOKEN__|${ODOO_MCP_TOKEN}|g" "$MCPORTER_DIR/mcporter.json"

echo "=== OpenClaw Agent for Odoo ==="
echo "Gateway: 0.0.0.0:18789"
echo "Telegram: ${TELEGRAM_BOT_TOKEN:+enabled}"
echo "Odoo MCP: ${ODOO_MCP_URL:-http://103.72.97.51:8200/sse}"
echo "Model: alibaba-coding/glm-5"
echo "==============================="

# Export env vars for agent Bash commands (PDF sending via Telegram)
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"

# --- Auto-approve elevated commands (skip approval UI for Telegram) ---
openclaw config set agents.defaults.elevatedDefault full 2>/dev/null || true
openclaw config set tools.exec.security full 2>/dev/null || true

# --- Disable OpenClaw native commands on Telegram (only show custom /masi etc.) ---
openclaw config set commands.native false 2>/dev/null || true
openclaw config set commands.nativeSkills false 2>/dev/null || true

# Run OpenClaw gateway
exec openclaw gateway run --bind lan --port 18789 "$@"
