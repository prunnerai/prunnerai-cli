"""PrunnerAI CLI — Local WebGUI dashboard (FastAPI + embedded React SPA)."""

import json
import os
import platform
import shutil
import sys
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path

from prunnerai import __version__
from prunnerai.config_manager import load_config

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>PrunnerAI — Local Command Center</title>
<script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<style>
:root {
  --bg: #0a0a0f;
  --bg-card: #12121a;
  --bg-card-hover: #1a1a25;
  --border: #1e1e2e;
  --text: #e0e0e8;
  --text-muted: #6e6e80;
  --primary: #8b5cf6;
  --primary-dim: #6d3fd0;
  --green: #22c55e;
  --yellow: #eab308;
  --red: #ef4444;
  --blue: #3b82f6;
  --font-mono: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: var(--font-sans); }
.container { max-width: 1280px; margin: 0 auto; padding: 16px; }
.header { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
.header h1 { font-size: 16px; font-weight: 600; letter-spacing: -0.02em; }
.header h1 span { color: var(--primary); }
.badge { padding: 4px 10px; border-radius: 9999px; font-size: 11px; font-weight: 500; font-family: var(--font-mono); }
.badge-online { background: rgba(34,197,94,0.15); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
.badge-offline { background: rgba(239,68,68,0.15); color: var(--red); border: 1px solid rgba(239,68,68,0.3); }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.stat-card .label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
.stat-card .value { font-size: 22px; font-weight: 700; font-family: var(--font-mono); }
.main-grid { display: grid; grid-template-columns: 340px 1fr; gap: 16px; margin-bottom: 16px; }
@media (max-width: 900px) { .main-grid { grid-template-columns: 1fr; } .stats-row { grid-template-columns: repeat(2, 1fr); } }
.panel { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.panel-title { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 12px; }
.empty { text-align: center; padding: 40px; color: var(--text-muted); font-size: 13px; }
</style>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
const { useState, useEffect, useCallback } = React;
const API = '';
function App() {
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch(API + '/api/status');
      const d = await r.json();
      setStatus(d);
      setConnected(d.connected || false);
    } catch { setConnected(false); }
  }, []);
  useEffect(() => { fetchStatus(); const si = setInterval(fetchStatus, 10000); return () => clearInterval(si); }, []);
  return (
    <div className="container">
      <div className="header">
        <h1><span>PrunnerAI</span> — Local Command Center v""" + __version__ + """</h1>
        <span className={'badge ' + (connected ? 'badge-online' : 'badge-offline')}>
          {connected ? '● Connected' : '○ Disconnected'}
        </span>
      </div>
      <div className="empty">Dashboard loading... Connect your bridge worker to see live data.</div>
    </div>
  );
}
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
</script>
</body>
</html>"""


def create_app(backend_url, anon_key):
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
    except ImportError:
        print("❌ FastAPI required for GUI. Install: pip install prunnerai-cli[gui]")
        import sys
        sys.exit(1)

    app = FastAPI(title="PrunnerAI Local Command Center")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return DASHBOARD_HTML

    @app.get("/api/status")
    async def api_status():
        cfg = load_config()
        bridge_key = cfg.get("bridge_key", "")
        connected = False
        if bridge_key:
            try:
                url = f"{backend_url}/functions/v1/bridge-poll"
                headers = {
                    "Content-Type": "application/json",
                    "apikey": anon_key,
                    "Authorization": f"Bearer {anon_key}",
                    "x-bridge-key": bridge_key,
                }
                body = json.dumps({"machine_name": "gui-check"}).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5):
                    connected = True
            except Exception:
                pass

        disk = shutil.disk_usage(str(Path.home()))
        return {
            "connected": connected,
            "cli_version": __version__,
            "machine": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "disk_free_gb": round(disk.free / (1024**3), 1),
        }

    return app


def handle_gui(args, default_backend, default_anon_key):
    try:
        import uvicorn
    except ImportError:
        print("❌ uvicorn is required for the GUI. Install it:")
        print("   pip install prunnerai-cli[gui]")
        sys.exit(1)

    cfg = load_config()
    backend = cfg.get("backend_url", default_backend)
    anon_key = cfg.get("anon_key", default_anon_key)
    port = getattr(args, "port", 8420) or 8420
    no_browser = getattr(args, "no_browser", False)

    print(f"""
╔═══════════════════════════════════════════╗
║  PrunnerAI CLI  v{__version__:<22}║
║  Local Command Center — WebGUI            ║
╚═══════════════════════════════════════════╝
""")
    print(f"🌐 Starting server on http://localhost:{port}")
    print(f"🔗 Backend: {backend}")

    if not no_browser:
        def open_browser():
            import webbrowser
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=open_browser, daemon=True).start()

    app = create_app(backend, anon_key)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
