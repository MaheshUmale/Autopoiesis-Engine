"""AMF Healing Adapter — agent-aware self-healing pattern integration."""

from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel

from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.core.healing import HealLearningCache
from autopoiesis.amf.registry import AMFRegistry


class HealingSuggestion(BaseModel):
    """Healing suggestion for a failed capability."""
    pattern_id: Optional[str] = None
    agent_id: str
    capability: str
    error_type: str
    fix_description: str
    fix_code_patch: str
    success_rate: float = 0.0
    source: str = "cache"  # "cache" or "generic"


class AMFHealingAdapter:
    """Wraps HealLearningCache with AMF agent-aware healing strategies.

    Provides:
    - Capability-specific fix suggestions
    - Learned pattern lookup by agent + capability + error
    - Generic fallback patches when no learned pattern exists
    """

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self._heal_cache = HealLearningCache(base_dir=base_dir)
        self._registry = AMFRegistry(base_dir=base_dir)

    def heal_capability_failure(
        self,
        agent_id: str,
        capability: str,
        error_type: str,
        error_msg: str,
        skill_id: Optional[str] = None,
    ) -> HealingSuggestion:
        """Suggests a fix for a failed capability invocation.

        Args:
            agent_id: Agent that experienced the failure
            capability: Capability name that failed
            error_type: Classification of the error
            error_msg: Raw error message/stderr
            skill_id: Optional direct skill ID if known

        Returns:
            HealingSuggestion with fix details
        """
        # Resolve skill_id from agent's capabilities if not provided
        if not skill_id:
            agent_def = self._registry.get_agent_def(agent_id)
            if agent_def:
                for cap in agent_def.capabilities:
                    if cap.name == capability:
                        skill_id = cap.skill_id
                        break

        skill_id = skill_id or f"{agent_id}.{capability}"

        # Check learned cache first
        suggested = self._heal_cache.find_suggested_fix(
            skill_id=skill_id,
            error_type=error_type,
            error_msg=error_msg,
        )

        if suggested:
            return HealingSuggestion(
                pattern_id=suggested.pattern_id,
                agent_id=agent_id,
                capability=capability,
                error_type=error_type,
                fix_description=suggested.fix_description,
                fix_code_patch=suggested.fix_code_patch,
                success_rate=suggested.success_count / (suggested.success_count + suggested.failure_count)
                if (suggested.success_count + suggested.failure_count) > 0
                else 0.0,
                source="cache",
            )

        # Generic fallback patches
        generic_patch, generic_desc = self._apply_generic_patch(error_type)
        return HealingSuggestion(
            agent_id=agent_id,
            capability=capability,
            error_type=error_type,
            fix_description=generic_desc,
            fix_code_patch=generic_patch,
            success_rate=0.0,
            source="generic",
        )

    def _apply_generic_patch(self, error_type: str) -> tuple[str, str]:
        """Applies generic diagnostic patches based on error type."""
        if error_type == "SchemaValidationError":
            return ("", "Generic patch: upstream input repair required")
        elif error_type in ("EnvironmentalError", "TimeoutError"):
            return ("# Auto-patched: added memory chunking / buffer flush\n", "Generic patch: memory chunking / buffer flush")
        elif error_type == "NetworkError":
            return ("import time\n# Auto-patched: added retry delay\n", "Generic patch: retry delay / time import")
        else:
            return ("# Auto-patched: logic hotfix\n", "Generic patch: logic hotfix")

    def learn_from_failure(
        self,
        agent_id: str,
        capability: str,
        error_type: str,
        error_msg: str,
        fix_code_patch: str,
        fix_description: str,
        skill_id: Optional[str] = None,
    ) -> str:
        """Learns a new error→fix pattern for future use.

        Args:
            agent_id: Agent that experienced the failure
            capability: Capability name that failed
            error_type: Classification of the error
            error_msg: Raw error message/stderr
            fix_code_patch: The code patch that fixed the issue
            fix_description: Human-readable description of the fix
            skill_id: Optional direct skill ID

        Returns:
            pattern_id of the learned pattern
        """
        if not skill_id:
            agent_def = self._registry.get_agent_def(agent_id)
            if agent_def:
                for cap in agent_def.capabilities:
                    if cap.name == capability:
                        skill_id = cap.skill_id
                        break

        skill_id = skill_id or f"{agent_id}.{capability}"

        pattern = self._heal_cache.learn_pattern(
            skill_id=skill_id,
            error_type=error_type,
            error_msg=error_msg,
            fix_code_patch=fix_code_patch,
            fix_description=fix_description,
        )
        return pattern.pattern_id

    def record_healing_outcome(self, pattern_id: str, success: bool) -> bool:
        """Records whether a healing pattern worked.

        Args:
            pattern_id: ID of the healing pattern
            success: Whether the fix worked

        Returns:
            True if pattern was found and updated
        """
        return self._heal_cache.record_outcome(pattern_id=pattern_id, success=success)

    def get_patterns_for_agent(self, agent_id: str) -> list:
        """Returns all learned healing patterns for an agent's capabilities."""
        agent_def = self._registry.get_agent_def(agent_id)
        if not agent_def:
            return []

        patterns = []
        for cap in agent_def.capabilities:
            agent_patterns = self._heal_cache.get_patterns_for_skill(cap.skill_id)
            for p in agent_patterns:
                patterns.append({
                    "pattern_id": p.pattern_id,
                    "capability": cap.name,
                    "skill_id": p.skill_id,
                    "error_type": p.error_type,
                    "fix_description": p.fix_description,
                    "success_count": p.success_count,
                    "failure_count": p.failure_count,
                    "success_rate": p.success_count / (p.success_count + p.failure_count)
                    if (p.success_count + p.failure_count) > 0
                    else 0.0,
                })
        return patterns

    def get_stats(self) -> Dict[str, Any]:
        """Returns healing cache statistics."""
        return self._heal_cache.get_stats()
