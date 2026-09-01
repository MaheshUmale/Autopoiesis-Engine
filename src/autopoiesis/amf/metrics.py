"""AMF Metrics Adapter — unified telemetry wrapper around AgenticObservability."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.core.observability import AgenticObservability
from autopoiesis.amf.registry import AMFRegistry


class AgentHealth(BaseModel):
    """Health snapshot for a single agent."""
    agent_id: str
    total_executions: int = 0
    success_rate: float = 0.0
    avg_execution_time: float = 0.0
    error_distribution: Dict[str, int] = {}
    top_slow_capabilities: List[Dict[str, Any]] = []


class AMFMetricsAdapter:
    """Wraps AgenticObservability with AMF agent-level aggregation.

    Tracks:
    - Per-agent capability invocations
    - System-wide health aggregation
    - Error distributions by agent and capability
    """

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self._observability = AgenticObservability(base_dir=base_dir)
        self._registry = AMFRegistry(base_dir=base_dir)
        self._agent_skill_index: Dict[str, List[str]] = {}
        self._load_agent_index()

    def _load_agent_index(self) -> None:
        """Builds index of agent_id -> [skill_ids] from registry."""
        for record in self._registry.list_agents():
            agent_def = self._registry.get_agent_def(record.agent_id)
            if agent_def:
                self._agent_skill_index[record.agent_id] = [c.skill_id for c in agent_def.capabilities]

    def record_capability_invocation(
        self,
        agent_id: str,
        capability: str,
        skill_id: str,
        success: bool,
        execution_time_sec: float,
        error_type: Optional[str] = None,
        payload_size_bytes: int = 0,
    ) -> None:
        """Records a capability invocation metric tagged with agent and capability."""
        # Tag skill_id with agent context for filtering
        tagged_skill_id = f"{agent_id}.{capability}"
        self._observability.record_execution(
            skill_id=tagged_skill_id,
            execution_time_sec=execution_time_sec,
            success=success,
            error_type=error_type,
            payload_size_bytes=payload_size_bytes,
            payload_storage="inline",
        )

    def record_skill_invocation(
        self,
        agent_id: str,
        skill_id: str,
        success: bool,
        execution_time_sec: float,
        error_type: Optional[str] = None,
        payload_size_bytes: int = 0,
    ) -> None:
        """Records a direct skill invocation metric."""
        tagged_skill_id = f"{agent_id}.skill.{skill_id}"
        self._observability.record_execution(
            skill_id=tagged_skill_id,
            execution_time_sec=execution_time_sec,
            success=success,
            error_type=error_type,
            payload_size_bytes=payload_size_bytes,
            payload_storage="inline",
        )

    def get_agent_health(self, agent_id: str) -> AgentHealth:
        """Returns health metrics for a specific agent."""
        # Find all skill_ids associated with this agent
        agent_skills = self._agent_skill_index.get(agent_id, [])
        tagged_skill_ids = [f"{agent_id}.{cap}" for cap in agent_skills] + [f"{agent_id}.skill.{sid}" for sid in agent_skills]

        # Filter metrics for this agent's tagged skills
        agent_metrics = []
        for metric in self._observability._metrics:
            if metric.skill_id in tagged_skill_ids or metric.skill_id.startswith(f"{agent_id}."):
                agent_metrics.append(metric)

        if not agent_metrics:
            return AgentHealth(agent_id=agent_id)

        succeeded = sum(1 for m in agent_metrics if m.success)
        total = len(agent_metrics)
        avg_time = sum(m.execution_time_sec for m in agent_metrics) / total if total > 0 else 0.0

        # Error distribution
        error_dist: Dict[str, int] = {}
        for m in agent_metrics:
            if not m.success and m.error_type:
                error_dist[m.error_type] = error_dist.get(m.error_type, 0) + 1

        # Top slow capabilities
        cap_times: Dict[str, List[float]] = {}
        for m in agent_metrics:
            if m.success:
                cap_name = m.skill_id.replace(f"{agent_id}.", "").replace("skill.", "")
                cap_times.setdefault(cap_name, []).append(m.execution_time_sec)

        slow_caps = []
        for cap, times in cap_times.items():
            avg = sum(times) / len(times)
            slow_caps.append({"capability": cap, "avg_time": round(avg, 3), "executions": len(times)})
        slow_caps.sort(key=lambda x: x["avg_time"], reverse=True)

        return AgentHealth(
            agent_id=agent_id,
            total_executions=total,
            success_rate=round(succeeded / total * 100, 2) if total > 0 else 0.0,
            avg_execution_time=round(avg_time, 3),
            error_distribution=error_dist,
            top_slow_capabilities=slow_caps[:5],
        )

    def get_system_health(self) -> Dict[str, Any]:
        """Returns aggregated system-wide health metrics."""
        total = self._observability.total_executions
        success_rate = self._observability.success_rate
        avg_time = self._observability.avg_execution_time

        # Per-agent health
        agent_health = {}
        for agent_id in self._agent_skill_index:
            health = self.get_agent_health(agent_id)
            agent_health[agent_id] = health.model_dump()

        # Derive unique agent IDs from tagged skill_ids in metrics
        agent_ids = set()
        for m in self._observability._metrics:
            parts = m.skill_id.split(".", 1)
            agent_ids.add(parts[0] if parts else m.skill_id)

        return {
            "total_executions": total,
            "success_rate_pct": success_rate,
            "avg_execution_time_sec": avg_time,
            "agent_count": len(agent_ids),
            "agents": agent_health,
            "top_slow_skills": self.get_top_slow_skills(10),
            "error_summary": self._observability.get_error_summary(),
        }

    def get_error_summary(self) -> Dict[str, Any]:
        """Returns error summary for all agents."""
        return self._observability.get_error_summary()

    def get_top_slow_skills(self, n: int = 10) -> List[Dict[str, Any]]:
        """Returns the N slowest capabilities across all agents."""
        raw = self._observability.get_top_slow_skills(n)
        result = []
        for entry in raw:
            skill_id = entry["skill_id"]
            # Extract capability name from tagged format: "agent_id.capability" or "agent_id.skill.skill_id"
            parts = skill_id.split(".", 1)
            if len(parts) > 1 and not parts[1].startswith("skill."):
                capability = parts[1]
            elif len(parts) > 1:
                capability = parts[1][6:]  # strip "skill." prefix
            else:
                capability = skill_id
            result.append({
                "capability": capability,
                "skill_id": skill_id,
                "avg_time": entry["avg_time"],
                "executions": entry["executions"],
            })
        return result
