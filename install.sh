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
echo "To activate your virtual environment in future terminal sessions, run:"
echo "  source .venv/bin/activate"
echo ""
echo "To start the MCP server daemon in stdio mode for IDEs (Claude / Cursor / VS Code):"
echo "  autopoiesis serve --mode stdio"
echo ""
echo "To start the MCP daemon in HTTP server mode:"
echo "  autopoiesis serve --mode http --host 127.0.0.1 --port 8000"
