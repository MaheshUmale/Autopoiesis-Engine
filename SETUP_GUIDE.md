# Setup Guide: Autopoiesis-Engine

This guide explains how to initialize your workspace and configure AI coding tools (Claude Desktop, Cursor, VS Code, Kilocode) to communicate with the Autopoiesis Engine via the Model Context Protocol (MCP).

---

## 1. Automated Setup

Run the installer script for your OS:

- **Windows (PowerShell):** `.\install.ps1`
- **Linux / macOS:** `./install.sh`

---

## 2. Manual Workspace Initialization

If you installed manually, navigate to your project folder and run:

```bash
autopoiesis init
```

This command automatically:
1. Creates local storage workspace at `.autopoiesis/`:
   - `autopoiesis.db` (Relational SQLite database)
   - `qdrant/` (Persistent vector database)
   - `staging/` (Parquet state pointers)
   - `traces/` (OpenTelemetry execution logs)
2. Creates 3-Tier Registry directories:
   - `registry/level_1_core/`
   - `registry/level_2_variants/`
   - `registry/level_3_templates/`
3. Generates root `mcp.json` configuration file.
4. Detects installed IDEs and injects `autopoiesis-engine` MCP configuration into client config files.

---

## 3. IDE Integration Configurations & Paths

### A. Local `mcp.json` (Universal Standard)

The `autopoiesis init` command generates `mcp.json` in your project root:

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

---

### B. Claude Desktop

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json` (Expanded to `C:\Users\<Username>\AppData\Roaming\Claude\claude_desktop_config.json`)
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

Restart Claude Desktop after running `autopoiesis init` to activate the dynamic MCP tools.

---

### C. Cursor & VS Code

For Cursor or VS Code with MCP extensions:
- Settings file updated at `.cursor/mcp.json` or `.vscode/mcp.json`.

---

### D. Kilocode & OpenCode

Settings file updated at `.kilocode/mcp.json`.

---

## 4. Starting the Server Daemon

### Stdio Mode (Default for IDEs):
```bash
autopoiesis serve --mode stdio
```

### HTTP Server Mode:
```bash
autopoiesis serve --mode http --host 127.0.0.1 --port 8000
```

When running in HTTP mode, you can verify server status at `http://127.0.0.1:8000/` and view active tools at `http://127.0.0.1:8000/tools`.
