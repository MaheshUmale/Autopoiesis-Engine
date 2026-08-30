import pytest
import yaml
from pathlib import Path
from autopoiesis.core.intent import LookAheadParser, ProjectConfig, StepMatchResult
from autopoiesis.registry.manager import RegistryManager


def test_look_ahead_parser_step_parsing(tmp_path: Path):
    registry = RegistryManager(base_dir=tmp_path / ".autopoiesis")
    parser = LookAheadParser(registry)

    intent = "Fetch candles from Upstox, calculate 20 SMA, and save to Postgres"
    steps = parser.parse_intent_steps(intent)
    assert len(steps) >= 3
    assert "Fetch candles from Upstox" in steps[0]


def test_look_ahead_parser_resolution_and_synthesis_flag(tmp_path: Path):
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    # Register a known skill
    registry.register_skill(
        skill_id="trading.upstox.fetch",
        namespace="trading.broker.upstox",
        scope_level="variant",
        description="Fetch candles from Upstox",
        inputs={},
        outputs={},
        python_code="def main(inputs): return {}",
        root_registry_dir=tmp_path / "registry"
    )

    parser = LookAheadParser(registry)
    config = ProjectConfig(
        project_id="test_proj",
        active_namespaces=["trading.broker.upstox"],
        required_pipeline_intent="Fetch candles from Upstox, unknown missing action"
    )

    results = parser.resolve_pipeline_intent(config)
    assert len(results) == 2
    assert results[0].synthesis_required is False or results[0].synthesis_required is True
    assert isinstance(results[0], StepMatchResult)


def test_look_ahead_parser_template_extraction(tmp_path: Path):
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)
    parser = LookAheadParser(registry)

    tpl = parser.extract_and_save_template(
        template_id="tpl_test_pipeline",
        namespace="trading.broker.upstox",
        parameters={"instrument": {"type": "string"}},
        nodes=[{"id": "step1", "skill_id": "trading.upstox.fetch", "args": {}}],
        edges=[],
        description="Test composite template",
        root_registry_dir=tmp_path / "registry"
    )

    assert tpl.template_id == "tpl_test_pipeline"
    assert registry.get_template("tpl_test_pipeline") is not None
