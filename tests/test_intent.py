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


def test_look_ahead_parser_auto_synthesis(tmp_path: Path):
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)
    parser = LookAheadParser(registry)

    config = ProjectConfig(
        project_id="test_auto_synth_proj",
        active_namespaces=["trading.broker.upstox"],
        required_pipeline_intent="Fetch historical OHLCV data from Upstox API"
    )

    results = parser.resolve_pipeline_intent(config, auto_synthesize=True, root_registry_dir=tmp_path / "registry")
    assert len(results) == 1
    res = results[0]
    assert res.match_found is True
    assert res.synthesis_required is True
    assert res.skill_id is not None
    assert res.synthesized_skill is not None

    # Verify synthesized skill exists in SQLite and Qdrant
    skill_meta = registry.get_skill(res.skill_id)
    assert skill_meta is not None
    assert Path(skill_meta.file_path).exists()


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
