#!/bin/bash
# SessionStart hook: Load project context from SQLite on every new session
# Also runs on resume, clear, compact events

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

# Get context summary
CONTEXT=$(python3 "$DB_SCRIPT" get-context "$PROJECT_PATH" 2>/dev/null)

# Build system message
if [ -n "$CONTEXT" ] && [ "$CONTEXT" != "{}" ]; then
    STATUS=$(echo "$CONTEXT" | python3 -c "
import sys, json
ctx = json.load(sys.stdin)
parts = []

# Current status
s = ctx.get('current_status')
if s and isinstance(s, dict):
    parts.append(f\"Project Status: {s.get('status','unknown')}\")
    if s.get('current_task'):
        parts.append(f\"Current Task: {s['current_task']}\")
    if s.get('pending_tasks'):
        parts.append(f\"Pending: {s['pending_tasks']}\")
    if s.get('notes'):
        parts.append(f\"Notes: {s['notes']}\")

# Recent actions
actions = ctx.get('recent_actions', [])
if actions:
    parts.append('Recent Actions:')
    for a in actions[:5]:
        parts.append(f\"  - [{a.get('action_type','')}] {a.get('description','')}\")

# Error patterns
patterns = ctx.get('error_patterns', [])
if patterns:
    parts.append('Known Error Patterns (with fixes):')
    for p in patterns[:5]:
        parts.append(f\"  - {p.get('error_type','')} (x{p.get('count',0)}): fix={p.get('last_fix','')}\")

print('\n'.join(parts) if parts else '')
" 2>/dev/null)

    if [ -n "$STATUS" ]; then
        echo "{\"continue\": true, \"suppressOutput\": true, \"systemMessage\": \"[Smart Memory] Project context loaded from SQLite:\\n$STATUS\"}"
        exit 0
    fi
fi

echo '{"continue": true, "suppressOutput": true}'
exit 0
