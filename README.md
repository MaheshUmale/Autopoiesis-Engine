# Autopoiesis-Engine
 Autonomous AI Coding Agents (Cursor, Claude 3.5 Sonnet, Windsurf, Devika)

# Technical Requirements Specification: Autopoietic Agent Framework (AAF)

**Project Codename:** `Autopoiesis-Engine`
**Target Audience:** Autonomous AI Coding Agents (Cursor, Claude 3.5 Sonnet, Windsurf, Devika)
**Protocol Standards:** Model Context Protocol (MCP), Temporal.io Distributed Harness
**System Objective:** Build a self-evolving, multi-tenant agent execution framework that autonomously writes, tests, caches, self-heals, and orchestrates micro-skills into composite workflow DAGs using a biological paradigm (DNA $\rightarrow$ RNA $\rightarrow$ Protein Synthesis).

---

## 1. System Philosophy & Architecture

The Autopoiesis-Engine eliminates the need for hardcoded, static agent tools. Instead, it relies on **Autopoietic Tool Synthesis**.

* **DNA Primitives (Micro-Skills):** Atomic, single-function Python modules with strict Pydantic inputs/outputs. Fully decoupled from runtime variables (parameterized).
* **Proteins (Composite DAGs):** Workflows built dynamically by assembling micro-skills.
* **Autopoiesis (Self-Healing & Synthesis):** The framework anticipates missing tools via look-ahead parsing, generates the missing logic, tests it in an isolated sandbox, repairs runtime errors via telemetry loops, and saves successful graphs as parameterized templates.

---

## 2. Global End-to-End System Flow

```
[ Incoming Project Intent (e.g., project.yaml / prompt) ]
                           │
                           ▼
   [ 1. Look-Ahead Spec Parser ] ──(Extracts Scope & Execution Pipeline)
                           │
                           ▼
   [ 2. Namespace Engine ] ──(Filters Vector Search by Active Domains)
                           │
                           ▼
   [ 3. Template Registry ] ──(DAG Match Found?)──► [ Direct Parameter Injection & Execution ]
                           │
                      (No Match)
                           │
                           ▼
   [ 4. Skill Registry ] ─────(Missing Tool?)─────► [ 5. Skill Writer Loop via MCP ]
                           │                                            │
                           ▼                                            ▼
   [ 6. Builder DAG Engine ] ◄───────────────────────── [ Verification Sandbox ]
                           │                                            │
                           ▼                                    (Auto-Fix Failure)
     [ Sandbox / Runtime Execution ] ──(Error?) ────────► [ Self-Healing Repair Loop ]
                           │
                       (Success)
                           │
                           ▼
     [ 7. Extract & Save Parameterized Composite Template ]

```

---

## 3. Storage Architecture: The 3-Tier Registry

The framework prevents semantic bloat and context-window exhaustion by segmenting tools into a strict 3-tier hierarchy indexed by both SQL (relational) and Qdrant (vector) databases.

### A. Directory Structure

```
/registry
  /level_1_core/                 # Universal DNA Primitives
    /json_parser/
      - skill.py
      - schema.json
  /level_2_variants/             # Domain-Specific Skill Implementations
    /trading.upstox/
      - fetch_historical.py
      - fetch_historical.json
  /level_3_templates/            # Composite DAG Workflows
    /trading.upstox/
      - fetch_and_write_db_tpl.json

```

### B. Skill Metadata Schema (`schema.json`)

Every generated tool must adhere to this JSON Schema definition for MCP tool exposure:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "id": "trading.upstox.fetch_historical",
  "namespace": "trading.broker.upstox",
  "scope_level": "variant",
  "description": "Fetches OHLCV candle data from Upstox REST endpoint.",
  "inputs": {
    "type": "object",
    "properties": {
      "instrument_key": { "type": "string" },
      "interval": { "type": "string", "enum": ["1minute", "5minute"] },
      "from_date": { "type": "string", "format": "date" }
    },
    "required": ["instrument_key", "interval", "from_date"]
  },
  "outputs": {
    "type": "object",
    "properties": {
      "status": { "type": "string" },
      "candles": { "type": "array" }
    }
  },
  "ast_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}

```

* **Constraint:** The Builder Agent MUST calculate the SHA-256 hash of the generated Python AST (`ast_hash`) before saving. If the hash matches an existing skill, the creation is bypassed (Deduplication).

---

## 4. Feature 1: Predictive Look-Ahead & Namespace Resolution

### The `project.yaml` Configuration

The system resolves the required context before execution starts to filter the vector registry.

```yaml
project_id: upstox_momentum_bot
active_namespaces:
  - global
  - trading.broker.upstox
  - analytics.indicators

required_pipeline_intent: |
  Fetch 1-minute historical candles from Upstox, calculate 20-period Volume SMA, 
  and store the result in PostgreSQL.

```

### Logic Sequence

1. Parse `required_pipeline_intent` to extract semantic nodes.
2. Search Qdrant vector database using payload filter: `namespace IN active_namespaces`.
3. If the vector search similarity for "Calculate 20-period Volume SMA" is below `0.85`, dispatch an asynchronous Temporal task to the **Skill Writer** to generate the tool *before* the Orchestrator reaches that execution step.

---

## 5. Feature 2: Parameterized Template Caching (Macro Workflows)

When the Builder successfully connects micro-skills into a sequence that executes without errors, the engine extracts an abstract template to bypass future LLM calls.

```json
{
  "template_id": "tpl_upstox_to_postgres",
  "namespace": "trading.broker.upstox",
  "parameters": {
    "timeframe": { "type": "string" },
    "target_table": { "type": "string" }
  },
  "dag": {
    "nodes": [
      {
        "id": "step_1",
        "skill_id": "trading.upstox.fetch_historical",
        "args": { "interval": "{{ parameters.timeframe }}" }
      },
      {
        "id": "step_2",
        "skill_id": "global.db.postgres_upsert",
        "args": {
          "table": "{{ parameters.target_table }}",
          "data": "{{ step_1.output }}"
        }
      }
    ]
  }
}

```

---

## 6. Feature 3: Sandbox Verification & Self-Healing Loop

All execution and validation occur in a closed loop. If an error is detected, the engine diagnoses the root cause.

### A. Dynamic Timeout Scaling

Hardcoded timeouts break on large data parsing. Timeouts must be calculated dynamically based on input payload size:

$$\text{Timeout}_{\text{total}} = 5 + \left( \frac{\text{Payload}_{\text{bytes}}}{1048576} \times 2.0 \right)$$


*(Base 5 seconds, plus 2 seconds per MB of input data).*

### B. Self-Healing Diagnostic Decision Tree

When an execution fails, evaluate the trace:

1. **Pydantic Schema Validation Fails on Input:** Issue lies with the *Upstream Node*. Do not mutate the current skill code. Trigger upstream pipeline repair.
2. **Sandbox Mock Pass $\rightarrow$ Live Fail (Timeout/OOM):** Environmental Resource failure. Auto-patch the Python code to use streaming/chunking generators instead of holding objects in memory.
3. **Sandbox Mock Pass $\rightarrow$ Live Fail (HTTP 429/500):** Network error. Auto-patch the skill with an exponential backoff decorator.
4. **Sandbox Mock Fail (TypeError / SyntaxError):** Logic error. Route the OpenTelemetry trace, `stderr`, and the source code back to the Skill Writer Agent for a hotfix. Maximum 3 retry loops. Tool execution errors must conform to MCP standard by returning `isError: true`.

---

## 7. Feature 4: Temporal.io Distributed Harness Integration

To manage multi-worker concurrency, timeouts, and state tracking, the engine uses **Temporal**. The coding agent must strictly follow Temporal Python SDK paradigms:

```python
from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from datetime import timedelta
from typing import Any
from pydantic import BaseModel

class ExecuteSkillParams(BaseModel):
    skill_id: str
    input_payload: dict[str, Any]

@activity.defn(name="execute_micro_skill")
async def execute_micro_skill_activity(params: ExecuteSkillParams) -> dict:
    # 1. Dynamically load skill code from Registry
    # 2. Invoke PlatformAdapter for sandboxed execution
    # 3. Return results or raise explicit Exception for Self-Healing trap
    pass

@workflow.defn(name="AutopoiesisDAGWorkflow")
class AutopoiesisDAGWorkflow:
    @workflow.run
    async def run(self, dag_template: dict) -> dict:
        # Deterministic DAG execution. No raw threading/network I/O here.
        # Execute each node using execute_micro_skill_activity.
        pass

```

* **Constraint:** Workflows must be deterministic (no random numbers, system clock calls, or un-mocked I/O inside the `@workflow.run` definition).

---

## 8. Feature 5: Cross-Platform Execution Abstraction

Agents must NEVER generate OS-specific shell strings (e.g., `bash -c` or `subprocess.run("ls")`). The engine enforces a `PlatformAdapter` to ensure seamless execution on Windows (PowerShell) and Linux/macOS.

```python
import sys
import subprocess
from pathlib import Path

class PlatformAdapter:
    @staticmethod
    def get_shell_command(cmd_string: str) -> list[str]:
        if sys.platform == "win32":
            return ["pwsh", "-NoProfile", "-NonInteractive", "-Command", cmd_string]
        return ["/bin/bash", "-c", cmd_string]

    @staticmethod
    def sanitize_path(path_str: str) -> Path:
        return Path(path_str).resolve()

```

---

## 9. Feature 6: Terminal Multiplexing (`wmux`/`tmux`)

To observe the distributed workers programmatically, the system relies on a `tmux` abstraction using `libtmux`. This allows multi-pane background processing resilient to SSH disconnections.

```python
import libtmux

class AgentWindowManager:
    def __init__(self, session_name="autopoiesis_engine"):
        self.server = libtmux.Server()
        self.session = self.server.find_where({"session_name": session_name})
        if not self.session:
            self.session = self.server.new_session(session_name=session_name)

    def spawn_worker_pane(self, worker_name: str, command: str):
        window = self.session.attached_window
        pane = window.split_window(vertical=False)
        pane.send_keys(f"echo 'Starting Worker: {worker_name}'", enter=True)
        pane.send_keys(command, enter=True)

```

---

## 10. Feature 7: Observability & Deterministic Replay

1. **OpenTelemetry (OTEL):** Every DAG node execution must wrap inside a trace span:
`span.set_attribute("skill.id", "trading.upstox.fetch")`
`span.set_attribute("payload.size_bytes", len(payload))`
2. **State Snapshot Files:** DAG step I/O must append to local state files for replay:
`.autopoiesis/traces/{execution_uuid}.json`

---

## Single-Shot Agent Implementation Directives

**To the AI Coding Agent generating this project:**

1. **Initialize Project:** Create the directory structure, setup `pyproject.toml` with `temporalio`, `qdrant-client`, `pydantic>=2.0`, `libtmux`, and `opentelemetry-sdk`.
2. **Database:** Initialize SQLite for relational mappings and Qdrant (local memory mode) for vector similarity of skill docstrings.
3. **Execution Layer:** Implement `PlatformAdapter` and `SandboxExecutor` first, as they are the bedrock for all generated skill evaluations.
4. **Temporal Workflows:** Map the logic in Section 7 exactly. Handle activity failures via Temporal's built-in `RetryPolicy`, routing terminal failures to a dedicated `SelfHealingWorkflow`.
5. **No Placeholders:** Write complete, production-ready Python code. Implement explicit AST-hash checking for the deduplication requirement.


The specification is exceptionally thorough, structurally complete, and covers almost every major engineering hurdle discussed. However, if an AI Coding Agent (such as Claude 3.5 Sonnet or Cursor) attempts to build this in a **single shot**, there are **three critical gaps** in the specification where the agent will be forced to make unguided architectural assumptions.

Addressing these three specific areas will ensure the spec is 100% deterministic and ready for single-shot generation:

---

### 1. The MCP (Model Context Protocol) Server Integration Layer

* **The Gap:** The spec references MCP in Section 3 and Section 6, but doesn't define *how* the engine serves these dynamically generated tools to target LLMs.
* **Why it needs elaboration:** An AI coding agent won't know whether to write an HTTP/REST server, an stdio-based MCP wrapper, or an OpenAI-style function-calling schema.
* **What to add to the Spec:**
* Define an `MCPServer` wrapper that dynamically mounts files in `Level 1` and `Level 2` of the registry as live MCP Tools.
* Explicitly specify that the server reads the `schema.json` of active namespaces and returns them via the standard MCP `tools/list` protocol endpoint.



---

### 2. The AST Hash Deduplication & Variation Rules

* **The Gap:** Section 3 states: *"If the AST hash matches an existing skill, creation is bypassed."* However, earlier we agreed to **preserve contextual variations** rather than forcing bad over-generalizations.
* **Why it needs elaboration:** Without exact rules, the AI coding agent will either reject useful domain-specific variations (because their logic looks similar) or flood the registry with near-duplicate code.
* **What to add to the Spec:**
* **Exact Deduplication Logic:** Strip docstrings, comments, and parameter variable names before AST hashing. If the normalized logic tree is identical, drop it.
* **Variation Exception Rule:** If the AST logic differs by domain-specific AST nodes (e.g., custom API headers, specific authentication payload keys, specialized parsing rules), permit creation and save it under the specific `namespace` scope (e.g., `trading.upstox` vs. `trading.zerodha`), even if the high-level semantic vector embedding is close.



---

### 3. Concrete State Bridge between DAG Nodes (The Inter-Node Data Pipeline)

* **The Gap:** Section 5 shows template nodes mapping outputs (`"args": { "raw_data": "{{ step_1.output }}" }`), but doesn't specify how large datasets (e.g., 100MB dataframes or file paths) move between workers without overwhelming memory or Temporal payload limits.
* **Why it needs elaboration:** Temporal activities have payload size limits (typically ~2MB–4MB). Passing massive JSON payloads directly through activity return values will crash Temporal.
* **What to add to the Spec:**
* **The Data-Pointer Strategy (Threshold Rule):**
* If payload size is $< 100 \text{ KB}$: Pass data inline as JSON directly in Temporal activity state.
* If payload size is $\ge 100 \text{ KB}$: The micro-skill must serialize the data to a local staging store (e.g., `.autopoiesis/state/{execution_id}/{step_id}.parquet` or SQLite/S3) and pass an explicit **File Pointer URI** (`file://...`) to the next DAG node.





---

### Revised Addendum Snippet to Insert into Your Final Specification

```markdown
## 11. Core Addendums for Single-Shot Code Generation

### A. Dynamic Model Context Protocol (MCP) Bridge
The framework must include an `MCPToolRegistry` module using `mcp-attr` or official `mcp` SDK:
1. Read active `namespace` directories from `registry/level_1_core/` and `registry/level_2_variants/`.
2. Automatically transform every skill's `schema.json` into a live MCP `Tool` definition.
3. Expose execution entrypoints through `mcp.types.Tool` with standard error wrapping (`isError: true` on Sandbox failure).

### B. Normalized AST Deduplication Implementation
```python
import ast

def get_normalized_ast_hash(python_code: str) -> str:
    """Strips docstrings, comments, and variable identifiers to generate a structural AST fingerprint."""
    tree = ast.parse(python_code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            node.name = "_"
        elif isinstance(node, ast.arg):
            node.arg = "_"
        elif isinstance(node, ast.Name):
            node.id = "_"
        # Strip docstrings
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)) and node.body:
            if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                node.body.pop(0)
    return hashlib.sha256(ast.dump(tree).encode("utf-8")).hexdigest()

```

### C. Inter-Node State Passing & Temporal Payload Safety

To avoid exceeding Temporal's activity payload limits:

* **Small Payloads (< 100 KB):** Passed inline via Temporal activity return values.
* **Large Payloads (>= 100 KB):** Serialized to disk/object storage (`.autopoiesis/staging/{execution_id}/{node_id}.parquet`), returning a payload pointer `{"_storage_type": "file", "path": "..."}`. The downstream node's runtime wrapper automatically hydrates this path back into a memory object.

```

---

<ElicitationsGroup message="How would you like to proceed with finalizing the spec?">

  <Elicitation label="Incorporate these 3 additions and output the consolidated final document" query="Please merge these 3 addendums into the full Technical Requirements Specification and output the final consolidated specification document."/>

  <Elicitation label="Focus on the Python code implementation directly" query="The spec is ready. Let's begin generating the core Python codebase starting with Feature 1 and Feature 4."/>

</ElicitationsGroup>

```
