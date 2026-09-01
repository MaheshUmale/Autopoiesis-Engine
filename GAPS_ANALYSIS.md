# Autopoiesis Engine — Gap Analysis Report

**Date:** 2026-09-01
**Scope:** Logical, Architectural, Workflow, Integration, and Testing Gaps

---

## Executive Summary

Analysis of the Autopoiesis Engine codebase revealed **14 critical gaps** across 5 categories. Each gap is documented with root cause, impact, and proposed solution.

---

## 1. LOGICAL GAPS

### GAP-L1: Message Bus Callbacks Never Invoked
**Location:** `src/autopoiesis/core/messaging.py`
**Severity:** HIGH

**Problem:** The `AgentMessageBus.subscribe()` method accepts a `callback` parameter and stores it, but `publish()` never invokes any callbacks. The pub/sub pattern is broken — agents cannot receive real-time messages.

**Impact:** Agent-to-agent communication is non-functional. The entire inter-agent messaging system is dead code.

**Solution:** Implement callback invocation in `publish()` with async delivery and error isolation.

---

### GAP-L2: Code Duplication in MCP Server Pipeline Execution
**Location:** `src/autopoiesis/mcp/server.py` (lines 118-758)
**Severity:** MEDIUM

**Problem:** Three functions (`run_intent_handler`, `synthesize_and_run`, `amf_genesis_synthesize`) share ~90% identical code for pipeline resolution and execution. Each has ~150 lines of duplicated logic.

**Impact:** Bug fixes must be applied in 3 places. Inconsistencies will emerge over time.

**Solution:** Extract shared pipeline execution logic into a single `execute_pipeline()` helper function.

---

### GAP-L3: Healing Cache Patterns Never Auto-Applied
**Location:** `src/autopoiesis/core/healing.py`, `src/autopoiesis/mcp/server.py`
**Severity:** HIGH

**Problem:** The `HealLearningCache` stores error→fix patterns, but the MCP server's `run_intent_handler` never checks the cache before executing skills. Patterns are only accessible via explicit `heal_suggestion` tool call.

**Impact:** Self-healing is manual, not automatic. The "self-evolving" design principle is not realized.

**Solution:** Integrate cache lookup into pipeline execution — check for known fixes before first execution attempt.

---

### GAP-L4: Orchestrator Retry Doesn't Apply Fix
**Location:** `src/autopoiesis/amf/orchestrator.py` (lines 143-157)
**Severity:** HIGH

**Problem:** When a node fails and a healing suggestion is found, the orchestrator sets `patched_inputs["_patched"] = True` but never actually applies `fix_code_patch` to the skill code. The retry executes the same broken code.

**Impact:** Self-healing in workflows is illusory — retries always fail with the same error.

**Solution:** Implement actual code patching by injecting the fix into the skill code before retry.

---

## 2. ARCHITECTURAL GAPS

### GAP-A1: No Event-Driven Architecture
**Location:** `src/autopoiesis/core/messaging.py`
**Severity:** HIGH

**Problem:** The message bus is a passive store. There's no event emitter, no async delivery, no delivery guarantees. Agents must poll for messages.

**Impact:** Real-time agent coordination is impossible. Workflows cannot react to external events.

**Solution:** Implement an `EventEmitter` pattern with async delivery, acknowledgment, and dead-letter queue for failed deliveries.

---

### GAP-A2: Split-Brain Between Session Manager and AMF Registry
**Location:** `src/autopoiesis/core/session.py`, `src/autopoiesis/amf/registry.py`
**Severity:** MEDIUM

**Problem:** Agent state is split across two SQLite databases (`.autopoiesis/autopoiesis.db` and `.autopoiesis/amf_registry.db`). No foreign keys, no transactions, no consistency guarantees.

**Impact:** Agent state can become inconsistent. Crash recovery may leave orphaned sessions or registry entries.

**Solution:** Unify agent state management under AMF Registry with session data embedded, or implement cross-db reconciliation.

---

### GAP-A3: Observability Data Loss Risk
**Location:** `src/autopoiesis/core/observability.py`
**Severity:** MEDIUM

**Problem:** Metrics are held in memory (`self._metrics: List`) and only persisted every 10 executions. A crash loses all unpersisted metrics.

**Impact:** Execution history gaps. Inaccurate success rates and health metrics after crashes.

**Solution:** Persist every execution immediately (with batching for performance). Add WAL mode for SQLite.

---

## 3. WORKFLOW GAPS

### GAP-W1: No Local Workflow Execution Fallback
**Location:** `src/autopoiesis/workflows/dag.py`
**Severity:** HIGH

**Problem:** `AutopoiesisDAGWorkflow` requires a Temporal.io server. Without it, no multi-step workflows can execute. The `AMFOrchestrator` implements its own DAG execution but it's not integrated with Temporal.

**Impact:** Users without Temporal cannot run composite workflows. The AMFOrchestrator is the only local option but lacks Temporal's durability.

**Solution:** Make Temporal optional — use AMFOrchestrator as primary, Temporal as optional enhancement for distributed execution.

---

### GAP-W2: No Workflow Pause/Resume
**Location:** `src/autopoiesis/amf/orchestrator.py`
**Severity:** MEDIUM

**Problem:** Once a workflow starts, it runs to completion or failure. There's no way to pause mid-execution, inspect state, and resume.

**Impact:** Long-running workflows cannot be debugged or manually intervened.

**Solution:** Implement checkpointing — persist node_outputs after each node, allow resume from last completed node.

---

### GAP-W3: Self-Healing Doesn't Modify Code
**Location:** `src/autopoiesis/workflows/activities.py`
**Severity:** HIGH

**Problem:** The `heal_skill_activity` in Temporal workflows doesn't actually modify skill code. It returns a result but the retry executes the same code.

**Impact:** Temporal-based self-healing is non-functional.

**Solution:** Implement actual code patching in the healing activity, or integrate with `HealLearningCache` for known fixes.

---

## 4. INTEGRATION GAPS

### GAP-I1: Missing MCP Tools
**Location:** `src/autopoiesis/mcp/server.py`
**Severity:** MEDIUM

**Problem:** Several AMF tools are exposed in CLI but not via MCP:
- `amf_get_agent_status` (only available via CLI)
- `amf_list_agents` (exposed but not documented)
- No `amf_workflow_list` tool

**Impact:** AI agents cannot discover or inspect AMF state programmatically.

**Solution:** Expose all AMF operations as MCP tools with proper schemas.

---

### GAP-I2: Request/Reply Pattern Not Functional
**Location:** `src/autopoiesis/amf/bus.py` (lines 111-151)
**Severity:** HIGH

**Problem:** `request_reply()` subscribes to a reply channel and sends a request, but returns immediately without waiting for the reply. The caller has no way to receive the response.

**Impact:** Synchronous-style agent communication is impossible.

**Solution:** Implement async polling with timeout for reply messages, or use asyncio.Event for notification.

---

### GAP-I3: No Inter-Agent Data Flow in Workflows
**Location:** `src/autopoiesis/amf/orchestrator.py`
**Severity:** MEDIUM

**Problem:** The orchestrator delivers messages between nodes via `AMFBusAdapter.deliver_to_agent()`, but these messages are never consumed by the target nodes. The data flow is one-way (node_outputs only).

**Impact:** Agents in a workflow cannot communicate asynchronously. Complex coordination patterns are impossible.

**Solution:** Implement message consumption in node execution — check agent's message queue before invocation.

---

## 5. TESTING GAPS

### GAP-T1: No Integration Tests for End-to-End Workflows
**Location:** `tests/`
**Severity:** HIGH

**Problem:** Unit tests exist for individual components, but no test exercises the full flow: intent → skill resolution → execution → observability → healing.

**Impact:** Regressions in integration logic go undetected.

**Solution:** Add integration tests that spin up the MCP server and execute multi-step intents.

---

### GAP-T2: No Tests for Message Delivery
**Location:** `tests/test_agentic.py`
**Severity:** MEDIUM

**Problem:** Tests verify message storage but not callback invocation or delivery guarantees.

**Impact:** The broken callback system (GAP-L1) is not caught by tests.

**Solution:** Add tests that subscribe with a callback and verify it's invoked on publish.

---

### GAP-T3: No Tests for Concurrent Agent Execution
**Location:** `tests/`
**Severity:** MEDIUM

**Problem:** No tests verify behavior when multiple agents execute simultaneously, share the message bus, or contend for registry access.

**Impact:** Race conditions and deadlocks in production.

**Solution:** Add concurrency tests with parallel agent execution and shared resources.

---

## Summary Matrix

| Gap | Category | Severity | Effort |
|-----|----------|----------|--------|
| L1 | Logical | HIGH | Medium |
| L2 | Logical | MEDIUM | Low |
| L3 | Logical | HIGH | Medium |
| L4 | Logical | HIGH | Medium |
| A1 | Architectural | HIGH | High |
| A2 | Architectural | MEDIUM | Medium |
| A3 | Architectural | MEDIUM | Low |
| W1 | Workflow | HIGH | High |
| W2 | Workflow | MEDIUM | Medium |
| W3 | Workflow | HIGH | Medium |
| I1 | Integration | MEDIUM | Low |
| I2 | Integration | HIGH | Medium |
| I3 | Integration | MEDIUM | Medium |
| T1 | Testing | HIGH | High |
| T2 | Testing | MEDIUM | Low |
| T3 | Testing | MEDIUM | Medium |

---

## Implementation Priority

1. **Phase 1 — Critical Fixes (HIGH severity, LOW effort):** L2, A3, I1, T2
2. **Phase 2 — Core Logic (HIGH severity, MEDIUM effort):** L1, L3, L4, I2
3. **Phase 3 — Architecture (HIGH severity, HIGH effort):** A1, W1, T1
4. **Phase 4 — Enhancements (MEDIUM severity):** A2, W2, W3, I3, T3
