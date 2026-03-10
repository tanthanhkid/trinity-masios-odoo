---
name: odoo-selfhost
description: This skill should be used when the user asks to "install Odoo", "deploy Odoo", "create Odoo module", "troubleshoot Odoo", "check Odoo logs", "monitor Odoo server", "update Odoo", "configure Odoo", "Odoo nginx setup", "Odoo PostgreSQL", "scaffold Odoo module", "Odoo ORM", "Odoo service restart", "backup Odoo database", or mentions Odoo self-hosting, on-premise deployment, or module development.
version: 1.0.0
---

# Odoo Self-Hosted: Install, Deploy, Develop & Troubleshoot

Comprehensive guide for managing self-hosted Odoo instances on Ubuntu servers. Covers installation, production deployment, custom module development, monitoring, and troubleshooting.

## Prerequisites

- Ubuntu 22.04/24.04 server with SSH access
- Python 3.12+ and PostgreSQL 16+
- Use the `ssh-devops` skill for SSH connection handling

## 1. Installation (Source Install on Ubuntu)

### Quick Install Script

Execute on remote server:

```bash
# System dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-dev python3-pip python3-venv \
  build-essential libxml2-dev libxslt1-dev libevent-dev \
  libsasl2-dev libldap2-dev libpq-dev libjpeg-dev zlib1g-dev \
  libfreetype6-dev liblcms2-dev libblas-dev libatlas-base-dev \
  nodejs npm postgresql postgresql-client

# wkhtmltopdf (required for PDF reports)
sudo apt install -y wkhtmltopdf

# rtlcss for RTL support
sudo npm install -g rtlcss

# PostgreSQL user
sudo -u postgres createuser -d -R -S odoo
sudo -u postgres createdb odoo

# Clone Odoo (Community)
sudo mkdir -p /opt/odoo
sudo git clone --depth 1 --branch master https://github.com/odoo/odoo.git /opt/odoo/odoo-server

# Python dependencies
cd /opt/odoo/odoo-server
sudo pip3 install -r requirements.txt
# Or use the debian helper:
# sudo ./setup/debinstall.sh

# Create Odoo system user
sudo useradd -m -d /opt/odoo -U -r -s /bin/bash odoo

# Create directories
sudo mkdir -p /opt/odoo/custom-addons
sudo mkdir -p /var/log/odoo
sudo chown -R odoo:odoo /opt/odoo /var/log/odoo
```

### Configuration File

Create `/etc/odoo.conf`:

```ini
[options]
admin_passwd = <strong_master_password>
db_host = localhost
db_port = 5432
db_user = odoo
db_password = <db_password>
db_name = odoo
addons_path = /opt/odoo/odoo-server/addons,/opt/odoo/custom-addons
logfile = /var/log/odoo/odoo-server.log
log_level = info
xmlrpc_port = 8069
proxy_mode = True
workers = 4
max_cron_threads = 1
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_time_cpu = 600
limit_time_real = 1200
```

**Worker calculation:** `(#CPU * 2) + 1`. 1 worker ≈ 6 concurrent users.
**RAM estimate:** `#workers * ((0.8 * 150MB) + (0.2 * 1024MB))`

### Systemd Service

Create `/etc/systemd/system/odoo.service`:

```ini
[Unit]
Description=Odoo
After=network.target postgresql.service

[Service]
Type=simple
SyslogIdentifier=odoo
PermissionsStartOnly=true
User=odoo
Group=odoo
ExecStart=/opt/odoo/odoo-server/odoo-bin -c /etc/odoo.conf
StandardOutput=journal+console
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable odoo
sudo systemctl start odoo
```

### Nginx Reverse Proxy

Refer to `references/nginx-odoo.conf` for the full production Nginx config with SSL and websocket support.

Key points:
- Upstream `odoo` on `127.0.0.1:8069` (HTTP)
- Upstream `odoochat` on `127.0.0.1:8072` (websocket/longpolling)
- `/websocket` location proxies to `odoochat`
- Enable `proxy_mode = True` in Odoo config

## 2. Module Development

### Scaffold a New Module

```bash
cd /opt/odoo/odoo-server
python3 odoo-bin scaffold <module_name> /opt/odoo/custom-addons/
```

This creates the module skeleton. Alternatively, create manually:

### Module Structure

```
my_module/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── my_model.py
├── views/
│   └── my_model_views.xml
├── security/
│   └── ir.model.access.csv
├── data/
│   └── data.xml
└── static/
    └── description/
        └── icon.png
```

### Minimal `__manifest__.py`

```python
{
    'name': 'My Module',
    'version': '1.0.0',
    'category': 'Uncategorized',
    'summary': 'Short description',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/my_model_views.xml',
    ],
    'installable': True,
    'application': True,
}
```

### Minimal Model

```python
from odoo import models, fields

class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'

    name = fields.Char(string='Name', required=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], default='draft')
```

### Upgrade Module After Changes

```bash
sudo systemctl restart odoo
# Or with upgrade flag:
/opt/odoo/odoo-server/odoo-bin -c /etc/odoo.conf -u my_module -d odoo --stop-after-init
sudo systemctl start odoo
```

For detailed ORM reference (fields, relations, computed fields, constraints), consult `references/odoo-orm-guide.md`.

## 3. Monitoring & Log Checking

### Service Status

```bash
systemctl status odoo
journalctl -u odoo --no-pager -n 100
journalctl -u odoo -f  # follow live
```

### Log File Analysis

```bash
# Recent errors
grep -i "error\|traceback\|critical" /var/log/odoo/odoo-server.log | tail -50

# Specific timeframe
grep "2024-01-15 14:" /var/log/odoo/odoo-server.log | grep -i error

# Slow queries
grep "query.*ms" /var/log/odoo/odoo-server.log | tail -20

# Follow logs live
tail -f /var/log/odoo/odoo-server.log
```

### Health Check

Use `scripts/odoo-health-check.sh` for comprehensive server + Odoo health monitoring.

Quick manual checks:
```bash
# Is Odoo responding?
curl -s -o /dev/null -w "%{http_code}" http://localhost:8069/web/login

# PostgreSQL connection
sudo -u odoo psql -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datname NOT IN ('template0','template1');"

# Disk usage
du -sh /opt/odoo/ /var/log/odoo/ /var/lib/postgresql/

# Worker count
ps aux | grep odoo-bin | grep -v grep | wc -l
```

## 4. Troubleshooting

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| 502 Bad Gateway | Odoo not running | `systemctl restart odoo` |
| Blank page | JS/CSS assets issue | Clear browser cache, regenerate assets |
| Login loop | Session/cookie issue | Clear cookies, check `proxy_mode` |
| Out of memory | Too many workers | Reduce `workers`, increase `limit_memory_*` |
| PDF not generating | wkhtmltopdf missing | Install wkhtmltopdf 0.12.6 |
| Module not found | Wrong addons_path | Check `addons_path` in config |
| DB connection refused | PostgreSQL down | `systemctl restart postgresql` |

### Regenerate Assets

```bash
# Via Odoo shell
/opt/odoo/odoo-server/odoo-bin shell -c /etc/odoo.conf -d odoo <<'EOF'
self.env['ir.attachment'].search([('url', 'like', '/web/assets/')]).unlink()
self.env.cr.commit()
EOF
sudo systemctl restart odoo
```

### Database Operations

```bash
# Backup
sudo -u odoo pg_dump odoo | gzip > /opt/odoo/backups/odoo_$(date +%Y%m%d_%H%M%S).sql.gz
# Also backup filestore:
tar czf /opt/odoo/backups/filestore_$(date +%Y%m%d).tar.gz /opt/odoo/.local/share/Odoo/filestore/

# Restore
gunzip < backup.sql.gz | sudo -u odoo psql odoo

# List databases
sudo -u odoo psql -l
```

## 5. Security Checklist

- Set strong `admin_passwd` (master password)
- Set `list_db = False` in production
- Use `dbfilter = ^%d$` to match database by hostname
- Enable HTTPS via Nginx + Let's Encrypt
- Run Odoo as non-root user (`odoo`)
- PostgreSQL user must NOT be superuser
- Block `/web/database` routes in Nginx
- Set up fail2ban for brute-force protection
- Regular backups with off-site copies

## Additional Resources

- **`references/nginx-odoo.conf`** - Production Nginx config with SSL and websocket
- **`references/odoo-orm-guide.md`** - ORM reference: fields, relations, methods, views
- **`scripts/odoo-health-check.sh`** - Server + Odoo health monitoring script
- **Official docs**: https://www.odoo.com/documentation/master/
