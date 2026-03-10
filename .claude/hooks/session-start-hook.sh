#!/bin/bash
# SessionStart hook: Load project context from SQLite + memory on every new session

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_SCRIPT="$SCRIPT_DIR/smart-memory-db.py"
DB_PATH="$HOME/.claude/smart-memory.db"

# Read stdin for hook input
INPUT=$(cat)
PROJECT_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd',''))" 2>/dev/null)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null)

# Initialize DB if not exists
if [ ! -f "$DB_PATH" ]; then
    python3 "$DB_SCRIPT" init >/dev/null 2>&1
fi

# Log session start
python3 -c "
import sqlite3, json
from datetime import datetime
db = sqlite3.connect('$DB_PATH')
db.execute('INSERT OR REPLACE INTO sessions (session_id, project_path, started_at) VALUES (?, ?, ?)',
    ('$SESSION_ID', '$PROJECT_PATH', datetime.now().isoformat()))
db.commit()
db.close()
" 2>/dev/null

# Get SQLite context
CONTEXT=$(python3 "$DB_SCRIPT" get-context "$PROJECT_PATH" 2>/dev/null)

# Build comprehensive system message
MSG=$(python3 -c "
import sys, json, os

parts = ['[Smart Memory - Session Context Loaded]']

# 1. SQLite context
try:
    ctx = json.loads('''$CONTEXT''') if '''$CONTEXT''' else {}

    s = ctx.get('current_status')
    if s and isinstance(s, dict):
        status_line = f\"Project: {s.get('status','unknown')}\"
        if s.get('current_task'):
            status_line += f\" | Task: {s['current_task']}\"
        parts.append(status_line)
        if s.get('completed_tasks'):
            parts.append(f\"Completed: {s['completed_tasks']}\")
        if s.get('pending_tasks'):
            parts.append(f\"Pending: {s['pending_tasks']}\")
        if s.get('notes'):
            parts.append(f\"Notes: {s['notes']}\")

    # Error patterns with fixes
    patterns = ctx.get('error_patterns', [])
    if patterns:
        parts.append('Known fixes:')
        for p in patterns[:8]:
            if p.get('last_fix'):
                parts.append(f\"  {p['error_type']}(x{p['count']}): {p['last_fix'][:150]}\")

    # Recent actions
    actions = ctx.get('recent_actions', [])
    if actions:
        parts.append('Recent: ' + '; '.join(f\"{a['action_type']}: {a['description'][:80]}\" for a in actions[:5]))

except:
    pass

# 2. Check for memory files
memory_dir = os.path.expanduser('~/.claude/projects/-Users-thanhtran-OFFLINE-FILES-Code-odoo/memory')
if os.path.isdir(memory_dir):
    memory_files = [f for f in os.listdir(memory_dir) if f.endswith('.md') and f != 'MEMORY.md']
    if memory_files:
        parts.append(f\"Memory files available: {', '.join(memory_files)}\")

# 3. Remind about auto-learning
parts.append('Auto-learning active: CLAUDE.md + memory + SQLite will be updated when session ends.')

print('\n'.join(parts))
" 2>/dev/null)

if [ -n "$MSG" ]; then
    # Escape for JSON
    MSG_ESCAPED=$(echo "$MSG" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))" 2>/dev/null)
    echo "{\"continue\": true, \"suppressOutput\": false, \"systemMessage\": $MSG_ESCAPED}"
else
    echo '{"continue": true, "suppressOutput": true}'
fi
exit 0
