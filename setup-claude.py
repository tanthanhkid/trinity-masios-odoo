#!/usr/bin/env python3
"""
Trinity Masios Odoo - Claude Code Setup Script (Cross-Platform)
Works on macOS, Linux, and Windows.

Run after cloning the repo on a new machine:
    python3 setup-claude.py     (macOS/Linux)
    python setup-claude.py      (Windows)
"""

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_home():
    return Path.home()


def get_claude_dir():
    return get_home() / ".claude"


def get_repo_dir():
    return Path(__file__).resolve().parent


def get_project_key():
    """Generate the Claude project key from repo path."""
    repo = str(get_repo_dir())
    if platform.system() == "Windows":
        # C:\Users\foo\Code\odoo -> -C-Users-foo-Code-odoo (Claude uses this format)
        key = repo.replace("\\", "-").replace(":", "")
        if key.startswith("-"):
            key = key[1:]
    else:
        # /Users/foo/Code/odoo -> -Users-foo-Code-odoo
        key = repo.replace("/", "-")
        if key.startswith("-"):
            key = key[1:]
    return key


def print_step(n, total, msg):
    print(f"\n[{n}/{total}] {msg}")


def copy_tree(src, dst):
    """Copy directory tree, creating dst if needed."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        s = src / item.name
        d = dst / item.name
        if s.is_dir():
            copy_tree(s, d)
        else:
            shutil.copy2(str(s), str(d))


def make_executable(path):
    """Make file executable on Unix systems."""
    if platform.system() != "Windows":
        for f in path.iterdir():
            if f.suffix in (".sh", ".py") and f.is_file():
                f.chmod(f.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def main():
    repo_dir = get_repo_dir()
    claude_dir = get_claude_dir()
    plugin_dir = claude_dir / "plugins" / "local" / "devops-ssh"
    installed_plugins_path = claude_dir / "plugins" / "installed_plugins.json"
    project_key = get_project_key()
    memory_dir = claude_dir / "projects" / project_key / "memory"
    db_script = plugin_dir / "hooks" / "smart-memory-db.py"
    system = platform.system()

    print("=========================================")
    print("  Trinity Masios Odoo - Claude Setup")
    print(f"  OS: {system}")
    print(f"  Repo: {repo_dir}")
    print(f"  Claude: {claude_dir}")
    print("=========================================")

    # --- Check Python version ---
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8+ required")
        sys.exit(1)

    # ========================================
    # Step 1: Install global plugin
    # ========================================
    print_step(1, 6, "Installing devops-ssh plugin...")

    plugin_manifest_dir = plugin_dir / ".claude-plugin"
    plugin_manifest_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "hooks").mkdir(parents=True, exist_ok=True)
    (plugin_dir / "skills").mkdir(parents=True, exist_ok=True)

    # Write plugin manifest
    manifest = {
        "name": "devops-ssh",
        "version": "1.1.0",
        "description": "SSH DevOps, Odoo self-hosting, and smart error-learning memory system with SQLite hooks",
        "skills": ["skills/ssh-devops", "skills/odoo-selfhost", "skills/smart-memory"],
        "hooks": "hooks/hooks.json",
    }
    with open(plugin_manifest_dir / "plugin.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # Copy hooks from repo
    repo_hooks = repo_dir / ".claude" / "hooks"
    if repo_hooks.exists():
        copy_tree(repo_hooks, plugin_dir / "hooks")
        make_executable(plugin_dir / "hooks")

    # Copy skills from repo
    repo_skills = repo_dir / ".claude" / "skills"
    if repo_skills.exists():
        copy_tree(repo_skills, plugin_dir / "skills")

    print(f"  Plugin installed at: {plugin_dir}")

    # ========================================
    # Step 2: Register plugin
    # ========================================
    print_step(2, 6, "Registering plugin...")

    (claude_dir / "plugins").mkdir(parents=True, exist_ok=True)

    if installed_plugins_path.exists():
        with open(installed_plugins_path, "r") as f:
            plugins_data = json.load(f)
    else:
        plugins_data = {"version": 2, "plugins": {}}

    if "devops-ssh@local" not in plugins_data.get("plugins", {}):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        plugins_data.setdefault("plugins", {})["devops-ssh@local"] = [
            {
                "scope": "user",
                "installPath": str(plugin_dir),
                "version": "1.1.0",
                "installedAt": now,
                "lastUpdated": now,
            }
        ]
        with open(installed_plugins_path, "w") as f:
            json.dump(plugins_data, f, indent=2)
        print("  Plugin registered")
    else:
        # Update installPath in case it changed (different machine)
        plugins_data["plugins"]["devops-ssh@local"][0]["installPath"] = str(plugin_dir)
        with open(installed_plugins_path, "w") as f:
            json.dump(plugins_data, f, indent=2)
        print("  Plugin already registered (path updated)")

    # ========================================
    # Step 3: Initialize SQLite DB
    # ========================================
    print_step(3, 6, "Initializing Smart Memory SQLite...")

    result = subprocess.run(
        [sys.executable, str(db_script), "init"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        try:
            info = json.loads(result.stdout)
            print(f"  DB at: {info.get('db_path', '~/.claude/smart-memory.db')}")
        except json.JSONDecodeError:
            print("  DB initialized")
    else:
        print(f"  WARNING: DB init failed: {result.stderr}")

    # ========================================
    # Step 4: Seed memory files
    # ========================================
    print_step(4, 6, "Setting up memory files...")

    memory_dir.mkdir(parents=True, exist_ok=True)

    repo_memory = repo_dir / ".claude" / "memory"
    if repo_memory.exists():
        copy_tree(repo_memory, memory_dir)
        print("  Memory files copied from repo")
    else:
        # Create minimal MEMORY.md
        memory_md = memory_dir / "MEMORY.md"
        if not memory_md.exists():
            memory_md.write_text(
                "# Trinity Masios Odoo - Project Memory\n\n"
                "## Server\n"
                "- IP: 103.72.97.51, Port: 24700, User: root, OS: Ubuntu 24.04\n"
                "- Odoo 18.0 at /opt/odoo/odoo-server/\n\n"
                "## Plugin\n"
                "- Skills: ssh-devops, odoo-selfhost, smart-memory\n"
            )
            print("  Default MEMORY.md created")

    # ========================================
    # Step 5: Seed SQLite with known patterns
    # ========================================
    print_step(5, 6, "Seeding project context & known error patterns...")

    def run_db(cmd, data):
        subprocess.run(
            [sys.executable, str(db_script), cmd, json.dumps(data)],
            capture_output=True,
            text=True,
        )

    run_db("update-status", {
        "project_path": str(repo_dir),
        "status": "active",
        "current_task": "Fresh setup on new machine",
        "completed_tasks": "Plugin installed, memory seeded, SQLite initialized",
        "pending_tasks": "Verify server access, check Odoo status",
        "notes": f"OS: {system}, Python: {sys.version.split()[0]}",
    })

    errors = [
        {
            "project_path": str(repo_dir),
            "error_type": "psycopg2.OperationalError",
            "error_message": "fe_sendauth: no password supplied",
            "fix_applied": "Add db_password to odoo.conf + md5 auth in pg_hba.conf for odoo user",
            "fix_worked": 1,
            "tags": "postgresql,odoo,auth",
        },
        {
            "project_path": str(repo_dir),
            "error_type": "KeyError",
            "error_message": "KeyError: ir.http - blank page after fresh install",
            "fix_applied": "Initialize DB: odoo-bin -c /etc/odoo.conf -d odoo -i base --stop-after-init --without-demo=all",
            "fix_worked": 1,
            "tags": "odoo,init,database",
        },
        {
            "project_path": str(repo_dir),
            "error_type": "pip.InstallError",
            "error_message": "Cannot uninstall cryptography, RECORD file not found",
            "fix_applied": "pip3 install --break-system-packages --ignore-installed cryptography",
            "fix_worked": 1,
            "tags": "python,pip,ubuntu2404",
        },
    ]
    for err in errors:
        run_db("log-error", err)

    print("  Seeded 3 known error patterns")

    # ========================================
    # Step 6: Platform-specific notes
    # ========================================
    print_step(6, 6, "Platform check...")

    # Check sshpass
    sshpass_installed = shutil.which("sshpass") is not None

    print("")
    print("=========================================")
    print("  Setup complete!")
    print("")
    print("  Next steps:")
    print("  1. Restart Claude Code (close & reopen)")

    if not sshpass_installed:
        if system == "Darwin":
            print("  2. Install sshpass: brew install hudochenkov/sshpass/sshpass")
        elif system == "Linux":
            print("  2. Install sshpass: sudo apt install sshpass")
        elif system == "Windows":
            print("  2. Install sshpass: choco install sshpass")
            print("     OR use WSL: wsl --install, then apt install sshpass")
            print("     OR use SSH keys instead of passwords")
    else:
        print("  2. sshpass: already installed")

    print("  3. Clone Odoo source: git submodule update --init")
    print("  4. Test: ask Claude to 'check Odoo server status'")

    if system == "Windows":
        print("")
        print("  Windows notes:")
        print("  - Bash hooks run via Git Bash (installed with Git for Windows)")
        print("  - If hooks fail, ensure Git Bash is in PATH")
        print("  - Alternative: use WSL for full Linux compatibility")

    print("=========================================")


if __name__ == "__main__":
    main()
