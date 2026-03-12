#!/usr/bin/env python3
"""Upload and execute seed_users.py on Odoo server via paramiko."""

import paramiko
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_SCRIPT = os.path.join(SCRIPT_DIR, 'seed_users.py')
REMOTE_SCRIPT = '/tmp/seed_users.py'

print("Connecting to Odoo server (103.72.97.51:24700)...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('103.72.97.51', port=24700, username='root')
print("Connected!")

# Upload script
print(f"Uploading {LOCAL_SCRIPT} -> {REMOTE_SCRIPT}")
sftp = ssh.open_sftp()
sftp.put(LOCAL_SCRIPT, REMOTE_SCRIPT)
sftp.close()
print("Upload complete.")

# Execute
print("\n" + "=" * 60)
print("EXECUTING seed_users.py ON SERVER")
print("=" * 60 + "\n")

stdin, stdout, stderr = ssh.exec_command(f'python3 {REMOTE_SCRIPT}', timeout=120)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')

if out:
    print(out)
if err:
    print("STDERR:", err)

exit_code = stdout.channel.recv_exit_status()
print(f"\nExit code: {exit_code}")

# Cleanup
ssh.exec_command(f'rm -f {REMOTE_SCRIPT}')
ssh.close()
print("Connection closed.")
