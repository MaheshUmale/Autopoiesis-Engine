import pytest
from pathlib import Path
from autopoiesis.registry.manager import RegistryManager


def test_registry_skill_registration_and_deduplication(tmp_path: Path):
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    code = """
def main(inputs: dict) -> dict:
    return {"result": inputs.get("val", 0) * 2}
"""

    skill1 = registry.register_skill(
        skill_id="global.math.double",
        namespace="global",
        scope_level="core",
        description="Doubles input value",
        inputs={"type": "object", "properties": {"val": {"type": "integer"}}},
        outputs={"type": "object", "properties": {"result": {"type": "integer"}}},
        python_code=code,
        root_registry_dir=tmp_path / "registry",
    )

    assert skill1.id == "global.math.double"

    # Registering duplicate AST should return same metadata via deduplication
    skill2 = registry.register_skill(
        skill_id="global.math.double_var",
        namespace="global",
        scope_level="core",
        description="Doubles input value again",
        inputs={"type": "object", "properties": {"val": {"type": "integer"}}},
        outputs={"type": "object", "properties": {"result": {"type": "integer"}}},
        python_code=code,
        root_registry_dir=tmp_path / "registry",
    )

    assert skill2.id == skill1.id


def test_registry_vector_search(tmp_path: Path):
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    code = "def main(inputs): return {'ok': True}"
    registry.register_skill(
        skill_id="trading.upstox.fetch",
        namespace="trading.broker.upstox",
        scope_level="variant",
        description="Fetches Upstox historical candles",
        inputs={},
        outputs={},
        python_code=code,
        root_registry_dir=tmp_path / "registry",
    )

    results = registry.search_skills("Upstox historical candles", active_namespaces=["trading.broker.upstox"])
    assert len(results) > 0
    assert results[0]["skill"].id == "trading.upstox.fetch"


def test_sync_delta_indexing(tmp_path: Path):
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    # Register skill
    registry.register_skill(
        skill_id="global.file.reader",
        namespace="global",
        scope_level="core",
        description="Reads file contents",
        inputs={},
        outputs={},
        python_code="def main(inputs): return {'read': True}",
        root_registry_dir=tmp_path / "registry",
    )

    res = registry.sync_delta_indexing(root_registry_dir=tmp_path / "registry")
    assert isinstance(res, dict)
    assert "reindexed" in res
    assert "purged" in res
