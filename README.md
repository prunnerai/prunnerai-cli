# 🔥 PrunnerAI CLI v2.0.0 — Universal Bridge Worker

**Your local execution arm for the PrunnerAI empire.**

Supports: real-time streaming, multi-machine, file transfer, session persistence, auto-reconnect with exponential backoff.

## Quick Start

\`\`\`bash
# Option 1: pip install (recommended)
pip install prunnerai
prunnerai start --key YOUR_BRIDGE_KEY --name my-machine

# Option 2: Clone and run
git clone https://github.com/YOUR_USERNAME/prunnerai-cli
cd prunnerai-cli
bash install.sh
python3 bridge_worker.py --key YOUR_BRIDGE_KEY
\`\`\`

## CLI Flags

| Flag | Description | Default |
|------|-------------|---------|
| \`--key\` | Bridge API key | \`BRIDGE_API_KEY\` env var |
| \`--name\` | Machine name for multi-machine setups | \`default\` |
| \`--poll-interval\` | Polling interval in seconds | \`2\` |
| \`--auto-restart\` | Auto-restart on crash | \`false\` |

## Environment Variables

| Variable | Description |
|----------|-------------|
| \`SUPABASE_URL\` | Your PrunnerAI backend URL |
| \`SUPABASE_ANON_KEY\` | Your PrunnerAI anon key |
| \`BRIDGE_API_KEY\` | Your bridge API key (generate in PrunnerAI app) |
| \`POLL_INTERVAL\` | Polling interval in seconds (default: 2) |
| \`MACHINE_NAME\` | Machine name (default: default) |

## Features (v2.0)

- **Real-time streaming**: stdout/stderr streamed line-by-line to the Live Terminal
- **Multi-machine**: Name your workers, target commands to specific machines
- **File transfer**: Upload/download files between cloud and local machines
- **Session persistence**: Maintains working directory and env between commands
- **Resilience**: Exponential backoff, auto-restart, graceful shutdown (SIGINT/SIGTERM)
- **Version tracking**: Reports worker version to the Health Dashboard

## Security

The worker blocks dangerous commands (rm -rf /, mkfs, etc.) and has a configurable timeout. Output is truncated at 50KB.

## Part of the Empire 💎

Built by Commander 100X. Sovereign AI, no compromises.
