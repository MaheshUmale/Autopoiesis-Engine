# User Manual: Autopoiesis-Engine (Windows Edition)

This manual details operating the Autopoiesis Engine on Windows, running CLI subcommands, managing registry skills, and monitoring agent executions.

---

## 1. CLI Commands Quick Reference

### `autopoiesis init`
Initializes local `.autopoiesis/` database storage, `registry/` directories, pre-seeds Level 1 Core micro-skills, and writes MCP configurations for Kilocode, Cursor, VS Code, and Claude Desktop.

```powershell
autopoiesis init
```

---

### `autopoiesis clean`
Purges local `.autopoiesis/` database state, `registry/` folder, `mcp.json`, and `.cursorrules` files.

```powershell
autopoiesis clean
```

---

### `autopoiesis serve`
Launches the MCP Server Daemon.

- **stdio mode (Default spawned automatically by IDEs):**
  ```powershell
  autopoiesis serve --mode stdio
  ```

- **HTTP mode (For Web Dashboard UI & remote access):**
  ```powershell
  autopoiesis serve --mode http --host 127.0.0.1 --port 8000
  ```

---

## 2. Checking Active Agent State & Logs

1. Launch HTTP mode:
   `autopoiesis serve --mode http --host 127.0.0.1 --port 8000`
2. Open `http://127.0.0.1:8000/ui` in your browser.
3. Every micro-skill (Core, Variant, Template) is displayed as an individual card with execution counts and a *"View Agent Logs"* button.
