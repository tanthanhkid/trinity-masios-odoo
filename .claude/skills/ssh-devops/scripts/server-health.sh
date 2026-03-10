#!/bin/bash
# Server Health Check Script
# Run on remote server to get a quick overview

echo "========================================="
echo "  SERVER HEALTH CHECK - $(hostname)"
echo "  $(date)"
echo "========================================="

echo ""
echo "--- OS Info ---"
lsb_release -d 2>/dev/null || cat /etc/os-release | head -2
uname -r
echo "Uptime: $(uptime -p 2>/dev/null || uptime)"

echo ""
echo "--- CPU ---"
echo "Load Average: $(cat /proc/loadavg | awk '{print $1, $2, $3}')"
echo "CPU Cores: $(nproc)"
top -bn1 | grep "Cpu(s)" | awk '{print "Usage: " $2 "% user, " $4 "% system, " $8 "% idle"}'

echo ""
echo "--- Memory ---"
free -h | grep -E "^(Mem|Swap)"

echo ""
echo "--- Disk Usage ---"
df -h | grep -E "^(/dev|Filesystem)" | head -10

echo ""
echo "--- Top 5 Processes by Memory ---"
ps aux --sort=-%mem | head -6

echo ""
echo "--- Docker Containers ---"
if command -v docker &>/dev/null; then
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker not accessible"
else
    echo "Docker not installed"
fi

echo ""
echo "--- Listening Ports ---"
ss -tlnp 2>/dev/null | head -20

echo ""
echo "--- Recent Errors (syslog, last 10) ---"
grep -i "error\|fail\|critical" /var/log/syslog 2>/dev/null | tail -10 || journalctl -p err --no-pager -n 10 2>/dev/null || echo "No syslog access"

echo ""
echo "========================================="
echo "  Health check complete"
echo "========================================="
