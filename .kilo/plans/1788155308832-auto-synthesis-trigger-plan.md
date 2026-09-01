# Plan: Explicit Auto-Synthesis Trigger & Missing Feature Audit

## 1. Current State Assessment

### What IS Implemented
- Auto-synthesis engine (`LookAheadParser.synthesize_and_register_skill()`)
- Implicit trigger via `run_intent` / `execute_macro_intent` (MCP tools)
- Template-based code generation for 5 categories (parse, double, save, shell, generic)
- Sandbox verification before registration
- AST-based deduplication and Qdrant indexing
- All 107 tests passing

### What is MISSING / Under-Tested
| Feature | Status | Evidence |
|---------|--------|----------|
| **Explicit auto-synthesis trigger** | ❌ Missing | No dedicated MCP tool or CLI command to synthesize a skill on-demand without full pipeline execution |
| **Auto-synthesis end-to-end via MCP** | ❌ Not tested | `run_intent_handler` calls `auto_synthesize=True` but no test verifies a NEW skill is actually created and executed |
| **Web dashboard functionality** | ⚠️ Untested | HTML exists but never served/verified with live data |
| **Temporal.io DAG execution** | ⚠️ Unverified | `temporalio` in deps but `AutopoiesisDAGWorkflow` may not be wired to Temporal server |
| **OpenTelemetry tracing** | ⚠️ Unverified | `opentelemetry-sdk` in deps but no explicit OTLP export configured |
| **AgentWindowManager (Windows)** | ⚠️ Partial | Code exists but only basic initialization tested |
| **Large payload staging (>100KB)** | ⚠️ Unverified | `process_payload_for_storage` exists but no integration test with >100KB payloads |
| **CLI `autopoiesis amf` commands** | ⚠️ Partial | `amf/cli.py` exists but not all subcommands tested end-to-end |

## 2. Primary Goal: Add Explicit Auto-Synthesis Trigger

### Problem
Current auto-synthesis is **implicit only**:
- User must call `run_intent` with a multi-step prompt
- Synthesis happens automatically if no skill matches (similarity < 0.85)
- No way to say "create a new skill called X that does Y" without also executing the full pipeline

### Proposed Solution

Add two new public interfaces:

#### A. New MCP Tool: `synthesize_skill`
```python
async def synthesize_skill(
    step_description: str,
    namespace: str = "global",
    test_inputs: dict = None
) -> dict:
    """Explicitly synthesize and register a new micro-skill from a natural language description.
    
    Returns:
        skill_id, generated_code, test_result, status
    """
```

**Behavior:**
1. Calls `LookAheadParser.synthesize_and_register_skill()`
2. Optionally tests the skill with `test_inputs` via `SandboxExecutor`
3. Returns skill metadata + execution result
4. Does NOT execute the skill in a pipeline — only creates and verifies it

#### B. New MCP Tool: `synthesize_and_run`
```python
async def synthesize_and_run(
    intent: str,
    active_namespaces: List[str] = None
) -> dict:
    """Synthesize missing skills and execute the full intent pipeline.
    
    This is the explicit version of the implicit auto-synthesis in run_intent.
    """
```

**Behavior:**
1. Same as `run_intent` but explicitly named to indicate synthesis happens
2. Returns full execution log with which skills were synthesized vs reused

#### C. CLI Command: `autopoiesis synthesize`
```powershell
autopoiesis synthesize "Double all values in data.json" --namespace global --test
```

## 3. Implementation Tasks

### Task 1: Add `synthesize_skill` MCP Tool
- **File:** `src/autopoiesis/mcp/server.py`
- **Change:** Add new async tool handler after `run_intent_handler`
- **Pattern:** Follow existing MCP tool pattern (see `agent_session_create`, `heal_suggestion`)
- **Dependencies:** `LookAheadParser`, `SandboxExecutor`

### Task 2: Add `synthesize_and_run` MCP Tool
- **File:** `src/autopoiesis/mcp/server.py`
- **Change:** Extract pipeline execution logic from `run_intent_handler` into reusable function, expose as separate tool
- **Benefit:** Clearer API contract — users know synthesis will happen

### Task 3: Add `synthesize` CLI Command
- **File:** `src/autopoiesis/cli/main.py` and `src/autopoiesis/cli/commands.py` (or existing CLI structure)
- **Change:** Add `synthesize` subcommand with `--namespace`, `--test`, `--json` flags

### Task 4: End-to-End Auto-Synthesis Tests
- **File:** `tests/test_auto_synthesis.py` (new)
- **Tests:**
  1. `test_synthesize_skill_creates_functional_skill` — verify skill is created and executes correctly
  2. `test_synthesize_skill_deduplication` — verify same description returns existing skill
  3. `test_synthesize_and_run_full_pipeline` — multi-step intent with synthesis
  4. `test_synthesize_skill_via_mcp_tool` — test MCP tool directly
  5. `test_synthesize_different_templates` — test all 5 template categories (parse, double, save, shell, generic)

### Task 5: Audit & Fix Other Missing Features
- **Temporal.io:** Verify `AutopoiesisDAGWorkflow` is wired to Temporal server; add test or remove dependency if unused
- **OpenTelemetry:** Configure OTLP export or remove unused deps
- **Web Dashboard:** Add test that serves dashboard and verifies API endpoints return data
- **Large Payloads:** Add integration test with >100KB payload through staging

## 4. Validation Plan

1. **Unit tests:** All new MCP tools and CLI commands have dedicated tests
2. **Integration test:** Full flow — `synthesize_skill` → skill created → skill invoked → result verified
3. **Regression:** Full test suite must still pass (107 → 112+ tests)
4. **Manual verification:** `autopoiesis synthesize "test description"` works in PowerShell

## 5. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Template-based synthesis produces broken code | Sandbox verification already exists — extend test coverage |
| Skill ID collisions | AST hash deduplication already handles this |
| MCP tool name conflicts | Use `synthesize_skill` prefix to avoid collisions |
| CLI command conflicts | `synthesize` is a new subcommand, no existing conflict |

## 6. Out of Scope

- LLM-based code generation (requires external API, not in current architecture)
- Real-time skill improvement from execution feedback (beyond current deduplication)
- Multi-language skill support (Python only)
