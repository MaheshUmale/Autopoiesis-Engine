# User Manual: Autopoiesis-Engine

Welcome to the **Autopoiesis Engine User Manual**. This document covers operating the CLI, managing skills in the 3-Tier Registry, executing DAG workflows, enabling AI Coding Agents (Kilocode, VS Code, Cursor, Claude) to execute synthesized tools, and verifying local execution state.

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

## 2. Verifying Autopoiesis Execution in Kilocode / VS Code / Cursor

When prompting an AI Agent (e.g., *"Parse JSON data from payload.json and double the value field"*), you can verify whether the action was executed by the **Autopoiesis Engine vs Raw LLM Chat** via:

1. **Kilocode Chat UI Tool Badge:** Look for the tool invocation card in Kilocode chat (`Using Tool: autopoiesis-engine -> execute_macro_intent` or `global.parsers.json_parser`).
2. **Local OTEL Trace Files:** Check `.autopoiesis/traces/{execution_id}.json` in your project folder. Every execution writes a JSON file recording execution time, stdout, stderr, and span attributes.
3. **SQLite Database Logs:** Query `.autopoiesis/autopoiesis.db` to view registered skills, parameters, and execution history.
4. **Daemon Terminal Logs:** When running `autopoiesis serve --mode http`, tool requests appear live in the terminal console.

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
