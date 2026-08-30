# Setup Guide: How AI Agents Connect & Execute Tools via MCP

This guide explains **how `mcp.json` works**, how to fix **"unavailable tool" / MCP connection lost errors**, how to reset MCP configs, and how VS Code, Kilocode, Cursor, and Claude Desktop communicate with the Autopoiesis Engine.

---

## ⚡ How to Force Reset / Re-inject MCP Config Files (`autopoiesis mcp-install`)

If your IDE loses the MCP connection or if you moved your project folder, run this single command in terminal or PowerShell:

```powershell
autopoiesis mcp-install
```

Or to completely wipe legacy databases and re-initialize MCP configs in one go:

```powershell
autopoiesis clean; autopoiesis init
```

---

## 🔧 How to Fix "Unavailable Tool / MCP Connection Lost" Error in Kilocode / VS Code

If your AI Agent in Kilocode or VS Code says:
> *"The autopoiesis-engine MCP tools are currently not available in this session... unavailable tool 'invalid'..."*

### Why this happens:
The IDE spawns `autopoiesis serve --mode stdio` as a background child process. If you updated python packages, changed virtual environment files, or closed a terminal session, the IDE's child stdio connection may have timed out or closed.

### ⚡ The 2-Second Fix:
1. Run `autopoiesis mcp-install` in your terminal.
2. In Kilocode or VS Code, press **`Ctrl+Shift+P`** (or `Cmd+Shift+P` on Mac).
3. Type **`Developer: Reload Window`** and press **Enter**.
4. When the window reloads, Kilocode / VS Code immediately re-spawns `autopoiesis serve --mode stdio` using the updated binary path and re-establishes the green MCP connection!

---

## ⚡ 24/7 Persistent Background Daemon Option

If you want a persistent daemon that stays running 24/7 in the background without depending on IDE child process lifecycles:

1. Open a terminal or PowerShell in your project folder and run:
   ```powershell
   autopoiesis serve --mode http --host 127.0.0.1 --port 8000
   ```
2. Open **`http://127.0.0.1:8000/ui`** in your web browser to view active agents and live logs!

---

## ❓ Frequently Asked Questions

### Q1: Is `"command": "autopoiesis"` in `.vscode/mcp.json` correct?
**YES!** `"command": "autopoiesis"` is valid if `autopoiesis.exe` is installed in system PATH or activated in your virtual environment.

When you run `autopoiesis init`, `autopoiesis mcp-install`, or `.\install.ps1`, the engine automatically updates `mcp.json` to use the **absolute path to your virtual environment binary** (e.g. `D:\Project\.venv\Scripts\autopoiesis.exe`). This guarantees that VS Code and Kilocode can spawn the engine even if `.venv` is not active in your global shell!

---

### Q2: Do I need to manually initialize every project? (`autopoiesis init`)
**NO!** You do **NOT** need to manually run `autopoiesis init` for every project.

When `autopoiesis serve` is launched by your IDE:
1. It checks if `.autopoiesis/` and `autopoiesis.db` exist in the current folder.
2. **If missing, `autopoiesis serve` automatically runs self-initialization on startup!**
3. It creates the database, seeds default Level 1 OS Core Base Pack micro-skills (`core_os_shell`, `core_fs_windows_ops`, etc.), and starts serving MCP tool requests immediately.

---

### Q3: How does VS Code / Kilocode know about the server?
1. **Discovery:** When VS Code or Kilocode opens a project workspace, it reads `.vscode/mcp.json` (or `.kilocode/mcp.json` or `.cursor/mcp.json`).
2. **Launch:** The IDE automatically spawns the process defined under `mcpServers.autopoiesis-engine.command`:
   `autopoiesis serve --mode stdio`
3. **Handshake:** Over standard input/output (`stdio`), the IDE sends an MCP `tools/list` request.
4. **Registration:** The Autopoiesis Engine responds with its registered tools (`run_intent`, `execute_macro_intent`, OS micro-skills).
5. **Execution:** When you chat with your AI Agent in Kilocode or Cursor, the AI Agent sees these tools in its context and invokes them automatically!
