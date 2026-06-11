from __future__ import annotations

import json
import re
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
        **payload,
    }

    run_path = get_runs_dir() / f"{file_stem}.json"
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    return {
        "run_id": file_stem,
        "run_path": str(run_path),
        "filename": file_stem,
    }
