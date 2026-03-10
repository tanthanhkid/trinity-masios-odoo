#!/usr/bin/env python3
"""Smart Memory SQLite DB for Claude Code error learning and project context.

Usage:
  smart-memory-db.py init                          # Initialize DB
  smart-memory-db.py log-error <json>              # Log an error + fix
  smart-memory-db.py search-errors <query>         # Search past errors
  smart-memory-db.py log-action <json>             # Log a completed action
  smart-memory-db.py get-context [project_path]    # Get project context summary
  smart-memory-db.py update-status <json>          # Update project status
  smart-memory-db.py get-status [project_path]     # Get current project status
  smart-memory-db.py compact-summary [project_path]# Get compact-safe summary
"""

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = os.path.expanduser("~/.claude/smart-memory.db")


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            project_path TEXT,
            error_type TEXT NOT NULL,
            error_message TEXT NOT NULL,
            context TEXT,
            fix_applied TEXT,
            fix_worked INTEGER DEFAULT 1,
            tool_name TEXT,
            file_path TEXT,
            tags TEXT,
            session_id TEXT
        );

        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            project_path TEXT,
            action_type TEXT NOT NULL,
            description TEXT NOT NULL,
            result TEXT,
            session_id TEXT
        );

        CREATE TABLE IF NOT EXISTS project_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_path TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            current_task TEXT,
            completed_tasks TEXT,
            pending_tasks TEXT,
            notes TEXT,
            session_id TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE,
            project_path TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            summary TEXT
        );

        -- Indexes for fast search
        CREATE INDEX IF NOT EXISTS idx_errors_project ON errors(project_path);
        CREATE INDEX IF NOT EXISTS idx_errors_type ON errors(error_type);
        CREATE INDEX IF NOT EXISTS idx_errors_message ON errors(error_message);
        CREATE INDEX IF NOT EXISTS idx_errors_tags ON errors(tags);
        CREATE INDEX IF NOT EXISTS idx_actions_project ON actions(project_path);
        CREATE INDEX IF NOT EXISTS idx_status_project ON project_status(project_path);
        CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_path);

        -- FTS virtual table for full-text search on errors
        CREATE VIRTUAL TABLE IF NOT EXISTS errors_fts USING fts5(
            error_type, error_message, context, fix_applied, tags,
            content='errors',
            content_rowid='id'
        );

        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS errors_ai AFTER INSERT ON errors BEGIN
            INSERT INTO errors_fts(rowid, error_type, error_message, context, fix_applied, tags)
            VALUES (new.id, new.error_type, new.error_message, new.context, new.fix_applied, new.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS errors_ad AFTER DELETE ON errors BEGIN
            INSERT INTO errors_fts(errors_fts, rowid, error_type, error_message, context, fix_applied, tags)
            VALUES ('delete', old.id, old.error_type, old.error_message, old.context, old.fix_applied, old.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS errors_au AFTER UPDATE ON errors BEGIN
            INSERT INTO errors_fts(errors_fts, rowid, error_type, error_message, context, fix_applied, tags)
            VALUES ('delete', old.id, old.error_type, old.error_message, old.context, old.fix_applied, old.tags);
            INSERT INTO errors_fts(rowid, error_type, error_message, context, fix_applied, tags)
            VALUES (new.id, new.error_type, new.error_message, new.context, new.fix_applied, new.tags);
        END;
    """)
    db.commit()
    db.close()
    print(json.dumps({"status": "initialized", "db_path": DB_PATH}))


def log_error(data):
    db = get_db()
    d = json.loads(data) if isinstance(data, str) else data
    db.execute("""
        INSERT INTO errors (timestamp, project_path, error_type, error_message, context, fix_applied, fix_worked, tool_name, file_path, tags, session_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        d.get("project_path", ""),
        d.get("error_type", "unknown"),
        d.get("error_message", ""),
        d.get("context", ""),
        d.get("fix_applied", ""),
        d.get("fix_worked", 1),
        d.get("tool_name", ""),
        d.get("file_path", ""),
        d.get("tags", ""),
        d.get("session_id", ""),
    ))
    db.commit()
    db.close()
    print(json.dumps({"status": "logged"}))


def search_errors(query):
    db = get_db()
    # Try FTS first
    rows = db.execute("""
        SELECT e.* FROM errors e
        JOIN errors_fts fts ON e.id = fts.rowid
        WHERE errors_fts MATCH ?
        ORDER BY e.timestamp DESC
        LIMIT 10
    """, (query,)).fetchall()

    if not rows:
        # Fallback to LIKE search
        q = f"%{query}%"
        rows = db.execute("""
            SELECT * FROM errors
            WHERE error_message LIKE ? OR error_type LIKE ? OR context LIKE ? OR fix_applied LIKE ? OR tags LIKE ?
            ORDER BY timestamp DESC LIMIT 10
        """, (q, q, q, q, q)).fetchall()

    results = [dict(r) for r in rows]
    db.close()
    print(json.dumps({"count": len(results), "results": results}, default=str))


def log_action(data):
    db = get_db()
    d = json.loads(data) if isinstance(data, str) else data
    db.execute("""
        INSERT INTO actions (timestamp, project_path, action_type, description, result, session_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        d.get("project_path", ""),
        d.get("action_type", ""),
        d.get("description", ""),
        d.get("result", ""),
        d.get("session_id", ""),
    ))
    db.commit()
    db.close()
    print(json.dumps({"status": "logged"}))


def get_context(project_path=""):
    db = get_db()

    # Recent errors for this project
    errors = db.execute("""
        SELECT error_type, error_message, fix_applied, timestamp
        FROM errors WHERE project_path LIKE ? AND fix_worked = 1
        ORDER BY timestamp DESC LIMIT 15
    """, (f"%{project_path}%",)).fetchall()

    # Recent actions
    actions = db.execute("""
        SELECT action_type, description, result, timestamp
        FROM actions WHERE project_path LIKE ?
        ORDER BY timestamp DESC LIMIT 15
    """, (f"%{project_path}%",)).fetchall()

    # Latest status
    status = db.execute("""
        SELECT * FROM project_status WHERE project_path LIKE ?
        ORDER BY timestamp DESC LIMIT 1
    """, (f"%{project_path}%",)).fetchone()

    # Recent sessions
    sessions = db.execute("""
        SELECT session_id, started_at, ended_at, summary
        FROM sessions WHERE project_path LIKE ?
        ORDER BY started_at DESC LIMIT 5
    """, (f"%{project_path}%",)).fetchall()

    # Error frequency (top patterns)
    patterns = db.execute("""
        SELECT error_type, COUNT(*) as count, MAX(fix_applied) as last_fix
        FROM errors WHERE project_path LIKE ?
        GROUP BY error_type ORDER BY count DESC LIMIT 10
    """, (f"%{project_path}%",)).fetchall()

    result = {
        "project": project_path,
        "recent_errors": [dict(r) for r in errors],
        "recent_actions": [dict(r) for r in actions],
        "current_status": dict(status) if status else None,
        "recent_sessions": [dict(r) for r in sessions],
        "error_patterns": [dict(r) for r in patterns],
    }
    db.close()
    print(json.dumps(result, default=str))


def update_status(data):
    db = get_db()
    d = json.loads(data) if isinstance(data, str) else data
    db.execute("""
        INSERT INTO project_status (project_path, timestamp, status, current_task, completed_tasks, pending_tasks, notes, session_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        d.get("project_path", ""),
        datetime.now().isoformat(),
        d.get("status", "active"),
        d.get("current_task", ""),
        d.get("completed_tasks", ""),
        d.get("pending_tasks", ""),
        d.get("notes", ""),
        d.get("session_id", ""),
    ))
    db.commit()
    db.close()
    print(json.dumps({"status": "updated"}))


def get_status(project_path=""):
    db = get_db()
    status = db.execute("""
        SELECT * FROM project_status WHERE project_path LIKE ?
        ORDER BY timestamp DESC LIMIT 1
    """, (f"%{project_path}%",)).fetchone()
    db.close()
    if status:
        print(json.dumps(dict(status), default=str))
    else:
        print(json.dumps({"status": "no_status_found"}))


def compact_summary(project_path=""):
    """Generate a concise summary for context preservation during compaction."""
    db = get_db()

    status = db.execute("""
        SELECT status, current_task, pending_tasks, notes
        FROM project_status WHERE project_path LIKE ?
        ORDER BY timestamp DESC LIMIT 1
    """, (f"%{project_path}%",)).fetchone()

    recent_actions = db.execute("""
        SELECT action_type, description FROM actions
        WHERE project_path LIKE ?
        ORDER BY timestamp DESC LIMIT 5
    """, (f"%{project_path}%",)).fetchall()

    unresolved = db.execute("""
        SELECT error_type, error_message FROM errors
        WHERE project_path LIKE ? AND fix_worked = 0
        ORDER BY timestamp DESC LIMIT 5
    """, (f"%{project_path}%",)).fetchall()

    summary = {
        "current_status": dict(status) if status else "No status recorded",
        "recent_actions": [dict(r) for r in recent_actions],
        "unresolved_errors": [dict(r) for r in unresolved],
    }
    db.close()
    print(json.dumps(summary, default=str))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else ""

    if cmd == "init":
        init_db()
    elif cmd == "log-error":
        log_error(arg)
    elif cmd == "search-errors":
        search_errors(arg)
    elif cmd == "log-action":
        log_action(arg)
    elif cmd == "get-context":
        get_context(arg)
    elif cmd == "update-status":
        update_status(arg)
    elif cmd == "get-status":
        get_status(arg)
    elif cmd == "compact-summary":
        compact_summary(arg)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
