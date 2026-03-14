#!/usr/bin/env python3
"""E2E test for 14 new MCP tools - executed on Odoo server via SSH.
Calls actual tool functions from server.py directly."""

import json
import os
import sqlite3
import subprocess
import sys

# Test script to run ON the server
REMOTE_SCRIPT = r'''
import json, sys, os
os.environ["ODOO_URL"] = "http://127.0.0.1:8069"
os.environ["ODOO_DB"] = "odoo"
os.environ["ODOO_USERNAME"] = "admin"
os.environ["ODOO_PASSWORD"] = os.environ.get("ODOO_ADMIN_PASSWORD", "admin")

# Add server dir to path and import
sys.path.insert(0, "/opt/odoo/mcp-server")
import importlib.util
spec = importlib.util.spec_from_file_location("server", "/opt/odoo/mcp-server/server.py")
mod = importlib.util.new_module("server")
# We need to prevent the server from starting - patch sys.argv
sys.argv = ["test"]

# Manual load: read the file, extract functions without running main
exec_ns = {"__name__": "server_test", "__file__": "/opt/odoo/mcp-server/server.py"}

# Actually, the functions are decorated with @mcp.tool() which registers them.
# We can just import the module - the if __name__ block prevents server start.
# But the module-level code creates the FastMCP instance.
# Let's just exec the relevant parts.

import xmlrpc.client
from datetime import date, datetime, timedelta

# Load config manually
url = "http://127.0.0.1:8069"
db = "odoo"
username = "admin"
password = "admin"

# Authenticate
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

def _sr(model, domain, fields=None, limit=0, order="", offset=0):
    kw = {}
    if fields: kw["fields"] = fields
    if limit: kw["limit"] = limit
    if order: kw["order"] = order
    if offset: kw["offset"] = offset
    return models.execute_kw(db, uid, password, model, "search_read", [domain], kw)

def _sc(model, domain):
    return models.execute_kw(db, uid, password, model, "search_count", [domain])

def _rg(model, domain, fields, groupby, lazy=True):
    return models.execute_kw(db, uid, password, model, "read_group", [domain, fields, groupby], {"lazy": lazy})

# Now import the actual server module to call its functions
# The tool functions use _connect() internally which returns (uid, models, url, db, password)
# Let's just call them via the MCP server's internal mechanism

# Better approach: just exec the server.py and grab the tool functions
import importlib, importlib.util

# Suppress server startup
os.environ["MCP_API_TOKEN"] = ""

# The server.py has: if __name__ == "__main__": ... which won't trigger on import
# But the module-level code registers tools via @mcp.tool()
# We need mcp package installed

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(json.dumps({"fatal": "mcp package not installed on server"}))
    sys.exit(1)

# Import the server module
spec = importlib.util.spec_from_file_location("odoo_server", "/opt/odoo/mcp-server/server.py")
server_mod = importlib.util.new_module("odoo_server")
spec.loader.exec_module(server_mod)

# Now call each tool function - they are decorated but the underlying function is accessible
# The @_odoo_error decorator wraps them, and @mcp.tool() registers them
# The actual functions should be callable directly

tests = [
    (1, "odoo_morning_brief", {}, "4 blocks"),
    (2, "odoo_ceo_alert", {"limit": 3}, "alerts"),
    (3, "odoo_revenue_today", {}, "revenue"),
    (4, "odoo_brief_hunter", {"period": "month"}, "hunter"),
    (5, "odoo_brief_farmer", {"period": "month"}, "farmer"),
    (6, "odoo_brief_ar", {}, "AR"),
    (7, "odoo_brief_cash", {"period": "month"}, "cash"),
    (8, "odoo_hunter_today", {"section": "all"}, "hunter today"),
    (9, "odoo_hunter_sla_details", {"status": "all", "limit": 5}, "SLA"),
    (10, "odoo_farmer_today", {"section": "all"}, "farmer today"),
    (11, "odoo_farmer_ar", {"limit": 5}, "farmer AR"),
    (12, "odoo_congno", {"mode": "overdue", "limit": 5}, "congno"),
    (13, "odoo_task_overdue", {"limit": 5}, "tasks"),
    (14, "odoo_flash_report", {"report_type": "midday"}, "flash"),
]

results = []
for num, name, params, desc in tests:
    try:
        fn = getattr(server_mod, name, None)
        if fn is None:
            results.append({"num": num, "tool": name, "status": "FAIL", "notes": "Function not found in server.py"})
            continue
        result_str = fn(**params)
        # Try to parse as JSON
        try:
            data = json.loads(result_str)
            if isinstance(data, dict) and "error" in data:
                results.append({"num": num, "tool": name, "status": "FAIL", "notes": data["error"][:200]})
            elif isinstance(data, dict):
                results.append({"num": num, "tool": name, "status": "PASS", "notes": f"keys={list(data.keys())[:8]}"})
            elif isinstance(data, list):
                results.append({"num": num, "tool": name, "status": "PASS", "notes": f"list len={len(data)}"})
            else:
                results.append({"num": num, "tool": name, "status": "PASS", "notes": f"type={type(data).__name__}"})
        except json.JSONDecodeError:
            results.append({"num": num, "tool": name, "status": "PASS", "notes": f"text len={len(result_str)}"})
    except Exception as e:
        results.append({"num": num, "tool": name, "status": "FAIL", "notes": str(e)[:200]})

print(json.dumps(results))
'''

def main():
    print("Running MCP tool tests on Odoo server via SSH...")

    # Write test script to server and execute it
    # Use sshpass to run on server
    proc = subprocess.run(
        [
            "sshpass", "-p", "root",
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-p", "24700",
            "root@103.72.97.51",
            f"python3 -c {repr(REMOTE_SCRIPT)}"
        ],
        capture_output=True, text=True, timeout=120
    )

    if proc.returncode != 0:
        print(f"SSH command failed: {proc.stderr[:500]}")
        # Try alternative: write script to file first
        print("Trying file-based approach...")

        # Write script to server
        write_proc = subprocess.run(
            [
                "sshpass", "-p", "root",
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-p", "24700",
                "root@103.72.97.51",
                "cat > /tmp/test_mcp.py"
            ],
            input=REMOTE_SCRIPT,
            capture_output=True, text=True, timeout=15
        )

        if write_proc.returncode != 0:
            print(f"Failed to write script: {write_proc.stderr}")
            return

        # Execute script
        proc = subprocess.run(
            [
                "sshpass", "-p", "root",
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-p", "24700",
                "root@103.72.97.51",
                "cd /opt/odoo/mcp-server && python3 /tmp/test_mcp.py"
            ],
            capture_output=True, text=True, timeout=120
        )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if stderr:
        # Filter out logging noise
        for line in stderr.split("\n"):
            if "ERROR" in line or "FAIL" in line or "Traceback" in line:
                print(f"  STDERR: {line}")

    # Parse results
    results = None
    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("["):
            try:
                results = json.loads(line)
                break
            except json.JSONDecodeError:
                pass

    if not results:
        print(f"Failed to parse results from server output:")
        print(stdout[-1000:] if len(stdout) > 1000 else stdout)
        return

    # Print summary table
    print(f"\n{'=' * 80}")
    print("E2E MCP TOOL TEST RESULTS")
    print("=" * 80)
    print(f"| {'#':>2} | {'Tool':<25} | {'Status':<6} | Notes")
    print(f"|{'-' * 4}|{'-' * 27}|{'-' * 8}|{'-' * 50}")

    errors_for_db = []
    for r in results:
        num = r["num"]
        tool = r["tool"]
        status = r["status"]
        notes = r["notes"]
        print(f"| {num:>2} | {tool:<25} | {status:<6} | {notes[:70]}")
        if status == "FAIL":
            errors_for_db.append((tool, notes))

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    print(f"\nTotal: {passed} PASS, {failed} FAIL out of {len(results)}")

    # Save errors to SQLite
    if errors_for_db:
        try:
            db_path = os.path.join(os.path.expanduser("~"), ".claude", "chat_history", "command_center_impl.db")
            conn = sqlite3.connect(db_path)
            conn.execute("""CREATE TABLE IF NOT EXISTS impl_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, phase TEXT, task TEXT, error_msg TEXT, iteration INTEGER
            )""")
            for tool_name, err in errors_for_db:
                conn.execute(
                    "INSERT INTO impl_errors (timestamp, phase, task, error_msg, iteration) VALUES (datetime('now'), 'P7-Test', ?, ?, 1)",
                    (tool_name, err)
                )
            conn.commit()
            conn.close()
            print(f"\nSaved {len(errors_for_db)} errors to SQLite DB at {db_path}")
        except Exception as e:
            print(f"\nFailed to save to SQLite: {e}")
    else:
        print("\nNo errors to save to SQLite - all tests passed!")


if __name__ == "__main__":
    main()
