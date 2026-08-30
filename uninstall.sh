#!/usr/bin/env bash
set -e

echo "=== Autopoiesis Engine Uninstaller (Linux / macOS) ==="

echo "Stopping any running autopoiesis daemon processes..."
pkill -f "autopoiesis serve" || true

echo "Uninstalling autopoiesis-engine package..."
pip uninstall -y autopoiesis-engine || true
if command -v uv &> /dev/null; then
    uv tool uninstall autopoiesis-engine || true
fi

echo "Purging runtime state and legacy workspace registry files..."
rm -rf .autopoiesis/
rm -rf registry/
rm -f mcp.json
rm -f .cursorrules

echo "Uninstallation and workspace cleanup complete."
