import json
import sqlite3
import hashlib
from pathlib import Path
from typing import Any, Optional, Dict, List
from pydantic import BaseModel, Field

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

from autopoiesis.core.ast import get_normalized_ast_hash
from autopoiesis.core.platform import PlatformAdapter


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
    """Manages 3-Tier Registry using SQLite for relational metadata and Qdrant for vector search."""

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.base_dir / "autopoiesis.db"
        self.qdrant_dir = self.base_dir / "qdrant"
        self.qdrant_dir.mkdir(parents=True, exist_ok=True)

        self._init_sqlite()
        self._init_qdrant()

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    scope_level TEXT NOT NULL,
                    description TEXT,
                    inputs_json TEXT NOT NULL,
                    outputs_json TEXT NOT NULL,
                    ast_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    template_id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    description TEXT,
                    parameters_json TEXT NOT NULL,
                    dag_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _init_qdrant(self) -> None:
        self.qdrant = QdrantClient(path=str(self.qdrant_dir))
        # Ensure collections exist
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

    def _dummy_embedding(self, text: str) -> List[float]:
        """Generates a deterministic vector representation for text when no LLM API is configured."""
        sha = hashlib.sha256(text.encode("utf-8")).digest()
        vector = []
        for i in range(384):
            val = (sha[i % len(sha)] / 255.0) * 2.0 - 1.0
            vector.append(val)
        return vector

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
        ast_hash = get_normalized_ast_hash(python_code)

        # Check for AST Hash deduplication
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM skills WHERE ast_hash = ?", (ast_hash,))
            existing = cursor.fetchone()
            if existing:
                # Deduplication hit: return existing skill metadata
                return self.get_skill(existing[0])  # type: ignore

        # Determine target file path based on scope_level
        root = PlatformAdapter.sanitize_path(root_registry_dir)
        if scope_level == "core":
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

        # Save vector embedding to Qdrant
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

    def search_skills(self, query: str, active_namespaces: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        """Searches skills by semantic similarity filtered by active_namespaces."""
        vector = self._dummy_embedding(query)

        # Build filter for namespace IN active_namespaces
        must_conditions = []
        if active_namespaces:
            # Match any of active_namespaces
            must_conditions.append(
                Filter(
                    should=[
                        FieldCondition(key="namespace", match=MatchValue(value=ns))
                        for ns in active_namespaces
                    ]
                )
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None

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

        # Index in Qdrant
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
