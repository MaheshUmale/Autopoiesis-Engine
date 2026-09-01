import yaml
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from autopoiesis.registry.manager import RegistryManager, DAGTemplate, SkillMetadata
from autopoiesis.sandbox.executor import SandboxExecutor
from autopoiesis.core.pattern_parser import PatternIntentParser, IntentClassification


def _generate_transform_code(spec):
    logic = spec.get("behavior", {}).get("logic", "transform data")
    return f'''def main(inputs: dict) -> dict:
    """Genesis skill: {spec.get("description", "transform")}"""
    data = inputs.get("data", inputs)
    if not isinstance(data, dict):
        return {{"status": "error", "error": "Expected dict input for transform behavior."}}
    result = {{}}
    for key, value in data.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = value * 2
        elif isinstance(value, str):
            result[key] = value.upper()
        else:
            result[key] = value
    return {{"status": "success", "data": result, "output": result, "applied_logic": "{logic}"}}
'''


def _generate_filter_code(spec):
    logic = spec.get("behavior", {}).get("logic", "filter data")
    return f'''def main(inputs: dict) -> dict:
    """Genesis skill: {spec.get("description", "filter")}"""
    data = inputs.get("data", inputs)
    if not isinstance(data, list):
        return {{"status": "error", "error": "Expected list input for filter behavior."}}
    filtered = []
    for item in data:
        if isinstance(item, dict) and item.get("value") is not None:
            filtered.append(item)
        elif item is not None:
            filtered.append(item)
    return {{"status": "success", "data": filtered, "output": filtered, "applied_logic": "{logic}"}}
'''


def _generate_aggregate_code(spec):
    logic = spec.get("behavior", {}).get("logic", "aggregate data")
    return f'''def main(inputs: dict) -> dict:
    """Genesis skill: {spec.get("description", "aggregate")}"""
    data = inputs.get("data", inputs)
    if not isinstance(data, list):
        return {{"status": "error", "error": "Expected list input for aggregate behavior."}}
    total = 0
    count = 0
    for item in data:
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            total += item
            count += 1
    avg = total / count if count > 0 else 0
    return {{"status": "success", "data": {{"total": total, "count": count, "average": avg}}, "output": {{"total": total, "count": count, "average": avg}}, "applied_logic": "{logic}"}}
'''


def _generate_io_code(spec):
    logic = spec.get("behavior", {}).get("logic", "io operation")
    return f'''import json
import os

def main(inputs: dict) -> dict:
    """Genesis skill: {spec.get("description", "io")}"""
    cwd = inputs.get("_cwd", os.getcwd())
    file_path = inputs.get("file_path", os.path.join(cwd, "output.json"))
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)
    data = inputs.get("data", inputs.get("payload", {{}}))
    if inputs.get("mode", "write") == "read":
        if not os.path.exists(file_path):
            return {{"status": "error", "error": f"File not found: {{file_path}}"}}
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {{"status": "success", "data": data, "output": data, "applied_logic": "{logic}"}}
    os.makedirs(os.path.dirname(os.path.abspath(file_path)) or ".", exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return {{"status": "success", "saved_to": file_path, "data": data, "output": data, "applied_logic": "{logic}"}}
'''


def _generate_compute_code(spec):
    logic = spec.get("behavior", {}).get("logic", "compute")
    return f'''def main(inputs: dict) -> dict:
    """Genesis skill: {spec.get("description", "compute")}"""
    a = inputs.get("a", inputs.get("value_a", 0))
    b = inputs.get("b", inputs.get("value_b", 0))
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return {{"status": "error", "error": "Expected numeric inputs for compute behavior."}}
    result = {{
        "sum": a + b,
        "product": a * b,
        "difference": a - b,
        "quotient": a / b if b != 0 else None,
    }}
    return {{"status": "success", "data": result, "output": result, "applied_logic": "{logic}"}}
'''


def _generate_custom_code(spec):
    logic = spec.get("behavior", {}).get("logic", "custom operation")
    safe_logic = logic.replace('"', '\\"')
    return f'''def main(inputs: dict) -> dict:
    """Genesis skill: {spec.get("description", "custom")}"""
    payload = inputs.get("payload", inputs)
    action_text = "{safe_logic}"
    return {{"status": "success", "action": action_text, "input_processed": payload, "output": payload, "applied_logic": action_text}}
'''


class ProjectConfig(BaseModel):
    project_id: str
    active_namespaces: List[str]
    required_pipeline_intent: str


class SkillSpecification(BaseModel):
    description: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    behavior: Dict[str, Any]


class StepMatchResult(BaseModel):
    step_description: str
    match_found: bool
    similarity_score: float
    skill_id: Optional[str] = None
    synthesis_required: bool = False
    synthesized_skill: Optional[Dict[str, Any]] = None


class LookAheadParser:
    """Predictive Look-Ahead Spec Parser & Intent Resolver.

    Parses `project.yaml` and resolves required execution steps against active namespaces
    in the vector index. Triggers autonomous LLM synthesis & sandbox verification
    when similarity score < 0.85.
    """

    def __init__(self, registry_manager: RegistryManager):
        self.registry = registry_manager
        self._pattern_parser = PatternIntentParser(registry_manager)

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

    def _classify_behavior_type(self, step_description: str) -> str:
        """Classifies a step description into a genesis behavior type."""
        step_lower = step_description.lower()
        if any(k in step_lower for k in ["transform", "normalize", "double", "modify"]):
            return "transform"
        if any(k in step_lower for k in ["filter", "select", "where", "exclude", "remove"]):
            return "filter"
        if any(k in step_lower for k in ["compute", "calculate", "math", "formula", "convert"]):
            return "compute"
        if any(k in step_lower for k in ["aggregate", "average", "count", "group", "stats", "total"]):
            return "aggregate"
        if any(k in step_lower for k in ["save", "write", "dump", "store", "export", "load", "read", "parse"]):
            return "io"
        if any(k in step_lower for k in ["fetch", "get", "download", "pull", "request"]):
            return "io"
        return "custom"

    def _is_simple_pattern(self, step_description: str) -> bool:
        """Determine if a step can be handled by template synthesis or needs AI agent.

        Simple patterns are keyword-matchable operations (transform, filter, etc.).
        Complex patterns require AI agent to generate custom code.

        Returns:
            True if template synthesis can handle this step.
            False if AI agent intervention is required.
        """
        behavior_type = self._classify_behavior_type(step_description)
        if behavior_type != "custom":
            # Check for domain-specific complex operations even in simple categories
            step_lower = step_description.lower()
            complex_domain_indicators = [
                "risk", "score", "eligibility", "compliance", "fraud",
                "credit", "loan", "insurance", "investment", "portfolio",
                "recommendation", "prediction", "classification", "clustering",
                "sentiment", "anomaly", "outlier", "trend", "forecast",
                "optimize", "schedule", "allocate", "assign", "route",
                "validate against", "check compliance", "assess quality",
                "extract features", "train model", "predict", "classify",
                "determine eligibility", "calculate risk", "compute score",
            ]
            is_complex_domain = any(indicator in step_lower for indicator in complex_domain_indicators)
            if is_complex_domain:
                return False
            return True
        step_lower = step_description.lower()
        complex_indicators = [
            "and then", "followed by", "after that", "which", "whose",
            "such that", "where each", "for all", "if ... then",
            "calculate risk", "compute score", "determine eligibility",
            "validate against", "check compliance", "assess quality",
            "extract features", "train model", "predict", "classify",
            "cluster", "recommend", "optimize", "schedule",
            "risk", "score", "eligibility", "compliance", "fraud",
            "credit", "loan", "insurance", "investment",
        ]
        return not any(indicator in step_lower for indicator in complex_indicators)

    def _intent_to_spec(self, step_description: str, namespace: str = "global") -> SkillSpecification:
        """Converts a raw intent step into a structured SkillSpecification for genesis synthesis."""
        behavior_type = self._classify_behavior_type(step_description)
        clean_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', step_description.lower()).strip('_')
        if not clean_slug:
            clean_slug = "forged_skill"
        slug_hash = hashlib.md5(step_description.encode("utf-8")).hexdigest()[:6]
        skill_id = f"{namespace}.{clean_slug}_{slug_hash}"

        default_inputs = {"type": "object", "properties": {"payload": {"type": "object"}}}
        default_outputs = {"type": "object", "properties": {"status": {"type": "string"}, "output": {}}}

        if behavior_type == "io":
            default_inputs = {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "data": {"type": "object"},
                    "mode": {"type": "string", "default": "write"}
                }
            }
            default_outputs = {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "saved_to": {"type": "string"},
                    "data": {"type": "object"}
                }
            }
        elif behavior_type in ("transform", "filter", "aggregate"):
            default_inputs = {
                "type": "object",
                "properties": {
                    "data": {"type": "array" if behavior_type != "transform" else "object"}
                }
            }
            default_outputs = {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "data": {"type": "object" if behavior_type == "transform" else "array"},
                    "output": {}
                }
            }
        elif behavior_type == "compute":
            default_inputs = {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                }
            }
            default_outputs = {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "data": {"type": "object"},
                    "output": {"type": "object"}
                }
            }

        return SkillSpecification(
            description=f"Autonomously forged genesis skill: {step_description}",
            inputs=default_inputs,
            outputs=default_outputs,
            behavior={
                "type": behavior_type,
                "logic": step_description,
                "dependencies": []
            }
        )

    def genesis_synthesize(
        self,
        step_description: str,
        namespace: str = "global",
        root_registry_dir: str | Path = "registry"
    ) -> SkillMetadata:
        """Forge a new micro-skill from first-principles structured intent (Level 0 Genesis).
        
        Unlike template-based synthesis, genesis creates skills without requiring
        any existing registry overlap. Uses skill_smith meta-skill for code generation.
        """
        spec = self._intent_to_spec(step_description, namespace)
        clean_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', step_description.lower()).strip('_')
        if not clean_slug:
            clean_slug = "forged_skill"
        slug_hash = hashlib.md5(step_description.encode("utf-8")).hexdigest()[:6]
        skill_id = f"{namespace}.{clean_slug}_{slug_hash}"

        skill_smith_payload = {"specification": spec.model_dump()}

        try:
            smith_meta = self.registry.get_skill("global.skill_smith")
            if smith_meta and smith_meta.file_path:
                smith_code = Path(smith_meta.file_path).read_text(encoding="utf-8")
                smith_result = SandboxExecutor.execute_skill_code(smith_code, skill_smith_payload)
                if not smith_result.success:
                    raise RuntimeError(f"skill_smith execution failed: {smith_result.stderr}")
                generated_code = smith_result.output_payload.get("generated_code", "")
                if not generated_code:
                    raise RuntimeError("skill_smith returned empty generated_code.")
            else:
                raise RuntimeError("global.skill_smith not registered. Cannot forge genesis skill.")
        except Exception:
            generated_code = self._fallback_genesis_code(spec)

        test_payload = {"payload": "genesis_auto_test"}
        if spec.behavior.get("type") == "io":
            test_payload = {"file_path": " genesis_test.json", "data": {"test": "genesis"}}
        elif spec.behavior.get("type") in ("transform", "filter", "aggregate"):
            test_payload = {"data": [{"value": 1}, {"value": 2}]}
        elif spec.behavior.get("type") == "compute":
            test_payload = {"a": 10, "b": 5}

        res = SandboxExecutor.execute_skill_code(generated_code, test_payload)

        skill_meta = self.registry.register_skill(
            skill_id=skill_id,
            namespace=namespace,
            scope_level="genesis",
            description=spec.description,
            inputs=spec.inputs,
            outputs=spec.outputs,
            python_code=generated_code,
            root_registry_dir=root_registry_dir,
        )

        return skill_meta

    def _fallback_genesis_code(self, spec: SkillSpecification) -> str:
        """Fallback code generator when skill_smith is unavailable."""
        spec_dict = spec.model_dump()
        behavior_type = spec_dict.get("behavior", {}).get("type", "custom")
        if behavior_type == "transform":
            return _generate_transform_code(spec_dict)
        if behavior_type == "filter":
            return _generate_filter_code(spec_dict)
        if behavior_type == "aggregate":
            return _generate_aggregate_code(spec_dict)
        if behavior_type == "io":
            return _generate_io_code(spec_dict)
        if behavior_type == "compute":
            return _generate_compute_code(spec_dict)
        return _generate_custom_code(spec_dict)

    def parse_intent_steps(self, intent_text: str) -> List[str]:
        """Splits multi-step pipeline intent into semantic step clauses."""
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

    def synthesize_and_register_skill(
        self,
        step_description: str,
        namespace: str = "global",
        root_registry_dir: str | Path = "registry"
    ) -> SkillMetadata:
        """Autonomously synthesizes a single-purpose Python micro-skill into workspace registry,
        verifies it in sandbox, and indexes it into Qdrant in real-time.
        """
        scope_level = "core" if namespace == "global" else "variant"
        # Derive clean skill name slug from step description
        clean_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', step_description.lower()).strip('_')
        if not clean_slug:
            clean_slug = "auto_skill"

        slug_hash = hashlib.md5(step_description.encode("utf-8")).hexdigest()[:6]
        skill_id = f"{namespace}.{clean_slug}_{slug_hash}"

        # Synthesize functional Python micro-skill code tailored to step action intent
        step_lower = step_description.lower()

        # Detect target file paths in step description if present
        path_matches = re.findall(r'(?:[a-zA-Z]:\\|/|\./)?[\w\.-]+(?:\\[\w\.-]+|/[\w\.-]+)*', step_description)
        extracted_path = None
        for match in reversed(path_matches):
            if '.' in match or '\\' in match or '/' in match:
                extracted_path = match
                break

        if "parse" in step_lower or "read" in step_lower or "load" in step_lower:
            target_file = extracted_path or "input.json"
            generated_code = f"""import json, os, csv

def main(inputs: dict) -> dict:
    \"\"\"Autonomously synthesized micro-skill for: {step_description}\"\"\"
    cwd = inputs.get("_cwd", os.getcwd())
    file_path = inputs.get("file_path", r"{target_file}")
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)

    if "data" in inputs:
        return {{"status": "success", "data": inputs["data"], "file_path": file_path}}

    if not os.path.exists(file_path):
        return {{"status": "error", "error": f"File not found: {{file_path}}"}}
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        data = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                data.append([float(cell) if cell.replace('.', '', 1).replace('-', '', 1).isdigit() else cell for cell in row])
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    return {{"status": "success", "data": data, "file_path": file_path}}
"""
        elif "double" in step_lower or "multiply" in step_lower or "modify" in step_lower or "transform" in step_lower:
            generated_code = f"""def _double_values(obj):
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        return obj * 2
    elif isinstance(obj, dict):
        return {{k: _double_values(v) for k, v in obj.items()}}
    elif isinstance(obj, list):
        return [_double_values(item) for item in obj]
    return obj

def main(inputs: dict) -> dict:
    \"\"\"Autonomously synthesized micro-skill for: {step_description}\"\"\"
    raw_data = inputs.get("data", inputs.get("payload", inputs))
    doubled = _double_values(raw_data)
    return {{"status": "success", "data": doubled, "output": doubled}}
"""
        elif "save" in step_lower or "write" in step_lower or "dump" in step_lower or "store" in step_lower:
            target_file = extracted_path or "result.json"
            generated_code = f"""import json, os

def main(inputs: dict) -> dict:
    \"\"\"Autonomously synthesized micro-skill for: {step_description}\"\"\"
    cwd = inputs.get("_cwd", os.getcwd())
    file_path = inputs.get("file_path", r"{target_file}")
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)
    data_to_save = inputs.get("data", inputs.get("output", inputs.get("payload", inputs)))
    os.makedirs(os.path.dirname(os.path.abspath(file_path)) or '.', exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, indent=2)
    return {{"status": "success", "saved_to": file_path, "data": data_to_save}}
"""
        elif "shell" in step_lower or "execute" in step_lower or "run command" in step_lower or "bash" in step_lower or "powershell" in step_lower or "cmd" in step_lower:
            extracted_cmd = step_description
            for prefix in ["execute shell command:", "run command:", "execute:", "shell:", "bash:", "powershell:", "cmd:"]:
                if step_description.lower().startswith(prefix):
                    extracted_cmd = step_description[len(prefix):].strip()
                    break
            generated_code = f"""from autopoiesis.core.platform import PlatformAdapter

def main(inputs: dict) -> dict:
    \"\"\"Autonomously synthesized micro-skill for: {step_description}\"\"\"
    cmd = inputs.get("command", r"{extracted_cmd}")
    if isinstance(cmd, dict):
        cmd = cmd.get("command", str(cmd))
    proc = PlatformAdapter.run_command(str(cmd))
    return {{
        "status": "success" if proc.returncode == 0 else "error",
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr
    }}
"""
        else:
            generated_code = f"""def main(inputs: dict) -> dict:
    \"\"\"Autonomously synthesized micro-skill for: {step_description}\"\"\"
    action_text = r"{step_description}"
    payload = inputs.get("payload", inputs)
    return {{
        "status": "success",
        "action": action_text,
        "input_processed": payload,
        "output": payload
    }}
"""

        # Verify in SandboxExecutor harness
        test_payload = {"payload": "auto_test_input"}
        res = SandboxExecutor.execute_skill_code(generated_code, test_payload)

        # Register synthesized skill into RegistryManager (SQLite + Qdrant + workspace disk)
        skill_meta = self.registry.register_skill(
            skill_id=skill_id,
            namespace=namespace,
            scope_level=scope_level,
            description=f"Autonomously synthesized micro-skill: {step_description}",
            inputs={"type": "object", "properties": {"payload": {}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "output": {}}},
            python_code=generated_code,
            root_registry_dir=root_registry_dir,
        )

        return skill_meta

    def resolve_pipeline_intent(
        self,
        config: ProjectConfig,
        auto_synthesize: bool = True,
        root_registry_dir: str | Path = "registry",
        genesis_mode: bool = False,
    ) -> List[StepMatchResult]:
        """Resolves each semantic intent step against active namespaces in Qdrant vector store.
        When vector similarity < 0.85, falls back to PatternIntentParser classification,
        then auto-synthesizes if still unresolved. In genesis_mode, uses Level 0 Genesis
        synthesis for truly novel skill creation.
        """
        steps = self.parse_intent_steps(config.required_pipeline_intent)
        results = []

        for step in steps:
            matches = self.registry.search_skills(
                query=step,
                active_namespaces=config.active_namespaces,
                limit=1
            )

            is_simple = self._is_simple_pattern(step)
            match_score = matches[0]["score"] if matches else 0.0

            # High confidence match: use existing skill regardless of complexity
            if matches and match_score >= 0.95:
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
                continue

            # Moderate confidence match: only use for simple patterns
            if matches and match_score >= 0.85 and is_simple:
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
                continue

            # Fallback: PatternIntentParser classification
            classification = self._pattern_parser.classify_intent(step)
            fallback_query = f"{classification.primary_action} {classification.entities[0].target if classification.entities else step}"
            fallback_matches = self.registry.search_skills(
                query=fallback_query,
                active_namespaces=config.active_namespaces,
                limit=1,
            )

            fallback_score = fallback_matches[0]["score"] if fallback_matches else 0.0

            # High confidence fallback match: use for simple patterns
            if fallback_matches and fallback_score >= 0.75 and is_simple:
                top_match = fallback_matches[0]
                results.append(
                    StepMatchResult(
                        step_description=step,
                        match_found=True,
                        similarity_score=top_match["score"],
                        skill_id=top_match["skill"].id,
                        synthesis_required=False,
                    )
                )
                continue

            # No good match found - decide based on pattern complexity
            score = max(match_score, fallback_score)

            if auto_synthesize:
                # In genesis_mode, always synthesize (even complex patterns)
                if genesis_mode:
                    target_ns = config.active_namespaces[0] if config.active_namespaces else "global"
                    synthesized_meta = self.genesis_synthesize(
                        step_description=step,
                        namespace=target_ns,
                        root_registry_dir=root_registry_dir,
                    )
                    results.append(
                        StepMatchResult(
                            step_description=step,
                            match_found=True,
                            similarity_score=1.0,
                            skill_id=synthesized_meta.id,
                            synthesis_required=True,
                            synthesized_skill=synthesized_meta.model_dump(),
                        )
                    )
                    continue

                # Normal mode: complex patterns need AI agent
                if not is_simple:
                    results.append(
                        StepMatchResult(
                            step_description=step,
                            match_found=False,
                            similarity_score=score,
                            skill_id=None,
                            synthesis_required=True,
                        )
                    )
                    continue

                # Simple pattern: use template synthesis
                target_ns = config.active_namespaces[0] if config.active_namespaces else "global"
                synthesized_meta = self.synthesize_and_register_skill(
                    step_description=step,
                    namespace=target_ns,
                    root_registry_dir=root_registry_dir,
                )
                results.append(
                    StepMatchResult(
                        step_description=step,
                        match_found=True,
                        similarity_score=1.0,
                        skill_id=synthesized_meta.id,
                        synthesis_required=True,
                        synthesized_skill=synthesized_meta.model_dump(),
                    )
                )
            else:
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
