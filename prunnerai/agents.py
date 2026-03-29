"""PrunnerAI CLI — Agent management with real subprocess workers."""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

from prunnerai.config_manager import load_config
from prunnerai.offline_queue import resilient_request

AGENTS_DIR = Path.home() / ".prunnerai" / "agents"


def _api_request(endpoint, data=None, method="GET", api_key="", backend="", anon_key="", token_header="x-bridge-key"):
    url = f"{backend}/functions/v1/{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        token_header: api_key,
    }
    if data:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
    else:
        req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  ⚠ API error {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"  ⚠ Request failed: {e}")
        return None


def _get_pid_file(agent_id):
    return AGENTS_DIR / f"{agent_id}.pid"


def _write_pid(agent_id):
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    pid_file = _get_pid_file(agent_id)
    pid_file.write_text(str(os.getpid()))


def _remove_pid(agent_id):
    pid_file = _get_pid_file(agent_id)
    if pid_file.exists():
        pid_file.unlink()


def _is_agent_running(agent_id):
    pid_file = _get_pid_file(agent_id)
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, PermissionError):
        pid_file.unlink(missing_ok=True)
        return False


def _execute_task(task):
    action_type = task.get("action_type", "")
    action_data = task.get("action_data") or {}
    description = task.get("action_description", "")

    print(f"  ⚡ Executing: {description[:60]}{'...' if len(description) > 60 else ''}")

    if action_type in ("shell", "command", "execute"):
        cmd = action_data.get("command", description)
        try:
            process = subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                cwd=action_data.get("cwd", str(Path.home())),
            )
            output_lines = []
            for line in iter(process.stdout.readline, ""):
                output_lines.append(line)
                if sum(len(l) for l in output_lines) > 50000:
                    output_lines.append("\n... [truncated] ...")
                    process.kill()
                    break
            process.wait(timeout=300)
            output = "".join(output_lines)
            return {
                "result_status": "completed" if process.returncode == 0 else "failed",
                "result_data": {"exit_code": process.returncode, "output": output},
            }
        except subprocess.TimeoutExpired:
            process.kill()
            return {"result_status": "failed", "result_data": {"error": "Timed out (5 min)"}}
        except Exception as e:
            return {"result_status": "failed", "result_data": {"error": str(e)}}

    elif action_type in ("python", "script"):
        script = action_data.get("script", "")
        if not script:
            return {"result_status": "failed", "result_data": {"error": "No script provided"}}
        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, timeout=300,
                cwd=action_data.get("cwd", str(Path.home())),
            )
            return {
                "result_status": "completed" if result.returncode == 0 else "failed",
                "result_data": {
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:20000],
                    "stderr": result.stderr[:5000],
                },
            }
        except Exception as e:
            return {"result_status": "failed", "result_data": {"error": str(e)}}

    else:
        return {
            "result_status": "completed",
            "result_data": {"message": f"Acknowledged task type: {action_type}", "description": description},
        }


def _agent_worker(agent_id, connection_token, backend, anon_key, poll_interval=5):
    running = True

    def stop_handler(sig, frame):
        nonlocal running
        print(f"\n🛑 Stopping agent {agent_id[:8]}...")
        running = False

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    _write_pid(agent_id)
    print(f"🤖 Agent worker started: {agent_id[:8]}...")
    print(f"   PID: {os.getpid()}")
    print(f"   Poll interval: {poll_interval}s")
    print(f"   Press Ctrl+C to stop\n")

    consecutive_errors = 0

    try:
        while running:
            try:
                url = f"{backend}/functions/v1/agent-task-queue"
                headers = {
                    "Content-Type": "application/json",
                    "apikey": anon_key,
                    "Authorization": f"Bearer {anon_key}",
                    "x-connection-token": connection_token,
                }
                req = urllib.request.Request(url, data=b'{}', headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        result = json.loads(resp.read().decode())
                except (urllib.error.URLError, OSError):
                    consecutive_errors += 1
                    if consecutive_errors > 5:
                        print(f"  ⏳ Backend unreachable, retrying...")
                    time.sleep(min(poll_interval * consecutive_errors, 60))
                    continue
                except urllib.error.HTTPError as e:
                    body = e.read().decode() if e.fp else ""
                    print(f"  ⚠ Poll error {e.code}: {body[:100]}")
                    time.sleep(poll_interval)
                    continue

                consecutive_errors = 0
                tasks = result.get("tasks", [])

                for task in tasks:
                    task_id = task.get("id")
                    exec_result = _execute_task(task)

                    resilient_request(
                        "agent-task-result",
                        data={
                            "task_id": task_id,
                            "result_status": exec_result["result_status"],
                            "result_data": exec_result["result_data"],
                        },
                        method="POST",
                        api_key=connection_token,
                        backend=backend,
                        anon_key=anon_key,
                    )

                    status_icon = "✅" if exec_result["result_status"] == "completed" else "❌"
                    print(f"  {status_icon} Task {task_id[:8]}... → {exec_result['result_status']}")

                messages = result.get("messages", [])
                for msg in messages:
                    print(f"  💬 Message from {msg.get('from_agent_id', '?')[:8]}...: {msg.get('content', '')[:60]}")

                time.sleep(poll_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"  ⚠ Worker error: {e}")
                time.sleep(5)
    finally:
        _remove_pid(agent_id)
        print(f"👋 Agent {agent_id[:8]}... stopped.")


def handle_agents(args, default_backend, default_anon_key):
    cfg = load_config()
    api_key = cfg.get("bridge_key")
    backend = cfg.get("backend_url", default_backend)
    anon_key = cfg.get("anon_key", default_anon_key)

    if not api_key:
        print("❌ Bridge key required. Run: prunnerai config set bridge_key pb_xxx")
        sys.exit(1)

    if not args.agents_action or args.agents_action == "list":
        print("📋 Fetching agents...")
        result = _api_request(
            "bridge-poll",
            data={"action": "list_agents"},
            method="POST",
            api_key=api_key, backend=backend, anon_key=anon_key,
        )
        if result and "agents" in result:
            agents = result["agents"]
            if not agents:
                print("  No agents bound to this bridge key.")
            else:
                for a in agents:
                    status_icon = "🟢" if a.get("status") == "active" else "⚪"
                    agent_id = a.get("id", "?")
                    running = _is_agent_running(agent_id)
                    local_status = " [running locally]" if running else ""
                    print(f"  {status_icon} {a.get('name', 'Unnamed')} ({a.get('agent_type', '?')}) — {agent_id[:8]}...{local_status}")
        else:
            print("  Could not fetch agents.")

    elif args.agents_action == "start":
        agent_id = args.agent_id
        poll_interval = getattr(args, 'poll_interval', 5) or 5

        if _is_agent_running(agent_id):
            print(f"⚠ Agent {agent_id[:8]}... is already running.")
            return

        connection_token = cfg.get("connection_token")
        if not connection_token:
            print("❌ Connection token required. Run: prunnerai config set connection_token <token>")
            print("   (Get this from your sandbox deployment in the dashboard)")
            sys.exit(1)

        _agent_worker(agent_id, connection_token, backend, anon_key, poll_interval)

    elif args.agents_action == "stop":
        agent_id = args.agent_id
        pid_file = _get_pid_file(agent_id)
        if not pid_file.exists():
            print(f"⚠ Agent {agent_id[:8]}... is not running.")
            return
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            print(f"🛑 Sent stop signal to agent {agent_id[:8]}... (PID {pid})")
            time.sleep(1)
            pid_file.unlink(missing_ok=True)
        except ProcessLookupError:
            print(f"⚠ Agent process not found, cleaning up PID file.")
            pid_file.unlink(missing_ok=True)
        except Exception as e:
            print(f"❌ Failed to stop agent: {e}")

    elif args.agents_action == "deploy":
        agent_id = args.agent_id
        platform_name = args.platform
        connection_token = cfg.get("connection_token")

        print(f"📦 Deploying agent {agent_id[:8]}... to {platform_name}")

        result = _api_request(
            "agent-spawn-request",
            data={
                "agent_id": agent_id,
                "platform": platform_name,
                "deploy_local": True,
            },
            method="POST",
            api_key=api_key, backend=backend, anon_key=anon_key,
        )
        if result and result.get("success"):
            print(f"  ✅ Agent registered for {platform_name}")
            if connection_token:
                print(f"  🚀 Starting local worker...")
                _agent_worker(agent_id, connection_token, backend, anon_key)
            else:
                print("  ⚠ No connection_token configured. Set it to start local execution:")
                print("     prunnerai config set connection_token <token>")
        else:
            error = result.get("error", "Unknown error") if result else "No response"
            print(f"  ❌ Deploy failed: {error}")

    else:
        print(f"Unknown agents action: {args.agents_action}")
