"""Initialize SQLite test database for Masi Bot test results."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "test_results.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            total_commands INTEGER,
            passed INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            command TEXT NOT NULL,
            scenario TEXT NOT NULL,
            path TEXT NOT NULL,
            messages_sent TEXT NOT NULL,
            chat_history TEXT NOT NULL,
            response TEXT NOT NULL,
            elapsed_ms INTEGER,
            tool_calls TEXT,
            tool_count INTEGER,
            has_pdf INTEGER DEFAULT 0,
            verdict TEXT NOT NULL,
            issues TEXT,
            agent_notes TEXT,
            tested_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS fixes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            command TEXT NOT NULL,
            issue TEXT NOT NULL,
            fix_description TEXT NOT NULL,
            files_changed TEXT,
            fixed_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
