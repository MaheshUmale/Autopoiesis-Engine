# AMF (Agentic Micro-Framework) Implementation Plan

## 1. AMF Vision

AMF is a formal lightweight framework layer inside Autopoiesis Engine that standardizes:
- **Agent Definition Schema** — declarative YAML/JSON specs for agent capabilities, inputs, outputs, dependencies
- **Agent Lifecycle** — create, start, stop, pause, resume, destroy with state persistence
- **Agent Composition** — orchestrate multiple agents into composite workflows (DAGs)
- **Agent Communication** — standardized pub/sub and request/reply via `AgentMessageBus`
- **Agent Observability** — unified metrics, tracing, health checks via `AgenticObservability`
- **Agent Healing** — learned self-healing patterns via `HealLearningCache`

AMF does NOT replace existing components. It **wraps and formalizes** them:
- `RegistryManager` → AMF Registry (skill/agent catalog)
- `SandboxExecutor` → AMF Runtime (isolated execution)
- `AgentSessionManager` → AMF Session (agent identity + memory)
- `AgentMessageBus` → AMF Bus (inter-agent messaging)
- `AgenticObservability` → AMF Metrics (telemetry)
- `AutopoiesisDAGWorkflow` → AMF Orchestrator (workflow execution)

## 2. Directory Structure

```
src/autopoiesis/amf/
├── __init__.py
├── schema.py            # Pydantic models: AgentDef, Capability, Dependency, AMFManifest
├── registry.py          # AMFRegistry: agent catalog, capability index, dependency graph
├── lifecycle.py         # AgentLifecycle: create/start/stop/pause/resume/destroy
├── runtime.py           # AMFRuntime: wraps SandboxExecutor with capability routing
├── bus.py               # AMFBusAdapter: standardized message envelopes
├── metrics.py           # AMFMetricsAdapter: unified telemetry wrapper
├── healing.py           # AMFHealingAdapter: self-healing pattern integration
├── orchestrator.py      # AMFOrchestrator: DAG-based multi-agent composition
├── cli.py               # AMF CLI commands (agent list, run, inspect, logs)
└── templates/
    ├── agent_manifest.yaml  # Template for agent definitions
    └── workflow_dag.json    # Template for composite workflows
```

## 3. Core Data Models (`schema.py`)

### AgentDef
```python
class AgentDef(BaseModel):
    agent_id: str                    # unique ID, e.g. "market_data_fetcher"
    namespace: str = "global"
    version: str = "1.0.0"
    description: str = ""
    capabilities: List[Capability]  # what the agent can do
    dependencies: List[Dependency]  # required skills, env vars, services
    metadata: Dict[str, Any] = {}    # tags, owner, priority
    lifecycle_hooks: LifecycleHooks = Field(default_factory=LifecycleHooks)
```

### Capability
```python
class Capability(BaseModel):
    name: str                        # e.g. "fetch_ohlcv"
    skill_id: str                    # maps to RegistryManager skill
    inputs: Dict[str, Any] = {}
    outputs: Dict[str, Any] = {}
    timeout_sec: float = 30.0
    retry_policy: RetryPolicy = Field(default_factory=lambda: RetryPolicy(max_attempts=3))
```

### Dependency
```python
class Dependency(BaseModel):
    type: str                        # "skill", "env", "service", "file"
    name: str                        # e.g. "UPSTOX_API_KEY", "core_http_client"
    required: bool = True
    version_constraint: str = "*"
```

### AMFManifest
```python
class AMFManifest(BaseModel):
    manifest_version: str = "1.0"
    project: str
    agents: List[AgentDef]
    workflows: List[WorkflowDef] = []
```

### LifecycleHooks
```python
class LifecycleHooks(BaseModel):
    on_start: List[str] = []         # skill_ids to run on agent start
    on_stop: List[str] = []          # skill_ids to run on agent stop
    on_error: str = "heal_and_retry" # "heal_and_retry", "fail_fast", "continue"
```

## 4. Component Design

### 4.1 AMFRegistry (`registry.py`)
- Wraps `RegistryManager`
- Indexes agents by `namespace`, `capability.name`, `dependency.name`
- Supports capability search: "find all agents that can fetch OHLCV"
- Validates dependency graphs at registration time
- Methods:
  - `register_agent(manifest_path)` → loads YAML/JSON, validates, stores in SQLite
  - `get_agent(agent_id)` → returns `AgentDef`
  - `find_capable_agents(capability_name)` → returns list of agent IDs
  - `resolve_dependencies(agent_id)` → validates all deps are satisfiable
  - `list_agents(namespace)` → filtered listing

### 4.2 AgentLifecycle (`lifecycle.py`)
- Wraps `AgentSessionManager`
- State machine: `created → starting → running → paused → stopping → stopped → destroyed`
- Persistent state in `.autopoiesis/agents/{agent_id}/state.json`
- Methods:
  - `create_agent(agent_id, namespace)` → creates session, returns agent_id
  - `start_agent(agent_id)` → runs `on_start` hooks, transitions to running
  - `stop_agent(agent_id)` → runs `on_stop` hooks, transitions to stopped
  - `pause_agent(agent_id)` → freezes state
  - `resume_agent(agent_id)` → unfreezes state
  - `destroy_agent(agent_id)` → removes session and state
  - `get_agent_status(agent_id)` → returns current state + health

### 4.3 AMFRuntime (`runtime.py`)
- Wraps `SandboxExecutor`
- Routes capability invocations to registered skills
- Injects agent context (`_agent_id`, `_session_id`, `_memory`, `_capability`)
- Applies timeout and retry policies from `Capability`
- Methods:
  - `invoke_capability(agent_id, capability_name, inputs)` → SandboxResult
  - `invoke_skill(skill_id, inputs, context)` → SandboxResult
  - `health_check(agent_id)` → runs all `on_start` hooks, returns health status

### 4.4 AMFBusAdapter (`bus.py`)
- Wraps `AgentMessageBus`
- Standardized message envelope:
  ```python
  class AMFMessage(BaseModel):
      message_id: str
      sender_agent: str
      target_agent: str | None = None
      target_channel: str | None = None
      capability: str | None = None
      payload: Dict[str, Any]
      correlation_id: str | None = None
      reply_to: str | None = None
      timestamp: str
  ```
- Methods:
  - `send(agent_from, agent_to, capability, payload)` → point-to-point
  - `broadcast(channel, sender, payload)` → channel-based
  - `request_reply(sender, target, capability, payload, timeout)` → synchronous-style

### 4.5 AMFMetricsAdapter (`metrics.py`)
- Wraps `AgenticObservability`
- Adds agent-level aggregation
- Methods:
  - `record_capability_invocation(agent_id, capability, result)` → records metric
  - `get_agent_health(agent_id)` → returns success_rate, avg_latency, error_distribution
  - `get_system_health()` → aggregates all agents

### 4.6 AMFHealingAdapter (`healing.py`)
- Wraps `HealLearningCache`
- Agent-aware healing strategies
- Methods:
  - `heal_capability_failure(agent_id, capability, error)` → suggests/applies fix
  - `record_healing_outcome(agent_id, pattern_id, success)` → updates cache

### 4.7 AMFOrchestrator (`orchestrator.py`)
- Wraps `AutopoiesisDAGWorkflow`
- Accepts `WorkflowDef` from manifest
- Resolves agent IDs to capability invocations
- Manages inter-agent data flow via AMFBusAdapter
- Methods:
  - `run_workflow(workflow_id, parameters)` → executes DAG
  - `get_workflow_status(workflow_id)` → returns execution state

### 4.8 AMF CLI (`cli.py`)
- New subcommands under `autopoiesis amf ...`:
  - `autopoiesis amf init <path>` → scaffold AMF manifest
  - `autopoiesis amf register <manifest>` → register agents
  - `autopoiesis amf list` → list all registered agents
  - `autopoiesis amf start <agent_id>` → start agent
  - `autopoiesis amf stop <agent_id>` → stop agent
  - `autopoiesis amf run <agent_id> --capability <cap> --input <json>` → invoke
  - `autopoiesis amf workflow run <workflow_id>` → run composite workflow
  - `autopoiesis amf inspect <agent_id>` → show agent definition + status
  - `autopoiesis amf logs <agent_id>` → show recent execution logs

## 5. MCP Integration

New MCP tools exposed via `create_mcp_server`:
- `amf_register_agent` — register from manifest
- `amf_list_agents` — list by namespace/capability
- `amf_start_agent` / `amf_stop_agent` / `amf_pause_agent` / `amf_resume_agent`
- `amf_invoke_capability` — invoke with auto-context injection
- `amf_run_workflow` — execute composite DAG
- `amf_agent_health` — health check + metrics
- `amf_heal_agent` — trigger self-healing for failed capability

## 6. Implementation Phases

### Phase 1: Foundation (schema + registry + lifecycle)
- [x] Create `src/autopoiesis/amf/__init__.py`
- [x] Implement `schema.py` with all Pydantic models
- [x] Implement `registry.py` wrapping `RegistryManager`
- [x] Implement `lifecycle.py` wrapping `AgentSessionManager`
- [x] Add tests for schema validation and registry operations

### Phase 2: Runtime + Bus + Metrics
- [x] Implement `runtime.py` wrapping `SandboxExecutor`
- [x] Implement `bus.py` wrapping `AgentMessageBus`
- [x] Implement `metrics.py` wrapping `AgenticObservability`
- [x] Add tests for runtime invocation, bus messaging, metrics recording

### Phase 3: Healing + Orchestration
- [x] Implement `healing.py` wrapping `HealLearningCache`
- [x] Implement `orchestrator.py` wrapping `AutopoiesisDAGWorkflow`
- [x] Add tests for healing suggestions and workflow execution

### Phase 4: CLI + MCP Exposure
- [x] Implement `cli.py` with all AMF subcommands
- [x] Wire AMF tools into `create_mcp_server`
- [x] Add CLI integration tests

### Phase 5: Templates + Documentation
- [x] Create `templates/agent_manifest.yaml`
- [x] Create `templates/workflow_dag.json`
- [x] Update `PLAN.md` with AMF completion status
- [x] Run full test suite and verify all tests pass

## 7. Success Criteria
- [x] All AMF components implemented and unit-tested (50+ new tests)
- [x] `autopoiesis amf` CLI fully functional
- [x] AMF tools exposed via MCP (stdio + HTTP)
- [x] End-to-end: manifest → register → start → invoke → observe → heal → stop → destroy
- [x] Composite workflow execution via AMFOrchestrator
- [x] Full backward compatibility: existing Autopoiesis Engine APIs unchanged
