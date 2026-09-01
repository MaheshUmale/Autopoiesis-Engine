"""Agent Session Manager — tracks persistent agent sessions, memory, and runtime context."""

import json
import uuid
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.core.validation import validate_agent_id, validate_namespace, ValidationError


class AgentSessionMetadata(BaseModel):
    session_id: str
    agent_id: str
    namespace: str
    created_at: str
    last_active_at: str
    total_invocations: int = 0
    tags: List[str] = Field(default_factory=list)


class AgentSessionManager:
    """Manages persistent agent sessions with in-memory key-value store.

    Each session holds:
    - Agent identity and namespace
    - Long-term memory (key-value pairs)
    - Runtime context (current working directory, active namespace, etc.)
    - Invocation history (list of recent tool calls with timestamps)
    """

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self.sessions_dir = self.base_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._active: Dict[str, Dict[str, Any]] = {}
        self._load_active_sessions()

    def _load_active_sessions(self) -> None:
        """Loads session state from disk for crash recovery."""
        if not self.sessions_dir.exists():
            return
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                sid = data.get("session_id")
                if sid:
                    self._active[sid] = data
            except (json.JSONDecodeError, KeyError):
                continue

    def _persist_session(self, session_id: str) -> None:
        """Atomic write of session state to disk."""
        data = self._active.get(session_id)
        if not data:
            return
        target = self.sessions_dir / f"{session_id}.json"
        tmp = self.sessions_dir / f"{session_id}.tmp"
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(target)

    def create_session(
        self,
        agent_id: str,
        namespace: str = "global",
        tags: Optional[List[str]] = None,
    ) -> str:
        """Creates a new agent session and returns the session ID."""
        # Validate inputs (fixes M-4)
        validate_agent_id(agent_id)
        validate_namespace(namespace)

        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        meta = AgentSessionMetadata(
            session_id=session_id,
            agent_id=agent_id,
            namespace=namespace,
            created_at=now,
            last_active_at=now,
            tags=tags or [],
        )
        self._active[session_id] = {
            "metadata": meta.model_dump(),
            "memory": {},
            "context": {
                "agent_id": agent_id,
                "namespace": namespace,
                "cwd": str(PlatformAdapter.sanitize_path(".").resolve()),
            },
            "history": [],
        }
        self._persist_session(session_id)
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a session by ID, returning None if not found."""
        return self._active.get(session_id)

    def get_or_create_session(
        self,
        agent_id: str,
        namespace: str = "global",
        tags: Optional[List[str]] = None,
    ) -> str:
        """Returns an existing active session for the agent, or creates a new one."""
        for sid, data in self._active.items():
            meta = data.get("metadata", {})
            if meta.get("agent_id") == agent_id and meta.get("namespace") == namespace:
                return sid
        return self.create_session(agent_id=agent_id, namespace=namespace, tags=tags)

    def set_memory(self, session_id: str, key: str, value: Any) -> bool:
        """Stores a key-value pair in agent session memory."""
        session = self._active.get(session_id)
        if not session:
            return False
        session["memory"][key] = {
            "value": value,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._persist_session(session_id)
        return True

    def get_memory(self, session_id: str, key: str, default: Any = None) -> Any:
        """Retrieves a value from agent session memory."""
        session = self._active.get(session_id)
        if not session:
            return default
        entry = session["memory"].get(key)
        return entry["value"] if entry else default

    def get_all_memory(self, session_id: str) -> Dict[str, Any]:
        """Returns all memory entries for a session."""
        session = self._active.get(session_id)
        if not session:
            return {}
        return {k: v["value"] for k, v in session["memory"].items()}

    def set_context(self, session_id: str, key: str, value: Any) -> bool:
        """Updates runtime context (cwd, active namespace, etc.)."""
        session = self._active.get(session_id)
        if not session:
            return False
        session["context"][key] = value
        self._persist_session(session_id)
        return True

    def get_context(self, session_id: str, key: str, default: Any = None) -> Any:
        """Reads a context value."""
        session = self._active.get(session_id)
        if not session:
            return default
        return session["context"].get(key, default)

    def append_history(
        self,
        session_id: str,
        tool: str,
        input_payload: Any,
        output: Any,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Records an invocation in the session history."""
        session = self._active.get(session_id)
        if not session:
            return
        session["history"].append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool": tool,
            "input": input_payload,
            "output": output,
            "success": success,
            "error": error,
        })
        # Trim history to last 50 entries
        if len(session["history"]) > 50:
            session["history"] = session["history"][-50:]
        meta = session["metadata"]
        meta["total_invocations"] = meta.get("total_invocations", 0) + 1
        meta["last_active_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._persist_session(session_id)

    def get_recent_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns recent invocation history."""
        session = self._active.get(session_id)
        if not session:
            return []
        return session["history"][-limit:]

    def list_sessions_for_agent(self, agent_id: str) -> List[str]:
        """Returns all session IDs belonging to an agent."""
        return [
            sid
            for sid, data in self._active.items()
            if data.get("metadata", {}).get("agent_id") == agent_id
        ]

    def close_session(self, session_id: str) -> bool:
        """Closes a session, removing it from active memory."""
        if session_id not in self._active:
            return False
        del self._active[session_id]
        try:
            (self.sessions_dir / f"{session_id}.json").unlink(missing_ok=True)
        except Exception:
            pass
        return True