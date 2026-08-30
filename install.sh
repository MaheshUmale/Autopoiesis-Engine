#!/usr/bin/env bash
set -e

echo "=== Autopoiesis Engine Automated Installer (Linux / macOS) ==="

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not installed."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Detected Python version: $PYTHON_VERSION"

# Ensure venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Upgrading pip and installing autopoiesis-engine..."
pip install --upgrade pip
pip install -e ".[dev]"

echo "Initializing Autopoiesis workspace & MCP config..."
autopoiesis init

echo ""
echo "=== Installation & Setup Complete! ==="
echo "NOTE: Your IDE (Kilocode / Cursor / VS Code / Claude) will automatically"
echo "start and connect to the Autopoiesis MCP Server in the background!"
echo "You do NOT need to run any manual server commands."
echo ""
echo "To open the interactive Web Dashboard UI & Monitor Logs in browser:"
echo "  autopoiesis serve --mode http --host 127.0.0.1 --port 8000"
echo "  Then open: http://127.0.0.1:8000/ui"
