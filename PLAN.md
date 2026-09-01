# Plan: Agentic Support System Enhancement for Autopoiesis Engine

## 1. Architecture Overview

The goal is to transform Autopoiesis Engine into a robust **agentic support system** that AI agents use for autonomous task execution. The system should support persistent agent sessions, cross-agent collaboration, intelligent skill discovery, and proactive self-improvement.

### Core Design Principles:
- **Agent-Centric**: Every operation is tied to an agent identity with persistent session state
- **Self-Evolving**: Skills improve via self-healing feedback loops and usage analytics
- **Compositional**: Micro-skills compose into macro workflows via DAG templates
- **Observable**: Full telemetry for debugging, auditing, and optimization

## 2. Architectural Gaps & Solutions

### Gap 1: No Agent Session/Memory System
**Problem**: Skills are stateless; there is no concept of agent identity, session context, or persistent memory.
**Solution**: Add `AgenticSessionManager` — tracks agent sessions, stores persistent key-value memory per agent, and provides context to skills.

### Gap 2: Static Intent Parsing (Keyword-Based)
**Problem**: `LookAheadParser` splits intent on commas/periods and uses fragile keyword matching for skill synthesis.
**Solution**: Add a `PatternIntentParser` that uses NLP-based intent classification to identify action entities (verbs + targets) and map them to skill templates.

### Gap 3: Limited Skill Library
**Problem**: Only 5 core skills exist. Missing HTTP operations, data processing, notifications, etc.
**Solution**: Expand Level 1 Core Base Pack with 12 additional skills: HTTP client, CSV processor, data viz, notification bridge, regex processor, JSON path, YAML processor, environment inspector, system health, network scanner, file watcher, process manager.

### Gap 4: No Agent Communication/Messaging
**Problem**: Agents cannot exchange messages or share data asynchronously.
**Solution**: Add `AgentMessageBus` — lightweight pub/sub for agent-to-agent communication with channel-based subscriptions.

### Gap 5: Basic Self-Healing (No Learning)
**Problem**: Self-healing just appends comments; no pattern analysis or learned fixes.
**Solution**: Add `HealLearningCache` — stores error→fix patterns; future errors check the cache before applying generic patches.

### Gap 6: Missing Observability
**Problem**: Basic trace files only; no metrics aggregation, health checks, or performance analytics.
**Solution**: Add `AgenticObservability` — aggregates execution metrics, computes error rates, skill effectiveness scores, and system health status.

### Gap 7: Broken Tests
**Problem**: Qdrant lockfile collision in test environment; tests don't cover core workflows.
**Solution**: Fix test isolation (unique temp dirs), add 10+ new tests covering all new components.

## 3. Implementation Steps

### Phase 1: Core Infrastructure (Agent Session & Memory)
- [x] Create `src/autopoiesis/core/session.py` — `AgenticSessionManager`
- [x] Create `src/autopoiesis/core/messaging.py` — `AgentMessageBus`
- [x] Create `src/autopoiesis/core/observability.py` — `AgenticObservability`
- [x] Create `src/autopoiesis/core/healing.py` — `HealLearningCache`

### Phase 2: Enhanced Intent Resolution
- [x] Create `src/autopoiesis/core/pattern_parser.py` — `PatternIntentParser`
- [x] Integrate into `LookAheadParser` as fallback strategy

### Phase 3: Expanded Skill Library
- [x] Add 12 new Level 1 core skills in `src/autopoiesis/cli/init.py`
- [x] Update `populate_seed_skills()` to register all new skills

### Phase 4: MCP Server Integration
- [x] Expose new tools via MCP: `agent_session_create`, `agent_memory_get`, `agent_memory_set`, `message_bus_publish`, `message_bus_subscribe`, `observability_metrics`, `heal_suggestion`
- [x] Wire agent session context into `run_intent_handler`

### Phase 5: Self-Healing Enhancement
- [x] Integrate `HealLearningCache` into `heal_skill_activity`
- [x] Add learned pattern suggestions to self-healing workflow

### Phase 6: Testing & Verification
- [x] Fix Qdrant lockfile in tests
- [x] Add tests for all new components
- [x] Run full test suite

### Phase 7: AMF (Agentic Micro-Framework) Implementation
- [x] Create `src/autopoiesis/amf/schema.py` — Core data models (AgentDef, Capability, Dependency, WorkflowDef, AMFMessage)
- [x] Create `src/autopoiesis/amf/registry.py` — AMFRegistry wrapping RegistryManager
- [x] Create `src/autopoiesis/amf/lifecycle.py` — AgentLifecycle wrapping AgentSessionManager
- [x] Create `src/autopoiesis/amf/runtime.py` — AMFRuntime wrapping SandboxExecutor
- [x] Create `src/autopoiesis/amf/bus.py` — AMFBusAdapter wrapping AgentMessageBus
- [x] Create `src/autopoiesis/amf/metrics.py` — AMFMetricsAdapter wrapping AgenticObservability
- [x] Create `src/autopoiesis/amf/healing.py` — AMFHealingAdapter wrapping HealLearningCache
- [x] Create `src/autopoiesis/amf/orchestrator.py` — AMFOrchestrator wrapping AutopoiesisDAGWorkflow
- [x] Create `src/autopoiesis/amf/cli.py` — AMF CLI commands
- [x] Create AMF templates (agent_manifest.yaml, workflow_dag.json)
- [x] Write 47 comprehensive AMF tests
- [x] Wire all AMF CLI commands into main.py (pause, resume, inspect, logs, health, heal)
- [x] Expose all AMF MCP tools (pause, resume, destroy, inspect, logs, health, heal)
- [x] Run full test suite and verify all tests pass

## 4. Success Criteria
- All tests passing (core + agentic + AMF suites)
- MCP `run_intent` works with natural language prompts end-to-end
- Agent sessions, memory, messaging, and observability all functional
- Web dashboard shows new metrics
- Self-healing learns from error patterns
- AMF layer fully implemented with 9 modules and CLI commands
