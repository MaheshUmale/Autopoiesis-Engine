#!/usr/bin/env bash
set -e

echo "=== Autopoiesis Engine Reinstaller (Linux / macOS) ==="

chmod +x uninstall.sh install.sh
./uninstall.sh
./install.sh

echo "Reinstallation completed successfully!"
