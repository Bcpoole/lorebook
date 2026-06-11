from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter

from lorebook.graph import build_app
from lorebook.state import WizardState
from lorebook.api.storage import save_run_result

router = APIRouter()


@router.post("/run")
async def run_workflow(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = body.get("raw_idea", "")
    initial_state: WizardState = {
        "raw_idea": raw_idea,
        "world_setting": "",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }

    graph = build_app()
    start = time.monotonic()
    result = graph.invoke(initial_state, config={"recursion_limit": 10})
    elapsed_ms = round((time.monotonic() - start) * 1000)

    saved = save_run_result(
        {
            "raw_idea": raw_idea,
            "state": dict(result),
            "meta": {"elapsed_ms": elapsed_ms},
        }
    )

    return {
        "run_id": saved["run_id"],
        "run_path": saved["run_path"],
        "state": dict(result),
        "meta": {"elapsed_ms": elapsed_ms},
    }
