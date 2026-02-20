#!/usr/bin/env python3
"""PrunnerAI Universal Bridge Worker v2.0.0
Supports: streaming output, multi-machine, file transfer, sessions, resilience.
Install: pip install prunnerai  OR  python3 bridge_worker.py --key YOUR_KEY
"""
import subprocess, requests, time, os, signal, sys, argparse, platform, json, base64, threading
from pathlib import Path

__version__ = "2.0.0"
WORKER_VERSION = "2.0.0"

# === CLI Args ===
parser = argparse.ArgumentParser(description="PrunnerAI Bridge Worker")
parser.add_argument("command", nargs="?", default="start", help="Command: start")
parser.add_argument("--key", default=os.environ.get("BRIDGE_API_KEY", ""), help="Bridge API key")
parser.add_argument("--name", default=os.environ.get("MACHINE_NAME", "default"), help="Machine name")
parser.add_argument("--poll-interval", type=int, default=int(os.environ.get("POLL_INTERVAL", "2")), help="Poll interval seconds")
parser.add_argument("--auto-restart", action="store_true", help="Auto-restart on crash")
args = parser.parse_args()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://xojgfprifegzbfejkkgm.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "sb_publishable_F0XckqGRBaqz2p9Q6wA7QA_G0pTQCPH")
BRIDGE_API_KEY = args.key
MACHINE_NAME = args.name
POLL_INTERVAL = args.poll_interval
MAX_OUTPUT = 50000
STREAM_BATCH_INTERVAL = 0.5
BLOCKED = ["rm -rf /", "mkfs", "dd if=/dev/zero", ":(){ :|:& };:", "format C:", "fdisk"]

# === Resilience ===
backoff = POLL_INTERVAL
MAX_BACKOFF = 60
total_executed = 0
last_error = None
uptime_start = time.time()

# === Sessions ===
sessions = {}
SESSION_TIMEOUT = 1800

running = True
def handle_sig(*_):
    global running
    running = False
    print("\nShutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sig)
signal.signal(signal.SIGTERM, handle_sig)

headers = {"Content-Type": "application/json", "x-bridge-api-key": BRIDGE_API_KEY}
os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

def poll():
    global backoff
    try:
        r = requests.post(
            f"{SUPABASE_URL}/functions/v1/bridge-poll",
            headers=headers,
            json={"worker_version": __version__, "os_info": os_info},
            timeout=10
        )
        if r.status_code == 200:
            backoff = POLL_INTERVAL
            return r.json().get("command")
        return None
    except Exception as e:
        global last_error
        last_error = str(e)
        backoff = min(backoff * 2, MAX_BACKOFF)
        print(f"Poll failed ({e}), retrying in {backoff}s...")
        return None

def stream_output(cmd_id, lines_batch):
    try:
        requests.post(
            f"{SUPABASE_URL}/functions/v1/bridge-stream",
            headers=headers,
            json={"command_id": cmd_id, "lines": lines_batch},
            timeout=10
        )
    except:
        pass

def execute_with_streaming(cmd_id, cmd_str, wd=None, timeout=60, session_id=None):
    if any(p in cmd_str for p in BLOCKED):
        return "BLOCKED: Dangerous command", 1

    cwd = wd
    env = None
    if session_id:
        cleanup_sessions()
        if session_id not in sessions:
            sessions[session_id] = {"cwd": os.getcwd(), "env": dict(os.environ), "last_used": time.time()}
        sess = sessions[session_id]
        cwd = cwd or sess["cwd"]
        env = sess["env"].copy()
        sess["last_used"] = time.time()

    try:
        proc = subprocess.Popen(
            cmd_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=cwd, env=env
        )

        all_output = []
        pending_lines = []
        last_flush = time.time()

        def read_stream(pipe, stream_name):
            for line in iter(pipe.readline, ""):
                all_output.append(line)
                pending_lines.append({"content": line.rstrip("\n"), "stream": stream_name})

        stdout_thread = threading.Thread(target=read_stream, args=(proc.stdout, "stdout"))
        stderr_thread = threading.Thread(target=read_stream, args=(proc.stderr, "stderr"))
        stdout_thread.start()
        stderr_thread.start()

        start = time.time()
        while stdout_thread.is_alive() or stderr_thread.is_alive():
            time.sleep(0.1)
            if time.time() - last_flush >= STREAM_BATCH_INTERVAL and pending_lines:
                stream_output(cmd_id, pending_lines[:])
                pending_lines.clear()
                last_flush = time.time()
            if time.time() - start > timeout:
                proc.kill()
                return "TIMEOUT", 124

        stdout_thread.join()
        stderr_thread.join()

        if pending_lines:
            stream_output(cmd_id, pending_lines)

        proc.wait()
        output = "".join(all_output)

        if session_id and proc.returncode == 0:
            try:
                pwd = subprocess.run("pwd", shell=True, capture_output=True, text=True, cwd=cwd, env=env, timeout=5)
                if pwd.returncode == 0:
                    sessions[session_id]["cwd"] = pwd.stdout.strip()
            except:
                pass

        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + "\n...[truncated]"
        return output, proc.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", 124
    except Exception as e:
        return f"ERROR: {e}", 1

def handle_file_upload(cmd):
    file_path = cmd.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        submit(cmd["id"], f"File not found: {file_path}", 1)
        return
    try:
        with open(file_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        r = requests.post(
            f"{SUPABASE_URL}/functions/v1/bridge-file-upload",
            headers=headers,
            json={"command_id": cmd["id"], "file_name": os.path.basename(file_path), "file_data": data},
            timeout=60
        )
        if r.status_code != 200:
            submit(cmd["id"], f"Upload failed: {r.text}", 1)
    except Exception as e:
        submit(cmd["id"], f"Upload error: {e}", 1)

def handle_file_download(cmd):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/functions/v1/bridge-file-download",
            headers=headers,
            json={"command_id": cmd["id"]},
            timeout=60
        )
        if r.status_code == 200:
            data = r.json()
            file_path = cmd.get("file_path") or data.get("file_path", "downloaded_file")
            content = base64.b64decode(data["file_data"])
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(content)
            print(f"Downloaded to {file_path}")
        else:
            submit(cmd["id"], f"Download failed: {r.text}", 1)
    except Exception as e:
        submit(cmd["id"], f"Download error: {e}", 1)

def cleanup_sessions():
    expired = [k for k, v in sessions.items() if time.time() - v["last_used"] > SESSION_TIMEOUT]
    for k in expired:
        del sessions[k]

def submit(cid, output, code):
    try:
        requests.post(
            f"{SUPABASE_URL}/functions/v1/bridge-result",
            headers=headers,
            json={"command_id": cid, "output": output, "exit_code": code},
            timeout=10
        )
    except:
        pass

def main_loop():
    global total_executed, backoff
    print(f"PrunnerAI Bridge Worker v{__version__}")
    print(f"Machine: {MACHINE_NAME} | OS: {os_info}")
    print(f"Polling every {POLL_INTERVAL}s...")

    while running:
        cmd = poll()
        if cmd:
            op = cmd.get("operation_type", "command")
            if op == "upload":
                print(f"Uploading: {cmd.get('file_path', '?')}")
                handle_file_upload(cmd)
            elif op == "download":
                print(f"Downloading: {cmd.get('file_path', '?')}")
                handle_file_download(cmd)
            else:
                print(f"Executing: {cmd['command'][:80]}...")
                out, code = execute_with_streaming(
                    cmd["id"], cmd["command"],
                    cmd.get("working_dir"), cmd.get("timeout_seconds", 60),
                    cmd.get("session_id")
                )
                submit(cmd["id"], out, code)
                print(f"Done (exit {code})")
            total_executed += 1
        time.sleep(backoff if not cmd else POLL_INTERVAL)

if __name__ == "__main__":
    if not BRIDGE_API_KEY:
        print("ERROR: No API key. Use --key YOUR_KEY or set BRIDGE_API_KEY env var.")
        sys.exit(1)

    while True:
        try:
            main_loop()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Worker crashed: {e}")
            if not args.auto_restart:
                break
            print("Restarting in 5s...")
            time.sleep(5)
