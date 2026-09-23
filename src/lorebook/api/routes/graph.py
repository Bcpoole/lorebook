from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from lorebook.workflow.graph import build_app

router = APIRouter()


@router.get("/graph", response_class=PlainTextResponse)
async def get_graph() -> str:
    graph = build_app()
    return graph.get_graph().draw_mermaid()
