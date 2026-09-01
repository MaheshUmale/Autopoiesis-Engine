"""
End-to-End Test: AI-Driven Skill Synthesis Pipeline
====================================================

This test demonstrates:
1. Qdrant fallback when Qdrant is unavailable (other client scenario)
2. Complete AI skill synthesis workflow:
   - Complex intent submission
   - Pattern classification (simple vs complex)
   - Template synthesis for simple patterns
   - AI agent intervention for complex patterns
   - Skill registration and reuse

Run with: python tests/test_e2e_ai_synthesis.py
"""

import os
import sys
import json
import shutil
import tempfile
import sqlite3
from pathlib import Path

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from autopoiesis.registry.manager import RegistryManager
from autopoiesis.core.intent import LookAheadParser, ProjectConfig
from autopoiesis.mcp.pipeline import PipelineExecutor
from autopoiesis.sandbox.executor import SandboxExecutor


def create_registry_no_qdrant(base_dir):
    """Create a registry with Qdrant disabled (simulates other client access)."""
    # Clear Qdrant instances cache to ensure new instances also have Qdrant disabled
    RegistryManager._qdrant_instances.clear()
    RegistryManager._qdrant_available.clear()

    reg = RegistryManager.__new__(RegistryManager)
    reg.base_dir = Path(base_dir)
    reg.base_dir.mkdir(parents=True, exist_ok=True)
    reg.db_path = reg.base_dir / "autopoiesis.db"
    reg.qdrant_dir = reg.base_dir / "qdrant"
    reg.qdrant_dir.mkdir(parents=True, exist_ok=True)

    # Initialize SQLite
    from autopoiesis.storage.migrations import migrate_autopoiesis_db
    migrate_autopoiesis_db(reg.db_path)

    # Explicitly disable Qdrant
    reg.qdrant = None
    reg._qdrant_available = False

    # Store in class-level cache so other instances also see Qdrant as unavailable
    key = str(reg.qdrant_dir.resolve())
    RegistryManager._qdrant_instances[key] = None
    RegistryManager._qdrant_available[key] = False

    return reg


class TestResults:
    """Collects and displays test results."""
    def __init__(self):
        self.results = []

    def add(self, name, passed, details=""):
        self.results.append({
            "name": name,
            "passed": passed,
            "details": details,
        })
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if details:
            print(f"         {details}")

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        print("\n" + "="*70)
        print(f"TEST SUMMARY: {passed}/{total} passed, {failed} failed")
        print("="*70)
        return failed == 0


def test_qdrant_fallback(results):
    """Test Qdrant fallback when Qdrant is unavailable."""
    print("\n" + "="*70)
    print("TEST: Qdrant Fallback (Other Client Access Scenario)")
    print("="*70)

    test_dir = tempfile.mkdtemp(prefix="autopoiesis_test_")
    try:
        base_dir = os.path.join(test_dir, ".autopoiesis")
        reg = create_registry_no_qdrant(base_dir)

        # Test 1: Qdrant is None
        results.add(
            "Qdrant set to None when unavailable",
            reg.qdrant is None,
            f"qdrant={reg.qdrant}"
        )

        # Test 2: _qdrant_available is False
        results.add(
            "Qdrant availability flag is False",
            reg._qdrant_available is False,
            f"_qdrant_available={reg._qdrant_available}"
        )

        # Test 3: Register skill works without Qdrant
        skill_code = '''
def main(inputs: dict) -> dict:
    """Test skill."""
    return {"status": "success", "data": inputs.get("data", {})}
'''
        meta = reg.register_skill(
            skill_id="global.test_skill",
            namespace="global",
            scope_level="core",
            description="Test skill for Qdrant fallback",
            inputs={"type": "object", "properties": {"data": {}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}}},
            python_code=skill_code,
        )
        results.add(
            "Register skill without Qdrant",
            meta.id == "global.test_skill",
            f"skill_id={meta.id}"
        )

        # Test 4: Search uses SQLite fallback
        search_results = reg.search_skills("test skill", active_namespaces=["global"])
        results.add(
            "Search uses SQLite fallback",
            len(search_results) > 0 and search_results[0]["skill"].id == "global.test_skill",
            f"found {len(search_results)} results"
        )

        # Test 5: Scores are normalized (0-1 range)
        all_normalized = all(0 <= r["score"] <= 1 for r in search_results)
        results.add(
            "Search scores normalized (0-1)",
            all_normalized,
            f"scores: {[r['score'] for r in search_results]}"
        )

        # Test 6: Multiple skills with different relevance
        skills_data = [
            ("global.data_transform", "Transform data by doubling numeric values"),
            ("global.data_filter", "Filter data based on conditions"),
            ("global.risk_score", "Calculate risk score for loan application"),
        ]
        for skill_id, desc in skills_data:
            code = f'''
def main(inputs: dict) -> dict:
    """{desc}"""
    return {{"status": "success", "output": inputs.get("data", {{}})}}
'''
            reg.register_skill(
                skill_id=skill_id,
                namespace="global",
                scope_level="core",
                description=desc,
                inputs={"type": "object", "properties": {"data": {}}},
                outputs={"type": "object", "properties": {"status": {"type": "string"}}},
                python_code=code,
            )

        search_results = reg.search_skills("transform data", active_namespaces=["global"])
        best_match = search_results[0]["skill"].id if search_results else None
        results.add(
            "Best match for 'transform data'",
            best_match == "global.data_transform",
            f"best_match={best_match}, scores={[r['score'] for r in search_results]}"
        )

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        RegistryManager._qdrant_instances.clear()


def test_pattern_classification(results):
    """Test pattern classification (simple vs complex)."""
    print("\n" + "="*70)
    print("TEST: Pattern Classification (Simple vs Complex)")
    print("="*70)

    test_dir = tempfile.mkdtemp(prefix="autopoiesis_test_")
    try:
        base_dir = os.path.join(test_dir, ".autopoiesis")
        reg = create_registry_no_qdrant(base_dir)
        parser = LookAheadParser(reg)

        # Simple patterns
        simple_patterns = [
            "double all numeric values in the dataset",
            "filter rows where value is greater than 10",
            "calculate sum and average of sales data",
            "save results to output.json",
            "load data from input.csv",
        ]

        for pattern in simple_patterns:
            is_simple = parser._is_simple_pattern(pattern)
            results.add(
                f"Simple: '{pattern[:40]}...'",
                is_simple,
                f"is_simple={is_simple}"
            )

        # Complex patterns
        complex_patterns = [
            "calculate risk score for loan application based on credit history",
            "determine eligibility for insurance policy based on medical records",
            "validate compliance with GDPR regulations for user data processing",
            "extract features from text data for sentiment classification",
            "optimize portfolio allocation based on risk tolerance",
        ]

        for pattern in complex_patterns:
            is_simple = parser._is_simple_pattern(pattern)
            results.add(
                f"Complex: '{pattern[:40]}...'",
                not is_simple,
                f"is_simple={is_simple} (should be False)"
            )

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        RegistryManager._qdrant_instances.clear()


def test_template_synthesis_simple_patterns(results):
    """Test template synthesis for simple patterns."""
    print("\n" + "="*70)
    print("TEST: Template Synthesis for Simple Patterns")
    print("="*70)

    test_dir = tempfile.mkdtemp(prefix="autopoiesis_test_")
    try:
        base_dir = os.path.join(test_dir, ".autopoiesis")
        reg = create_registry_no_qdrant(base_dir)
        parser = LookAheadParser(reg)

        config = ProjectConfig(
            project_id="test_project",
            active_namespaces=["global"],
            required_pipeline_intent="double all numeric values in the dataset",
        )

        results_list = parser.resolve_pipeline_intent(
            config,
            auto_synthesize=True,
            root_registry_dir=Path(base_dir) / "registry",
        )

        result = results_list[0]
        results.add(
            "Simple pattern synthesized",
            result.match_found and result.synthesis_required,
            f"match_found={result.match_found}, synthesis_required={result.synthesis_required}"
        )

        results.add(
            "Skill ID generated",
            result.skill_id is not None and result.skill_id.startswith("global."),
            f"skill_id={result.skill_id}"
        )

        # Verify skill registered
        skill = reg.get_skill(result.skill_id)
        results.add(
            "Skill registered in registry",
            skill is not None and skill.file_path is not None,
            f"file_path={skill.file_path if skill else 'None'}"
        )

        # Verify skill file exists
        if skill and skill.file_path:
            results.add(
                "Skill file exists on disk",
                Path(skill.file_path).exists(),
                f"path={skill.file_path}"
            )

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        RegistryManager._qdrant_instances.clear()


def test_complex_pattern_ai_synthesis(results):
    """Test that complex patterns trigger AI synthesis requirement."""
    print("\n" + "="*70)
    print("TEST: Complex Pattern Triggers AI Synthesis")
    print("="*70)

    test_dir = tempfile.mkdtemp(prefix="autopoiesis_test_")
    try:
        base_dir = os.path.join(test_dir, ".autopoiesis")
        reg = create_registry_no_qdrant(base_dir)
        parser = LookAheadParser(reg)

        config = ProjectConfig(
            project_id="test_project",
            active_namespaces=["global"],
            required_pipeline_intent="calculate risk score for loan application based on credit history",
        )

        results_list = parser.resolve_pipeline_intent(
            config,
            auto_synthesize=True,
            root_registry_dir=Path(base_dir) / "registry",
        )

        result = results_list[0]
        results.add(
            "Complex pattern NOT auto-synthesized",
            not result.match_found and result.synthesis_required,
            f"match_found={result.match_found}, synthesis_required={result.synthesis_required}"
        )

        results.add(
            "Skill ID is None (needs AI)",
            result.skill_id is None,
            f"skill_id={result.skill_id}"
        )

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        RegistryManager._qdrant_instances.clear()


def test_genesis_mode_synthesizes_all(results):
    """Test genesis mode synthesizes both simple and complex patterns."""
    print("\n" + "="*70)
    print("TEST: Genesis Mode Synthesizes All Patterns")
    print("="*70)

    test_dir = tempfile.mkdtemp(prefix="autopoiesis_test_")
    try:
        base_dir = os.path.join(test_dir, ".autopoiesis")
        reg = create_registry_no_qdrant(base_dir)
        parser = LookAheadParser(reg)

        config = ProjectConfig(
            project_id="test_project",
            active_namespaces=["global"],
            required_pipeline_intent="calculate risk score for loan application",
        )

        results_list = parser.resolve_pipeline_intent(
            config,
            auto_synthesize=True,
            root_registry_dir=Path(base_dir) / "registry",
            genesis_mode=True,
        )

        result = results_list[0]
        results.add(
            "Genesis mode synthesizes complex pattern",
            result.match_found and result.synthesis_required and result.skill_id is not None,
            f"match_found={result.match_found}, skill_id={result.skill_id}"
        )

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        RegistryManager._qdrant_instances.clear()


def test_full_ai_synthesis_workflow(results):
    """Test complete workflow: intent → synthesis_needed → AI generates → retry."""
    print("\n" + "="*70)
    print("TEST: Full AI Synthesis Workflow")
    print("="*70)

    test_dir = tempfile.mkdtemp(prefix="autopoiesis_test_")
    try:
        base_dir = os.path.join(test_dir, ".autopoiesis")
        reg = create_registry_no_qdrant(base_dir)
        pipeline = PipelineExecutor(base_dir=base_dir)

        # Step 1: Submit complex intent
        complex_intent = "calculate risk score for loan application based on credit history"
        result = pipeline.execute_pipeline(
            intent=complex_intent,
            active_namespaces=["global"],
        )

        print(f"\n  Step 1: Initial Pipeline Execution")
        print(f"    Intent: {complex_intent}")
        print(f"    Status: {result['status']}")
        print(f"    Synthesis pending: {len(result['synthesis_pending'])}")

        results.add(
            "Step 1: Pipeline returns synthesis_needed",
            result["status"] == "synthesis_needed",
            f"status={result['status']}"
        )

        results.add(
            "Step 1: synthesis_pending has 1 item",
            len(result["synthesis_pending"]) == 1,
            f"pending={len(result['synthesis_pending'])}"
        )

        # Step 2: AI agent generates custom code
        ai_generated_code = '''
def main(inputs: dict) -> dict:
    """AI-generated skill: Calculate risk score for loan application."""
    credit_history = inputs.get("credit_history", {})
    
    # Risk scoring logic
    risk_factors = {
        "payment_history": credit_history.get("payment_history", 0.5),
        "credit_utilization": credit_history.get("credit_utilization", 0.3),
        "credit_age_years": credit_history.get("credit_age_years", 0),
        "recent_inquiries": credit_history.get("recent_inquiries", 0),
    }
    
    # Calculate risk score (0-100, lower is better)
    risk_score = (
        (1 - risk_factors["payment_history"]) * 30 +
        risk_factors["credit_utilization"] * 25 +
        max(0, 10 - risk_factors["credit_age_years"]) * 2 +
        risk_factors["recent_inquiries"] * 5
    )
    
    risk_level = "low" if risk_score < 30 else "medium" if risk_score < 60 else "high"
    
    return {
        "status": "success",
        "risk_score": round(risk_score, 2),
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "recommendation": "approve" if risk_level == "low" else "review" if risk_level == "medium" else "decline",
    }
'''

        # Verify the AI-generated code works
        test_result = SandboxExecutor.execute_skill_code(
            ai_generated_code,
            {"credit_history": {"payment_history": 0.9, "credit_utilization": 0.2, "credit_age_years": 5, "recent_inquiries": 1}}
        )
        results.add(
            "Step 2: AI-generated code executes successfully",
            test_result.success,
            f"success={test_result.success}, output={test_result.output_payload}"
        )

        # Register the AI skill
        skill_id = "global.calculate_risk_score_for_loan_application_based_on_credit_history"
        skill_meta = reg.register_skill(
            skill_id=skill_id,
            namespace="global",
            scope_level="ai_generated",
            description="AI-generated: Calculate risk score for loan application",
            inputs={"type": "object", "properties": {"credit_history": {}}},
            outputs={"type": "object", "properties": {"risk_score": {"type": "number"}, "risk_level": {"type": "string"}}},
            python_code=ai_generated_code,
            root_registry_dir=Path(base_dir) / "registry",
        )
        results.add(
            "Step 2: AI skill registered",
            skill_meta.id == skill_id,
            f"skill_id={skill_meta.id}"
        )

        # Step 3: Retry pipeline
        retry_result = pipeline.retry_with_ai_skills(
            intent=complex_intent,
            active_namespaces=["global"],
        )

        print(f"\n  Step 3: Pipeline Retry")
        print(f"    Status: {retry_result['status']}")
        print(f"    Synthesized: {retry_result['stats']['synthesized']}")
        print(f"    Failed: {retry_result['stats']['failed']}")

        results.add(
            "Step 3: Pipeline completes after retry",
            retry_result["status"] == "completed",
            f"status={retry_result['status']}"
        )

        results.add(
            "Step 3: No failures",
            retry_result["stats"]["failed"] == 0,
            f"failed={retry_result['stats']['failed']}"
        )

        # Step 4: Verify skill is reusable
        search_results = reg.search_skills("risk score loan", active_namespaces=["global"])
        found = any(r["skill"].id == skill_id for r in search_results)
        results.add(
            "Step 4: AI skill is reusable",
            found,
            f"found in search results: {found}"
        )

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        RegistryManager._qdrant_instances.clear()


def test_multi_step_pipeline(results):
    """Test pipeline with mixed complexity steps."""
    print("\n" + "="*70)
    print("TEST: Multi-Step Pipeline with Mixed Complexity")
    print("="*70)

    test_dir = tempfile.mkdtemp(prefix="autopoiesis_test_")
    try:
        base_dir = os.path.join(test_dir, ".autopoiesis")
        reg = create_registry_no_qdrant(base_dir)
        pipeline = PipelineExecutor(base_dir=base_dir)

        multi_intent = """
        load data from input.json,
        double all numeric values in the dataset,
        calculate risk score for loan application based on credit history,
        save results to output.json
        """

        result = pipeline.execute_pipeline(
            intent=multi_intent,
            active_namespaces=["global"],
        )

        print(f"\n  Intent: {multi_intent.strip()[:80]}...")
        print(f"  Status: {result['status']}")
        print(f"  Total steps: {result['stats']['total_steps']}")
        print(f"  Synthesized: {result['stats']['synthesized']}")
        print(f"  Failed: {result['stats']['failed']}")
        print(f"  Synthesis pending: {len(result['synthesis_pending'])}")

        for i, step in enumerate(result['steps']):
            print(f"\n    Step {i+1}: {step['step_description'][:50]}...")
            print(f"      Match found: {step['match_found']}")
            print(f"      Synthesis required: {step['synthesis_required']}")
            print(f"      Skill ID: {step.get('skill_id', 'N/A')}")

        results.add(
            "Multi-step pipeline has 4 steps",
            result['stats']['total_steps'] == 4,
            f"total_steps={result['stats']['total_steps']}"
        )

        results.add(
            "At least 1 step requires AI synthesis",
            len(result['synthesis_pending']) >= 1,
            f"synthesis_pending={len(result['synthesis_pending'])}"
        )

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        RegistryManager._qdrant_instances.clear()


def test_sandbox_execution(results):
    """Test skill execution in sandbox."""
    print("\n" + "="*70)
    print("TEST: Sandbox Execution")
    print("="*70)

    skill_code = '''
def main(inputs: dict) -> dict:
    """Test skill for sandbox execution."""
    data = inputs.get("data", [])
    if isinstance(data, list):
        doubled = [x * 2 if isinstance(x, (int, float)) else x for x in data]
        return {"status": "success", "data": doubled, "output": doubled}
    return {"status": "error", "error": "Expected list input"}
'''

    result = SandboxExecutor.execute_skill_code(
        skill_code,
        {"data": [1, 2, 3, 4, 5]}
    )

    results.add(
        "Sandbox execution succeeds",
        result.success,
        f"success={result.success}"
    )

    results.add(
        "Output is correct",
        result.output_payload.get("data") == [2, 4, 6, 8, 10] if result.success else False,
        f"output={result.output_payload.get('data') if result.success else 'N/A'}"
    )


def main():
    """Run all end-to-end tests."""
    print("="*70)
    print("END-TO-END TEST: AI-DRIVEN SKILL SYNTHESIS PIPELINE")
    print("="*70)

    results = TestResults()

    test_qdrant_fallback(results)
    test_pattern_classification(results)
    test_template_synthesis_simple_patterns(results)
    test_complex_pattern_ai_synthesis(results)
    test_genesis_mode_synthesizes_all(results)
    test_full_ai_synthesis_workflow(results)
    test_multi_step_pipeline(results)
    test_sandbox_execution(results)

    all_passed = results.summary()

    if all_passed:
        print("\n[OK] All tests passed! The AI-driven skill synthesis pipeline is working correctly.")
        print("\nKey findings:")
        print("  1. Qdrant fallback works - registry operates in SQLite-only mode when Qdrant is unavailable")
        print("  2. Pattern classification correctly distinguishes simple vs complex patterns")
        print("  3. Simple patterns are auto-synthesized via templates")
        print("  4. Complex patterns correctly trigger AI synthesis requirement")
        print("  5. Genesis mode can synthesize any pattern")
        print("  6. Full workflow works: intent -> synthesis_needed -> AI generates -> retry -> completed")
        print("  7. AI-generated skills are registered and reusable")
    else:
        print("\n✗ Some tests failed. Review the output above for details.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
