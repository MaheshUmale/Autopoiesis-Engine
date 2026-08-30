# Installation Guide: Autopoiesis-Engine

This guide covers step-by-step installation instructions for `autopoiesis-engine` across Linux, macOS, and Windows.

---

## Prerequisites

- **Python:** `>= 3.11`
- **System Shell:**
  - Linux / macOS: `/bin/bash` or `/bin/zsh`
  - Windows: PowerShell (`pwsh` or `powershell.exe`) or Command Prompt (`cmd.exe`)
- **Temporal Server (Optional):** Required for production distributed workflow orchestration (`temporal server start-dev`).

---

## Option 1: Automated 1-Click Installation (Recommended)

Run the included platform-specific installation script in your project directory:

### Windows (PowerShell):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process; .\install.ps1
```

### Linux / macOS:
```bash
chmod +x install.sh && ./install.sh
```

---

## Option 2: Manual Step-by-Step Installation

Clone the repository and install in editable mode:

```bash
git clone https://github.com/autopoiesis/autopoiesis-engine.git
cd autopoiesis-engine
```

### Step 1: Create and Activate Virtual Environment

#### Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows (PowerShell):
```powershell
python -m venv .venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```

#### Windows (Command Prompt - `cmd.exe`):
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

---

### Step 2: Install Package from Local Source Directory

> **Important Note:** Do not run `uv tool install autopoiesis-engine` directly without specifying a local path before the package is published to PyPI. Always install from the local folder target `.`.

#### Using `pip`:
```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

#### Using `uv`:
```bash
# Install into active virtualenv using uv
uv pip install -e .

# Or install as a global tool from the local folder
uv tool install .
```

#### Using `pipx`:
```bash
pipx install .
```

---

### Step 3: Initialize Workspace

After installing the package, run:

```bash
autopoiesis init
```

This creates `.autopoiesis/`, `registry/` directories, and generates/injects `mcp.json` configs for VS Code, Cursor, Claude Desktop, and Kilocode.

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
