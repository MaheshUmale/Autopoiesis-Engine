# Complete Windows Setup & Integration Guide

---

## 1. Single Universal Setup Procedure for Windows

You do **NOT** need multiple setup steps or conflicting commands. Follow this exact 3-step process:

### Step 1: Run the Automated PowerShell Installer
Open PowerShell in your target project directory and run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\install.ps1
```

This single command sets up your virtual environment, installs `autopoiesis-engine`, builds the workspace directory structure (`.autopoiesis/` and `registry/`), pre-seeds core OS micro-skills, and writes the `mcp.json` configuration files for Kilocode, Cursor, VS Code, and Claude Desktop.

---

### Step 2: Open Your IDE & Reload Window
1. Open your project folder in **Kilocode**, **Cursor**, **VS Code**, or **Claude Desktop**.
2. If your IDE was already open during installation:
   - Press **`Ctrl+Shift+P`**
   - Type **`Developer: Reload Window`** and press **Enter**.
3. Your IDE will automatically detect `mcp.json` and start the Autopoiesis MCP Server in the background.

---

### Step 3: Prompt Your AI Agent Naturally
Simply type your request in Kilocode or Cursor chat:
> *"List running python processes and save them to processes.txt"*

The AI Agent automatically calls the `run_intent` tool provided by the Autopoiesis Engine!

---

## 2. Monitoring & Real-Time Dashboard (Optional)

If you want to visually observe agent execution, logs, and statistics in your web browser:

1. Open PowerShell in your project folder and run:
   ```powershell
   autopoiesis serve --mode http --host 127.0.0.1 --port 8000
   ```
2. Open **`http://127.0.0.1:8000/ui`** in Google Chrome or Edge.
3. You will see live cards for every agent along with an *"View Agent Logs"* button for real-time trace inspection.

---

## 3. Resetting / Clearing Workspace State

If you want to clear old databases or reset your project workspace:

```powershell
autopoiesis clean
```
or run a complete clean reinstallation:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\reinstall.ps1
```
