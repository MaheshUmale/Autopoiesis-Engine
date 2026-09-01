"""Shared pipeline execution logic for MCP server tools.

This module extracts the common pipeline execution pattern used by
run_intent_handler, synthesize_and_run, and amf_genesis_synthesize
to eliminate code duplication (GAP-L2).

Fixes:
- GAP-L2: Code duplication eliminated via PipelineExecutor class
- GAP-L3: Healing cache integration (post-failure only, not pre-check)
- N-1: EventEmitter integration for skill execution events
- N-2: Removed ineffective pre-execution healing check
"""

import json
import logging
import re
import sqlite3
import uuid
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from autopoiesis.registry.manager import RegistryManager
from autopoiesis.sandbox.executor import SandboxExecutor
from autopoiesis.core.intent import LookAheadParser, ProjectConfig
from autopoiesis.core.session import AgentSessionManager
from autopoiesis.core.observability import AgenticObservability
from autopoiesis.core.healing import HealLearningCache
from autopoiesis.core.events import EventEmitter, Event, SystemEvents
from autopoiesis.cli.init import PlatformAdapter

logger = logging.getLogger("autopoiesis.mcp.pipeline")


# ANSI Color constants for visual terminal feedback
RESET = "\033[0m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"


def log_visual_activity(tag: str, message: str, color: str = CYAN) -> None:
    """Logs a highlighted real-time visual console entry.

    Uses logging instead of print() for consistent log output (fixes L-1).
    """
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    logger.info(f"{BOLD}{color}[AUTOPOIESIS | {timestamp}] [{tag}]{RESET} {message}")


def record_mcp_tool_trace(
    base_dir: str,
    skill_id: str,
    success: bool,
    output: Dict[str, Any],
    stdout: str = "",
    stderr: str = "",
    execution_time_sec: float = 0.012,
    error_type: str | None = None,
):
    """Logs an execution trace file in .autopoiesis/traces/ and updates SQLite execution_history table."""
    b_path = PlatformAdapter.sanitize_path(base_dir)
    traces_dir = b_path / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    exec_uuid = f"mcp_{uuid.uuid4().hex[:8]}"
    trace_file = traces_dir / f"{exec_uuid}.json"

    trace_entry = [{
        "node_id": "mcp_call",
        "skill_id": skill_id,
        "success": success,
        "error_type": error_type,
        "execution_time_sec": execution_time_sec,
        "stdout": stdout or f"Executed tool: {skill_id}",
        "stderr": stderr,
        "output": output,
        "timestamp": datetime.datetime.now().isoformat()
    }]
    trace_file.write_text(json.dumps(trace_entry, indent=2), encoding="utf-8")

    db_path = b_path / "autopoiesis.db"
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO execution_history (id, skill_id, success, execution_time_sec) VALUES (?, ?, ?, ?)",
                (exec_uuid, skill_id, 1 if success else 0, execution_time_sec),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.warning(f"Failed to record MCP tool trace for '{skill_id}': {e}")
    except Exception as e:
        logger.error(f"Unexpected error recording trace: {e}", exc_info=True)


class PipelineExecutor:
    """Shared pipeline execution engine for intent resolution and skill execution.

    Eliminates code duplication between run_intent_handler, synthesize_and_run,
    and amf_genesis_synthesize.

    Features:
    - EventEmitter integration for real-time event notifications
    - Post-failure healing cache integration
    - Session persistence and observability tracking
    """

    def __init__(
        self,
        base_dir: str = ".autopoiesis",
        session_mgr: Optional[AgentSessionManager] = None,
        observability: Optional[AgenticObservability] = None,
        heal_cache: Optional[HealLearningCache] = None,
        event_emitter: Optional[EventEmitter] = None,
    ):
        self.base_dir = base_dir
        self._session_mgr = session_mgr or AgentSessionManager(base_dir=base_dir)
        self._observability = observability or AgenticObservability(base_dir=base_dir)
        self._heal_cache = heal_cache or HealLearningCache(base_dir=base_dir)
        # EventEmitter integration (N-1)
        self._events = event_emitter or EventEmitter(base_dir=base_dir)

    def get_registry(self) -> RegistryManager:
        return RegistryManager(base_dir=self.base_dir)

    def execute_pipeline(
        self,
        intent: str,
        active_namespaces: List[str] = None,
        agent_id: str = "default_agent",
        session_id: str = "",
        genesis_mode: bool = False,
        auto_heal: bool = True,
    ) -> Dict[str, Any]:
        """Execute a multi-step intent pipeline.

        Args:
            intent: Natural language intent to execute
            active_namespaces: Namespaces to search for skills
            agent_id: Agent identifier for session tracking
            session_id: Existing session ID (creates new if empty)
            genesis_mode: Use Level 0 Genesis synthesis for novel skills
            auto_heal: Check healing cache after execution failure

        Returns:
            Dict with intent, steps, execution_log, final_payload, stats
        """
        log_visual_activity("MCP AGENT ENGAGED", f"Executing intent: '{intent}'", MAGENTA)

        # Emit pipeline started event
        self._events.emit(Event(
            event_type=SystemEvents.WORKFLOW_STARTED,
            source="PipelineExecutor",
            payload={"intent": intent, "agent_id": agent_id, "genesis_mode": genesis_mode},
        ))

        reg = self.get_registry()
        parser = LookAheadParser(reg)
        config = ProjectConfig(
            project_id="mcp_intent_exec",
            active_namespaces=active_namespaces or ["global"],
            required_pipeline_intent=intent,
        )
        root_registry_dir = Path(self.base_dir) / "registry"
        results = parser.resolve_pipeline_intent(
            config,
            auto_synthesize=True,
            root_registry_dir=root_registry_dir,
            genesis_mode=genesis_mode,
        )
        output_data = [res.model_dump() for res in results]

        current_payload = {
            "intent": intent,
            "active_namespaces": active_namespaces or ["global"],
            "_cwd": str(Path.cwd()),
        }
        execution_log = []

        # Ensure agent session exists
        if not session_id:
            session_id = self._session_mgr.get_or_create_session(
                agent_id=agent_id,
                namespace=active_namespaces[0] if active_namespaces else "global",
            )

        synthesized_count = 0
        reused_count = 0
        failed_count = 0
        synthesis_pending = []

        for res in results:
            if res.match_found and res.skill_id:
                skill = reg.get_skill(res.skill_id)
                if not skill or not skill.file_path:
                    execution_log.append({
                        "step": res.step_description,
                        "skill_id": res.skill_id,
                        "status": "error",
                        "error": f"Skill '{res.skill_id}' not found.",
                    })
                    failed_count += 1
                    # Emit skill failed event
                    self._events.emit(Event(
                        event_type=SystemEvents.SKILL_FAILED,
                        source="PipelineExecutor",
                        payload={"skill_id": res.skill_id, "error": "Skill not found"},
                    ))
                    continue

                if res.synthesis_required:
                    synthesized_count += 1
                    # Emit skill synthesized event
                    self._events.emit(Event(
                        event_type=SystemEvents.SKILL_SYNTHESIZED,
                        source="PipelineExecutor",
                        payload={"skill_id": res.skill_id, "step": res.step_description},
                    ))
                else:
                    reused_count += 1

                python_code = open(skill.file_path, "r", encoding="utf-8").read()
                step_lower = res.step_description.lower()
                is_parse_step = "parse" in step_lower or "read" in step_lower or "load" in step_lower

                # Pre-load data for parse steps
                if is_parse_step and "data" not in current_payload:
                    file_path = self._extract_file_path(res.step_description, current_payload)
                    if file_path and not Path(file_path).is_absolute():
                        file_path = str(Path.cwd() / file_path)
                    if file_path and Path(file_path).exists():
                        try:
                            current_payload["data"] = self._load_file_data(file_path)
                        except Exception:
                            pass

                # Inject session context into payload
                current_payload["_session_id"] = session_id
                current_payload["_agent_id"] = agent_id
                current_payload["_memory"] = self._session_mgr.get_all_memory(session_id)

                log_visual_activity(
                    "PIPELINE EXEC",
                    f"Running skill '{res.skill_id}' for step: '{res.step_description}'",
                    YELLOW,
                )

                exec_res = SandboxExecutor.execute_skill_code(python_code, current_payload)

                # Record trace
                record_mcp_tool_trace(
                    base_dir=self.base_dir,
                    skill_id=res.skill_id,
                    success=exec_res.success,
                    output=exec_res.output_payload,
                    stdout=exec_res.stdout,
                    stderr=exec_res.stderr,
                    execution_time_sec=exec_res.execution_time_sec,
                    error_type=exec_res.error_type,
                )

                # Record in observability
                payload_bytes = len(json.dumps(exec_res.output_payload).encode("utf-8"))
                self._observability.record_execution(
                    skill_id=res.skill_id,
                    execution_time_sec=exec_res.execution_time_sec,
                    success=exec_res.success,
                    error_type=exec_res.error_type,
                    payload_size_bytes=payload_bytes,
                )

                if exec_res.success:
                    current_payload = exec_res.output_payload
                    execution_log.append({
                        "step": res.step_description,
                        "skill_id": res.skill_id,
                        "status": "success",
                        "synthesized": res.synthesis_required,
                        "output": exec_res.output_payload,
                        "execution_time_sec": exec_res.execution_time_sec,
                    })
                    log_visual_activity("PIPELINE SUCCESS", f"Skill '{res.skill_id}' completed.", GREEN)
                    self._session_mgr.append_history(
                        session_id, res.skill_id, current_payload, exec_res.output_payload, True
                    )
                    # Emit skill executed event
                    self._events.emit(Event(
                        event_type=SystemEvents.SKILL_EXECUTED,
                        source="PipelineExecutor",
                        payload={
                            "skill_id": res.skill_id,
                            "execution_time_sec": exec_res.execution_time_sec,
                            "synthesized": res.synthesis_required,
                        },
                    ))
                else:
                    # Try auto-heal on failure (post-failure only, fixes N-2)
                    healed = False
                    if auto_heal and self._heal_cache:
                        suggested_fix = self._heal_cache.find_suggested_fix(
                            skill_id=res.skill_id,
                            error_type=exec_res.error_type or "LogicError",
                            error_msg=exec_res.stderr,
                        )
                        if suggested_fix and suggested_fix.fix_code_patch:
                            log_visual_activity(
                                "AUTO-HEAL",
                                f"Retrying '{res.skill_id}' with learned fix",
                                GREEN,
                            )
                            patched_code = self._apply_fix_to_code(python_code, suggested_fix.fix_code_patch)
                            retry_res = SandboxExecutor.execute_skill_code(patched_code, current_payload)
                            if retry_res.success:
                                current_payload = retry_res.output_payload
                                execution_log.append({
                                    "step": res.step_description,
                                    "skill_id": res.skill_id,
                                    "status": "success",
                                    "healed": True,
                                    "output": retry_res.output_payload,
                                    "execution_time_sec": retry_res.execution_time_sec,
                                })
                                self._session_mgr.append_history(
                                    session_id, res.skill_id, current_payload, retry_res.output_payload, True
                                )
                                self._heal_cache.record_outcome(suggested_fix.pattern_id, True)
                                healed = True
                                # Emit healing applied event
                                self._events.emit(Event(
                                    event_type=SystemEvents.HEALING_APPLIED,
                                    source="PipelineExecutor",
                                    payload={
                                        "skill_id": res.skill_id,
                                        "pattern_id": suggested_fix.pattern_id,
                                    },
                                ))
                            else:
                                self._heal_cache.record_outcome(suggested_fix.pattern_id, False)
                                # Emit healing failed event
                                self._events.emit(Event(
                                    event_type=SystemEvents.HEALING_FAILED,
                                    source="PipelineExecutor",
                                    payload={
                                        "skill_id": res.skill_id,
                                        "pattern_id": suggested_fix.pattern_id,
                                    },
                                ))

                    if not healed:
                        execution_log.append({
                            "step": res.step_description,
                            "skill_id": res.skill_id,
                            "status": "error",
                            "synthesized": res.synthesis_required,
                            "error": exec_res.stderr,
                            "error_type": exec_res.error_type,
                        })
                        failed_count += 1
                        log_visual_activity(
                            "PIPELINE ERROR",
                            f"Skill '{res.skill_id}' failed: {exec_res.stderr}",
                            YELLOW,
                        )
                        self._session_mgr.append_history(
                            session_id, res.skill_id, current_payload, {"error": exec_res.stderr}, False, error=exec_res.stderr
                        )
                        # Emit skill failed event
                        self._events.emit(Event(
                            event_type=SystemEvents.SKILL_FAILED,
                            source="PipelineExecutor",
                            payload={
                                "skill_id": res.skill_id,
                                "error": exec_res.stderr,
                                "error_type": exec_res.error_type,
                            },
                        ))
                        break
            elif res.synthesis_required and not res.skill_id:
                # Complex pattern: AI agent needs to generate code
                log_visual_activity(
                    "AI SYNTHESIS REQUIRED",
                    f"Step '{res.step_description}' requires AI-generated skill",
                    MAGENTA,
                )
                self._events.emit(Event(
                    event_type=SystemEvents.SKILL_SYNTHESIZED,
                    source="PipelineExecutor",
                    payload={
                        "step": res.step_description,
                        "status": "synthesis_needed",
                        "similarity_score": res.similarity_score,
                    },
                ))
                execution_log.append({
                    "step": res.step_description,
                    "status": "synthesis_needed",
                    "similarity_score": res.similarity_score,
                    "message": "Complex pattern detected. AI agent must generate custom code using submit_ai_skill().",
                })
                synthesis_pending.append({
                    "step": res.step_description,
                    "context": current_payload.copy(),
                })
            else:
                execution_log.append({
                    "step": res.step_description,
                    "status": "skipped",
                    "reason": "No matching skill found.",
                })
                failed_count += 1

        # Record overall trace
        record_mcp_tool_trace(
            base_dir=self.base_dir,
            skill_id="pipeline_execution",
            success=failed_count == 0,
            output={"intent": intent, "steps": output_data, "execution_log": execution_log, "final_payload": current_payload},
            stdout=f"Pipeline: '{intent}' -> {len(results)} steps ({synthesized_count} synthesized, {reused_count} reused).",
            execution_time_sec=0.025,
        )

        log_visual_activity(
            "PIPELINE COMPLETE",
            f"Resolved & executed {len(results)} steps.",
            GREEN,
        )

        # Emit workflow completed/failed event
        if failed_count == 0:
            self._events.emit(Event(
                event_type=SystemEvents.WORKFLOW_COMPLETED,
                source="PipelineExecutor",
                payload={"intent": intent, "steps": len(results)},
            ))
        else:
            self._events.emit(Event(
                event_type=SystemEvents.WORKFLOW_FAILED,
                source="PipelineExecutor",
                payload={"intent": intent, "failed_steps": failed_count},
            ))

        return {
            "intent": intent,
            "steps": output_data,
            "execution_log": execution_log,
            "final_payload": current_payload,
            "stats": {
                "total_steps": len(results),
                "synthesized": synthesized_count,
                "reused": reused_count,
                "failed": failed_count,
            },
            "genesis": genesis_mode,
            "synthesis_pending": synthesis_pending,
            "status": "synthesis_needed" if synthesis_pending else ("completed" if failed_count == 0 else "failed"),
        }

    def _extract_file_path(self, step_description: str, current_payload: Dict[str, Any]) -> str:
        """Extract file path from step description or current payload."""
        file_path = current_payload.get("file_path", "")
        if not file_path:
            path_matches = re.findall(
                r'(?:[a-zA-Z]:\\|/|\./)?[\w\.-]+(?:\\[\w\.-]+|/[\w\.-]+)*',
                step_description,
            )
            for match in reversed(path_matches):
                if "." in match or "\\" in match or "/" in match:
                    file_path = match
                    break
        return file_path

    def _load_file_data(self, file_path: str) -> Any:
        """Load data from a file (JSON or CSV)."""
        if file_path.endswith(".csv"):
            import csv
            data: list = []
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    data.append([
                        float(cell)
                        if cell.replace(".", "", 1).replace("-", "", 1).isdigit()
                        else cell
                        for cell in row
                    ])
            return data
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

    @staticmethod
    def apply_fix_to_code(original_code: str, fix_patch: str) -> str:
        """Apply a healing fix patch to skill code.

        The fix_patch is appended before the main() function or at the end.
        This is a shared utility for all executors.

        Args:
            original_code: Original skill Python code
            fix_patch: Code patch to apply

        Returns:
            Patched code
        """
        if not fix_patch or not fix_patch.strip():
            return original_code
        # Simple patching: append fix code before main() or at end
        if "def main(" in original_code:
            # Insert fix before main()
            parts = original_code.split("def main(", 1)
            return parts[0] + fix_patch + "\ndef main(" + parts[1]
        return original_code + "\n" + fix_patch

    def retry_with_ai_skills(
        self,
        intent: str,
        active_namespaces: List[str] = None,
        agent_id: str = "default_agent",
        session_id: str = "",
        genesis_mode: bool = False,
        auto_heal: bool = True,
    ) -> Dict[str, Any]:
        """Retry pipeline execution after AI skills have been submitted.

        This method re-runs the pipeline, which will now find the newly
        registered AI-generated skills in the registry.

        Returns:
            Same as execute_pipeline, but with retry context
        """
        log_visual_activity(
            "AI RETRY",
            f"Retrying pipeline after AI skill submission",
            MAGENTA,
        )
        result = self.execute_pipeline(
            intent=intent,
            active_namespaces=active_namespaces,
            agent_id=agent_id,
            session_id=session_id,
            genesis_mode=genesis_mode,
            auto_heal=auto_heal,
        )
        result["retry"] = True
        return result
