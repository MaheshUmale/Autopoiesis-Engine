import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from autopoiesis.registry.manager import RegistryManager, DAGTemplate


class ProjectConfig(BaseModel):
    project_id: str
    active_namespaces: List[str]
    required_pipeline_intent: str


class StepMatchResult(BaseModel):
    step_description: str
    match_found: bool
    similarity_score: float
    skill_id: Optional[str] = None
    synthesis_required: bool = False


class LookAheadParser:
    """Predictive Look-Ahead Spec Parser & Intent Resolver.

    Parses `project.yaml` and resolves required execution steps against active namespaces
    in the vector index. Triggers synthesis flag if similarity score < 0.85.
    """

    def __init__(self, registry_manager: RegistryManager):
        self.registry = registry_manager

    @classmethod
    def from_file(cls, config_path: str | Path, base_dir: str | Path = ".autopoiesis") -> "LookAheadParser":
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Project config file not found at {path}")

        raw_yaml = yaml.safe_load(path.read_text(encoding="utf-8"))
        config = ProjectConfig(**raw_yaml)
        registry = RegistryManager(base_dir=base_dir)
        parser = cls(registry)
        parser.config = config
        return parser

    def parse_intent_steps(self, intent_text: str) -> List[str]:
        """Splits multi-step pipeline intent into semantic step clauses."""
        # Simple clause segmentation by comma, newline, or 'and'
        raw_lines = [line.strip() for line in intent_text.splitlines() if line.strip()]
        steps = []
        for line in raw_lines:
            sub_steps = [s.strip() for s in line.split(",") if s.strip()]
            for s in sub_steps:
                if s.lower().startswith("and "):
                    s = s[4:].strip()
                if s:
                    steps.append(s)
        return steps

    def resolve_pipeline_intent(self, config: ProjectConfig) -> List[StepMatchResult]:
        """Resolves each semantic intent step against active namespaces in Qdrant vector store."""
        steps = self.parse_intent_steps(config.required_pipeline_intent)
        results = []

        for step in steps:
            matches = self.registry.search_skills(
                query=step,
                active_namespaces=config.active_namespaces,
                limit=1
            )

            if matches and matches[0]["score"] >= 0.85:
                top_match = matches[0]
                results.append(
                    StepMatchResult(
                        step_description=step,
                        match_found=True,
                        similarity_score=top_match["score"],
                        skill_id=top_match["skill"].id,
                        synthesis_required=False,
                    )
                )
            else:
                score = matches[0]["score"] if matches else 0.0
                results.append(
                    StepMatchResult(
                        step_description=step,
                        match_found=False,
                        similarity_score=score,
                        skill_id=None,
                        synthesis_required=True,
                    )
                )

        return results

    def extract_and_save_template(
        self,
        template_id: str,
        namespace: str,
        parameters: Dict[str, Any],
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        description: str = "",
        root_registry_dir: str | Path = "registry"
    ) -> DAGTemplate:
        """Abstracts a successful multi-step execution DAG into a parameterized template."""
        dag = {
            "nodes": nodes,
            "edges": edges,
        }
        return self.registry.register_template(
            template_id=template_id,
            namespace=namespace,
            parameters=parameters,
            dag=dag,
            description=description,
            root_registry_dir=root_registry_dir,
        )
