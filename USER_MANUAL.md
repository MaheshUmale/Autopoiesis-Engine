# User Manual: Autopoiesis-Engine

Welcome to the **Autopoiesis Engine User Manual**. This document covers operating the CLI, managing skills in the 3-Tier Registry, executing DAG workflows, and enabling AI Coding Agents (Kilocode, VS Code, Cursor, Claude) to execute synthesized tools.

---

## 1. CLI Commands Reference

### `autopoiesis init`

Initializes a project directory for Autopoiesis Engine execution.

```bash
autopoiesis init [--path /path/to/project]
```

This sets up:
- `.autopoiesis/` local state storage (SQLite database, Qdrant vector storage, Parquet staging files).
- `registry/` folder structure (`level_1_core`, `level_2_variants`, `level_3_templates`).
- MCP configuration files for Kilocode (`.kilocode/mcp.json`), VS Code (`.vscode/mcp.json`), Cursor (`.cursor/mcp.json`), and Claude Desktop.

---

### `autopoiesis serve`

Launches the MCP Server daemon.

- **stdio mode (Default for IDEs & Agents):**
  ```bash
  autopoiesis serve --mode stdio
  ```

- **HTTP/SSE mode (Background Daemon for Web & Remote Services):**
  ```bash
  autopoiesis serve --mode http --host 127.0.0.1 --port 8000
  ```

---

## 2. How AI Agents (Kilocode / VS Code / Cursor) Execute Tools

1. Your IDE (Kilocode, VS Code, Cursor) starts and reads its MCP configuration file (`.kilocode/mcp.json` or `.vscode/mcp.json`).
2. The IDE launches `autopoiesis serve --mode stdio` in the background.
3. When you prompt your AI Agent in Kilocode or VS Code:
   > *"Parse JSON data from payload.json and double the value field"*
4. The AI Agent inspects the available tools provided by the Autopoiesis Engine, formats a tool call request, and passes it to the engine over standard MCP stdio.
5. The Autopoiesis Engine executes the code in a sandboxed subprocess and returns the result back to the AI Agent.

---

## 3. The 3-Tier Registry Architecture

The framework organizes skills and workflows into three tiers:

1. **Level 1 Core (`registry/level_1_core/`):** Universal, domain-agnostic primitive Python micro-skills (e.g., JSON parsers, HTTP fetchers).
2. **Level 2 Variants (`registry/level_2_variants/`):** Domain-specific skill implementations (e.g., broker integrations, custom exchange parsers).
3. **Level 3 Templates (`registry/level_3_templates/`):** Parameterized composite DAG workflow definitions connecting micro-skills into pipelines.

---

## 4. Writing Micro-Skills

Every micro-skill is a standalone Python script defining a `main(inputs: dict) -> dict` entry point.

### Example Micro-Skill (`skill.py`):

```python
def main(inputs: dict) -> dict:
    val = inputs.get("val", 0)
    return {"double_val": val * 2}
```

### Accompanying Schema (`schema.json`):

```json
{
  "id": "global.math.double",
  "namespace": "global",
  "scope_level": "core",
  "description": "Doubles an input integer value.",
  "inputs": {
    "type": "object",
    "properties": {
      "val": { "type": "integer" }
    },
    "required": ["val"]
  },
  "outputs": {
    "type": "object",
    "properties": {
      "double_val": { "type": "integer" }
    }
  },
  "ast_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

---

## 5. Sandbox Execution & State Thresholding

- **Dynamic Timeout Scaling:**
  Executing micro-skills in the sandbox scales timeout automatically based on input size:
  $$\text{Timeout} = 5.0 + (\text{Payload}_{\text{MB}} \times 2.0) \text{ seconds}$$

- **100 KB Payload Boundary Rule:**
  - Payloads `< 100 KB` pass inline directly through activity execution.
  - Payloads `>= 100 KB` serialize automatically to disk/Parquet (`.autopoiesis/staging/{execution_id}_{node_id}.parquet`) returning a `_storage_type: file` pointer. Downstream skills hydrate file pointers back into memory transparently.

---

## 6. Temporal DAG Workflows & Self-Healing

- Workflows execute deterministically using `AutopoiesisDAGWorkflow`.
- If a skill fails due to logic errors or syntax issues, failure routes to `SelfHealingWorkflow`.
- The Diagnostic Decision Tree attempts up to **3 hotfix retries** before aborting.
