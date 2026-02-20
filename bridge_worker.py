#!/usr/bin/env python3
"""PrunnerAI Universal Bridge Worker — Chief of Staff's local arm 🔥"""
import subprocess, requests, time, os, signal, sys

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
BRIDGE_API_KEY = os.environ.get("BRIDGE_API_KEY", "")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "2"))
MAX_OUTPUT = 50000
BLOCKED = ["rm -rf /", "mkfs", "dd if=/dev/zero", ":(){ :|:& };:", "format C:", "fdisk", "shutdown", "reboot"]

running = True
def handle_sig(*_):
    global running
    running = False
    print("\nShutting down...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sig)

headers = {"Content-Type": "application/json", "x-bridge-api-key": BRIDGE_API_KEY}

def poll():
    try:
        r = requests.post(f"{SUPABASE_URL}/functions/v1/bridge-poll", headers=headers, json={}, timeout=10)
        return r.json().get("command") if r.status_code == 200 else None
    except:
        return None

def execute(cmd, wd=None, timeout=60):
    if any(p in cmd for p in BLOCKED):
        return "BLOCKED: Dangerous command", 1
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=wd)
        out = r.stdout + r.stderr
        return (out[:MAX_OUTPUT] + "\n...[truncated]") if len(out) > MAX_OUTPUT else out, r.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", 124
    except Exception as e:
        return f"ERROR: {e}", 1

def submit(cid, output, code):
    try:
        requests.post(f"{SUPABASE_URL}/functions/v1/bridge-result", headers=headers, json={"command_id": cid, "output": output, "exit_code": code}, timeout=10)
    except:
        pass

print("🔥 PrunnerAI Bridge Worker started. Polling every {}s...".format(POLL_INTERVAL))
while running:
    cmd = poll()
    if cmd:
        print(f"⚡ Executing: {cmd['command'][:80]}...")
        out, code = execute(cmd["command"], cmd.get("working_dir"), cmd.get("timeout_seconds", 60))
        submit(cmd["id"], out, code)
        print(f"✅ Done (exit {code})")
    time.sleep(POLL_INTERVAL)
