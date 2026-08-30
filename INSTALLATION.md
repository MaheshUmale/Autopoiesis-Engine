# Installation Guide: Autopoiesis-Engine

This guide covers installing `autopoiesis-engine` across Linux, macOS, and Windows.

---

## Prerequisites

- **Python:** `>= 3.11`
- **System Shell:**
  - Linux / macOS: `/bin/bash` or `/bin/zsh`
  - Windows: PowerShell (`pwsh` or `powershell.exe`) or Command Prompt (`cmd.exe`)
- **Temporal Server (Optional):** Required for production distributed workflow orchestration (`temporal server start-dev`).

---

## Installation Methods

### Method 1: Local Source Installation (Recommended for Development)

Clone the repository, navigate into the directory, and install in editable mode:

```bash
git clone https://github.com/autopoiesis/autopoiesis-engine.git
cd autopoiesis-engine
```

#### Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

#### Windows (PowerShell):
```powershell
python -m venv .venv
# If script execution is restricted, run: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

#### Windows (Command Prompt - `cmd.exe`):
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
pip install -e ".[dev]"
```

#### Using `uv` (Local Folder):
When installing from a local repository clone (before PyPI release), install from the current directory `.`:
```powershell
# Install into active virtualenv using uv
uv pip install -e .

# Or install globally as a tool from local folder
uv tool install .
```

---

### Method 2: Global Tool Installation via `pipx` / `uv`

To install the CLI tool globally from source directory:

```powershell
# Install from local directory using uv
uv tool install .

# Or install from local directory using pipx
pipx install .
```

> **Note:** Running `uv tool install autopoiesis-engine` without publishing to PyPI will fail with a `not found in package registry` error. Always specify the local directory path `.` when installing from source.

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
