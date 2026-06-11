from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from lorebook.api.routes import graph, run, save, stream


def create_app() -> FastAPI:
    app = FastAPI(title="Lorebook API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(run.router, prefix="/api")
    app.include_router(stream.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")
    app.include_router(save.router, prefix="/api")

    # Serve compiled Svelte build in production.
    dist_dir = Path(__file__).resolve().parents[3] / "ui" / "dist"
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="ui")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def root() -> str:
            return (
                "<html><body style='font-family: system-ui; padding: 2rem;'>"
                "<h1>Lorebook is running</h1>"
                "<p>The Svelte app is not built yet.</p>"
                "<ul>"
                "<li><a href='http://localhost:5173'>Open the Vite dev server</a></li>"
                "<li><a href='/docs'>Open the API docs</a></li>"
                "</ul>"
                "</body></html>"
            )

    return app


app = create_app()
