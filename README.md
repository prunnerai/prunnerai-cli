# 🔥 PrunnerAI CLI — Universal Bridge Worker

**Your local execution arm for the PrunnerAI empire.**

This worker polls PrunnerAI for commands and executes them on your local machine. It's the bridge between PrunnerAI's cloud brain and your local hardware.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/YOUR_USERNAME/prunnerai-cli
cd prunnerai-cli
bash install.sh

# Edit .env with your keys (pre-filled if deployed from PrunnerAI)
nano .env

# Run the bridge
python3 bridge_worker.py
```

## Manual Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your keys
python3 bridge_worker.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Your PrunnerAI backend URL |
| `SUPABASE_ANON_KEY` | Your PrunnerAI anon key |
| `BRIDGE_API_KEY` | Your bridge API key (generate in PrunnerAI app) |
| `POLL_INTERVAL` | Polling interval in seconds (default: 2) |

## Security

The worker blocks dangerous commands (rm -rf /, mkfs, etc.) and has a configurable timeout. Output is truncated at 50KB to prevent memory issues.

## Part of the Empire 💎

Built by Commander 100X. Sovereign AI, no compromises.
