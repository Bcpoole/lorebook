from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from lorebook.graph import build_app
from lorebook.state import WizardState

router = APIRouter()


async def _event_generator(raw_idea: str, request: Request) -> AsyncIterator[Dict[str, str]]:
    initial_state: WizardState = {
        "raw_idea": raw_idea,
        "world_setting": "",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }

    graph = build_app()

    async for event in graph.astream(initial_state, config={"recursion_limit": 10}):
        if await request.is_disconnected():
            break
        for node_name, node_output in event.items():
            yield {
                "event": "node",
                "data": json.dumps({"node": node_name, "output": node_output}),
            }
        await asyncio.sleep(0)

    yield {"event": "done", "data": "{}"}


@router.get("/stream")
async def stream_workflow(raw_idea: str, request: Request) -> EventSourceResponse:
    return EventSourceResponse(_event_generator(raw_idea, request))
