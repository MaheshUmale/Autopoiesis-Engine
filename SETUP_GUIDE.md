# Setup Guide: Autopoiesis-Engine

This guide explains how to initialize your workspace and configure AI coding tools (Claude Desktop, Cursor, VS Code, Kilocode) to communicate with the Autopoiesis Engine via the Model Context Protocol (MCP).

---

## 1. Workspace Initialization

Navigate to your target project folder and run:

```bash
autopoiesis init
```

This single command performs the following actions:

1. Creates the local storage workspace at `.autopoiesis/`:
   - `autopoiesis.db` (Relational SQLite database)
   - `qdrant/` (Persistent vector database)
   - `staging/` (Parquet state pointers)
   - `traces/` (OpenTelemetry execution logs)
2. Creates the 3-Tier Registry directories:
   - `registry/level_1_core/`
   - `registry/level_2_variants/`
   - `registry/level_3_templates/`
3. Generates a root `mcp.json` file.
4. Detects and injects `autopoiesis-engine` configuration into installed client configuration files.

---

## 2. IDE Integration Configurations

### A. Local `mcp.json` (Universal Standard)

The `autopoiesis init` command creates `mcp.json` in your project root:

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
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

Restart Claude Desktop after running `autopoiesis init` to activate the dynamic tools.

---

### C. Cursor & VS Code

For Cursor or VS Code with MCP extensions:
- Settings file updated at `.cursor/mcp.json` or `.vscode/mcp.json`.

---

### D. Kilocode & OpenCode

Settings file updated at `.kilocode/mcp.json`.
For HTTP daemon mode, launch the server in daemon mode:

```bash
autopoiesis serve --mode http --host 127.0.0.1 --port 8000
```
Then point your browser/web client to `http://127.0.0.1:8000/tools`.
