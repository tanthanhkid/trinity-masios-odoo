#!/bin/bash
# Phase 5A: Production readiness deployment script
# Run this on the Odoo server (103.72.97.51) as root
# Usage: bash phase5a-deploy.sh

set -e

ODOO_DIR="/opt/odoo/odoo-server"
CUSTOM_ADDONS="/opt/odoo/custom-addons"
MCP_SERVER="/opt/odoo/mcp-server"
BACKUP_DIR="/opt/odoo/backups"
DB_NAME="odoo"
ODOO_CONF="/etc/odoo.conf"

echo "=== Phase 5A: Production Readiness Deployment ==="
echo ""

# 0. Check disk space first
echo "[0/7] Checking disk space..."
DISK_USAGE=$(df / --output=pcent | tail -1 | tr -d ' %')
if [ "$DISK_USAGE" -gt 90 ]; then
    echo "WARNING: Disk usage at ${DISK_USAGE}%. Cleaning up..."
    apt-get clean 2>/dev/null || true
    find /var/log -name "*.gz" -delete 2>/dev/null || true
    find /var/log -name "*.1" -delete 2>/dev/null || true
    journalctl --vacuum-size=50M 2>/dev/null || true
    echo "Cleaned. New usage: $(df / --output=pcent | tail -1 | tr -d ' ')"
fi
echo ""

# 1. Backup database before any changes
echo "[1/7] Creating database backup..."
mkdir -p "$BACKUP_DIR"
sudo -u postgres pg_dump "$DB_NAME" | gzip > "$BACKUP_DIR/odoo_pre_phase5a_$(date +%Y%m%d_%H%M).gz"
echo "Backup saved to $BACKUP_DIR/"
echo ""

# 2. Install sale_management module (pulls in account, product, sale)
echo "[2/7] Installing sale_management module..."
systemctl stop odoo
sudo -u odoo "$ODOO_DIR/odoo-bin" -c "$ODOO_CONF" -i sale_management -d "$DB_NAME" --stop-after-init 2>&1 | tail -5
echo "sale_management installed."
echo ""

# 3. Deploy updated custom modules
echo "[3/7] Deploying custom modules..."
# Copy from repo (assumes repo is cloned at /tmp/odoo-repo or similar)
# If running from repo directly:
if [ -d "./custom-addons/masios_credit_control" ]; then
    cp -r ./custom-addons/masios_credit_control "$CUSTOM_ADDONS/"
    cp -r ./custom-addons/masios_dashboard "$CUSTOM_ADDONS/"
    chown -R odoo:odoo "$CUSTOM_ADDONS/"
fi

# Install custom modules
sudo -u odoo "$ODOO_DIR/odoo-bin" -c "$ODOO_CONF" -i masios_credit_control -d "$DB_NAME" --stop-after-init 2>&1 | tail -5
sudo -u odoo "$ODOO_DIR/odoo-bin" -c "$ODOO_CONF" -i masios_dashboard -d "$DB_NAME" --stop-after-init 2>&1 | tail -5
echo "Custom modules installed."
echo ""

# 4. Deploy updated MCP server
echo "[4/7] Deploying updated MCP server..."
if [ -f "./mcp/odoo-server/server.py" ]; then
    cp ./mcp/odoo-server/server.py "$MCP_SERVER/server.py"
    chown root:root "$MCP_SERVER/server.py"
fi
systemctl restart odoo-mcp
echo "MCP server restarted."
echo ""

# 5. Start Odoo
echo "[5/7] Starting Odoo..."
systemctl start odoo
sleep 3
systemctl is-active odoo && echo "Odoo is running." || echo "ERROR: Odoo failed to start!"
echo ""

# 6. Set up automated backup
echo "[6/7] Setting up daily backup cron..."
cat > /opt/odoo/backup.sh << 'BACKUP_SCRIPT'
#!/bin/bash
BACKUP_DIR="/opt/odoo/backups"
mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d_%H%M)
sudo -u postgres pg_dump odoo | gzip > "$BACKUP_DIR/odoo_${DATE}.gz"
# Keep only last 7 days
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete
# Log
echo "$(date): Backup completed - odoo_${DATE}.gz" >> /var/log/odoo/backup.log
BACKUP_SCRIPT
chmod +x /opt/odoo/backup.sh

# Add to cron (daily 2 AM) if not already there
(crontab -l 2>/dev/null | grep -v "backup.sh"; echo "0 2 * * * /opt/odoo/backup.sh") | crontab -
echo "Backup cron installed (daily 2 AM)."
echo ""

# 7. Verify all services
echo "[7/7] Verifying services..."
echo "  Odoo:     $(systemctl is-active odoo)"
echo "  MCP:      $(systemctl is-active odoo-mcp)"
echo "  Nginx:    $(systemctl is-active nginx)"
echo "  PgSQL:    $(systemctl is-active postgresql)"
echo "  Disk:     $(df / --output=pcent | tail -1 | tr -d ' ')"
echo ""

echo "=== Phase 5A Complete ==="
echo ""
echo "REMAINING MANUAL TASKS:"
echo "1. Change admin password: Odoo Settings > Users > Administrator > Change Password"
echo "2. Currency change (USD→VND): Delete all journal entries first, then change in Settings > Companies"
echo "   OR: Create new database with VND from scratch (recommended for clean start)"
echo "3. Purge test data: Delete test partners, leads, orders via Odoo UI"
echo "4. Configure Vietnamese chart of accounts and VAT rates"
echo "5. Create named user accounts for each employee"
echo "6. Deploy updated OpenClaw Docker configs to Mac Studio (100.81.203.48)"
