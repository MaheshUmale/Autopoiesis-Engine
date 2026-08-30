# Installation Guide: Autopoiesis-Engine

This guide covers step-by-step installation instructions for `autopoiesis-engine` across Windows, Linux, and macOS.

---

## Prerequisites

- **Python:** `>= 3.11`
- **System Shell:**
  - Windows: PowerShell (`pwsh` or `powershell.exe`) or Command Prompt (`cmd.exe`)
  - Linux / macOS: `/bin/bash` or `/bin/zsh`
- **Git:** Installed and available in PATH.
- **Temporal Server (Optional):** Required for production distributed workflow orchestration (`temporal server start-dev`).

---

## ⚡ Direct 1-Line Installation from Git Repository (Windows PowerShell)

To install `autopoiesis-engine` directly from the Git repository into your Python environment without manually cloning first:

```powershell
# Install directly from GitHub using pip
pip install git+https://github.com/autopoiesis/autopoiesis-engine.git

# Or install globally as a tool using uv
uv tool install git+https://github.com/autopoiesis/autopoiesis-engine.git

# Or install globally using pipx
pipx install git+https://github.com/autopoiesis/autopoiesis-engine.git
```

Then initialize your workspace in your project directory:
```powershell
autopoiesis init
```

---

## Option 1: Automated Installer Script (Local Repository Clone)

Run the included platform-specific installation script in your project directory:

### Windows (PowerShell):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\install.ps1
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

#### Windows (PowerShell):
```powershell
python -m venv .venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
.\.venv\Scripts\Activate.ps1
```

#### Windows (Command Prompt - `cmd.exe`):
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

#### Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### Step 2: Install Package from Local Source Directory

```powershell
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

---

### Step 3: Initialize Workspace

After installing the package, run:

```powershell
autopoiesis init
```

This creates `.autopoiesis/`, `registry/` directories, and generates/injects `mcp.json` configs for VS Code, Cursor, Claude Desktop, and Kilocode.

---

## Verifying Installation

Run the following command in PowerShell or terminal:

```powershell
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
