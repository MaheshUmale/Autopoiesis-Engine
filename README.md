# Autopoiesis-Engine: Windows Quick Start Guide

**Autonomous AI Agent Execution Engine for Kilocode, Cursor, VS Code & Claude Desktop**

---

## ⚡ 1-Step Windows Setup

Open PowerShell in your project directory and run this single command:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\install.ps1
```

### What `install.ps1` automatically does for you:
1. Creates a local Python environment (`.venv`) and installs `autopoiesis-engine`.
2. Initializes local storage (`.autopoiesis/`) and pre-seeds OS Core micro-skills.
3. Automatically writes `.kilocode/mcp.json`, `.vscode/mcp.json`, `.cursor/mcp.json`, and `.cursorrules` pointing to your local environment binary!

---

## 🚀 How to Use with AI Agents (Kilocode / Cursor / VS Code / Claude)

### Step 1: Open your project folder in your IDE (Kilocode / Cursor / VS Code).
*(If the IDE was already open, press `Ctrl+Shift+P` and select `Developer: Reload Window` so it loads the newly created `mcp.json`).*

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

## 🔄 Reinstalling or Resetting Workspace

To clear legacy databases and perform a clean reinstallation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\reinstall.ps1
```

---

## 📚 Detailed Documentation

- **[Installation & Reinstallation Guide](INSTALLATION.md)**
- **[IDE Setup & Verification Guide](SETUP_GUIDE.md)**
- **[User Manual](USER_MANUAL.md)**
- **[Technical Specifications Specification](REQUIREMENTS.md)**
