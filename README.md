# Lorebook

Lorebook is a local-first Python app for generating a world setting and companion character through a LangGraph workflow, with a FastAPI backend and a Svelte frontend.

## Project Structure

- `src/lorebook/`: Package source (state, nodes, graph, CLI).
- `src/lorebook/api/`: FastAPI app, routes, and persistence helpers.
- `run.py`: Compatibility launcher that exposes the package `app`.
- `ui/`: Svelte + Vite frontend.
- `scripts/dev.ps1`: Starts the backend and frontend together.
- `outputs/`: Saved run artifacts and generated assets.
- `requirements.txt`: Runtime dependencies.
- `requirements-dev.txt`: Dev and test dependencies.
- `AGENTS.md`: Agent/role documentation for the pipeline.

## Quick Start

```powershell
& ./start.ps1
```

## Prerequisites

- Python 3.10+
- A local text-generation endpoint at `http://localhost:5001`
- Node.js 20.19+ and npm 10+ for the Svelte frontend

## Setup (PowerShell on Windows)

```powershell
# Create virtual environment
py -3 -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install Python dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

# Install package in editable mode (enables `python -m lorebook`)
python -m pip install -e .

# Install frontend dependencies
Set-Location .\ui
npm install
Set-Location ..

# Optional: override the LLM endpoint if your local server uses a different host
$env:LOREBOOK_LLM_ENDPOINT = "http://localhost:5001"
```

## Run

### Backend only

```powershell
# Compatibility launcher
python run.py

# Package entrypoint
python -m lorebook

# API server directly
uvicorn lorebook.api.app:app --reload --port 8000
```

### Full app

```powershell
.\scripts\dev.ps1
```

## Development

```powershell
# Lint
ruff check .

# Test
pytest -q

# Frontend build
Set-Location .\ui
npm run build
Set-Location ..
```

## API Endpoints

- `POST /api/run` - blocking workflow run, saves JSON output to `outputs/runs/`
- `POST /api/story` - generate structured Story artifact fields (`title`, `description`, `plot`, `locations`, `objects`, etc.)
- `POST /api/character` - generate one standalone character payload
- `GET /api/gallery` - list saved run previews with search/tag filtering
- `POST /api/character-role` - persist character/persona role changes to a saved run
- `GET /api/stream?raw_idea=...` - SSE stream of per-node updates
- `GET /api/graph` - Mermaid graph definition for the workflow

## Saved Output

Blocking runs save JSON artifacts under `outputs/runs/` and the UI shows the saved run id and path after each run.

## Offline Fixture Testing

Capture a real local-LLM output once, then run tests without a live connection:

```powershell
# Capture fixture data from your running local endpoint
python scripts/capture_test_fixtures.py

# Run tests offline (unit tests monkeypatch LLM calls)
pytest -q
```

## Next Improvements

- Add robust response validation for `call_local_llm`.
- Implement real asset export in `save_assets_node`.
- Add automated tests for routing and node outputs.
