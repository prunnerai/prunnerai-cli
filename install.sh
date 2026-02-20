#!/bin/bash
# PrunnerAI CLI v2.0.0 — Setup 🚀
set -e
echo "🔥 Setting up PrunnerAI Bridge Worker v2.0.0..."
echo ""
echo "Option 1 (recommended): pip install prunnerai"
echo "Option 2 (manual):      python3 -m pip install -r requirements.txt"
echo ""
python3 -m pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "📝 Created .env from template — fill in your keys!"
else
  echo "✅ .env already exists"
fi
echo ""
echo "💎 Setup complete! Run: python3 bridge_worker.py --key YOUR_KEY --name my-machine"
