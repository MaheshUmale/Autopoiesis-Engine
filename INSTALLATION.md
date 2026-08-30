# Installation & Workspace Update Guide: Autopoiesis-Engine

This guide provides single-command installation, uninstallation, and workspace update instructions for `autopoiesis-engine` across Windows, Linux, and macOS.

---

## Prerequisites

- **Python:** `>= 3.11`
- **System Shell:**
  - Windows: PowerShell (`pwsh` or `powershell.exe`) or Command Prompt (`cmd.exe`)
  - Linux / macOS: `/bin/bash` or `/bin/zsh`
- **Git:** Installed and available in PATH.
- **Temporal Server (Optional):** Required for production distributed workflow orchestration (`temporal server start-dev`).

---

## ⚡ 1-Click Automated Installation (Single Command)

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

## ⚡ Direct 1-Line Installation from GitHub (Any OS)

To install `autopoiesis-engine` directly from GitHub into your active Python environment:

```powershell
pip install git+https://github.com/autopoiesis/autopoiesis-engine.git
autopoiesis init
```

---

## 🔄 How to Update Old Workspaces & Clear Legacy Files

If you modified directory structures, updated versions, or experienced `unavailable tool` connection errors in Kilocode or VS Code, use these commands to clear older files and update configs:

### Option 1: Re-install MCP Configuration Pointers (`autopoiesis mcp-install`)
Overwrites local workspace `.kilocode/mcp.json`, `.vscode/mcp.json`, `.cursor/mcp.json`, `mcp.json`, and Claude Desktop settings with resolved absolute virtualenv binary paths:

```powershell
autopoiesis mcp-install
```

### Option 2: Purge Legacy Databases & Reset Workspace (`autopoiesis clean`)
Wipes old `.autopoiesis/` database runtime state, `registry/` folder, `mcp.json`, and `.cursorrules` so fresh seed databases are instantiated:

```powershell
autopoiesis clean; autopoiesis init
```

### Option 3: Automated 1-Click Reinstall Script
Executes clean uninstallation and fresh reinstallation in one step:

#### Windows (PowerShell):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\reinstall.ps1
```

#### Linux / macOS:
```bash
chmod +x reinstall.sh && ./reinstall.sh
```

---

## 🗑️ Uninstallation

To remove the package and clean local workspace database files:

### Windows (PowerShell):
```powershell
.\uninstall.ps1
```

### Linux / macOS:
```bash
chmod +x uninstall.sh && ./uninstall.sh
```

---

## Verifying Installation

Run the following command in PowerShell or terminal:

```powershell
autopoiesis --help
```

Output:
```
usage: autopoiesis [-h] {init,mcp-install,clean,serve} ...

Autopoiesis Engine CLI Tool

positional arguments:
  {init,mcp-install,clean,serve}
    init        Initialize workspace and IDE MCP configurations.
    mcp-install Force overwrite MCP configuration files for IDEs.
    clean       Purge runtime state (.autopoiesis) and legacy workspace files.
    serve       Run the MCP server daemon.
```
