#!/bin/bash
# PostToolUse hook: Track errors from tool executions
# When a tool fails, log the error. When it succeeds after a previous failure, log the fix.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_SCRIPT="$SCRIPT_DIR/smart-memory-db.py"
DB_PATH="$HOME/.claude/smart-memory.db"

INPUT=$(cat)

# Parse hook input
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)
TOOL_RESULT=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_result','')[:500])" 2>/dev/null)
PROJECT_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)

# Check if tool result contains error indicators
IS_ERROR=$(echo "$TOOL_RESULT" | python3 -c "
import sys
result = sys.stdin.read().lower()
indicators = ['error', 'traceback', 'exception', 'failed', 'errno', 'permission denied', 'not found', 'command failed', 'exit code']
print('1' if any(ind in result for ind in indicators) else '0')
" 2>/dev/null)

if [ "$IS_ERROR" = "1" ]; then
    # Extract error type
    ERROR_TYPE=$(echo "$TOOL_RESULT" | python3 -c "
import sys, re
result = sys.stdin.read()
# Try to extract error class
m = re.search(r'(\w+Error|\w+Exception)', result)
if m:
    print(m.group(1))
else:
    print('ToolError')
" 2>/dev/null)

    # Search for past fixes
    PAST_FIX=$(python3 "$DB_SCRIPT" search-errors "$ERROR_TYPE" 2>/dev/null)
    HAS_FIX=$(echo "$PAST_FIX" | python3 -c "
import sys,json
d=json.load(sys.stdin)
results = d.get('results',[])
fixes = [r for r in results if r.get('fix_applied')]
if fixes:
    print(fixes[0]['fix_applied'][:200])
else:
    print('')
" 2>/dev/null)

    # Log the error
    ERROR_JSON=$(python3 -c "
import json
print(json.dumps({
    'project_path': '$PROJECT_PATH',
    'error_type': '$ERROR_TYPE',
    'error_message': '''$TOOL_RESULT'''[:300],
    'tool_name': '$TOOL_NAME',
    'session_id': '$SESSION_ID',
    'fix_worked': 0
}))
" 2>/dev/null)
    python3 "$DB_SCRIPT" log-error "$ERROR_JSON" >/dev/null 2>&1

    # If we found a past fix, suggest it
    if [ -n "$HAS_FIX" ]; then
        echo "{\"continue\": true, \"systemMessage\": \"[Smart Memory] Similar error seen before. Past fix: $HAS_FIX\"}"
    else
        echo '{"continue": true}'
    fi
else
    echo '{"continue": true, "suppressOutput": true}'
fi
exit 0
