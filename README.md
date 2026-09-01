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
pip install git+https://github.com/MaheshUmale/autopoiesis-engine.git
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

- **[Project Status & Achievements](PROJECT_STATUS.md)** — Comprehensive summary of all completed work
- **[Installation & Reinstallation Guide](INSTALLATION.md)**
- **[IDE Setup & Verification Guide](SETUP_GUIDE.md)**
- **[User Manual](USER_MANUAL.md)**
- **[Technical Specifications](REQUIREMENTS.md)**
- **[Audit Report](AUDIT_REPORT.md)** — Security and code quality audit

---

## 📊 Project Status

| Metric | Value |
|--------|-------|
| **Tests** | 378 passing |
| **Security Tests** | 85 |
| **Code Quality** | A- |
| **Status** | Production-Ready |
| **Core Skills** | 17 |
| **MCP Tools** | 29 + dynamic skills |

**All identified gaps and audit findings have been resolved.** See [PROJECT_STATUS.md](PROJECT_STATUS.md) for details.

---

## 🧩 Skills & Micro-Skills

### Core Skills (17 Built-in)

| Category | Skills |
|----------|--------|
| **OS & Shell** | `core_os_shell`, `core_os_env_path`, `core_os_proc_monitor`, `core_process_manager` |
| **File System** | `core_fs_windows_ops`, `core_file_watcher` |
| **Data Processing** | `core_data_utilities`, `core_csv_processor`, `core_json_path`, `core_yaml_processor`, `core_regex_processor` |
| **Networking** | `core_http_client`, `core_network_scanner` |
| **System** | `core_env_inspector`, `core_system_health` |
| **Messaging** | `core_notification_bridge` |
| **Visualization** | `core_data_viz` |

### Skill Types

| Type | Description |
|------|-------------|
| `core` | Built-in OS base skills |
| `variant` | Project-specific variants |
| `genesis` | Forged by L0 Genesis pathway |
| `ai_generated` | AI-synthesized at runtime |

### AI-Driven Synthesis

Complex intents that don't match existing skills trigger AI synthesis:
1. Engine detects `synthesis_needed`
2. AI agent generates Python code
3. Code submitted via `submit_ai_skill` (sandbox-verified)
4. Pipeline retries via `retry_intent`
