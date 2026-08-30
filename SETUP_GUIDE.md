# Setup Guide: How AI Agents Connect & Execute Tools

This guide explains **how AI Coding Agents** (in Kilocode, VS Code, Cursor, or Claude Desktop) discover, call, and execute micro-skills from the Autopoiesis Engine using the **Model Context Protocol (MCP)**, and **how to troubleshoot and verify** that execution is connected.

---

## 🔧 Troubleshooting Kilocode "Unavailable Tool" / Connection Error

If Kilocode displays `unavailable tool` or `failed to connect to server`:

### 1. Verify `mcp.json` Absolute Binary Path
`autopoiesis init` resolves the absolute path to your Python virtual environment binary.
Check `.kilocode/mcp.json` or `.vscode/mcp.json` in your project folder:

```json
{
  "mcpServers": {
    "autopoiesis-engine": {
      "command": "D:\\Autopoiesis-Engine\\.venv\\Scripts\\autopoiesis.exe",
      "args": ["serve", "--mode", "stdio"],
      "env": {
        "AUTOPOIESIS_ENV": "development"
      }
    }
  }
}
```

### 2. Reload Kilocode / VS Code Window
If you installed or ran `autopoiesis init` while Kilocode was open:
- Press **`Ctrl+Shift+P`** (or `Cmd+Shift+P` on Mac).
- Select **`Developer: Reload Window`** to force Kilocode to reload the MCP stdio connection.
- After reload, Kilocode will launch `autopoiesis serve --mode stdio` automatically!

---

## 🖥️ Global Real-Time Web Dashboard UI

The Autopoiesis Engine includes a real-time web dashboard to visualize all active agents, execution statistics, and individual agent logs in one place!

1. Launch the MCP server daemon in HTTP mode:
   ```bash
   autopoiesis serve --mode http --host 127.0.0.1 --port 8000
   ```
2. Open **`http://127.0.0.1:8000/ui`** (or `http://127.0.0.1:8000/dashboard`) in your web browser.
3. Features available on the dashboard:
   - **System Summary Stats:** View total agents, Level 1 Core Base Pack, synthesized Level 2 Variants, Level 3 Templates, and total execution runs.
   - **Individual Agent Cards:** Displays every agent with status (`READY / ACTIVE` vs `IDLE`), namespace, execution count, and scope level.
   - **Isolated Agent Logs:** Click *"View Agent Logs"* on any card to view stdout, stderr, execution time, and OTEL trace snapshots for that specific agent!

---

## ⚡ Do AI Tools Automatically Know to Initialize? (`autopoiesis init`)

**YES!** You do **not** need to manually run `autopoiesis init` before launching your AI Agent.

When Kilocode, Cursor, or VS Code starts up, it reads its MCP configuration file (`.kilocode/mcp.json` or `.vscode/mcp.json`) and spawns `autopoiesis serve --mode stdio`.

When `autopoiesis serve` launches:
1. It inspects the local directory for `.autopoiesis/` and `autopoiesis.db`.
2. **If missing, it automatically runs `init_workspace()` on the spot!**
3. It seeds default Level 1 Core Base Pack micro-skills (`core_os_shell`, `core_fs_windows_ops`, `global.parsers.json_parser`, etc.).
4. It starts listening for MCP tool calls with real-time colored visual console feedback.

---

## 🔍 Proof of Execution Points

When you prompt an AI Agent in Kilocode (e.g., *"Parse JSON data from payload.json and double the value field"*), you can verify that the **Autopoiesis Engine executed the action** using four distinct proof points:

1. **Global Web Dashboard UI (`http://127.0.0.1:8000/ui`):** View real-time agent execution counts and individual agent log terminals.
2. **Kilocode Chat UI Tool Call Badge:** In Kilocode chat, look for the tool call card: `Using Tool: autopoiesis-engine -> run_intent`.
3. **Real-Time Terminal Console Logs:** When running `autopoiesis serve`, you will see live visual tags: `[AUTOPOIESIS | 14:32:01] [MCP AGENT ENGAGED] Executing intent`.
4. **Local State Traces (`.autopoiesis/traces/`):** Timestamped JSON files recorded under `.autopoiesis/traces/{exec_id}.json`.
