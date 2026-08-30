# Autopoiesis-Engine: Windows Quick Start Guide

**Autonomous AI Agent Execution Engine for Kilocode, Cursor, VS Code & Claude Desktop**

---

## ⚡ 1-Step Single-Command Automated Installation

Choose your platform to run the single-command automated installer:

### Windows (PowerShell):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\install.ps1
```

### Linux / macOS:
```bash
chmod +x install.sh && ./install.sh
```

### Direct Install from GitHub (Any OS):
```powershell
pip install git+https://github.com/autopoiesis/autopoiesis-engine.git
autopoiesis init
```

---

## 🔄 Updating Old Workspaces & Resetting Legacy Files

If you modified directory structures, updated the engine version, or experienced "unavailable tool" connection errors, use these commands to update and reset old workspaces:

### 1. Update MCP Configuration Files (`autopoiesis mcp-install`)
Overwrites local and global IDE MCP configuration files (`.kilocode/mcp.json`, `.vscode/mcp.json`, `.cursor/mcp.json`, Claude Desktop) with current absolute virtualenv binary paths:
```powershell
autopoiesis mcp-install
```

### 2. Purge Legacy Databases & Reset Workspace (`autopoiesis clean`)
Wipes old `.autopoiesis/` database runtime state, `registry/` folder, and legacy `mcp.json` configs so fresh databases can be created:
```powershell
autopoiesis clean; autopoiesis init
```

### 3. Automated 1-Click Reinstaller Script
Runs complete uninstallation and fresh installation in one step:
- **Windows (PowerShell):** `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\reinstall.ps1`
- **Linux / macOS:** `chmod +x reinstall.sh && ./reinstall.sh`

---

## 🚀 How to Use with AI Agents (Kilocode / Cursor / VS Code / Claude)

### Step 1: Open your project folder in your IDE (Kilocode / Cursor / VS Code).
*(If the IDE was already open, press `Ctrl+Shift+P` and select `Developer: Reload Window` so it loads the newly updated `mcp.json`).*

### Step 2: Prompt your AI Agent naturally!
You do **NOT** need to manually start a daemon or remember tool names. Simply prompt your AI Agent in Kilocode or Cursor:
> *"Parse data from input.json, double the numbers, and save to result.json"*

The AI Agent will automatically invoke the Autopoiesis Engine (`run_intent` / `execute_macro_intent`) and execute the task!

---

## 🖥️ (Optional) Web Dashboard & Process Monitoring

To view all active agents, execution statistics, and real-time logs in your web browser:

1. Open PowerShell and run:
   ```powershell
   autopoiesis serve --mode http --host 127.0.0.1 --port 8000
   ```
2. Open **`http://127.0.0.1:8000/ui`** in your browser.

---

## 📚 Detailed Documentation

- **[Installation & Reinstallation Guide](INSTALLATION.md)**
- **[IDE Setup & Verification Guide](SETUP_GUIDE.md)**
- **[User Manual](USER_MANUAL.md)**
- **[Technical Specifications Specification](REQUIREMENTS.md)**
