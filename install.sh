#!/bin/bash
# PrunnerAI CLI — Quick Install
set -e

echo "╔═══════════════════════════════════════════╗"
echo "║   PrunnerAI CLI — Installer               ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Install it from https://python.org"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

echo "📦 Installing PrunnerAI CLI..."
pip install -e . 2>/dev/null || pip3 install -e .

echo ""
echo "✅ Installation complete!"
echo ""
echo "Usage:"
echo "  prunnerai config set bridge_key pb_YOUR_KEY"
echo "  prunnerai status"
echo "  prunnerai bridge start"
echo ""
echo "For AI features (model download/inference):"
echo "  pip install prunnerai-cli[ai]"
echo ""
