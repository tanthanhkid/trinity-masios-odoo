# Trinity Masios Odoo - Project Guide

## Project Overview
Self-hosted Odoo deployment on Ubuntu server with custom module development capabilities.

## Server Details
- **IP**: 103.72.97.51
- **SSH Port**: 24700
- **User**: root
- **OS**: Ubuntu 24.04 LTS
- **Odoo Version**: 18.0 (Community)
- **Odoo Port**: 8069 (HTTP), 8072 (longpolling)

## Architecture
- Odoo installed at `/opt/odoo/odoo-server/`
- Custom addons at `/opt/odoo/custom-addons/`
- Config at `/etc/odoo.conf`
- Logs at `/var/log/odoo/odoo-server.log`
- Nginx reverse proxy on port 80/443
- PostgreSQL 16 local

## Skills Available
- **ssh-devops**: SSH operations, server management
- **odoo-selfhost**: Odoo install, deploy, module dev, troubleshoot
- **smart-memory**: Error learning via SQLite, project context persistence

## Conventions
- Use `sshpass` for SSH connections to this server
- Always backup before destructive operations
- Log errors and fixes to Smart Memory SQLite
- Custom modules go in `/opt/odoo/custom-addons/`
