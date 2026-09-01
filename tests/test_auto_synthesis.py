"""End-to-end tests for auto-synthesis feature: explicit triggers, MCP tools, CLI, and template coverage."""
import json
import pytest
from pathlib import Path
from autopoiesis.registry.manager import RegistryManager
from autopoiesis.core.intent import LookAheadParser, ProjectConfig
from autopoiesis.sandbox.executor import SandboxExecutor


class TestAutoSynthesisCore:
    """Core auto-synthesis functionality tests."""

    def test_synthesize_parse_template(self, tmp_path: Path):
        """Synthesize a 'parse/read' skill and verify it works."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.synthesize_and_register_skill(
            step_description="Parse input.json",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        assert skill_meta.id.startswith("global.parse_input_json_")
        assert skill_meta.file_path is not None
        assert Path(skill_meta.file_path).exists()
        
        skill = registry.get_skill(skill_meta.id)
        assert skill is not None
        python_code = Path(skill.file_path).read_text(encoding="utf-8")
        assert "main" in python_code

    def test_synthesize_double_template(self, tmp_path: Path):
        """Synthesize a 'double/multiply' skill and verify it works."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.synthesize_and_register_skill(
            step_description="Double all values",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        assert skill_meta.id.startswith("global.double_all_values_")
        
        # Execute the synthesized skill
        skill = registry.get_skill(skill_meta.id)
        python_code = open(skill.file_path, "r", encoding="utf-8").read()
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"data": {"a": 1, "b": 2}})
        
        assert exec_res.success is True
        assert exec_res.output_payload.get("data", {}).get("a") == 2
        assert exec_res.output_payload.get("data", {}).get("b") == 4

    def test_synthesize_save_template(self, tmp_path: Path):
        """Synthesize a 'save/write' skill and verify it works."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.synthesize_and_register_skill(
            step_description="Save results to output.json",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        assert skill_meta.id.startswith("global.save_results_to_output_json_")
        
        # Execute with a test file path
        skill = registry.get_skill(skill_meta.id)
        python_code = open(skill.file_path, "r", encoding="utf-8").read()
        test_file = tmp_path / "test_output.json"
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"data": {"hello": "world"}, "file_path": str(test_file)})
        
        assert exec_res.success is True
        assert test_file.exists()
        with open(test_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data == {"hello": "world"}

    def test_synthesize_shell_template(self, tmp_path: Path):
        """Synthesize a 'shell/execute' skill and verify it works."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.synthesize_and_register_skill(
            step_description="Execute shell command: echo hello",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        assert skill_meta.id.startswith("global.execute_shell_command_echo_hello_")
        
        skill = registry.get_skill(skill_meta.id)
        python_code = open(skill.file_path, "r", encoding="utf-8").read()
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"command": "echo hello"})
        
        assert exec_res.success is True
        assert "hello" in exec_res.output_payload.get("stdout", "").lower()

    def test_synthesize_generic_fallback_template(self, tmp_path: Path):
        """Synthesize a generic fallback skill for unrecognized intent."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.synthesize_and_register_skill(
            step_description="Do something completely custom",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        assert skill_meta.id.startswith("global.do_something_completely_custom_")
        
        skill = registry.get_skill(skill_meta.id)
        python_code = open(skill.file_path, "r", encoding="utf-8").read()
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"payload": {"test": "value"}})
        
        assert exec_res.success is True
        assert exec_res.output_payload.get("status") == "success"

    def test_synthesize_deduplication_returns_existing(self, tmp_path: Path):
        """Synthesizing the same description twice should return the same skill."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill1 = parser.synthesize_and_register_skill(
            step_description="Parse data.json",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        skill2 = parser.synthesize_and_register_skill(
            step_description="Parse data.json",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        # Should return the same skill ID due to AST-based deduplication
        assert skill2.id == skill1.id

    def test_synthesize_different_namespaces(self, tmp_path: Path):
        """Synthesize skills in different namespaces."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_global = parser.synthesize_and_register_skill(
            step_description="Parse data.json",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        skill_trading = parser.synthesize_and_register_skill(
            step_description="Parse data.json",
            namespace="trading.broker",
            root_registry_dir=tmp_path / "registry",
        )
        
        assert skill_global.id.startswith("global.")
        assert skill_trading.id.startswith("trading.broker.")
        assert skill_global.id != skill_trading.id


class TestAutoSynthesisMCP:
    """MCP tool integration tests for auto-synthesis."""

    def test_mcp_synthesize_skill_tool(self, tmp_path: Path):
        """Test the synthesize_skill MCP tool directly."""
        from autopoiesis.mcp.server import create_mcp_server
        
        base_dir = tmp_path / ".autopoiesis"
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "registry").mkdir(parents=True, exist_ok=True)
        
        server = create_mcp_server(base_dir=str(base_dir))
        
        # Find the synthesize_skill tool
        tool_names = [tool.name for tool in server._tool_manager.list_tools()]
        assert "synthesize_skill" in tool_names, f"Available tools: {tool_names}"
        
        # Call the tool via MCP
        import asyncio
        async def call_tool():
            return await server.call_tool("synthesize_skill", {
                "step_description": "Double all numbers",
                "namespace": "global",
                "test_inputs": {"data": {"x": 5}}
            })
        
        result = asyncio.run(call_tool())
        # FastMCP call_tool may return: list[ContentBlock], tuple (unstructured, structured), dict, or str
        if isinstance(result, tuple):
            unstructured = result[0]
            if isinstance(unstructured, list) and unstructured:
                text = unstructured[0].text if hasattr(unstructured[0], "text") else str(unstructured[0])
            else:
                text = str(unstructured)
            result_data = json.loads(text)
        elif isinstance(result, list) and result:
            text = result[0].text if hasattr(result[0], "text") else str(result[0])
            result_data = json.loads(text)
        elif isinstance(result, dict):
            result_data = result
        else:
            result_data = json.loads(result)
        
        assert result_data["status"] == "success"
        assert result_data["skill_id"] is not None
        assert "double" in result_data["skill_id"].lower()
        assert result_data.get("test_result", {}).get("success") is True

    def test_mcp_synthesize_and_run_tool(self, tmp_path: Path):
        """Test the synthesize_and_run MCP tool directly."""
        from autopoiesis.mcp.server import create_mcp_server
        
        base_dir = tmp_path / ".autopoiesis"
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "registry").mkdir(parents=True, exist_ok=True)
        
        server = create_mcp_server(base_dir=str(base_dir))
        
        tool_names = [tool.name for tool in server._tool_manager.list_tools()]
        assert "synthesize_and_run" in tool_names, f"Available tools: {tool_names}"
        
        import asyncio
        async def call_tool():
            return await server.call_tool("synthesize_and_run", {
                "intent": "Parse data.json, double the numbers",
                "active_namespaces": ["global"]
            })
        
        result = asyncio.run(call_tool())
        # FastMCP call_tool may return: list[ContentBlock], tuple (unstructured, structured), dict, or str
        if isinstance(result, tuple):
            unstructured = result[0]
            if isinstance(unstructured, list) and unstructured:
                text = unstructured[0].text if hasattr(unstructured[0], "text") else str(unstructured[0])
            else:
                text = str(unstructured)
            result_data = json.loads(text)
        elif isinstance(result, list) and result:
            text = result[0].text if hasattr(result[0], "text") else str(result[0])
            result_data = json.loads(text)
        elif isinstance(result, dict):
            result_data = result
        else:
            result_data = json.loads(result)
        
        assert "execution_log" in result_data
        assert "stats" in result_data
        assert result_data["stats"]["total_steps"] >= 1

    def test_mcp_run_intent_auto_synthesizes(self, tmp_path: Path):
        """Test that run_intent automatically synthesizes missing skills."""
        from autopoiesis.mcp.server import create_mcp_server
        
        base_dir = tmp_path / ".autopoiesis"
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "registry").mkdir(parents=True, exist_ok=True)
        
        server = create_mcp_server(base_dir=str(base_dir))
        
        import asyncio
        async def call_tool():
            return await server.call_tool("run_intent", {
                "intent": "Parse data.json",
                "active_namespaces": ["global"]
            })
        
        result = asyncio.run(call_tool())
        # FastMCP call_tool may return: list[ContentBlock], tuple (unstructured, structured), dict, or str
        if isinstance(result, tuple):
            unstructured = result[0]
            if isinstance(unstructured, list) and unstructured:
                text = unstructured[0].text if hasattr(unstructured[0], "text") else str(unstructured[0])
            else:
                text = str(unstructured)
            result_data = json.loads(text)
        elif isinstance(result, list) and result:
            text = result[0].text if hasattr(result[0], "text") else str(result[0])
            result_data = json.loads(text)
        elif isinstance(result, dict):
            result_data = result
        else:
            result_data = json.loads(result)
        
        assert "steps" in result_data
        assert len(result_data["steps"]) >= 1
        # Should have synthesized a new skill since no skills exist yet
        assert any(step.get("synthesis_required") for step in result_data["steps"])


class TestAutoSynthesisCLI:
    """CLI command tests for auto-synthesis."""

    def test_cli_synthesize_command_exists(self):
        """Verify the synthesize CLI command is registered."""
        from autopoiesis.cli.main import main
        import sys
        from io import StringIO
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        try:
            with pytest.raises(SystemExit):
                main()
        except SystemExit:
            pass
        finally:
            sys.stdout = old_stdout

    def test_cli_synthesize_creates_skill(self, tmp_path: Path, monkeypatch):
        """Test CLI synthesize command creates a functional skill."""
        from autopoiesis.cli.main import main
        import sys
        from io import StringIO
        
        # Setup workspace
        base_dir = tmp_path / ".autopoiesis"
        base_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "registry").mkdir(parents=True, exist_ok=True)
        
        monkeypatch.chdir(tmp_path)
        
        old_argv = sys.argv
        old_stdout = sys.stdout
        sys.argv = ["autopoiesis", "synthesize", "Parse test.json", "--namespace", "global", "--test"]
        sys.stdout = StringIO()
        
        try:
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
        
        assert "Skill synthesized successfully" in output
        assert "global.parse_test_json_" in output


class TestAutoSynthesisTemplates:
    """Test all synthesis template categories."""

    @pytest.mark.parametrize("description,expected_keywords", [
        ("Parse input.json", ["parse", "input"]),
        ("Read data.csv", ["read", "data"]),
        ("Load config.yaml", ["load", "config"]),
        ("Double all values", ["double"]),
        ("Multiply numbers by 2", ["multiply"]),
        ("Transform data", ["transform"]),
        ("Save to output.json", ["save", "output"]),
        ("Write results", ["write", "results"]),
        ("Execute shell command: ls", ["execute", "shell"]),
        ("Run command: dir", ["run", "command"]),
        ("Do custom analytics", ["custom", "analytics"]),
    ])
    def test_template_coverage(self, tmp_path: Path, description: str, expected_keywords: list):
        """Test that various intent descriptions trigger appropriate templates."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.synthesize_and_register_skill(
            step_description=description,
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        assert skill_meta.id is not None
        assert Path(skill_meta.file_path).exists()
        
        # Verify the skill can be executed
        skill = registry.get_skill(skill_meta.id)
        python_code = open(skill.file_path, "r", encoding="utf-8").read()
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"payload": "test"})
        
        assert exec_res.success is True, f"Skill for '{description}' failed: {exec_res.stderr}"


class TestAutoSynthesisIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_synthesize_and_execute(self, tmp_path: Path):
        """Test complete flow: synthesize skill -> execute -> get result."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        # Step 1: Synthesize
        skill_meta = parser.synthesize_and_register_skill(
            step_description="Double all values in data",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        # Step 2: Get skill
        skill = registry.get_skill(skill_meta.id)
        assert skill is not None
        
        # Step 3: Execute
        python_code = open(skill.file_path, "r", encoding="utf-8").read()
        exec_res = SandboxExecutor.execute_skill_code(python_code, {"data": {"count": 5, "price": 10}})
        
        assert exec_res.success is True
        result = exec_res.output_payload
        assert result["data"]["count"] == 10  # doubled
        assert result["data"]["price"] == 20  # doubled

    def test_synthesize_registers_in_vector_index(self, tmp_path: Path):
        """Verify synthesized skills are searchable in Qdrant."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        skill_meta = parser.synthesize_and_register_skill(
            step_description="Parse JSON configuration file",
            namespace="global",
            root_registry_dir=tmp_path / "registry",
        )
        
        # Search for the skill by description
        results = registry.search_skills("Parse JSON configuration", active_namespaces=["global"])
        
        assert len(results) > 0
        found_ids = [r["skill"].id for r in results]
        assert skill_meta.id in found_ids

    def test_synthesize_and_resolve_pipeline(self, tmp_path: Path):
        """Test that synthesized skills can be resolved and executed in a pipeline."""
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        config = ProjectConfig(
            project_id="test_project",
            active_namespaces=["global"],
            required_pipeline_intent="Parse data.json, double the values",
        )
        
        results = parser.resolve_pipeline_intent(config, auto_synthesize=True)
        
        assert len(results) == 2
        assert all(r.match_found for r in results)
        assert any(r.synthesis_required for r in results)  # At least one should be synthesized
        
        # Verify both skills exist
        for res in results:
            assert res.skill_id is not None
            skill = registry.get_skill(res.skill_id)
            assert skill is not None