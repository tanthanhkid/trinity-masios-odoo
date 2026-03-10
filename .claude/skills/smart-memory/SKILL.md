---
name: smart-memory
description: This skill should be used when encountering errors, needing to log fixes, checking past error patterns, updating project status, or when the user asks to "save this fix", "remember this error", "what errors have I seen", "project status", "update status". Provides smart error-learning memory via SQLite.
version: 1.0.0
---

# Smart Memory - Error Learning & Project Context System

A SQLite-backed persistent memory system that tracks errors, fixes, actions, and project status across Claude Code sessions.

## How It Works

### Automatic (via hooks)
- **SessionStart**: Loads project context from SQLite, shows past errors/fixes/status
- **PostToolUse**: Detects errors in Bash/Write/Edit results, logs them, suggests past fixes
- **PreCompact**: Preserves critical context before compaction
- **Stop**: Prompts to save project status before ending session

### Manual (via CLI)
The DB script is at `~/.claude/plugins/local/devops-ssh/hooks/smart-memory-db.py`.

#### Log an error with its fix
```bash
python3 ~/.claude/plugins/local/devops-ssh/hooks/smart-memory-db.py log-error '{
  "project_path": "/path/to/project",
  "error_type": "ImportError",
  "error_message": "No module named xyz",
  "fix_applied": "pip install xyz",
  "fix_worked": 1,
  "tags": "python,dependency"
}'
```

#### Search past errors
```bash
python3 ~/.claude/plugins/local/devops-ssh/hooks/smart-memory-db.py search-errors "ImportError"
```

#### Update project status
```bash
python3 ~/.claude/plugins/local/devops-ssh/hooks/smart-memory-db.py update-status '{
  "project_path": "/path/to/project",
  "status": "in_progress",
  "current_task": "Deploying Odoo",
  "completed_tasks": "Installed PostgreSQL, configured Nginx",
  "pending_tasks": "SSL setup, custom modules"
}'
```

#### Get project context
```bash
python3 ~/.claude/plugins/local/devops-ssh/hooks/smart-memory-db.py get-context "/path/to/project"
```

## DB Schema

| Table | Purpose |
|-------|---------|
| `errors` | Error log with type, message, fix, tags (FTS-indexed) |
| `actions` | Completed actions log |
| `project_status` | Current project state snapshots |
| `sessions` | Session tracking |
| `errors_fts` | Full-text search on errors |

## When to Use Manually

- After fixing a tricky bug: log the error + fix for future reference
- Before ending a long session: update project status
- When encountering an error: search past fixes first
- Starting work on a project: check context for recent status
