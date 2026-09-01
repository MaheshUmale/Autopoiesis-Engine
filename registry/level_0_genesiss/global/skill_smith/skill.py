import ast
import hashlib
import json
import os
import re
from typing import Any, Dict


def _validate_generated_code(code: str) -> Dict[str, Any]:
    """Validates generated skill code for structural correctness."""
    try:
        tree = ast.parse(code)
        has_main = any(
            isinstance(node, ast.FunctionDef) and node.name == "main"
            for node in ast.walk(tree)
        )
        if not has_main:
            return {"valid": False, "error": "Generated code missing 'main(inputs)' entrypoint."}
        return {"valid": True}
    except SyntaxError as e:
        return {"valid": False, "error": f"Syntax error: {e}"}


def _generate_transform_code(spec: Dict[str, Any]) -> str:
    """Generates a data transformation micro-skill."""
    logic = spec.get("behavior", {}).get("logic", "transform data")
    return f'''def main(inputs: dict) -> dict:
    """Autonomously forged genesis skill: {spec.get("description", "transform")}"""
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


def _generate_filter_code(spec: Dict[str, Any]) -> str:
    """Generates a data filtering micro-skill."""
    logic = spec.get("behavior", {}).get("logic", "filter data")
    return f'''def main(inputs: dict) -> dict:
    """Autonomously forged genesis skill: {spec.get("description", "filter")}"""
    data = inputs.get("data", inputs)
    condition = inputs.get("condition", "value is not None")
    
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


def _generate_aggregate_code(spec: Dict[str, Any]) -> str:
    """Generates a data aggregation micro-skill."""
    logic = spec.get("behavior", {}).get("logic", "aggregate data")
    return f'''def main(inputs: dict) -> dict:
    """Autonomously forged genesis skill: {spec.get("description", "aggregate")}"""
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


def _generate_io_code(spec: Dict[str, Any]) -> str:
    """Generates an I/O micro-skill."""
    logic = spec.get("behavior", {}).get("logic", "io operation")
    return f'''import json
import os

def main(inputs: dict) -> dict:
    """Autonomously forged genesis skill: {spec.get("description", "io")}"""
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


def _generate_compute_code(spec: Dict[str, Any]) -> str:
    """Generates a computation micro-skill."""
    logic = spec.get("behavior", {}).get("logic", "compute")
    return f'''def main(inputs: dict) -> dict:
    """Autonomously forged genesis skill: {spec.get("description", "compute")}"""
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


def _generate_custom_code(spec: Dict[str, Any]) -> str:
    """Generates a custom micro-skill from a free-form logic description."""
    logic = spec.get("behavior", {}).get("logic", "custom operation")
    safe_logic = logic.replace('"', '\\"')
    return f'''def main(inputs: dict) -> dict:
    """Autonomously forged genesis skill: {spec.get("description", "custom")}"""
    payload = inputs.get("payload", inputs)
    action_text = "{safe_logic}"
    return {{"status": "success", "action": action_text, "input_processed": payload, "output": payload, "applied_logic": action_text}}
'''


_BEHAVIOR_GENERATORS = {
    "transform": _generate_transform_code,
    "filter": _generate_filter_code,
    "aggregate": _generate_aggregate_code,
    "io": _generate_io_code,
    "compute": _generate_compute_code,
    "custom": _generate_custom_code,
}


def main(inputs: dict) -> dict:
    """Genesis meta-skill: forges new micro-skills from structured SkillSpecification."""
    specification = inputs.get("specification")
    if not specification or not isinstance(specification, dict):
        return {"status": "error", "error": "Missing 'specification' dict in inputs."}
    
    behavior = specification.get("behavior", {})
    behavior_type = behavior.get("type", "custom")
    generator = _BEHAVIOR_GENERATORS.get(behavior_type, _generate_custom_code)
    
    generated_code = generator(specification)
    validation = _validate_generated_code(generated_code)
    
    if not validation.get("valid"):
        return {"status": "error", "error": validation.get("error"), "generated_code": generated_code}
    
    ast_hash = hashlib.sha256(generated_code.encode("utf-8")).hexdigest()[:16]
    
    return {
        "status": "success",
        "skill_id": specification.get("id", "global.forged_skill"),
        "generated_code": generated_code,
        "ast_hash": ast_hash,
        "validation": validation,
        "behavior_type": behavior_type,
    }
