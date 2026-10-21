"""Local filesystem locations with Momentum-first legacy compatibility."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MomentumStorage:
    """Resolve writable paths without losing an existing legacy workspace."""

    results_directory: Path
    cache_directory: Path
    memory_log_path: Path
    memory_log_max_entries: int | None = None

    @classmethod
    def from_environment(cls, user_home: Path | None = None) -> MomentumStorage:
        base_directory = cls._base_directory(user_home or Path.home())
        return cls(
            results_directory=cls._environment_path(
                "MOMENTUM_RESULTS_DIR",
                "TRADINGAGENTS_RESULTS_DIR",
                base_directory / "logs",
            ),
            cache_directory=cls._environment_path(
                "MOMENTUM_CACHE_DIR",
                "TRADINGAGENTS_CACHE_DIR",
                base_directory / "cache",
            ),
            memory_log_path=cls._environment_path(
                "MOMENTUM_MEMORY_LOG_PATH",
                "TRADINGAGENTS_MEMORY_LOG_PATH",
                base_directory / "memory" / "trading_memory.md",
            ),
        )

    @staticmethod
    def _base_directory(user_home: Path) -> Path:
        legacy_directory = user_home / ".tradingagents"
        if legacy_directory.exists() and not legacy_directory.is_symlink():
            return legacy_directory
        return user_home / ".momentum"

    @staticmethod
    def _environment_path(primary: str, legacy: str, default: Path) -> Path:
        configured = os.getenv(primary) or os.getenv(legacy)
        if configured:
            return Path(configured).expanduser()
        return default
