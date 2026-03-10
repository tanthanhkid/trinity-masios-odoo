#!/bin/bash
# PreCompact hook: Save current session state to SQLite before context compression
# This ensures critical context survives compaction

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_SCRIPT="$SCRIPT_DIR/smart-memory-db.py"
DB_PATH="$HOME/.claude/smart-memory.db"

INPUT=$(cat)
PROJECT_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd',''))" 2>/dev/null)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null)

# Get compact summary from SQLite
SUMMARY=$(python3 "$DB_SCRIPT" compact-summary "$PROJECT_PATH" 2>/dev/null)

if [ -n "$SUMMARY" ] && [ "$SUMMARY" != "{}" ]; then
    MSG=$(echo "$SUMMARY" | python3 -c "
import sys, json
s = json.load(sys.stdin)
parts = ['[Smart Memory - Preserved Context]']
st = s.get('current_status', {})
if isinstance(st, dict):
    parts.append(f\"Status: {st.get('status','')}, Task: {st.get('current_task','')}\")
    if st.get('pending_tasks'):
        parts.append(f\"Pending: {st['pending_tasks']}\")
actions = s.get('recent_actions', [])
if actions:
    parts.append('Recent: ' + '; '.join(f\"{a['action_type']}: {a['description']}\" for a in actions[:3]))
errs = s.get('unresolved_errors', [])
if errs:
    parts.append('Unresolved: ' + '; '.join(f\"{e['error_type']}: {e['error_message']}\" for e in errs[:3]))
print(' | '.join(parts))
" 2>/dev/null)
    echo "{\"continue\": true, \"systemMessage\": \"$MSG\"}"
else
    echo '{"continue": true}'
fi
exit 0
