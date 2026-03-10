---
name: ssh-devops
description: This skill should be used when the user asks to "ssh to server", "deploy project", "check server logs", "monitor server", "restart service", "check disk space", "check server status", "deploy to production", "view nginx logs", "check docker containers", "server maintenance", or provides SSH credentials (IP, port, username, password). Handles all remote Linux/Ubuntu server operations via SSH.
---

# SSH DevOps - Remote Server Operations

Manage remote Ubuntu/Linux servers via SSH for deployment, log analysis, and monitoring.

## Server Credentials Format

Expect credentials in this format (may be provided in Vietnamese or English):

```
IP: <address>
Username/Tài khoản: <user>
Password/Mật khẩu: <password>
SSH Port/Cổng SSH: <port>
OS: Ubuntu
```

## Credential Storage

Store server credentials in the project's `.claude/devops-ssh.local.md` for reuse across sessions.

Format of `.claude/devops-ssh.local.md`:

```yaml
---
servers:
  - name: production
    host: 103.72.97.51
    user: root
    port: 24700
    os: Ubuntu
---
```

**IMPORTANT:** Never store passwords in config files. Prompt for password each session or use SSH keys.
When credentials are provided, save the non-sensitive parts to `.claude/devops-ssh.local.md` and remind the user to set up SSH key authentication for security.

## SSH Connection

Use `sshpass` or direct `ssh` to connect. Build the SSH command as:

```bash
sshpass -p '<password>' ssh -o StrictHostKeyChecking=no -p <port> <user>@<host> '<command>'
```

If `sshpass` is not available, install it:
- macOS: `brew install hudochenkov/sshpass/sshpass`
- Linux: `apt install sshpass`

For long-running or multi-step operations, chain commands with `&&` or use a heredoc:

```bash
sshpass -p '<password>' ssh -o StrictHostKeyChecking=no -p <port> <user>@<host> bash <<'REMOTE_EOF'
command1
command2
command3
REMOTE_EOF
```

## Core Operations

### 1. Deployment

Before deploying, gather project info:
- What type of project? (Node.js, Python, PHP, Docker, static)
- Where is the project on the server? (e.g., `/var/www/project`, `/home/user/app`)
- What's the deployment method? (git pull, docker, rsync, scp)

**Common deployment flow:**

```bash
# Git-based deployment
cd /path/to/project && git pull origin main && <build_command> && <restart_service>

# Docker deployment
cd /path/to/project && docker compose pull && docker compose up -d

# File upload (run locally)
sshpass -p '<pass>' scp -P <port> -r ./dist/* <user>@<host>:/var/www/project/
```

After deployment, always verify the service is running:
```bash
systemctl status <service>
# or
docker ps
# or
curl -s -o /dev/null -w "%{http_code}" http://localhost:<port>
```

### 2. Log Checking

**Common log locations on Ubuntu:**
- Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- Apache: `/var/log/apache2/access.log`, `/var/log/apache2/error.log`
- System: `/var/log/syslog`, `journalctl`
- Docker: `docker logs <container>`
- App logs: Check project directory or systemd journal
- PM2: `pm2 logs`

**Log commands:**
```bash
# Recent logs (last 100 lines)
tail -n 100 /var/log/nginx/error.log

# Follow logs in real-time (use timeout to avoid hanging)
timeout 10 tail -f /var/log/nginx/error.log

# Search logs for errors
grep -i "error\|fail\|critical" /var/log/syslog | tail -50

# Docker container logs
docker logs --tail 100 <container_name>

# Systemd service logs
journalctl -u <service_name> --no-pager -n 100

# Logs within a time range
journalctl --since "1 hour ago" --no-pager
```

### 3. Monitoring

**Quick server health check** - use the bundled script:
Read and execute `scripts/server-health.sh` on the remote server.

**Individual checks:**
```bash
# CPU & Memory
top -bn1 | head -20

# Disk usage
df -h

# Memory details
free -h

# Running services
systemctl list-units --type=service --state=running --no-pager

# Docker containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Network connections
ss -tlnp

# Process by resource usage
ps aux --sort=-%mem | head -20
```

### 4. Service Management

```bash
# Systemd services
systemctl status|start|stop|restart <service>
systemctl enable|disable <service>

# Docker
docker compose up -d / docker compose down / docker compose restart
docker compose logs --tail 50 <service>

# Nginx
nginx -t && systemctl reload nginx

# PM2 (Node.js)
pm2 list / pm2 restart <app> / pm2 logs <app>
```

## Safety Rules

- **Always confirm** before running destructive commands (rm -rf, drop database, stop production service)
- **Check before restart**: Verify config syntax before restarting services (e.g., `nginx -t`)
- **Backup first**: Before modifying config files, create a backup: `cp file file.bak.$(date +%Y%m%d)`
- **Use timeout**: For tail -f and watch commands, wrap with `timeout` to prevent hanging
- **Never store passwords** in files - use SSH keys when possible

## Troubleshooting

If SSH connection fails:
1. Check if port is correct
2. Verify IP is reachable: `ping <host>` or `nc -zv <host> <port>`
3. Check if sshpass is installed
4. Try with verbose: add `-v` flag to ssh

If command hangs:
- Use `timeout <seconds>` prefix
- Avoid interactive commands (use `-y` flags, `--no-pager`, `DEBIAN_FRONTEND=noninteractive`)

## Additional Resources

- **`scripts/server-health.sh`** - Comprehensive server health check script
- **`references/ubuntu-cheatsheet.md`** - Common Ubuntu administration commands
