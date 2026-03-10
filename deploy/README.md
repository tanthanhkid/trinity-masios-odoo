# Deployment Config

Server config files (sanitized - no real passwords).

## Files

- `config/odoo.conf` - Odoo server configuration
- `config/odoo.service` - Systemd service unit
- `nginx/odoo.conf` - Nginx reverse proxy config

## Deploy to server

```bash
# Copy config (update passwords first!)
scp -P 24700 config/odoo.conf root@103.72.97.51:/etc/odoo.conf
scp -P 24700 config/odoo.service root@103.72.97.51:/etc/systemd/system/odoo.service
scp -P 24700 nginx/odoo.conf root@103.72.97.51:/etc/nginx/sites-available/odoo.conf

# Restart services
ssh -p 24700 root@103.72.97.51 'systemctl daemon-reload && systemctl restart odoo && systemctl reload nginx'
```

## Custom modules

Place custom Odoo modules in `/custom-addons/` directory. They will be synced to the server at `/opt/odoo/custom-addons/`.
