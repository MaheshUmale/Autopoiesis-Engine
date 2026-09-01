"""Heal Learning Cache — stores and reuses error→fix patterns across skill executions."""

import json
import hashlib
import logging
import threading
import time as _time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from autopoiesis.core.platform import PlatformAdapter

logger = logging.getLogger("autopoiesis.core.healing")

# Healing configuration (fixes L-3)
ERROR_SIGNATURE_MAX_CHARS = 200  # Max characters to use for error signature
ERROR_SIGNATURE_HASH_LENGTH = 16  # Length of MD5 hash for signature


class HealPattern(BaseModel):
    """A learned error→fix pattern for a specific skill."""
    pattern_id: str
    skill_id: str
    error_type: str
    error_signature: str  # hashed error message
    fix_code_patch: str
    fix_description: str
    success_count: int = 0
    failure_count: int = 0
    last_used_at: Optional[str] = None
    created_at: str


class HealLearningCache:
    """Persistent cache of error→fix patterns learned from past self-heal attempts.

    The cache:
    - Stores patterns keyed by (skill_id, error_type, error_signature)
    - Tracks success/failure rates for each pattern
    - Suggests the best-known fix for a new error based on historical effectiveness
    - Persists to disk under .autopoiesis/heal_cache/
    """

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self.cache_dir = self.base_dir / "heal_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._patterns: Dict[str, HealPattern] = {}
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Loads all persisted patterns from disk."""
        if not self.cache_dir.exists():
            return
        for p_file in self.cache_dir.glob("pattern_*.json"):
            try:
                data = json.loads(p_file.read_text(encoding="utf-8"))
                pattern = HealPattern(**data)
                self._patterns[pattern.pattern_id] = pattern
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"Failed to load pattern from {p_file.name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error loading pattern: {e}", exc_info=True)

    def _persist_pattern(self, pattern: HealPattern) -> None:
        """Persists a single pattern to disk."""
        target = self.cache_dir / f"pattern_{pattern.pattern_id}.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(pattern.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(target)

    def _compute_error_signature(self, error_msg: str) -> str:
        """Computes a stable signature for an error message."""
        # Take first N chars to get stable signature (fixes L-3)
        key_part = error_msg[:ERROR_SIGNATURE_MAX_CHARS] if error_msg else ""
        return hashlib.md5(key_part.encode("utf-8")).hexdigest()[:ERROR_SIGNATURE_HASH_LENGTH]

    def learn_pattern(
        self,
        skill_id: str,
        error_type: str,
        error_msg: str,
        fix_code_patch: str,
        fix_description: str,
    ) -> HealPattern:
        """Records a new error→fix pattern. If a similar one exists, updates success/failure counts."""
        signature = self._compute_error_signature(error_msg)
        # Look for existing pattern
        with self._lock:
            for existing in self._patterns.values():
                if (
                    existing.skill_id == skill_id
                    and existing.error_type == error_type
                    and existing.error_signature == signature
                ):
                    existing.success_count += 1
                    existing.last_used_at = self._now()
                    self._persist_pattern(existing)
                    return existing

            # Create new pattern
            pattern = HealPattern(
                pattern_id=f"pat_{int(_time.time() * 1000)}_{hashlib.md5(signature.encode()).hexdigest()[:6]}",
                skill_id=skill_id,
                error_type=error_type,
                error_signature=signature,
                fix_code_patch=fix_code_patch,
                fix_description=fix_description,
                created_at=self._now(),
            )
            self._patterns[pattern.pattern_id] = pattern
            self._persist_pattern(pattern)
            return pattern

    def find_suggested_fix(
        self,
        skill_id: str,
        error_type: str,
        error_msg: str,
    ) -> Optional[HealPattern]:
        """Finds the best matching fix from past experience."""
        signature = self._compute_error_signature(error_msg)
        with self._lock:
            best: Optional[HealPattern] = None
            best_score = 0.0
            for pattern in self._patterns.values():
                if pattern.skill_id != skill_id or pattern.error_type != error_type:
                    continue
                # Score based on success rate and recency
                total_uses = pattern.success_count + pattern.failure_count
                if total_uses == 0:
                    score = 0.0
                else:
                    score = pattern.success_count / total_uses
                # Boost for exact signature match
                if pattern.error_signature == signature:
                    score += 0.5
                if best is None or score > best_score:
                    best = pattern
                    best_score = score
            return best

    def record_outcome(
        self,
        pattern_id: str,
        success: bool,
    ) -> bool:
        """Records whether a pattern's suggested fix worked or not."""
        with self._lock:
            pattern = self._patterns.get(pattern_id)
            if not pattern:
                return False
            if success:
                pattern.success_count += 1
            else:
                pattern.failure_count += 1
            pattern.last_used_at = self._now()
            self._persist_pattern(pattern)
            return True

    def get_patterns_for_skill(self, skill_id: str) -> List[HealPattern]:
        """Returns all learned patterns for a specific skill."""
        with self._lock:
            return [p for p in self._patterns.values() if p.skill_id == skill_id]

    def get_stats(self) -> Dict[str, Any]:
        """Returns cache statistics."""
        with self._lock:
            total_patterns = len(self._patterns)
            if total_patterns == 0:
                return {"total_patterns": 0, "total_uses": 0, "effective_patterns": 0}
            total_uses = sum(p.success_count + p.failure_count for p in self._patterns.values())
            effective = sum(
                1 for p in self._patterns.values()
                if (p.success_count + p.failure_count) > 0 and p.success_count > p.failure_count
            )
            return {
                "total_patterns": total_patterns,
                "total_uses": total_uses,
                "effective_patterns": effective,
            }

    def clear(self) -> None:
        """Clears all learned patterns (for testing or reset)."""
        with self._lock:
            self._patterns.clear()
            for p_file in self.cache_dir.glob("pattern_*.json"):
                p_file.unlink(missing_ok=True)

    def _now(self) -> str:
        return _time.strftime("%Y-%m-%dT%H:%M:%S")