# Setup Guide: How AI Agents (VS Code, Kilocode, Cursor, Claude) Connect & Execute Tools

This guide explains **exactly how AI Coding Agents** (in VS Code, Kilocode, Cursor, or Claude Desktop) discover, call, and execute micro-skills from the Autopoiesis Engine using the **Model Context Protocol (MCP)**.

---

## 💡 How It Works (The Execution Pipeline)

When you run `autopoiesis init`, the engine configures your IDE to launch the `autopoiesis serve` background process over **MCP stdio** (standard input/output).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    YOUR IDE / AI AGENT (Kilocode / VS Code)             │
│                                                                         │
│   1. Agent starts & reads .kilocode/mcp.json or .vscode/mcp.json       │
│   2. Agent sends standard MCP "list_tools" request over stdio          │
│   3. Agent sees available tools (e.g. trading.upstox.fetch_historical)  │
│   4. Agent calls tool with JSON parameters                              │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ (MCP stdio protocol)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AUTOPOIESIS ENGINE DAEMON                          │
│                                                                         │
│   • Runs skill code in isolated python sandbox                          │
│   • Handles payload thresholding (<100KB inline vs >=100KB parquet)     │
│   • Auto-repairs runtime errors via Self-Healing loop                   │
│   • Returns JSON execution result back to Kilocode / VS Code Agent      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Step-by-Step Setup Guide by IDE

### 1. Kilocode / OpenCode Setup

Kilocode natively supports MCP servers via `.kilocode/mcp.json`.

1. Open your project root folder in Kilocode.
2. Run the installer or initialization command in your terminal:
   ```powershell
   autopoiesis init
   ```
3. `autopoiesis init` automatically creates `.kilocode/mcp.json` with the following configuration:
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
2. Run `autopoiesis init` in the terminal.
3. The `.vscode/mcp.json` file is created automatically.
4. If using VS Code with MCP plugins (like Continue or Cline):
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

---

## 🔍 How to Verify Agent Tool Discovery

To verify that your tools are properly registered and discoverable by your AI Agent:

1. Register or synthesize a micro-skill (or place one in `registry/level_1_core/` or `registry/level_2_variants/`).
2. Test tool execution locally via HTTP or stdio:
   ```bash
   autopoiesis serve --mode http --host 127.0.0.1 --port 8000
   ```
3. Open `http://127.0.0.1:8000/tools` in your browser. You will see a JSON array of all active tools available to Kilocode, VS Code, Cursor, and Claude!
