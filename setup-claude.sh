#!/bin/bash
# Trinity Masios Odoo - Claude Code Setup Script
# Run this after cloning the repo on a new machine to restore all skills, hooks, memory, and SQLite.
#
# Usage: bash setup-claude.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$HOME/.claude/plugins/local/devops-ssh"
INSTALLED_PLUGINS="$HOME/.claude/plugins/installed_plugins.json"
PROJECT_KEY=$(echo "$REPO_DIR" | sed 's|/|-|g' | sed 's|^-||')
MEMORY_DIR="$HOME/.claude/projects/$PROJECT_KEY/memory"
DB_PATH="$HOME/.claude/smart-memory.db"

echo "========================================="
echo "  Trinity Masios Odoo - Claude Setup"
echo "  Repo: $REPO_DIR"
echo "========================================="

# --- 1. Install global plugin ---
echo ""
echo "[1/5] Installing devops-ssh plugin..."
mkdir -p "$PLUGIN_DIR/.claude-plugin"
mkdir -p "$PLUGIN_DIR/hooks"
mkdir -p "$PLUGIN_DIR/skills"

# Copy plugin manifest
cat > "$PLUGIN_DIR/.claude-plugin/plugin.json" <<'PJSON'
{
  "name": "devops-ssh",
  "version": "1.1.0",
  "description": "SSH DevOps, Odoo self-hosting, and smart error-learning memory system with SQLite hooks",
  "skills": ["skills/ssh-devops", "skills/odoo-selfhost", "skills/smart-memory"],
  "hooks": "hooks/hooks.json"
}
PJSON

# Copy hooks from repo
cp -r "$REPO_DIR/.claude/hooks/"* "$PLUGIN_DIR/hooks/"
chmod +x "$PLUGIN_DIR/hooks/"*.sh "$PLUGIN_DIR/hooks/"*.py 2>/dev/null

# Copy skills from repo
cp -r "$REPO_DIR/.claude/skills/"* "$PLUGIN_DIR/skills/"
echo "  Plugin installed at: $PLUGIN_DIR"

# --- 2. Register plugin in installed_plugins.json ---
echo ""
echo "[2/5] Registering plugin..."
mkdir -p "$HOME/.claude/plugins"

if [ ! -f "$INSTALLED_PLUGINS" ]; then
    echo '{"version": 2, "plugins": {}}' > "$INSTALLED_PLUGINS"
fi

# Check if already registered
if grep -q "devops-ssh@local" "$INSTALLED_PLUGINS" 2>/dev/null; then
    echo "  Plugin already registered"
else
    # Add plugin entry using python for safe JSON manipulation
    python3 -c "
import json
with open('$INSTALLED_PLUGINS', 'r') as f:
    data = json.load(f)
data.setdefault('plugins', {})['devops-ssh@local'] = [{
    'scope': 'user',
    'installPath': '$PLUGIN_DIR',
    'version': '1.1.0',
    'installedAt': '$(date -u +%Y-%m-%dT%H:%M:%S.000Z)',
    'lastUpdated': '$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'
}]
with open('$INSTALLED_PLUGINS', 'w') as f:
    json.dump(data, f, indent=2)
"
    echo "  Plugin registered in installed_plugins.json"
fi

# --- 3. Initialize SQLite DB ---
echo ""
echo "[3/5] Initializing Smart Memory SQLite..."
python3 "$PLUGIN_DIR/hooks/smart-memory-db.py" init
echo "  DB at: $DB_PATH"

# --- 4. Seed memory files ---
echo ""
echo "[4/5] Setting up memory files..."
mkdir -p "$MEMORY_DIR"

# Copy memory files from repo if they exist, or create defaults
if [ -d "$REPO_DIR/.claude/memory" ]; then
    cp -r "$REPO_DIR/.claude/memory/"* "$MEMORY_DIR/" 2>/dev/null
    echo "  Memory files copied from repo"
else
    # Create default MEMORY.md from CLAUDE.md knowledge
    cat > "$MEMORY_DIR/MEMORY.md" <<'MEMEOF'
# Trinity Masios Odoo - Project Memory

## Server
- IP: 103.72.97.51, Port: 24700, User: root, OS: Ubuntu 24.04 LTS
- Odoo 18.0 Community at /opt/odoo/odoo-server/
- Custom addons at /opt/odoo/custom-addons/
- Config: /etc/odoo.conf, Logs: /var/log/odoo/odoo-server.log

## Known Fixes
- PostgreSQL auth: needs db_password in odoo.conf + md5 in pg_hba.conf
- Fresh DB: run `odoo-bin -i base --stop-after-init` first
- pip cryptography on Ubuntu 24.04: use `--ignore-installed`

## Plugin
- Global: ~/.claude/plugins/local/devops-ssh/
- Skills: ssh-devops, odoo-selfhost, smart-memory
- Hooks: session-start, error-tracker, compact, stop (auto-learn)

## Topic Files
- [server-config.md](server-config.md)
- [odoo-patterns.md](odoo-patterns.md)
MEMEOF
    echo "  Default memory created"
fi

# --- 5. Seed SQLite with project status ---
echo ""
echo "[5/5] Seeding project context..."
python3 "$PLUGIN_DIR/hooks/smart-memory-db.py" update-status "{
    \"project_path\": \"$REPO_DIR\",
    \"status\": \"active\",
    \"current_task\": \"Fresh setup on new machine\",
    \"completed_tasks\": \"Plugin installed, memory seeded, SQLite initialized\",
    \"pending_tasks\": \"Verify server access, check Odoo status\",
    \"notes\": \"Run: sshpass -p 'PASSWORD' ssh -p 24700 root@103.72.97.51 'systemctl status odoo'\"
}"

# Seed known error patterns
python3 "$PLUGIN_DIR/hooks/smart-memory-db.py" log-error "{
    \"project_path\": \"$REPO_DIR\",
    \"error_type\": \"psycopg2.OperationalError\",
    \"error_message\": \"fe_sendauth: no password supplied\",
    \"fix_applied\": \"Add db_password to odoo.conf + md5 auth in pg_hba.conf for odoo user\",
    \"fix_worked\": 1,
    \"tags\": \"postgresql,odoo,auth\"
}"

python3 "$PLUGIN_DIR/hooks/smart-memory-db.py" log-error "{
    \"project_path\": \"$REPO_DIR\",
    \"error_type\": \"KeyError\",
    \"error_message\": \"KeyError: ir.http - blank page after fresh install\",
    \"fix_applied\": \"Initialize DB: odoo-bin -c /etc/odoo.conf -d odoo -i base --stop-after-init --without-demo=all\",
    \"fix_worked\": 1,
    \"tags\": \"odoo,init,database\"
}"

python3 "$PLUGIN_DIR/hooks/smart-memory-db.py" log-error "{
    \"project_path\": \"$REPO_DIR\",
    \"error_type\": \"pip.InstallError\",
    \"error_message\": \"Cannot uninstall cryptography, RECORD file not found\",
    \"fix_applied\": \"pip3 install --break-system-packages --ignore-installed cryptography\",
    \"fix_worked\": 1,
    \"tags\": \"python,pip,ubuntu2404\"
}"

echo ""
echo "========================================="
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Restart Claude Code (close & reopen)"
echo "  2. Install sshpass: brew install hudochenkov/sshpass/sshpass"
echo "  3. Clone Odoo source: git submodule update --init"
echo "  4. Test: ask Claude to 'check Odoo server status'"
echo "========================================="
