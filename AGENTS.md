# AGENTS

This repository uses a package layout under `src/lorebook/` with a compatibility launcher in `run.py`.

- Core graph composition lives in `src/lorebook/graph.py`.
- Node implementations live in `src/lorebook/nodes.py`.
- LLM transport helper lives in `src/lorebook/llm.py`.

## Agent Roles in `run.py`

The logical agent roles are implemented in package node functions and surfaced by the workflow graph.

1. `loremaster_node`
- Expands a raw idea into world-setting structure and rules.

2. `character_designer_node`
- Designs a companion character from the world setting.

3. `editor_node`
- Critiques quality and consistency.
- Returns pass/fail, routing to revise or save.

4. `save_assets_node`
- Terminal step for export logic.

## Web API

The FastAPI backend lives in `src/lorebook/api/`:

- `app.py` — FastAPI application factory; CORS configured for `localhost:5173`
- `routes/run.py` — `POST /api/run` — blocking full-graph invocation
- `routes/stream.py` — `GET /api/stream?raw_idea=...` — SSE per-node streaming
- `routes/graph.py` — `GET /api/graph` — Mermaid diagram of the workflow

The Svelte+Vite frontend lives in `ui/`. Run both together with `scripts/dev.ps1`.

## Notes

- LLM calls are made through `call_local_llm` to a local endpoint at `http://localhost:5001/api/v1/generate`.
- `LOREBOOK_LLM_ENDPOINT` env var overrides the default endpoint.
- Add file export implementation inside `save_assets_node`.
- Generated outputs go to `outputs/` (gitignored).
