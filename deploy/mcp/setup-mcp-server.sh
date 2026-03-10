#!/bin/bash
# Deploy Odoo MCP Server on the remote server
# Run this via SSH or from local: sshpass -p 'PASS' ssh -p 24700 root@103.72.97.51 'bash -s' < deploy/mcp/setup-mcp-server.sh

set -e

echo "=== Installing Odoo MCP Server ==="

# 1. Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "[1/4] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "[1/4] uv already installed"
fi

# 2. Copy server files
echo "[2/4] Setting up server files..."
mkdir -p /opt/odoo/mcp-server
cat > /opt/odoo/mcp-server/server.py << 'SERVEREOF'
PLACEHOLDER_WILL_BE_REPLACED
SERVEREOF

echo "[3/4] Installing systemd service..."
cat > /etc/systemd/system/odoo-mcp.service << 'SVCEOF'
[Unit]
Description=Odoo MCP Server (HTTP)
After=network.target odoo.service
Wants=odoo.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/odoo/mcp-server
Environment=ODOO_URL=http://127.0.0.1:8069
Environment=ODOO_DB=odoo
Environment=ODOO_USERNAME=admin
Environment=ODOO_PASSWORD=admin
ExecStart=/root/.local/bin/uv run --with mcp python3 /opt/odoo/mcp-server/server.py --http --port 8200
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable odoo-mcp
systemctl restart odoo-mcp

echo "[4/4] Checking status..."
sleep 2
systemctl status odoo-mcp --no-pager || true

echo ""
echo "=== MCP Server deployed ==="
echo "  URL: http://103.72.97.51:8200/mcp"
echo "  Status: systemctl status odoo-mcp"
echo "  Logs: journalctl -u odoo-mcp -f"
echo ""
echo "  For any OpenClaw:"
echo "    mcporter config add odoo http://103.72.97.51:8200/mcp --scope home"
