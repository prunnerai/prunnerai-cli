"""PrunnerAI CLI — Self-update via GitHub."""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

from prunnerai import __version__
from prunnerai.config_manager import load_config


def _version_tuple(v):
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0, 0, 0)


def handle_update():
    cfg = load_config()
    repo_owner = cfg.get("github_repo_owner", "")

    if not repo_owner:
        print("⚠ GitHub repo owner not configured.")
        print("  Run: prunnerai config set github_repo_owner YOUR_GITHUB_USERNAME")
        print("  (This is set automatically on first deploy)")
        return

    print(f"🔍 Checking for updates...")
    print(f"   Current version: v{__version__}")

    version_url = f"https://raw.githubusercontent.com/{repo_owner}/prunnerai-cli/main/version.json"
    try:
        req = urllib.request.Request(version_url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            remote = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("❌ version.json not found in remote repo.")
            print(f"   Checked: {version_url}")
        else:
            print(f"❌ Failed to check for updates: HTTP {e.code}")
        return
    except Exception as e:
        print(f"❌ Failed to check for updates: {e}")
        return

    remote_version = remote.get("version", "0.0.0")
    print(f"   Remote version:  v{remote_version}")

    if _version_tuple(remote_version) <= _version_tuple(__version__):
        print("✅ You're already on the latest version!")
        return

    print(f"\n📦 Update available: v{__version__} → v{remote_version}")

    cli_dir = _find_cli_dir()
    if not cli_dir:
        print("❌ Cannot locate CLI installation directory.")
        print("   Try manually: cd <cli-dir> && git pull && pip install -e .")
        return

    print(f"   CLI directory: {cli_dir}")
    print("   Updating...")

    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=str(cli_dir),
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"❌ git pull failed: {result.stderr}")
            return
        print(f"   ✅ git pull: {result.stdout.strip()}")

        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            cwd=str(cli_dir),
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"❌ pip install failed: {result.stderr[:300]}")
            return
        print(f"   ✅ pip install -e . completed")

        print(f"\n🎉 Updated to v{remote_version}!")
        print("   Restart your terminal or run 'prunnerai --version' to verify.")

    except subprocess.TimeoutExpired:
        print("❌ Update timed out.")
    except FileNotFoundError as e:
        print(f"❌ Required tool not found: {e}")
        print("   Make sure git and pip are installed.")
    except Exception as e:
        print(f"❌ Update failed: {e}")


def _find_cli_dir():
    try:
        import prunnerai
        pkg_dir = Path(prunnerai.__file__).parent
        repo_dir = pkg_dir.parent
        if (repo_dir / ".git").exists() and (repo_dir / "setup.py").exists():
            return repo_dir
    except Exception:
        pass

    candidates = [
        Path.home() / "prunnerai-cli",
        Path.home() / "projects" / "prunnerai-cli",
        Path.home() / "code" / "prunnerai-cli",
        Path.home() / "dev" / "prunnerai-cli",
    ]
    for d in candidates:
        if d.exists() and (d / "setup.py").exists():
            return d

    return None
