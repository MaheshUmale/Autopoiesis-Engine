# User Manual: Autopoiesis-Engine

Welcome to the **Autopoiesis Engine User Manual**. This document covers operating the CLI, managing skills in the 3-Tier Registry, executing DAG workflows, and utilizing sandbox execution.

---

## 1. CLI Commands Reference

### `autopoiesis init`

Initializes a project directory for Autopoiesis Engine execution.

```bash
autopoiesis init [--path /path/to/project]
```

---

### `autopoiesis serve`

Launches the MCP Server router.

- **stdio mode (Default for IDEs):**
  ```bash
  autopoiesis serve --mode stdio
  ```

- **HTTP/SSE mode (Background Daemon):**
  ```bash
  autopoiesis serve --mode http --host 127.0.0.1 --port 8000
  ```

---

## 2. The 3-Tier Registry Architecture

The framework organizes skills and workflows into three tiers:

1. **Level 1 Core (`registry/level_1_core/`):** Universal, domain-agnostic primitive Python micro-skills (e.g., JSON parsers, HTTP fetchers).
2. **Level 2 Variants (`registry/level_2_variants/`):** Domain-specific skill implementations (e.g., broker integrations, custom exchange parsers).
3. **Level 3 Templates (`registry/level_3_templates/`):** Parameterized composite DAG workflow definitions connecting micro-skills into pipelines.

---

## 3. Writing Micro-Skills

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

## 4. Sandbox Execution & State Thresholding

- **Dynamic Timeout Scaling:**
  Executing micro-skills in the sandbox scales timeout automatically based on input size:
  $$\text{Timeout} = 5.0 + (\text{Payload}_{\text{MB}} \times 2.0) \text{ seconds}$$

- **100 KB Payload Boundary Rule:**
  - Payloads `< 100 KB` pass inline directly through activity execution.
  - Payloads `>= 100 KB` serialize automatically to disk/Parquet (`.autopoiesis/staging/{execution_id}_{node_id}.parquet`) returning a `_storage_type: file` pointer. Downstream skills hydrate file pointers back into memory transparently.

---

## 5. Temporal DAG Workflows & Self-Healing

- Workflows execute deterministically using `AutopoiesisDAGWorkflow`.
- If a skill fails due to logic errors or syntax issues, failure routes to `SelfHealingWorkflow`.
- The Diagnostic Decision Tree attempts up to **3 hotfix retries** before aborting.
