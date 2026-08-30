# Setup Guide: How AI Agents Connect & Execute Tools

This guide explains **how AI Coding Agents** (in Kilocode, VS Code, Cursor, or Claude Desktop) discover, call, and execute micro-skills from the Autopoiesis Engine using the **Model Context Protocol (MCP)**, and **how to verify** that execution is handled by the Autopoiesis Engine vs raw LLM chat.

---

## ⚡ Do AI Tools Automatically Know to Initialize? (`autopoiesis init`)

**YES!** You do **not** need to manually run `autopoiesis init` before launching your AI Agent.

When Kilocode, Cursor, or VS Code starts up, it reads its MCP configuration file (`.kilocode/mcp.json` or `.vscode/mcp.json`) and spawns:

```bash
autopoiesis serve --mode stdio
```

When `autopoiesis serve` launches:
1. It inspects the local directory for `.autopoiesis/` and `autopoiesis.db`.
2. **If missing, it automatically runs `init_workspace()` on the spot!**
3. It seeds default core primitive skills (`global.parsers.json_parser` and `global.file.writer`).
4. It starts listening for MCP tool calls from your AI Agent with real-time colored visual console feedback.

---

## 🔍 How to Know If Execution Triggered the Autopoiesis Engine vs Raw LLM Chat

When you prompt an AI Agent in Kilocode (e.g., *"Parse JSON data from payload.json and double the value field"*), you can verify that the **Autopoiesis Engine executed the action** using four distinct proof points:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PROOF OF AUTOPOIESIS EXECUTION                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Kilocode Chat UI Tool Call Badge:                                   │
│     In Kilocode chat, you will see an explicit tool call badge:         │
│     "Using Tool: autopoiesis-engine -> execute_macro_intent"            │
│     or "Using Tool: global.parsers.json_parser"                         │
│                                                                         │
│  2. Real-Time Terminal Console Logs:                                    │
│     When running `autopoiesis serve`, you will see live visual tags:    │
│     [AUTOPOIESIS | 14:32:01] [MCP AGENT ENGAGED] Executing intent       │
│     [AUTOPOIESIS | 14:32:02] [TOOL CALL EXECUTED] AI Agent invoked tool │
│     [AUTOPOIESIS | 14:32:02] [SANDBOX SUCCESS] Completed in 0.012s      │
│                                                                         │
│  3. Local State Traces (.autopoiesis/traces/):                          │
│     Check the `.autopoiesis/traces/` directory in your project root.    │
│     Every execution creates a timestamped JSON file (e.g. exec_123.json)│
│     containing execution metrics, OTEL spans, stdout, and stderr.       │
│                                                                         │
│  4. Relational DB Execution Log (.autopoiesis/autopoiesis.db):          │
│     Inspect `.autopoiesis/autopoiesis.db` in SQLite:                   │
│     `SELECT * FROM skills;` or `SELECT * FROM templates;`               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Step-by-Step Setup Guide by IDE

### 1. Kilocode / OpenCode Setup

Kilocode natively supports MCP servers via `.kilocode/mcp.json`.

1. Open your project root folder in Kilocode.
2. Run `autopoiesis init` or run the 1-line installer script (`install.ps1` / `install.sh`).
3. Kilocode uses `.kilocode/mcp.json`:
   ```json
   {
     "mcpServers": {
       "autopoiesis-engine": {
         "command": "autopoiesis",
         "args": ["serve", "--mode", "stdio"],
         "env": {
           "AUTOPOIESIS_ENV": "development"
         }
       }
     }
   }
   ```
4. **Restart Kilocode or Reload Window.**
5. When you prompt Kilocode (e.g., *"Fetch 1-minute historical candles for Upstox"*), Kilocode's AI Agent automatically detects the `autopoiesis-engine` tools and invokes them to perform execution!

---

### 2. VS Code (via Continue.dev / MCP Extension)

1. Open VS Code in your project root.
2. Run `autopoiesis init`.
3. The `.vscode/mcp.json` file is created automatically.
4. When using VS Code with MCP plugins (like Continue or Cline):
   - The plugin reads `.vscode/mcp.json` on startup.
   - All synthesized micro-skills in `registry/` become visible in the tool picker.

---

### 3. Cursor IDE

1. Open Cursor in your project root.
2. Run `autopoiesis init`.
3. Cursor reads `.cursor/mcp.json`.
4. Go to **Cursor Settings -> Features -> MCP Servers**. You will see `autopoiesis-engine` listed with a green status indicator `Active`.

---

### 4. Claude Desktop

1. Run `autopoiesis init`.
2. The engine injects the entry directly into your global `claude_desktop_config.json`:
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
3. Restart Claude Desktop.
4. Click the 🔨 **Hammer Icon** in the Claude chat prompt box—all registered Autopoiesis micro-skills will be listed as tools!
