"""Save every exhibition run to disk: inputs, evidence, prompts, outputs and timings.

A run is written to ``runs/<run_id>/run.json`` (``runs/`` is git-ignored).
Agents and the pipeline call ``recorder.record(kind, **data)``; every event is
time-stamped and stored in order, so a run can be replayed and debugged later,
and ``evaluation/evaluate_run.py`` can score it.
"""
from __future__ import annotations

import dataclasses
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class RunRecorder:
    def __init__(self, runs_dir: str | Path | None = None, run_id: str | None = None, config: dict | None = None):
        started = datetime.now(timezone.utc)
        self.run_id = run_id or f"{started:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.runs_dir = Path(runs_dir) if runs_dir else DEFAULT_RUNS_DIR
        self.started_at = started.isoformat()
        self.config = config or {}
        self.events: list[dict] = []
        self.timings: dict[str, float] = {}
        self._t0 = time.monotonic()
        self._lock = threading.Lock()

    def record(self, kind: str, **data: Any) -> None:
        event = {"t": round(time.monotonic() - self._t0, 3), "kind": kind, **_jsonable(data)}
        with self._lock:
            self.events.append(event)

    def timing(self, stage: str, seconds: float) -> None:
        with self._lock:
            self.timings[stage] = round(seconds, 3)

    def events_of(self, kind: str) -> list[dict]:
        with self._lock:
            return [e for e in self.events if e["kind"] == kind]

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "run_id": self.run_id,
                "started_at": self.started_at,
                "duration_s": round(time.monotonic() - self._t0, 3),
                "config": _jsonable(self.config),
                "timings": dict(self.timings),
                "events": list(self.events),
            }

    def save(self) -> Path:
        folder = self.runs_dir / self.run_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "run.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def load_run(path: str | Path) -> dict:
    path = Path(path)
    if path.is_dir():
        path = path / "run.json"
    return json.loads(path.read_text(encoding="utf-8"))
