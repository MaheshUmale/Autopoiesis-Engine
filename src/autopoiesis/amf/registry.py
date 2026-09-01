"""AMF Registry — agent catalog, capability index, and dependency graph."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.amf.schema import AgentDef, Capability, Dependency, LifecycleHooks, AMFManifest, WorkflowDef
from autopoiesis.storage.migrations import migrate_amf_registry_db


class AgentRecord(BaseModel):
    """Persisted agent record in AMF registry."""
    agent_id: str
    namespace: str
    version: str
    description: str
    capabilities_json: str
    dependencies_json: str
    metadata_json: str
    lifecycle_hooks_json: str
    manifest_path: Optional[str] = None
    state: str = "created"  # created, starting, running, paused, stopping, stopped, destroyed


class AMFRegistry:
    """Manages AMF agent catalog backed by SQLite.

    Wraps RegistryManager for skill/agent metadata and provides:
    - Agent CRUD operations
    - Capability search index
    - Dependency validation
    """

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_dir / "amf_registry.db"
        migrate_amf_registry_db(self.db_path)

    def register_agent(self, agent_def: AgentDef, manifest_path: Optional[str] = None) -> AgentRecord:
        """Registers an agent definition in the AMF registry."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO amf_agents
                (agent_id, namespace, version, description, capabilities_json,
                 dependencies_json, metadata_json, lifecycle_hooks_json, manifest_path, state, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'created', CURRENT_TIMESTAMP)
            """, (
                agent_def.agent_id,
                agent_def.namespace,
                agent_def.version,
                agent_def.description,
                json.dumps([c.model_dump() for c in agent_def.capabilities]),
                json.dumps([d.model_dump() for d in agent_def.dependencies]),
                json.dumps(agent_def.metadata),
                json.dumps(agent_def.lifecycle_hooks.model_dump()),
                str(manifest_path) if manifest_path else None,
            ))
            conn.commit()

        # Rebuild capability index
        self._rebuild_capability_index(agent_def)

        return self.get_agent(agent_def.agent_id)

    def _rebuild_capability_index(self, agent_def: AgentDef) -> None:
        """Rebuilds capability search index for an agent."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM amf_capability_index WHERE agent_id = ?", (agent_def.agent_id,))
            for cap in agent_def.capabilities:
                cursor.execute(
                    "INSERT INTO amf_capability_index (agent_id, capability_name, skill_id) VALUES (?, ?, ?)",
                    (agent_def.agent_id, cap.name, cap.skill_id),
                )
            conn.commit()

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        """Retrieves an agent by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT agent_id, namespace, version, description, capabilities_json,
                       dependencies_json, metadata_json, lifecycle_hooks_json, manifest_path, state
                FROM amf_agents WHERE agent_id = ?
            """, (agent_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return AgentRecord(
                agent_id=row[0],
                namespace=row[1],
                version=row[2],
                description=row[3],
                capabilities_json=row[4],
                dependencies_json=row[5],
                metadata_json=row[6],
                lifecycle_hooks_json=row[7],
                manifest_path=row[8],
                state=row[9],
            )

    def get_agent_def(self, agent_id: str) -> Optional[AgentDef]:
        """Retrieves full AgentDef for an agent."""
        record = self.get_agent(agent_id)
        if not record:
            return None
        try:
            capabilities = [Capability(**c) for c in json.loads(record.capabilities_json)]
            dependencies = [Dependency(**d) for d in json.loads(record.dependencies_json)]
            metadata = json.loads(record.metadata_json)
            lifecycle_hooks = LifecycleHooks(**json.loads(record.lifecycle_hooks_json))
            return AgentDef(
                agent_id=record.agent_id,
                namespace=record.namespace,
                version=record.version,
                description=record.description,
                capabilities=capabilities,
                dependencies=dependencies,
                metadata=metadata,
                lifecycle_hooks=lifecycle_hooks,
            )
        except Exception:
            return None

    def update_agent_state(self, agent_id: str, state: str) -> bool:
        """Updates agent lifecycle state."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE amf_agents SET state = ?, updated_at = CURRENT_TIMESTAMP WHERE agent_id = ?",
                (state, agent_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_agents(self, namespace: Optional[str] = None, state: Optional[str] = None) -> List[AgentRecord]:
        """Lists agents, optionally filtered by namespace and/or state."""
        query = "SELECT agent_id, namespace, version, description, capabilities_json, dependencies_json, metadata_json, lifecycle_hooks_json, manifest_path, state FROM amf_agents WHERE 1=1"
        params = []
        if namespace:
            query += " AND namespace = ?"
            params.append(namespace)
        if state:
            query += " AND state = ?"
            params.append(state)
        query += " ORDER BY agent_id"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [
                AgentRecord(
                    agent_id=row[0],
                    namespace=row[1],
                    version=row[2],
                    description=row[3],
                    capabilities_json=row[4],
                    dependencies_json=row[5],
                    metadata_json=row[6],
                    lifecycle_hooks_json=row[7],
                    manifest_path=row[8],
                    state=row[9],
                )
                for row in cursor.fetchall()
            ]

    def find_capable_agents(self, capability_name: str) -> List[str]:
        """Finds all agents that declare a specific capability."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT agent_id FROM amf_capability_index WHERE capability_name = ?",
                (capability_name,),
            )
            return [row[0] for row in cursor.fetchall()]

    def resolve_dependencies(self, agent_id: str) -> Dict[str, Any]:
        """Validates that all agent dependencies are satisfiable.

        Returns:
            Dict with 'satisfied' bool, 'missing' list, and 'warnings' list.
        """
        agent_def = self.get_agent_def(agent_id)
        if not agent_def:
            return {"satisfied": False, "missing": ["agent_not_found"], "warnings": []}

        missing = []
        warnings = []

        for dep in agent_def.dependencies:
            if not dep.required:
                continue
            if dep.type == "skill":
                # Check if skill exists in RegistryManager
                try:
                    from autopoiesis.registry.manager import RegistryManager
                    reg = RegistryManager(base_dir=self.base_dir)
                    if not reg.get_skill(dep.name):
                        missing.append(f"skill:{dep.name}")
                except Exception:
                    missing.append(f"skill:{dep.name}")
            elif dep.type == "env":
                import os
                if dep.name not in os.environ:
                    missing.append(f"env:{dep.name}")
            elif dep.type == "service":
                # Service checks would go here (e.g., Redis, Qdrant running)
                warnings.append(f"service:{dep.name} (unchecked)")
            elif dep.type == "file":
                if not Path(dep.name).exists():
                    missing.append(f"file:{dep.name}")

        return {
            "satisfied": len(missing) == 0,
            "missing": missing,
            "warnings": warnings,
        }

    def unregister_agent(self, agent_id: str) -> bool:
        """Removes an agent from the registry."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM amf_capability_index WHERE agent_id = ?", (agent_id,))
            cursor.execute("DELETE FROM amf_agents WHERE agent_id = ?", (agent_id,))
            conn.commit()
            return cursor.rowcount > 0

    def load_from_manifest(self, manifest_path: str | Path) -> AMFManifest:
        """Loads an AMF manifest from YAML or JSON file."""
        path = PlatformAdapter.sanitize_path(manifest_path)
        if not path.exists():
            raise FileNotFoundError(f"AMF manifest not found at {path}")

        content = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            try:
                import yaml
                data = yaml.safe_load(content)
            except ImportError:
                raise ImportError("PyYAML is required for YAML manifests. Install with: pip install pyyaml")
        else:
            data = json.loads(content)

        return AMFManifest(**data)

    def register_workflow(self, workflow_def: WorkflowDef, manifest_path: Optional[str] = None) -> bool:
        """Registers a workflow definition in the AMF registry."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO amf_workflows
                (workflow_id, namespace, description, dag_json, parameters_json, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                workflow_def.workflow_id,
                workflow_def.namespace,
                workflow_def.description,
                json.dumps(workflow_def.model_dump()),
                json.dumps(workflow_def.parameters),
            ))
            conn.commit()
        return True

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDef]:
        """Retrieves a workflow definition by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT workflow_id, namespace, description, dag_json, parameters_json
                FROM amf_workflows WHERE workflow_id = ?
            """, (workflow_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = json.loads(row[3])
            return WorkflowDef(**data)

    def list_workflows(self, namespace: Optional[str] = None) -> List[WorkflowDef]:
        """Lists all registered workflows, optionally filtered by namespace."""
        query = "SELECT dag_json FROM amf_workflows WHERE 1=1"
        params = []
        if namespace:
            query += " AND namespace = ?"
            params.append(namespace)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [WorkflowDef(**json.loads(row[0])) for row in cursor.fetchall()]

    def unregister_workflow(self, workflow_id: str) -> bool:
        """Removes a workflow from the registry."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM amf_workflows WHERE workflow_id = ?", (workflow_id,))
            conn.commit()
            return cursor.rowcount > 0

    def register_manifest(self, manifest_path: str | Path) -> List[AgentRecord]:
        """Registers all agents from a manifest file."""
        manifest = self.load_from_manifest(manifest_path)
        records = []
        for agent_def in manifest.agents:
            record = self.register_agent(agent_def, manifest_path=str(manifest_path))
            records.append(record)
        return records
