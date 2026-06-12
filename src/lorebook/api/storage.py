from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any


def get_outputs_root() -> Path:
    return Path(__file__).resolve().parents[3] / "outputs"


def get_runs_dir() -> Path:
    runs_dir = get_outputs_root() / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir


def get_drafts_dir() -> Path:
    drafts_dir = get_runs_dir() / "_drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    return drafts_dir


def save_run_result(payload: dict[str, Any], filename: str | None = None) -> dict[str, str]:
    if filename:
        safe = re.sub(r"[^\w\-]", "_", filename.strip())
        file_stem = safe if safe else uuid4().hex
    else:
        file_stem = uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()
    record = {
        "run_id": file_stem,
        "saved_at": started_at,
        "saved_at_ns": time.time_ns(),
        **payload,
    }

    run_path = get_runs_dir() / f"{file_stem}.json"
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    return {
        "run_id": file_stem,
        "run_path": str(run_path),
        "filename": file_stem,
    }


def save_draft_state(payload: dict[str, Any], draft_id: str = "latest") -> dict[str, str]:
    record = {
        "draft_id": draft_id,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    draft_path = get_drafts_dir() / f"{draft_id}.json"
    draft_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {
        "draft_id": draft_id,
        "draft_path": str(draft_path),
    }


def load_run(run_id: str) -> dict[str, Any] | None:
    run_path = get_runs_dir() / f"{run_id}.json"
    if not run_path.exists():
        return None
    return json.loads(run_path.read_text(encoding="utf-8"))


def load_latest_run() -> dict[str, Any] | None:
    latest_record: dict[str, Any] | None = None
    latest_sort_key: tuple[str, int, str] | None = None
    for run_path in get_runs_dir().glob("*.json"):
        record = json.loads(run_path.read_text(encoding="utf-8"))
        saved_at = str(record.get("saved_at", ""))
        saved_at_ns = int(record.get("saved_at_ns", 0))
        sort_key = (saved_at_ns, saved_at, run_path.stat().st_mtime_ns, run_path.name)
        if latest_record is None or latest_sort_key is None or sort_key > latest_sort_key:
            latest_record = record
            latest_sort_key = sort_key
    return latest_record


def load_draft_state(draft_id: str = "latest") -> dict[str, Any] | None:
    draft_path = get_drafts_dir() / f"{draft_id}.json"
    if not draft_path.exists():
        return None
    return json.loads(draft_path.read_text(encoding="utf-8"))
