"""AMF Core Data Models — declarative schemas for agents, capabilities, workflows, and messages."""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RetryPolicy(BaseModel):
    """Retry configuration for capability invocations."""
    max_attempts: int = 3
    initial_interval_sec: float = 1.0
    max_interval_sec: float = 5.0
    backoff_multiplier: float = 2.0


class Capability(BaseModel):
    """Declares what an agent can do, mapping to a registered skill."""
    name: str                        # e.g. "fetch_ohlcv"
    skill_id: str                    # maps to RegistryManager skill ID
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    timeout_sec: float = 30.0
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class Dependency(BaseModel):
    """External requirement for an agent to function."""
    type: str                        # "skill", "env", "service", "file"
    name: str                        # e.g. "UPSTOX_API_KEY", "core_http_client"
    required: bool = True
    version_constraint: str = "*"


class LifecycleHooks(BaseModel):
    """Lifecycle event handlers for an agent."""
    on_start: List[str] = Field(default_factory=list)         # skill_ids to run on start
    on_stop: List[str] = Field(default_factory=list)          # skill_ids to run on stop
    on_error: str = "heal_and_retry"                          # "heal_and_retry", "fail_fast", "continue"


class AgentDef(BaseModel):
    """Formal agent definition in AMF manifest."""
    agent_id: str
    namespace: str = "global"
    version: str = "1.0.0"
    description: str = ""
    capabilities: List[Capability] = Field(default_factory=list)
    dependencies: List[Dependency] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    lifecycle_hooks: LifecycleHooks = Field(default_factory=LifecycleHooks)


class WorkflowNode(BaseModel):
    """Node in an AMF workflow DAG."""
    node_id: str
    agent_id: str
    capability: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    timeout_sec: float = 60.0


class WorkflowEdge(BaseModel):
    """Directed edge between workflow nodes."""
    source: str
    target: str
    condition: Optional[str] = None    # optional condition expression


class WorkflowDef(BaseModel):
    """Composite workflow definition."""
    workflow_id: str
    namespace: str = "global"
    description: str = ""
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AMFManifest(BaseModel):
    """Top-level manifest declaring agents and workflows."""
    manifest_version: str = "1.0"
    project: str
    agents: List[AgentDef] = Field(default_factory=list)
    workflows: List[WorkflowDef] = Field(default_factory=list)


class AMFMessage(BaseModel):
    """Standardized message envelope for AMF bus."""
    message_id: str
    sender_agent: str
    target_agent: Optional[str] = None
    target_channel: Optional[str] = None
    capability: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
