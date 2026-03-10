# Server Configuration Details

## SSH
```
Host: 103.72.97.51
Port: 24700
User: root
Auth: password (sshpass)
```

## Odoo Config (/etc/odoo.conf)
- workers = 3 (for 2 CPU server)
- max_cron_threads = 1
- limit_memory_hard = 1677721600 (1.6GB)
- limit_memory_soft = 629145600 (600MB)
- proxy_mode = True
- list_db = False
- dbfilter = ^odoo$
- xmlrpc_port = 8069
- gevent_port = 8072

## Nginx
- /etc/nginx/sites-available/odoo.conf
- Upstream: odoo (8069), odoochat (8072)
- /websocket -> odoochat
- / -> odoo
- client_max_body_size = 200m
- No SSL yet (needs domain + certbot)

## PostgreSQL
- Version: 16
- Auth: md5 for odoo user (pg_hba.conf modified)
- DB name: odoo
- DB user: odoo

## Services
- systemctl start/stop/restart odoo
- systemctl reload nginx
- systemctl restart postgresql

## Other Services on Server
- Docker: running on port 3000
- Node.js app: running on port 3001
- Don't disrupt these when working with Odoo
