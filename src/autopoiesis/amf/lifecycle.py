"""AMF Agent Lifecycle — state machine for agent create/start/stop/pause/resume/destroy.

Fixes:
- N-1: EventEmitter integration for agent lifecycle events
- A2: Cross-database consistency with registry reconciliation
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.core.session import AgentSessionManager
from autopoiesis.core.events import EventEmitter, Event, SystemEvents
from autopoiesis.amf.registry import AMFRegistry
from autopoiesis.amf.schema import AgentDef, LifecycleHooks

logger = logging.getLogger("autopoiesis.amf.lifecycle")


class AgentState(BaseModel):
    """Persisted agent state."""
    agent_id: str
    state: str = "created"  # created, starting, running, paused, stopping, stopped, destroyed
    session_id: Optional[str] = None
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = {}


class AgentLifecycle:
    """Manages AMF agent lifecycle state machine backed by AgentSessionManager.

    States: created → starting → running → paused → stopping → stopped → destroyed
    """

    VALID_TRANSITIONS = {
        "created": ["starting", "destroyed"],
        "starting": ["running", "destroyed"],
        "running": ["paused", "stopping", "destroyed"],
        "paused": ["running", "stopping", "destroyed"],
        "stopping": ["stopped", "destroyed"],
        "stopped": ["starting", "destroyed"],
        "destroyed": [],
    }

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self.agents_dir = self.base_dir / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self._session_mgr = AgentSessionManager(base_dir=base_dir)
        self._registry = AMFRegistry(base_dir=base_dir)
        # EventEmitter integration (N-1)
        self._events = EventEmitter(base_dir=base_dir)
        self._load_states()

    def _load_states(self) -> None:
        """Loads persisted agent states from disk."""
        self._states: Dict[str, AgentState] = {}
        if not self.agents_dir.exists():
            return
        for state_file in self.agents_dir.rglob("state.json"):
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                agent_id = data.get("agent_id")
                if agent_id:
                    self._states[agent_id] = AgentState(**data)
            except Exception:
                continue

    def _persist_state(self, agent_state: AgentState) -> None:
        """Persists agent state to disk atomically."""
        agent_dir = self.agents_dir / agent_state.agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        target = agent_dir / "state.json"
        tmp = agent_dir / "state.tmp"
        tmp.write_text(agent_state.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(target)
        self._states[agent_state.agent_id] = agent_state

    def _get_state(self, agent_id: str) -> Optional[AgentState]:
        """Gets current agent state."""
        return self._states.get(agent_id)

    def _transition(self, agent_id: str, new_state: str) -> bool:
        """Validates and performs state transition."""
        current = self._get_state(agent_id)
        if not current:
            return False
        allowed = self.VALID_TRANSITIONS.get(current.state, [])
        if new_state not in allowed:
            raise ValueError(
                f"Invalid state transition for agent '{agent_id}': {current.state} -> {new_state}. "
                f"Allowed: {allowed}"
            )
        current.state = new_state
        current.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._persist_state(current)
        return True

    def create_agent(self, agent_id: str, namespace: str = "global", metadata: Optional[Dict[str, Any]] = None) -> AgentState:
        """Creates a new agent session and initializes lifecycle state.

        Fixes A2: Cross-database consistency - session and registry entries
        are created together with rollback on failure.
        """
        if agent_id in self._states:
            raise ValueError(f"Agent '{agent_id}' already exists.")

        session_id = None
        try:
            # Create session via AgentSessionManager
            session_id = self._session_mgr.create_session(
                agent_id=agent_id,
                namespace=namespace,
                tags=[namespace, "amf_agent"],
            )

            now = time.strftime("%Y-%m-%dT%H:%M:%S")
            state = AgentState(
                agent_id=agent_id,
                state="created",
                session_id=session_id,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
            )
            self._persist_state(state)

            # Ensure registry entry exists
            agent_def = self._registry.get_agent_def(agent_id)
            if not agent_def:
                # Create minimal registry entry
                from autopoiesis.amf.schema import AgentDef as AD, Capability, Dependency, LifecycleHooks
                minimal_def = AD(
                    agent_id=agent_id,
                    namespace=namespace,
                    description=metadata.get("description", "") if metadata else "",
                    metadata=metadata or {},
                )
                self._registry.register_agent(minimal_def)

            # Emit agent created event (N-1)
            self._events.emit(Event(
                event_type=SystemEvents.AGENT_CREATED,
                source="AgentLifecycle",
                payload={"agent_id": agent_id, "namespace": namespace},
            ))

            return state

        except Exception as e:
            # Rollback session on failure (fixes A2)
            if session_id:
                self._session_mgr.close_session(session_id)
            raise

    def start_agent(self, agent_id: str) -> AgentState:
        """Starts an agent: runs on_start hooks, transitions to running."""
        state = self._get_state(agent_id)
        if not state:
            raise ValueError(f"Agent '{agent_id}' not found. Create it first.")

        self._transition(agent_id, "starting")

        # Run on_start hooks if agent has them
        agent_def = self._registry.get_agent_def(agent_id)
        if agent_def and agent_def.lifecycle_hooks.on_start:
            for skill_id in agent_def.lifecycle_hooks.on_start:
                # Execute start hooks in background (fire-and-forget with logging)
                try:
                    from autopoiesis.sandbox.executor import SandboxExecutor
                    from autopoiesis.registry.manager import RegistryManager
                    reg = RegistryManager(base_dir=self.base_dir)
                    skill = reg.get_skill(skill_id)
                    if skill and skill.file_path:
                        code = Path(skill.file_path).read_text(encoding="utf-8")
                        payload = {
                            "_agent_id": agent_id,
                            "_session_id": state.session_id,
                            "_cwd": str(Path.cwd()),
                        }
                        SandboxExecutor.execute_skill_code(code, payload)
                except Exception as e:
                    # Log but don't fail startup
                    logger.warning(f"Start hook '{skill_id}' failed for agent '{agent_id}': {e}")

        self._transition(agent_id, "running")

        # Emit agent started event (N-1)
        self._events.emit(Event(
            event_type=SystemEvents.AGENT_STARTED,
            source="AgentLifecycle",
            payload={"agent_id": agent_id},
        ))

        return self._get_state(agent_id)

    def stop_agent(self, agent_id: str) -> AgentState:
        """Stops an agent: runs on_stop hooks, transitions to stopped."""
        state = self._get_state(agent_id)
        if not state:
            raise ValueError(f"Agent '{agent_id}' not found.")

        self._transition(agent_id, "stopping")

        # Run on_stop hooks
        agent_def = self._registry.get_agent_def(agent_id)
        if agent_def and agent_def.lifecycle_hooks.on_stop:
            for skill_id in agent_def.lifecycle_hooks.on_stop:
                try:
                    from autopoiesis.sandbox.executor import SandboxExecutor
                    from autopoiesis.registry.manager import RegistryManager
                    reg = RegistryManager(base_dir=self.base_dir)
                    skill = reg.get_skill(skill_id)
                    if skill and skill.file_path:
                        code = Path(skill.file_path).read_text(encoding="utf-8")
                        payload = {
                            "_agent_id": agent_id,
                            "_session_id": state.session_id,
                            "_cwd": str(Path.cwd()),
                        }
                        SandboxExecutor.execute_skill_code(code, payload)
                except Exception as e:
                    logger.warning(f"Stop hook '{skill_id}' failed for agent '{agent_id}': {e}")

        self._transition(agent_id, "stopped")

        # Emit agent stopped event (N-1)
        self._events.emit(Event(
            event_type=SystemEvents.AGENT_STOPPED,
            source="AgentLifecycle",
            payload={"agent_id": agent_id},
        ))

        return self._get_state(agent_id)

    def pause_agent(self, agent_id: str) -> AgentState:
        """Pauses a running agent."""
        state = self._get_state(agent_id)
        if not state:
            raise ValueError(f"Agent '{agent_id}' not found.")
        self._transition(agent_id, "paused")
        return self._get_state(agent_id)

    def resume_agent(self, agent_id: str) -> AgentState:
        """Resumes a paused agent."""
        state = self._get_state(agent_id)
        if not state:
            raise ValueError(f"Agent '{agent_id}' not found.")
        self._transition(agent_id, "running")
        return self._get_state(agent_id)

    def destroy_agent(self, agent_id: str) -> bool:
        """Destroys an agent: removes session and state."""
        state = self._get_state(agent_id)
        if not state:
            return False

        # Close session
        if state.session_id:
            self._session_mgr.close_session(state.session_id)

        # Remove state file
        agent_dir = self.agents_dir / agent_id
        if agent_dir.exists():
            for f in agent_dir.glob("*"):
                f.unlink(missing_ok=True)
            agent_dir.rmdir()

        # Remove from local state
        del self._states[agent_id]

        # Update registry
        self._registry.update_agent_state(agent_id, "destroyed")

        # Emit agent destroyed event (N-1)
        self._events.emit(Event(
            event_type=SystemEvents.AGENT_DESTROYED,
            source="AgentLifecycle",
            payload={"agent_id": agent_id},
        ))

        return True

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Returns current agent status including health info."""
        state = self._get_state(agent_id)
        if not state:
            return None

        agent_def = self._registry.get_agent_def(agent_id)
        session = self._session_mgr.get_session(state.session_id) if state.session_id else None

        result = {
            "agent_id": agent_id,
            "state": state.state,
            "session_id": state.session_id,
            "namespace": agent_def.namespace if agent_def else "global",
            "version": agent_def.version if agent_def else "1.0.0",
            "description": agent_def.description if agent_def else "",
            "capabilities": [c.name for c in agent_def.capabilities] if agent_def else [],
            "dependencies": [d.name for d in agent_def.dependencies] if agent_def else [],
            "created_at": state.created_at,
            "updated_at": state.updated_at,
            "metadata": state.metadata,
            "memory_keys": list(session.get("memory", {}).keys()) if session else [],
        }

        # Add dependency resolution
        dep_check = self._registry.resolve_dependencies(agent_id)
        result["dependencies_satisfied"] = dep_check["satisfied"]
        result["missing_dependencies"] = dep_check["missing"]
        result["dependency_warnings"] = dep_check["warnings"]

        return result

    def list_agents(self, namespace: Optional[str] = None, state: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all agents with their current status."""
        records = self._registry.list_agents(namespace=namespace, state=state)
        result = []
        for record in records:
            status = self.get_agent_status(record.agent_id)
            if status:
                result.append(status)
        return result

    def reconcile_state(self) -> Dict[str, Any]:
        """Reconciles state between session manager and AMF registry (fixes A2).
        
        Detects and reports inconsistencies:
        - Agents in registry but not in session manager
        - Agents in session manager but not in registry
        - State mismatches between the two stores
        
        Returns:
            Dict with reconciliation results
        """
        issues = []
        fixed = []

        # Get all agents from registry
        registry_agents = self._registry.list_agents()
        registry_ids = {a.agent_id for a in registry_agents}

        # Get all sessions from session manager
        session_ids = set()
        session_agent_map = {}
        for sid, data in self._session_mgr._active.items():
            meta = data.get("metadata", {})
            aid = meta.get("agent_id")
            if aid:
                session_ids.add(aid)
                session_agent_map[aid] = sid

        # Check for agents in registry but not in sessions
        for agent_id in registry_ids - session_ids:
            issues.append({
                "type": "missing_session",
                "agent_id": agent_id,
                "message": f"Agent '{agent_id}' exists in registry but has no session",
            })
            # Fix: Create missing session
            try:
                agent_def = self._registry.get_agent_def(agent_id)
                namespace = agent_def.namespace if agent_def else "global"
                self._session_mgr.create_session(
                    agent_id=agent_id,
                    namespace=namespace,
                    tags=[namespace, "amf_agent", "reconciled"],
                )
                fixed.append(agent_id)
            except Exception as e:
                logger.error(f"Failed to create session for '{agent_id}': {e}")

        # Check for agents in sessions but not in registry
        for agent_id in session_ids - registry_ids:
            issues.append({
                "type": "missing_registry_entry",
                "agent_id": agent_id,
                "message": f"Agent '{agent_id}' has a session but no registry entry",
            })
            # Fix: Create minimal registry entry
            try:
                from autopoiesis.amf.schema import AgentDef as AD
                session_data = self._session_mgr.get_session(session_agent_map[agent_id])
                namespace = "global"
                if session_data:
                    namespace = session_data.get("metadata", {}).get("namespace", "global")
                minimal_def = AD(
                    agent_id=agent_id,
                    namespace=namespace,
                    description="Auto-created by reconciliation",
                )
                self._registry.register_agent(minimal_def)
                fixed.append(agent_id)
            except Exception as e:
                logger.error(f"Failed to create registry entry for '{agent_id}': {e}")

        # Check for state mismatches
        for agent_id in registry_ids & session_ids:
            state = self._get_state(agent_id)
            registry_record = self._registry.get_agent(agent_id)
            if state and registry_record:
                if state.state != registry_record.state:
                    issues.append({
                        "type": "state_mismatch",
                        "agent_id": agent_id,
                        "message": f"State mismatch for '{agent_id}': lifecycle={state.state}, registry={registry_record.state}",
                    })
                    # Fix: Sync registry state to match lifecycle state
                    self._registry.update_agent_state(agent_id, state.state)
                    fixed.append(agent_id)

        result = {
            "checked": len(registry_ids | session_ids),
            "issues_found": len(issues),
            "issues": issues,
            "fixed": fixed,
            "status": "healthy" if not issues else "repaired" if fixed else "needs_attention",
        }

        if issues:
            logger.warning(f"Reconciliation found {len(issues)} issues, fixed {len(fixed)}")

        return result
