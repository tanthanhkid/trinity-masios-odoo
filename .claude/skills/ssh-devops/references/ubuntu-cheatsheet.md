# Ubuntu Server Administration Cheatsheet

## Package Management

```bash
apt update && apt upgrade -y          # Update system
apt install <package> -y              # Install package
apt remove <package> -y               # Remove package
apt autoremove -y                     # Clean unused packages
dpkg -l | grep <keyword>              # Search installed packages
```

## User Management

```bash
adduser <username>                    # Create user
usermod -aG sudo <username>           # Add to sudo group
passwd <username>                     # Change password
deluser <username>                    # Delete user
who                                   # Show logged in users
last -10                              # Recent logins
```

## Firewall (UFW)

```bash
ufw status verbose                    # Check firewall status
ufw allow <port>/tcp                  # Allow port
ufw allow from <ip> to any port <port>  # Allow specific IP
ufw deny <port>                       # Deny port
ufw enable / ufw disable              # Toggle firewall
```

## Nginx

```bash
nginx -t                              # Test config
systemctl reload nginx                # Reload (no downtime)
systemctl restart nginx               # Full restart
ls /etc/nginx/sites-enabled/          # Active sites
cat /etc/nginx/sites-available/<site> # View site config
```

## Docker & Docker Compose

```bash
docker ps                             # Running containers
docker ps -a                          # All containers
docker logs --tail 100 <container>    # Container logs
docker exec -it <container> bash      # Enter container
docker stats --no-stream              # Resource usage
docker system prune -f                # Clean unused resources

docker compose up -d                  # Start services
docker compose down                   # Stop services
docker compose logs -f --tail 50      # Follow logs
docker compose pull                   # Pull latest images
docker compose restart <service>      # Restart one service
```

## Systemd Services

```bash
systemctl status <service>            # Service status
systemctl start/stop/restart <service>
systemctl enable/disable <service>    # Auto-start on boot
systemctl list-units --type=service --state=running --no-pager
journalctl -u <service> -f --no-pager  # Follow service logs
```

## SSL/TLS (Let's Encrypt)

```bash
certbot --nginx -d domain.com         # Get cert for nginx
certbot renew --dry-run               # Test renewal
certbot certificates                  # List certificates
```

## Monitoring Commands

```bash
htop                                  # Interactive process viewer
iotop                                 # Disk I/O monitor
nethogs                               # Network by process
vnstat                                # Network traffic stats
ncdu /                                # Disk usage explorer
```

## File Operations

```bash
find /path -name "*.log" -mtime +30 -delete  # Delete old logs
du -sh /path/*                        # Directory sizes
tar czf backup.tar.gz /path           # Create backup
rsync -avz src/ dest/                 # Sync files
```

## Cron Jobs

```bash
crontab -l                            # List cron jobs
crontab -e                            # Edit cron jobs
# Format: MIN HOUR DOM MON DOW command
# 0 2 * * * /path/to/backup.sh       # Daily at 2am
```

## Network

```bash
ss -tlnp                              # Listening ports
curl -I https://domain.com            # Check HTTP headers
ping -c 4 <host>                      # Test connectivity
traceroute <host>                     # Trace route
dig <domain>                          # DNS lookup
```

## Security

```bash
fail2ban-client status                # Fail2ban status
fail2ban-client status sshd           # SSH ban status
cat /var/log/auth.log | tail -50      # Auth logs
```

## Database

```bash
# MySQL/MariaDB
mysql -u root -p -e "SHOW DATABASES;"
mysqldump -u root -p <db> > backup.sql
mysql -u root -p <db> < backup.sql

# PostgreSQL
sudo -u postgres psql -l              # List databases
pg_dump <db> > backup.sql
psql <db> < backup.sql
```

## PM2 (Node.js Process Manager)

```bash
pm2 list                              # List processes
pm2 start app.js --name "myapp"       # Start app
pm2 restart myapp                     # Restart
pm2 logs myapp --lines 100            # View logs
pm2 monit                             # Monitor dashboard
pm2 save && pm2 startup               # Auto-start on boot
```
