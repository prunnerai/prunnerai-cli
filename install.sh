#!/bin/bash
# PrunnerAI CLI — One-liner setup 🚀
set -e
echo "🔥 Setting up PrunnerAI Bridge Worker..."
python3 -m pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "📝 Created .env from template — fill in your keys!"
else
  echo "✅ .env already exists"
fi
echo ""
echo "💎 Setup complete! Run: python3 bridge_worker.py"
