"""Persist a complete, secret-free audit trail for one agent run."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path, PurePath
from typing import Any
from zoneinfo import ZoneInfo

from config import EXPERIMENT_DIR


LOG_TIMEZONE = ZoneInfo("Asia/Shanghai")


class CallLogger:
    """Write one JSON object per line for a single Function Calling run."""

    def __init__(
        self,
        user_message: str,
        model_name: str,
        *,
        log_dir: Path | str | None = None,
    ) -> None:
        target_dir = Path(log_dir) if log_dir is not None else EXPERIMENT_DIR / "logs"
        self.log_dir = self._require_inside_experiment(target_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.run_id = uuid.uuid4().hex
        started_at = datetime.now(LOG_TIMEZONE)
        timestamp = started_at.strftime("%Y%m%dT%H%M%S")
        self.path = self.log_dir / f"run_{timestamp}_{self.run_id[:10]}.jsonl"
        self._write(
            "run_start",
            user_message=user_message,
            model_name=model_name,
            started_at=started_at.isoformat(),
        )

    @staticmethod
    def _require_inside_experiment(path: Path | PurePath) -> Path:
        resolved_path = path.resolve()
        try:
            resolved_path.relative_to(EXPERIMENT_DIR)
        except ValueError as exc:
            raise ValueError(
                "Logs must be written inside experiment3_function_calling."
            ) from exc
        return resolved_path

    @staticmethod
    def timestamp() -> str:
        return datetime.now(LOG_TIMEZONE).isoformat()

    def record(self, event_type: str, **data: Any) -> None:
        """Append an event without modifying the caller-provided data."""

        self._write(event_type, **data)

    def _write(self, event_type: str, **data: Any) -> None:
        event = {
            "timestamp": self.timestamp(),
            "run_id": self.run_id,
            "event": event_type,
            **data,
        }
        with self.path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(event, ensure_ascii=False) + "\n")
