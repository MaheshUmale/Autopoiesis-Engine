import json
import logging
import sqlite3
import hashlib
import ast
import atexit
import os
import time
from pathlib import Path
from typing import Any, Optional, Dict, List
from pydantic import BaseModel, Field

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from qdrant_client.common.client_exceptions import QdrantException

from autopoiesis.core.ast import get_normalized_ast_hash
from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.sandbox.executor import SandboxExecutor
from autopoiesis.storage.migrations import migrate_autopoiesis_db
from autopoiesis.core.validation import validate_skill_id, validate_namespace, ValidationError


def _cleanup_qdrant_instances():
    """Explicitly closes all active QdrantClient instances prior to interpreter shutdown."""
    try:
        if hasattr(RegistryManager, "_qdrant_instances"):
            for client in list(RegistryManager._qdrant_instances.values()):
                try:
                    client.close()
                except Exception:
                    pass
            RegistryManager._qdrant_instances.clear()
    except Exception:
        pass


atexit.register(_cleanup_qdrant_instances)

# Qdrant mode configuration
_QDRANT_MODE = "local"  # local|remote (use env var QDRANT_MODE)
_QDRANT_URL = "http://localhost:6333"  # used for remote mode
_QDRANT_HOST = "localhost"  # used for remote mode
_QDRANT_PORT = 6333  # used for remote mode

# Embedding configuration (fixes L-3)
EMBEDDING_VECTOR_SIZE = 384  # Dimensionality of skill embeddings
EMBEDDING_TOKEN_SIZE = 3  # Character n-gram size for tokenization


class SkillMetadata(BaseModel):
    id: str
    namespace: str
    scope_level: str  # "core" or "variant"
    description: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    ast_hash: str
    created_at: Optional[str] = None
    file_path: Optional[str] = None


class DAGTemplate(BaseModel):
    template_id: str
    namespace: str
    parameters: Dict[str, Any]
    dag: Dict[str, Any]
    description: Optional[str] = ""


class RegistryManager:
    """Manages 3-Tier Registry using SQLite for relational metadata and Qdrant for vector search.

    If Qdrant is unavailable, falls back to SQLite-only mode with warning (fixes M-3).
    """

    _qdrant_instances: Dict[str, QdrantClient] = {}
    _qdrant_available: Dict[str, bool] = {}  # Track Qdrant availability per instance

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.base_dir / "autopoiesis.db"
        self.qdrant_dir = self.base_dir / "qdrant"
        self.qdrant_dir.mkdir(parents=True, exist_ok=True)

        migrate_autopoiesis_db(self.db_path)
        self._qdrant_available = True
        self._init_qdrant()

    def _init_qdrant(self) -> None:
        """Initialize Qdrant with fallback to SQLite-only mode on failure (fixes M-3)."""
        key = str(self.qdrant_dir.resolve())
        if key in RegistryManager._qdrant_instances:
            self.qdrant = RegistryManager._qdrant_instances[key]
        else:
            try:
                self.qdrant = self._create_qdrant_client()
                RegistryManager._qdrant_instances[key] = self.qdrant
            except Exception as e:
                # Fallback: SQLite-only mode (fixes M-3)
                import logging
                logging.getLogger("autopoiesis.registry.manager").warning(
                    f"Qdrant unavailable, falling back to SQLite-only mode: {e}"
                )
                self.qdrant = None
                self._qdrant_available = False
                return

        # Ensure collections exist
        try:
            collections = [c.name for c in self.qdrant.get_collections().collections]
            if "skills" not in collections:
                self.qdrant.create_collection(
                    collection_name="skills",
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
            if "templates" not in collections:
                self.qdrant.create_collection(
                    collection_name="templates",
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
        except Exception as e:
            import logging
            logging.getLogger("autopoiesis.registry.manager").warning(
                f"Failed to initialize Qdrant collections: {e}"
            )
            self.qdrant = None
            self._qdrant_available = False

    def _create_qdrant_client(self) -> QdrantClient:
        """Creates a QdrantClient supporting local or remote mode with retry for local lock conflicts.

        Modes are controlled by environment variables:
        - QDRANT_MODE: 'local' (default) or 'remote'
        - QDRANT_URL: URL for remote mode (default http://localhost:6333)
        - QDRANT_TIMEOUT: max seconds to wait for local lock (default 30)
        - QDRANT_RETRY_DELAY: seconds between local lock retries (default 1)
        """
        mode = os.environ.get("QDRANT_MODE", "local").strip().lower()

        if mode == "remote":
            url = os.environ.get("QDRANT_URL", os.environ.get("QDRANT_HOST", "http://localhost:6333"))
            return QdrantClient(url=url, timeout=30)

        # Local mode with retry logic for multi-process access
        path = str(self.qdrant_dir)
        max_wait = int(os.environ.get("QDRANT_TIMEOUT", "30"))
        retry_delay = float(os.environ.get("QDRANT_RETRY_DELAY", "1"))
        start_time = time.time()
        last_error = None

        while time.time() - start_time < max_wait:
            try:
                client = QdrantClient(path=path)
                # Verify the client can actually access the storage
                _ = client.get_collections()
                return client
            except (RuntimeError, QdrantException) as e:
                last_error = e
                time.sleep(retry_delay)
            except Exception as e:
                last_error = e
                break

        raise RuntimeError(
            f"Could not acquire Qdrant local storage at {path} after {max_wait}s. "
            f"Another process may be holding the lock. "
            f"Set QDRANT_MODE=remote to use a remote Qdrant server, "
            f"or set QDRANT_TIMEOUT to increase wait time. "
            f"Last error: {last_error}"
        )

    def _qdrant_upsert_skill(self, skill_id: str, namespace: str, description: str) -> None:
        """Upsert a skill vector to Qdrant, handling unavailable state gracefully."""
        if not self._qdrant_available or self.qdrant is None:
            return
        try:
            vector = self._dummy_embedding(f"{skill_id} {namespace} {description}")
            point_id = int(hashlib.md5(skill_id.encode("utf-8")).hexdigest(), 16) % (2**63 - 1)
            self.qdrant.upsert(
                collection_name="skills",
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={"id": skill_id, "namespace": namespace, "description": description}
                    )
                ]
            )
        except Exception as e:
            logging.getLogger("autopoiesis.registry.manager").warning(f"Qdrant upsert failed for '{skill_id}': {e}")

    def _qdrant_upsert_template(self, template_id: str, namespace: str, description: str) -> None:
        """Upsert a template vector to Qdrant, handling unavailable state gracefully."""
        if not self._qdrant_available or self.qdrant is None:
            return
        try:
            vector = self._dummy_embedding(f"{template_id} {namespace} {description}")
            point_id = int(hashlib.md5(template_id.encode("utf-8")).hexdigest(), 16) % (2**63 - 1)
            self.qdrant.upsert(
                collection_name="templates",
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={"template_id": template_id, "namespace": namespace, "description": description}
                    )
                ]
            )
        except Exception as e:
            logging.getLogger("autopoiesis.registry.manager").warning(f"Qdrant upsert failed for template '{template_id}': {e}")
        """Delete a skill vector from Qdrant, handling unavailable state gracefully."""
        if not self._qdrant_available or self.qdrant is None:
            return
        try:
            point_id = int(hashlib.md5(skill_id.encode("utf-8")).hexdigest(), 16) % (2**63 - 1)
            self.qdrant.delete(collection_name="skills", points_selector=[point_id])
        except Exception:
            pass

    def _qdrant_upsert_template(self, template_id: str, namespace: str, description: str) -> None:
        """Upsert a template vector to Qdrant, handling unavailable state gracefully."""
        if not self._qdrant_available or self.qdrant is None:
            return
        try:
            vector = self._dummy_embedding(f"{template_id} {namespace} {description}")
            point_id = int(hashlib.md5(template_id.encode("utf-8")).hexdigest(), 16) % (2**63 - 1)
            self.qdrant.upsert(
                collection_name="templates",
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={"template_id": template_id, "namespace": namespace, "description": description}
                    )
                ]
            )
        except Exception as e:
            logging.getLogger("autopoiesis.registry.manager").warning(f"Qdrant upsert failed for template '{template_id}': {e}")

    def _dummy_embedding(self, text: str) -> List[float]:
        """Generates a normalized deterministic vector representation using character n-gram term frequencies.

        NOTE: This is a placeholder implementation for development/testing.
        For production use, replace with a real embedding model such as:
        - sentence-transformers (local)
        - OpenAI text-embedding-3-small (API)
        - Cohere embed-v3 (API)

        The current implementation uses MD5-based hashing which does NOT produce
        semantically meaningful embeddings. Vector search results will be random.
        """
        import math
        tokens = [text[i:i+EMBEDDING_TOKEN_SIZE].lower() for i in range(max(1, len(text) - EMBEDDING_TOKEN_SIZE - 1))]
        if not tokens:
            tokens = [text.lower()]

        vec = [0.0] * EMBEDDING_VECTOR_SIZE
        for token in tokens:
            idx = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % EMBEDDING_VECTOR_SIZE
            vec[idx] += 1.0

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def sync_delta_indexing(self, root_registry_dir: str | Path = None) -> Dict[str, int]:
        """Scans 3-Tier Registry on disk, reconciles vectors with Qdrant, re-indexes new/modified skills, and purges deleted disk skills."""
        if root_registry_dir is None:
            root_registry_dir = self.base_dir / "registry"
        root = PlatformAdapter.sanitize_path(root_registry_dir)
        reindexed_count = 0
        purged_count = 0

        # 1. Scan disk for schema.json and skill.py
        disk_skills = {}
        for schema_path in root.glob("**/schema.json"):
            try:
                schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
                skill_id = schema_data.get("id")
                skill_file = schema_path.parent / "skill.py"
                if skill_id and skill_file.exists():
                    disk_skills[skill_id] = (schema_data, skill_file)
            except Exception:
                pass

        # 2. Re-index disk skills into SQLite & Qdrant if missing or modified
        for skill_id, (schema_data, skill_file) in disk_skills.items():
            existing = self.get_skill(skill_id)
            code_text = skill_file.read_text(encoding="utf-8")
            ast_hash = get_normalized_ast_hash(code_text)

            if not existing or existing.ast_hash != ast_hash:
                # Update DB and Qdrant
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO skills (id, namespace, scope_level, description, inputs_json, outputs_json, ast_hash, file_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        skill_id,
                        schema_data.get("namespace", "global"),
                        schema_data.get("scope_level", "core"),
                        schema_data.get("description", ""),
                        json.dumps(schema_data.get("inputs", {})),
                        json.dumps(schema_data.get("outputs", {})),
                        ast_hash,
                        str(skill_file)
                    ))
                    conn.commit()

                # Upsert Qdrant vector (handles unavailable state)
                self._qdrant_upsert_skill(
                    skill_id,
                    schema_data.get("namespace", "global"),
                    schema_data.get("description", "")
                )
                reindexed_count += 1

        # 3. Purge skills in SQLite/Qdrant if missing on disk
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, file_path FROM skills")
            db_rows = cursor.fetchall()
            for row in db_rows:
                s_id, f_path = row[0], row[1]
                if s_id not in disk_skills or not Path(f_path).exists():
                    cursor.execute("DELETE FROM skills WHERE id = ?", (s_id,))
                    # Delete from Qdrant (handles unavailable state)
                    self._qdrant_delete_skill(s_id)
                    purged_count += 1
            conn.commit()

        return {"reindexed": reindexed_count, "purged": purged_count}

    def register_skill(
        self,
        skill_id: str,
        namespace: str,
        scope_level: str,
        description: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        python_code: str,
        root_registry_dir: str | Path = "registry"
    ) -> SkillMetadata:
        """Registers a micro-skill in the relational DB, vector store, and 3-Tier disk registry."""
        # Validate inputs (fixes M-4)
        validate_skill_id(skill_id)
        validate_namespace(namespace)

        ast_hash = get_normalized_ast_hash(python_code)

        # Validate code has a main entrypoint function
        try:
            tree = ast.parse(python_code)
            has_main = any(
                isinstance(node, ast.FunctionDef) and node.name == "main"
                for node in ast.walk(tree)
            )
            if not has_main:
                raise AttributeError("Skill code does not define a 'main(inputs)' entrypoint function.")
        except SyntaxError as e:
            raise AttributeError(f"Skill code contains invalid syntax: {e}") from e

        # Check for AST Hash deduplication within target namespace
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM skills WHERE ast_hash = ? AND namespace = ?", (ast_hash, namespace))
            existing = cursor.fetchone()
            if existing:
                # Deduplication hit: return existing skill metadata
                return self.get_skill(existing[0])  # type: ignore

        # Determine target file path based on scope_level
        root = PlatformAdapter.sanitize_path(root_registry_dir)
        if scope_level == "genesis":
            skill_dir = root / "level_0_genesiss" / namespace / skill_id.split(".")[-1]
        elif scope_level == "core":
            skill_dir = root / "level_1_core" / skill_id.replace(".", "/")
        else:
            skill_dir = root / "level_2_variants" / namespace / skill_id.split(".")[-1]

        skill_dir.mkdir(parents=True, exist_ok=True)
        code_file = skill_dir / "skill.py"
        schema_file = skill_dir / "schema.json"

        code_file.write_text(python_code, encoding="utf-8")

        metadata = SkillMetadata(
            id=skill_id,
            namespace=namespace,
            scope_level=scope_level,
            description=description,
            inputs=inputs,
            outputs=outputs,
            ast_hash=ast_hash,
            file_path=str(code_file),
        )

        schema_file.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

        # Save to SQLite
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO skills (id, namespace, scope_level, description, inputs_json, outputs_json, ast_hash, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                skill_id,
                namespace,
                scope_level,
                description,
                json.dumps(inputs),
                json.dumps(outputs),
                ast_hash,
                str(code_file)
            ))
            conn.commit()

        # Save vector embedding to Qdrant (with fallback handling)
        self._qdrant_upsert_skill(skill_id, namespace, description)

        return metadata

    def get_skill(self, skill_id: str) -> Optional[SkillMetadata]:
        """Retrieves a skill by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, namespace, scope_level, description, inputs_json, outputs_json, ast_hash, file_path, created_at FROM skills WHERE id = ?", (skill_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return SkillMetadata(
                id=row[0],
                namespace=row[1],
                scope_level=row[2],
                description=row[3],
                inputs=json.loads(row[4]),
                outputs=json.loads(row[5]),
                ast_hash=row[6],
                file_path=row[7],
                created_at=str(row[8]) if row[8] else None,
            )

    def invoke_skill(self, skill_id: str, input_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Loads a registered skill's code from disk and executes it in the sandbox."""
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found.")
        
        code = Path(skill.file_path).read_text(encoding="utf-8")
        result = SandboxExecutor.execute_skill_code(python_code=code, input_payload=input_payload)
        if not result.success:
            raise RuntimeError(f"Skill execution failed: {result.stderr}")
        return result.output_payload

    def upsert_skill(self, skill_id: str, metadata: Dict[str, Any], score: float = 0.5) -> None:
        """Directly upserts a skill vector into Qdrant and SQLite without full registration."""
        description = metadata.get("description", "")
        namespace = metadata.get("namespace", "global")
        scope_level = metadata.get("scope_level", "core")
        vector = self._dummy_embedding(f"{skill_id} {description}")
        point_id = int(hashlib.md5(skill_id.encode("utf-8")).hexdigest(), 16) % (2**63 - 1)

        # Save to SQLite (Qdrant upsert handled by _qdrant_upsert_skill)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO skills (id, namespace, scope_level, description, inputs_json, outputs_json, ast_hash, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                skill_id,
                namespace,
                scope_level,
                description,
                json.dumps(metadata.get("inputs", {})),
                json.dumps(metadata.get("outputs", {})),
                metadata.get("ast_hash", ""),
                metadata.get("file_path", ""),
            ))
            conn.commit()

        # Save vector embedding to Qdrant (with fallback handling)
        self._qdrant_upsert_skill(skill_id, namespace, description)

    def search_skills(self, query: str, active_namespaces: List[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Searches skills by semantic similarity filtered by active_namespaces + 'global' for cross-project reusability.
        
        Falls back to SQLite-based search when Qdrant is unavailable (fixes M-3).
        """
        # Always include 'global' namespace for universal cross-project skill reusability
        effective_namespaces = list(set((active_namespaces or []) + ["global"]))

        # Fallback: SQLite-only search when Qdrant is unavailable
        if not self._qdrant_available or self.qdrant is None:
            return self._sqlite_search_skills(query, effective_namespaces, limit)

        vector = self._dummy_embedding(query)

        # Build filter for namespace IN effective_namespaces
        query_filter = Filter(
            should=[
                FieldCondition(key="namespace", match=MatchValue(value=ns))
                for ns in effective_namespaces
            ]
        )

        if hasattr(self.qdrant, "query_points"):
            results = self.qdrant.query_points(
                collection_name="skills",
                query=vector,
                query_filter=query_filter,
                limit=limit,
            ).points
        else:
            results = self.qdrant.search(
                collection_name="skills",
                query_vector=vector,
                query_filter=query_filter,
                limit=limit,
            )

        output = []
        for res in results:
            skill = self.get_skill(res.payload["id"])
            if skill:
                output.append({
                    "skill": skill,
                    "score": getattr(res, "score", 1.0)
                })
        return output

    def _sqlite_search_skills(self, query: str, namespaces: List[str], limit: int) -> List[Dict[str, Any]]:
        """SQLite-based skill search fallback when Qdrant is unavailable.
        
        Performs case-insensitive substring matching on skill descriptions.
        """
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Build namespace filter
            namespace_placeholders = ",".join("?" for _ in namespaces)
            cursor.execute(
                f"SELECT id, namespace, scope_level, description, ast_hash FROM skills WHERE namespace IN ({namespace_placeholders})",
                namespaces,
            )
            rows = cursor.fetchall()
        
        # Score by bidirectional term overlap (normalized 0-1)
        scored = []
        for row in rows:
            skill_id, namespace, scope_level, description, ast_hash = row
            desc_lower = (description or "").lower()
            desc_terms = desc_lower.split()

            # Check for near-exact match: description is substantial substring of query
            # Remove common prefix/suffix words for flexible matching
            desc_core = desc_lower.replace('ai-generated:', '').replace('autonomously synthesized', '').strip()
            query_lower = query_lower.strip()

            if desc_core in query_lower or query_lower in desc_core:
                # One is substring of the other - high confidence match
                score = 1.0
            elif desc_core and query_lower:
                # Token-based Jaccard similarity for partial matches
                desc_tokens = set(desc_core.split())
                query_tokens = set(query_lower.split())
                if desc_tokens and query_tokens:
                    intersection = desc_tokens & query_tokens
                    union = desc_tokens | query_tokens
                    jaccard = len(intersection) / len(union) if union else 0.0

                    # Also compute directional coverage
                    query_coverage = sum(1 for term in query_lower.split() if term in desc_core) / len(query_lower.split()) if query_lower.split() else 0.0
                    desc_coverage = sum(1 for term in desc_core.split() if term in query_lower) / len(desc_core.split()) if desc_core.split() else 0.0

                    # Use maximum of Jaccard and directional coverage
                    score = max(jaccard, desc_coverage, query_coverage)
                else:
                    score = 0.0
            else:
                score = 0.0

            if score > 0 or not query_terms:
                scored.append({
                    "skill": SkillMetadata(
                        id=skill_id,
                        namespace=namespace,
                        scope_level=scope_level,
                        description=description or "",
                        inputs={},
                        outputs={},
                        ast_hash=ast_hash or "",
                    ),
                    "score": round(score, 4),
                })
        
        # Sort by score descending, then by id for stability
        scored.sort(key=lambda x: (-x["score"], x["skill"].id))
        return scored[:limit]

    def register_template(
        self,
        template_id: str,
        namespace: str,
        parameters: Dict[str, Any],
        dag: Dict[str, Any],
        description: str = "",
        root_registry_dir: str | Path = "registry"
    ) -> DAGTemplate:
        """Registers a composite workflow template."""
        root = PlatformAdapter.sanitize_path(root_registry_dir)
        tpl_dir = root / "level_3_templates" / namespace
        tpl_dir.mkdir(parents=True, exist_ok=True)

        tpl_file = tpl_dir / f"{template_id}.json"
        template = DAGTemplate(
            template_id=template_id,
            namespace=namespace,
            parameters=parameters,
            dag=dag,
            description=description,
        )

        tpl_file.write_text(template.model_dump_json(indent=2), encoding="utf-8")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO templates (template_id, namespace, description, parameters_json, dag_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                template_id,
                namespace,
                description,
                json.dumps(parameters),
                json.dumps(dag),
            ))
            conn.commit()

        # Index in Qdrant (with fallback handling)
        self._qdrant_upsert_template(template_id, namespace, description)

        return template

    def get_template(self, template_id: str) -> Optional[DAGTemplate]:
        """Retrieves a DAG template by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT template_id, namespace, description, parameters_json, dag_json FROM templates WHERE template_id = ?", (template_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return DAGTemplate(
                template_id=row[0],
                namespace=row[1],
                description=row[2],
                parameters=json.loads(row[3]),
                dag=json.loads(row[4]),
            )
