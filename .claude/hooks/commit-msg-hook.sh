#!/bin/bash
# Commit message quality validator for Claude Code PreToolUse hook
# Reads tool input from stdin, validates git commit message quality

INPUT=$(cat)

# Only process Bash tool calls that contain "git commit"
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    cmd = data.get('command', '') or data.get('input', {}).get('command', '')
    print(cmd)
except:
    print('')
" 2>/dev/null)

# Skip if not a git commit command
if ! echo "$COMMAND" | grep -q 'git commit'; then
    echo '{"decision": "allow"}'
    exit 0
fi

# Extract the commit message from the command
# Handle both -m "msg" and heredoc patterns
MSG=$(echo "$COMMAND" | python3 -c "
import sys, re

cmd = sys.stdin.read()

# Try heredoc pattern: cat <<'EOF' ... EOF
heredoc = re.search(r\"<<'?EOF'?\\n(.+?)\\nEOF\", cmd, re.DOTALL)
if heredoc:
    print(heredoc.group(1).strip())
    sys.exit(0)

# Try -m \"msg\" pattern
m_flag = re.search(r'-m\s+\"([^\"]+)\"', cmd)
if m_flag:
    print(m_flag.group(1).strip())
    sys.exit(0)

# Try -m 'msg' pattern
m_flag_sq = re.search(r\"-m\s+'([^']+)'\", cmd)
if m_flag_sq:
    print(m_flag_sq.group(1).strip())
    sys.exit(0)

print('')
" 2>/dev/null)

# If we can't extract the message, allow (don't block on parsing edge cases)
if [ -z "$MSG" ]; then
    echo '{"decision": "allow"}'
    exit 0
fi

ERRORS=""

# Rule 1: Subject line must exist and be non-trivial (>10 chars)
SUBJECT=$(echo "$MSG" | head -1)
SUBJECT_LEN=${#SUBJECT}
if [ "$SUBJECT_LEN" -lt 10 ]; then
    ERRORS="${ERRORS}\n- Subject line too short ($SUBJECT_LEN chars). Must be >10 chars with meaningful description."
fi

# Rule 2: Subject should follow type(scope): format
if ! echo "$SUBJECT" | grep -qE '^(feat|fix|refactor|docs|deploy|security|test|chore|auto)\('; then
    ERRORS="${ERRORS}\n- Subject must start with type(scope): format. Types: feat, fix, refactor, docs, deploy, security, test, chore"
fi

# Rule 3: Must have a body (description beyond subject)
BODY=$(echo "$MSG" | tail -n +3)
# Remove Co-Authored-By line from body check
BODY_CLEAN=$(echo "$BODY" | grep -v "Co-Authored-By:" | sed '/^$/d')
if [ -z "$BODY_CLEAN" ]; then
    ERRORS="${ERRORS}\n- Commit must have a description body explaining WHY, not just WHAT. Include a 'Changes:' section listing specific files/functions modified."
fi

# Rule 4: Should have Changes: section for non-trivial commits
if ! echo "$MSG" | grep -qi "changes:\|change:"; then
    # Only warn, don't block - some small commits may not need it
    if [ "$SUBJECT_LEN" -gt 0 ] && ! echo "$SUBJECT" | grep -qE '^(docs|chore|auto)\('; then
        ERRORS="${ERRORS}\n- Missing 'Changes:' section. List specific files and functions modified."
    fi
fi

# Rule 5: Reject known vague messages
VAGUE_PATTERNS="^fix bug$|^update$|^update code$|^misc$|^changes$|^wip$|^temp$|^stuff$|^minor$|^cleanup$|^fix$|^update files$"
if echo "$SUBJECT" | grep -qiE "$VAGUE_PATTERNS"; then
    ERRORS="${ERRORS}\n- Commit message is too vague. Describe WHAT changed and WHY."
fi

if [ -n "$ERRORS" ]; then
    # Escape for JSON
    ERRORS_JSON=$(echo -e "$ERRORS" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")
    echo "{\"decision\": \"block\", \"reason\": \"Commit message does not meet quality standards:\\n${ERRORS_JSON}\\n\\nRequired format:\\n<type>(<scope>): <summary>\\n\\n<why this change>\\n\\nChanges:\\n- <file>: <what changed>\"}"
    exit 0
fi

echo '{"decision": "allow"}'
