#!/bin/bash
# Odoo Server Health Check Script
# Run on remote server to get Odoo-specific health overview

echo "========================================="
echo "  ODOO HEALTH CHECK - $(hostname)"
echo "  $(date)"
echo "========================================="

# --- System ---
echo ""
echo "--- System Info ---"
lsb_release -d 2>/dev/null || cat /etc/os-release | head -2
echo "Uptime: $(uptime -p 2>/dev/null || uptime)"
echo "Load: $(cat /proc/loadavg | awk '{print $1, $2, $3}')"

# --- Odoo Service ---
echo ""
echo "--- Odoo Service ---"
if systemctl is-active --quiet odoo 2>/dev/null; then
    echo "Status: RUNNING"
    echo "PID(s): $(pgrep -f odoo-bin | tr '\n' ' ')"
    echo "Workers: $(pgrep -f odoo-bin | wc -l)"
    echo "Memory: $(ps aux | grep odoo-bin | grep -v grep | awk '{sum+=$6} END {printf "%.0f MB\n", sum/1024}')"
else
    echo "Status: STOPPED or NOT FOUND"
fi

# --- Odoo HTTP Check ---
echo ""
echo "--- Odoo HTTP ---"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://localhost:8069/web/login 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "Web Login: OK (HTTP $HTTP_CODE)"
elif [ -n "$HTTP_CODE" ] && [ "$HTTP_CODE" != "000" ]; then
    echo "Web Login: WARNING (HTTP $HTTP_CODE)"
else
    echo "Web Login: UNREACHABLE"
fi

# Check longpolling/websocket port
WS_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8072/ 2>/dev/null)
echo "Longpolling (8072): HTTP $WS_CODE"

# --- PostgreSQL ---
echo ""
echo "--- PostgreSQL ---"
if systemctl is-active --quiet postgresql 2>/dev/null; then
    echo "Status: RUNNING"
    # Database sizes
    sudo -u postgres psql -t -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datname NOT IN ('template0','template1','postgres') ORDER BY pg_database_size(datname) DESC LIMIT 10;" 2>/dev/null || echo "Cannot query databases"
    # Active connections
    echo "Active connections: $(sudo -u postgres psql -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null | xargs)"
    echo "Total connections: $(sudo -u postgres psql -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null | xargs)"
else
    echo "Status: STOPPED"
fi

# --- Nginx ---
echo ""
echo "--- Nginx ---"
if systemctl is-active --quiet nginx 2>/dev/null; then
    echo "Status: RUNNING"
    nginx -t 2>&1 | tail -1
else
    echo "Status: NOT RUNNING or NOT INSTALLED"
fi

# --- Disk Usage ---
echo ""
echo "--- Disk Usage ---"
df -h / | tail -1 | awk '{print "Root: " $3 " used / " $2 " total (" $5 " used)"}'
echo "Odoo install: $(du -sh /opt/odoo/ 2>/dev/null | awk '{print $1}')"
echo "Odoo logs: $(du -sh /var/log/odoo/ 2>/dev/null | awk '{print $1}')"
echo "PostgreSQL: $(du -sh /var/lib/postgresql/ 2>/dev/null | awk '{print $1}')"

# Check filestore
FILESTORE_PATH="/opt/odoo/.local/share/Odoo/filestore"
if [ -d "$FILESTORE_PATH" ]; then
    echo "Filestore: $(du -sh $FILESTORE_PATH 2>/dev/null | awk '{print $1}')"
fi

# --- Memory ---
echo ""
echo "--- Memory ---"
free -h | grep -E "^(Mem|Swap)"

# --- Recent Odoo Errors ---
echo ""
echo "--- Recent Odoo Errors (last 10) ---"
if [ -f /var/log/odoo/odoo-server.log ]; then
    grep -i "error\|traceback\|critical" /var/log/odoo/odoo-server.log 2>/dev/null | tail -10
else
    journalctl -u odoo --no-pager -p err -n 10 2>/dev/null || echo "No Odoo logs found"
fi

# --- SSL Certificate ---
echo ""
echo "--- SSL Certificate ---"
CERT_FILE=$(find /etc/letsencrypt/live/ -name "fullchain.pem" 2>/dev/null | head -1)
if [ -n "$CERT_FILE" ]; then
    EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_FILE" 2>/dev/null | cut -d= -f2)
    echo "Expires: $EXPIRY"
    DAYS_LEFT=$(( ($(date -d "$EXPIRY" +%s 2>/dev/null || echo 0) - $(date +%s)) / 86400 ))
    if [ "$DAYS_LEFT" -lt 30 ] && [ "$DAYS_LEFT" -gt 0 ]; then
        echo "WARNING: Certificate expires in $DAYS_LEFT days!"
    elif [ "$DAYS_LEFT" -le 0 ]; then
        echo "CRITICAL: Certificate expired!"
    else
        echo "Days remaining: $DAYS_LEFT"
    fi
else
    echo "No Let's Encrypt certificate found"
fi

echo ""
echo "========================================="
echo "  Health check complete"
echo "========================================="
