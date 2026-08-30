# Complete Setup, Workspace Update & Integration Guide

---

## 1. Single Universal Setup Procedure for Windows & Unix

Follow this exact process to set up or update your workspace:

### Step 1: Run the Automated 1-Click Installer
Open terminal or PowerShell in your project directory and run:

#### Windows (PowerShell):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\install.ps1
```

#### Linux / macOS:
```bash
chmod +x install.sh && ./install.sh
```

This single command sets up your virtual environment, installs `autopoiesis-engine`, builds the workspace directory structure (`.autopoiesis/` and `registry/`), pre-seeds core OS micro-skills, and writes the `mcp.json` configuration files for Kilocode, Cursor, VS Code, and Claude Desktop.

---

## 2. How to Update Old Workspaces & Fix Connection Errors

If you previously installed an older version, updated folder structures, or experienced `unavailable tool` connection errors in Kilocode / VS Code:

### 🔄 Option A: Re-inject MCP Configuration Files (`autopoiesis mcp-install`)
Forces generation and overwriting of MCP configuration files across local workspace paths (`.kilocode/mcp.json`, `.vscode/mcp.json`, `.cursor/mcp.json`) and global client settings using absolute executable binary paths:

```powershell
autopoiesis mcp-install
```

### 🔄 Option B: Purge Old Databases & Re-initialize Workspace (`autopoiesis clean`)
Purges legacy `.autopoiesis/` database state, `registry/` folder, and old configuration files:

```powershell
autopoiesis clean; autopoiesis init
```

### 🔄 Option C: Automated 1-Click Reinstall Script
Runs complete uninstallation and clean reinstallation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\reinstall.ps1
```

After updating or running clean/reinstall, press **`Ctrl+Shift+P`** in Kilocode or VS Code and select **`Developer: Reload Window`** to re-establish the background MCP connection!

---

## 3. How IDE AI Agents Discover & Execute Tools

1. When Kilocode, VS Code, or Cursor opens your project, it reads `.kilocode/mcp.json` or `.vscode/mcp.json`.
2. The IDE automatically spawns `autopoiesis serve --mode stdio` in the background.
3. If `.autopoiesis/` is missing or uninitialized, `autopoiesis serve` automatically runs self-initialization on startup!
4. When you prompt your AI Agent naturally (*"List python processes and write to file"*), the agent delegates the request directly to the `run_intent` or `execute_macro_intent` tool provided by Autopoiesis Engine.

---

## 4. Monitoring & Real-Time Dashboard (Optional)

If you want to visually observe agent execution, logs, and statistics in your web browser:

1. Open PowerShell or terminal in your project folder and run:
   ```powershell
   autopoiesis serve --mode http --host 127.0.0.1 --port 8000
   ```
2. Open **`http://127.0.0.1:8000/ui`** in Google Chrome or Edge.
3. You will see live cards for every agent along with an *"View Agent Logs"* button for real-time trace inspection.
