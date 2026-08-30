# Installation Guide: Autopoiesis-Engine

This guide covers installing `autopoiesis-engine` across Linux, macOS, and Windows.

---

## Prerequisites

- **Python:** `>= 3.11`
- **System Shell:** `/bin/bash` (Linux/macOS) or `PowerShell / pwsh` (Windows)
- **Temporal Server (Optional):** Required for production distributed workflow orchestration (`temporal server start-dev`).

---

## Installation Methods

### Method 1: Local Development Installation (Recommended)

Clone the repository and install in editable mode:

```bash
git clone https://github.com/autopoiesis/autopoiesis-engine.git
cd autopoiesis-engine

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package with development dependencies
pip install -e ".[dev]"
```

---

### Method 2: Global Installation via `pipx` / `uv`

Install `autopoiesis-engine` as an isolated global CLI command:

```bash
# Using pipx
pipx install autopoiesis-engine

# Using uv (Recommended for speed)
uv tool install autopoiesis-engine
```

---

## Verifying Installation

Run the following command to check if the CLI is correctly installed:

```bash
autopoiesis --help
```

Output:
```
usage: autopoiesis [-h] {init,serve} ...

Autopoiesis Engine CLI Tool

positional arguments:
  {init,serve}
    init        Initialize workspace and IDE MCP configurations.
    serve       Run the MCP server daemon.
```
