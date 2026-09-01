"""End-to-end tests for Level 0 Genesis pathway."""
import json
import pytest
from pathlib import Path
from autopoiesis.registry.manager import RegistryManager
from autopoiesis.core.intent import LookAheadParser, ProjectConfig, SkillSpecification
from autopoiesis.sandbox.executor import SandboxExecutor


class TestGenesisRegistry:
    """Tests for genesis skill registration in level_0_genesiss/."""

    def test_genesis_skill_routes_to_level_0_genesiss(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        
        skill_meta = registry.register_skill(
            skill_id="test.novel_skill_abc123",
            namespace="test",
            scope_level="genesis",
            description="A novel genesis skill",
            inputs={"type": "object", "properties": {"value": {"type": "integer"}}},
            outputs={"type": "object", "properties": {"result": {"type": "integer"}}},
            python_code='def main(inputs: dict) -> dict:\n    return {"status": "success", "result": inputs.get("value", 0) * 2}\n',
            root_registry_dir=tmp_path / "registry",
        )
        
        assert skill_meta.scope_level == "genesis"
        assert skill_meta.file_path is not None
        skill_path = Path(skill_meta.file_path)
        assert skill_path.exists()
        assert "level_0_genesiss" in skill_path.as_posix()
        assert skill_path.parent.name == "novel_skill_abc123"
        
        schema_path = skill_path.parent / "schema.json"
        assert schema_path.exists()
        schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema_data["scope_level"] == "genesis"
        assert schema_data["id"] == "test.novel_skill_abc123"

    def test_genesis_skill_sync_delta_indexing(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        
        skill_dir = tmp_path / "registry" / "level_0_genesiss" / "test" / "sync_skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "skill.py").write_text('def main(inputs: dict) -> dict:\n    return {"status": "success"}\n', encoding="utf-8")
        (skill_dir / "schema.json").write_text(json.dumps({
            "id": "test.sync_skill",
            "namespace": "test",
            "scope_level": "genesis",
            "description": "Sync test genesis skill",
            "inputs": {"type": "object"},
            "outputs": {"type": "object"}
        }), encoding="utf-8")
        
        result = registry.sync_delta_indexing(root_registry_dir=tmp_path / "registry")
        assert result["reindexed"] >= 1
        
        skill = registry.get_skill("test.sync_skill")
        assert skill is not None
        assert skill.scope_level == "genesis"


class TestGenesisSynthesis:
    """Tests for genesis_synthesize method."""

    def test_genesis_synthesize_creates_novel_skill(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.genesis_synthesize(
            step_description="Compress data using gzip",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        assert skill_meta.scope_level == "genesis"
        assert skill_meta.id.startswith("global.compress_data_using_gzip_")
        assert skill_meta.file_path is not None
        assert Path(skill_meta.file_path).exists()
        assert "level_0_genesiss" in Path(skill_meta.file_path).as_posix()

    def test_genesis_synthesize_executes_successfully(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.genesis_synthesize(
            step_description="Filter active users from list",
            namespace="trading",
            root_registry_dir=tmp_path / "registry",
        )
        
        skill = registry.get_skill(skill_meta.id)
        assert skill is not None
        python_code = Path(skill.file_path).read_text(encoding="utf-8")
        
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"data": [{"value": 1}, {"value": None}, {"value": 3}]})
        assert exec_res.success is True
        assert "data" in exec_res.output_payload

    def test_genesis_synthesize_compute_behavior(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.genesis_synthesize(
            step_description="Calculate portfolio return and risk metrics",
            namespace="trading",
            root_registry_dir=tmp_path / "registry",
        )
        
        skill = registry.get_skill(skill_meta.id)
        python_code = Path(skill.file_path).read_text(encoding="utf-8")
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"a": 100, "b": 20})
        
        assert exec_res.success is True
        assert exec_res.output_payload["data"]["sum"] == 120
        assert exec_res.output_payload["data"]["product"] == 2000

    def test_genesis_synthesize_io_behavior(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.genesis_synthesize(
            step_description="Export trade signals to JSON file",
            namespace="trading",
            root_registry_dir=tmp_path / "registry",
        )
        
        skill = registry.get_skill(skill_meta.id)
        python_code = Path(skill.file_path).read_text(encoding="utf-8")
        test_file = tmp_path / "genesis_test_output.json"
        exec_res = SandboxExecutor.execute_skill_code(python_code, {
            "file_path": str(test_file),
            "data": {"signal": "BUY", "symbol": "RELIANCE"}
        })
        
        assert exec_res.success is True
        assert test_file.exists()
        saved = json.loads(test_file.read_text(encoding="utf-8"))
        assert saved["signal"] == "BUY"

    def test_genesis_synthesize_aggregate_behavior(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.genesis_synthesize(
            step_description="Aggregate daily volume statistics",
            namespace="trading",
            root_registry_dir=tmp_path / "registry",
        )
        
        skill = registry.get_skill(skill_meta.id)
        python_code = Path(skill.file_path).read_text(encoding="utf-8")
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"data": [10, 20, 30]})
        
        assert exec_res.success is True
        assert exec_res.output_payload["data"]["total"] == 60
        assert exec_res.output_payload["data"]["count"] == 3
        assert exec_res.output_payload["data"]["average"] == 20

    def test_genesis_synthesize_transform_behavior(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.genesis_synthesize(
            step_description="Normalize price data values",
            namespace="trading",
            root_registry_dir=tmp_path / "registry",
        )
        
        skill = registry.get_skill(skill_meta.id)
        python_code = Path(skill.file_path).read_text(encoding="utf-8")
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"data": {"price": 100, "symbol": "rel"}})
        
        assert exec_res.success is True
        assert exec_res.output_payload["data"]["price"] == 200
        assert exec_res.output_payload["data"]["symbol"] == "REL"

    def test_genesis_synthesize_custom_fallback(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.genesis_synthesize(
            step_description="Quantum entanglement the portfolio weights",
            namespace="trading",
            root_registry_dir=tmp_path / "registry",
        )
        
        skill = registry.get_skill(skill_meta.id)
        python_code = Path(skill.file_path).read_text(encoding="utf-8")
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"payload": {"test": "value"}})
        
        assert exec_res.success is True
        assert exec_res.output_payload["status"] == "success"


class TestGenesisPipeline:
    """End-to-end pipeline tests for genesis mode."""

    def test_resolve_pipeline_intent_with_genesis_mode(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        config = ProjectConfig(
            project_id="test_genesis_pipeline",
            active_namespaces=["trading"],
            required_pipeline_intent="Compress data using gzip, then filter active users"
        )
        
        results = parser.resolve_pipeline_intent(
            config,
            auto_synthesize=True,
            root_registry_dir=tmp_path / "registry",
            genesis_mode=True,
        )
        
        assert len(results) == 2
        for res in results:
            assert res.match_found is True
            assert res.skill_id is not None
            assert res.synthesis_required is True
            assert res.synthesized_skill is not None
            assert res.synthesized_skill.get("scope_level") == "genesis"
            
            skill = registry.get_skill(res.skill_id)
            assert skill is not None
            assert "level_0_genesiss" in Path(skill.file_path).as_posix()

    def test_genesis_pipeline_execution(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        config = ProjectConfig(
            project_id="test_genesis_exec",
            active_namespaces=["global"],
            required_pipeline_intent="Calculate sum and product of portfolio values"
        )
        
        results = parser.resolve_pipeline_intent(
            config,
            auto_synthesize=True,
            root_registry_dir=tmp_path / "registry",
            genesis_mode=True,
        )
        
        assert len(results) == 1
        skill = registry.get_skill(results[0].skill_id)
        python_code = Path(skill.file_path).read_text(encoding="utf-8")
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"a": 50, "b": 10})
        
        assert exec_res.success is True
        assert exec_res.output_payload["data"]["sum"] == 60
        assert exec_res.output_payload["data"]["product"] == 500

    def test_genesis_skills_are_independent_of_existing_registry(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        novel_intents = [
            "Orchestrate multi-leg options hedging strategy",
            "Stream real-time sentiment from Twitter API",
            "Backtest walk-forward optimization with parameter annealing",
        ]
        
        created_skills = []
        for intent in novel_intents:
            skill_meta = parser.genesis_synthesize(
                step_description=intent,
                namespace="trading",
                root_registry_dir=tmp_path / "registry",
            )
            created_skills.append(skill_meta)
            
            skill = registry.get_skill(skill_meta.id)
            assert skill is not None
            assert skill.scope_level == "genesis"
            python_code = Path(skill.file_path).read_text(encoding="utf-8")
            exec_res = SandboxExecutor.execute_skill_code(python_code, {"payload": "test"})
            assert exec_res.success is True
        
        assert len(created_skills) == 3
        assert len(set(s.id for s in created_skills)) == 3


class TestGenesisMCP:
    """Tests for Genesis MCP tool exposure."""

    def test_genesis_forge_skill_mcp_tool(self, tmp_path: Path):
        from autopoiesis.mcp.server import create_fastapi_app
        from fastapi.testclient import TestClient
        
        base_dir = tmp_path / ".autopoiesis"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        app = create_fastapi_app(base_dir=str(base_dir))
        client = TestClient(app)
        
        response = client.post("/messages", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "amf_genesis_forge_skill",
                "arguments": {
                    "specification": {
                        "description": "Calculate Kelly criterion position size",
                        "inputs": {"type": "object", "properties": {"win_rate": {"type": "number"}, "avg_win": {"type": "number"}, "avg_loss": {"type": "number"}}},
                        "outputs": {"type": "object", "properties": {"position_size": {"type": "number"}}},
                        "behavior": {"type": "compute", "logic": "calculate kelly criterion"}
                    },
                    "namespace": "trading"
                }
            }
        })
        
        assert response.status_code == 200
        result = response.json()
        assert "result" in result
        text = result["result"].get("content", [{}])[0].get("text", "{}")
        parsed = json.loads(text)
        assert parsed["status"] == "success"
        assert "skill_id" in parsed
        assert parsed["scope_level"] == "genesis"

    def test_genesis_synthesize_mcp_tool(self, tmp_path: Path):
        from autopoiesis.mcp.server import create_fastapi_app
        from fastapi.testclient import TestClient
        
        base_dir = tmp_path / ".autopoiesis"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        app = create_fastapi_app(base_dir=str(base_dir))
        client = TestClient(app)
        
        response = client.post("/messages", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "amf_genesis_synthesize",
                "arguments": {
                    "intent": "Compress data using gzip, then filter active users",
                    "active_namespaces": ["global"]
                }
            }
        })
        
        assert response.status_code == 200
        result = response.json()
        assert "result" in result
        text = result["result"].get("content", [{}])[0].get("text", "{}")
        parsed = json.loads(text)
        assert parsed["genesis"] is True
        assert parsed["stats"]["synthesized"] >= 1


class TestSkillSpecification:
    """Tests for SkillSpecification model."""

    def test_skill_specification_model(self):
        spec = SkillSpecification(
            description="Test skill",
            inputs={"type": "object"},
            outputs={"type": "object"},
            behavior={"type": "compute", "logic": "do math"}
        )
        assert spec.description == "Test skill"
        assert spec.behavior["type"] == "compute"
        assert spec.model_dump()["behavior"]["logic"] == "do math"
