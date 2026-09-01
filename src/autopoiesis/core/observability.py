"""Agentic Observability — aggregates execution metrics, telemetry, and system health status."""

import json
import logging
import sqlite3
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.storage.migrations import migrate_autopoiesis_db

logger = logging.getLogger("autopoiesis.core.observability")


class ExecutionMetric(BaseModel):
    """Metadata for a single skill execution."""
    skill_id: str
    execution_time_sec: float
    success: bool
    error_type: Optional[str] = None
    timestamp: str
    payload_size_bytes: int
    payload_storage: str  # "inline" or "file"


class AgenticObservability:
    """Tracks execution metrics, computes system health, and surfaces observability data."""

    base_dir: Path
    db_path: Path

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self.db_path = self.base_dir / "autopoiesis.db"
        migrate_autopoiesis_db(self.db_path)
        self._metrics: List[ExecutionMetric] = []
        self._lock = threading.Lock()
        self._loaded = False  # Lazy loading flag (fixes N-5)

    def _ensure_loaded(self) -> None:
        """Lazily load metrics from SQLite on first access (fixes N-5)."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load_from_sqlite()
            self._loaded = True

    def _load_from_sqlite(self) -> None:
        """Loads execution metrics from SQLite (fixes N-5: replaces slow trace file loading)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT skill_id, execution_time_sec, success, error_type, timestamp, payload_size_bytes, payload_storage
                    FROM execution_metrics
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """)
                for row in cursor.fetchall():
                    metric = ExecutionMetric(
                        skill_id=row[0],
                        execution_time_sec=row[1],
                        success=bool(row[2]),
                        error_type=row[3],
                        timestamp=row[4],
                        payload_size_bytes=row[5],
                        payload_storage=row[6],
                    )
                    self._metrics.append(metric)
        except sqlite3.Error as e:
            logger.warning(f"Failed to load metrics from SQLite: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading metrics: {e}", exc_info=True)

    def _load_existing_metrics(self) -> None:
        """Deprecated: replaced by lazy loading from SQLite."""
        pass

    def record_execution(
        self,
        skill_id: str,
        execution_time_sec: float,
        success: bool,
        error_type: Optional[str],
        payload_size_bytes: int = 0,
        payload_storage: str = "inline",
    ) -> None:
        """Records a skill execution metric.
        
        Fixes GAP-A3: Persist every execution immediately to prevent data loss on crash.
        Uses WAL mode for concurrent read performance.
        """
        self._ensure_loaded()
        with self._lock:
            metric = ExecutionMetric(
                skill_id=skill_id,
                execution_time_sec=execution_time_sec,
                success=success,
                error_type=error_type,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                payload_size_bytes=payload_size_bytes,
                payload_storage=payload_storage,
            )
            self._metrics.append(metric)
            # Persist immediately to prevent data loss (fixes GAP-A3)
            self._persist_metric(metric)

    def _persist_metric(self, metric: ExecutionMetric) -> None:
        """Persists a single metric to SQLite immediately (fixes GAP-A3)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Enable WAL mode for concurrent read performance
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=5000")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO execution_metrics (skill_id, execution_time_sec, success, error_type, timestamp, payload_size_bytes, payload_storage)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric.skill_id,
                    metric.execution_time_sec,
                    1 if metric.success else 0,
                    metric.error_type,
                    metric.timestamp,
                    metric.payload_size_bytes,
                    metric.payload_storage,
                ))
                conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"Failed to persist metric for skill '{metric.skill_id}': {e}")
        except Exception as e:
            logger.error(f"Unexpected error persisting metric: {e}", exc_info=True)

    def _persist_all(self) -> None:
        """Persists all metrics to SQLite and traces (batch operation)."""
        db_path = self.db_path
        try:
            with sqlite3.connect(db_path) as conn:
                # Enable WAL mode for concurrent read performance
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=5000")
                cursor = conn.cursor()
                for metric in self._metrics[-100:]:  # last 100 only
                    cursor.execute("""
                        INSERT OR IGNORE INTO execution_metrics (skill_id, execution_time_sec, success, error_type, timestamp, payload_size_bytes, payload_storage)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        metric.skill_id,
                        metric.execution_time_sec,
                        1 if metric.success else 0,
                        metric.error_type,
                        metric.timestamp,
                        metric.payload_size_bytes,
                        metric.payload_storage,
                    ))
                conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"Failed to batch persist metrics: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in batch persist: {e}", exc_info=True)

    @property
    def total_executions(self) -> int:
        """Total number of executions recorded."""
        self._ensure_loaded()
        with self._lock:
            return len(self._metrics)

    @property
    def success_rate(self) -> float:
        """Overall success rate percentage."""
        self._ensure_loaded()
        with self._lock:
            if not self._metrics:
                return 0.0
            succeeded = sum(1 for m in self._metrics if m.success)
            return round(succeeded / len(self._metrics) * 100, 2)

    @property
    def avg_execution_time(self) -> float:
        """Average execution time across all recorded runs."""
        self._ensure_loaded()
        with self._lock:
            if not self._metrics:
                return 0.0
            total = sum(m.execution_time_sec for m in self._metrics)
            return round(total / len(self._metrics), 3)

    @property
    def avg_execution_time_success(self) -> float:
        """Average execution time for successful runs only."""
        self._ensure_loaded()
        with self._lock:
            success_metrics = [m for m in self._metrics if m.success]
            if not success_metrics:
                return 0.0
            total = sum(m.execution_time_sec for m in success_metrics)
            return round(total / len(success_metrics), 3)

    @property
    def avg_execution_time_failure(self) -> float:
        """Average execution time for failed runs only."""
        self._ensure_loaded()
        with self._lock:
            fail_metrics = [m for m in self._metrics if not m.success]
            if not fail_metrics:
                return 0.0
            total = sum(m.execution_time_sec for m in fail_metrics)
            return round(total / len(fail_metrics), 3)

    @property
    def error_type_distribution(self) -> Dict[str, int]:
        """Distribution of error types."""
        self._ensure_loaded()
        with self._lock:
            dist: Dict[str, int] = {}
            for m in self._metrics:
                if m.error_type:
                    dist[m.error_type] = dist.get(m.error_type, 0) + 1
            return dist

    def get_skill_metrics(self, skill_id: str) -> Dict[str, Any]:
        """Returns metrics aggregated for a single skill."""
        self._ensure_loaded()
        with self._lock:
            skill_metrics = [m for m in self._metrics if m.skill_id == skill_id]
            if not skill_metrics:
                return {
                    "total_executions": 0,
                    "success_rate": 0.0,
                    "avg_execution_time": 0.0,
                    "error_types": {},
                }
            succeeded = sum(1 for m in skill_metrics if m.success)
            error_types: Dict[str, int] = {}
            for m in skill_metrics:
                if m.error_type:
                    error_types[m.error_type] = error_types.get(m.error_type, 0) + 1
            return {
                "total_executions": len(skill_metrics),
                "success_rate": round(succeeded / len(skill_metrics) * 100, 2),
                "avg_execution_time": round(sum(m.execution_time_sec for m in skill_metrics) / len(skill_metrics), 3),
                "error_types": error_types,
            }

    def get_top_slow_skills(self, n: int = 10) -> List[Dict[str, Any]]:
        """Returns the N slowest skills by average execution time."""
        self._ensure_loaded()
        with self._lock:
            # Group by skill_id and compute avg time
            skill_times: Dict[str, List[float]] = {}
            for m in self._metrics:
                if m.success:
                    skill_times.setdefault(m.skill_id, []).append(m.execution_time_sec)

            avgs = [
                {
                    "skill_id": sid,
                    "avg_time": round(sum(times) / len(times), 3),
                    "executions": len(times),
                }
                for sid, times in skill_times.items()
            ]
            avgs.sort(key=lambda x: x["avg_time"], reverse=True)
            return avgs[:n]

    def get_error_summary(self) -> Dict[str, Any]:
        """Returns a summary of errors with top causes."""
        self._ensure_loaded()
        with self._lock:
            error_counts = {}
            for m in self._metrics:
                if not m.success and m.error_type:
                    error_counts[m.error_type] = error_counts.get(m.error_type, 0) + 1

            total_errors = sum(error_counts.values())
            if total_errors == 0:
                return {"total_errors": 0, "top_causes": [], "by_type": {}}

            # Top 5 causes
            top_causes = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            return {
                "total_errors": total_errors,
                "top_causes": [
                    {"error_type": et, "count": c, "percentage": round(c / total_errors * 100, 1)}
                    for et, c in top_causes
                ],
                "by_type": error_counts,
            }