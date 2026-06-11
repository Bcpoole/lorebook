# Lorebook

Small Python project for generating a world setting and companion character through a LangGraph workflow.

## Project Structure

- `src/lorebook/`: Package source (state, nodes, graph, CLI).
- `run.py`: Compatibility launcher that exposes the package `app`.
- `requirements.txt`: Runtime dependencies.
- `requirements-dev.txt`: Dev and test dependencies.
- `AGENTS.md`: Agent/role documentation for the pipeline.

## Prerequisites

- Python 3.10+
- A local text-generation endpoint at `http://localhost:5001/api/v1/generate`

## Setup (PowerShell on Windows)

```powershell
# Create virtual environment
py -3 -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

# Install package in editable mode (enables `python -m lorebook`)
python -m pip install -e .
```

## Run

```powershell
# Compatibility launcher
python run.py

# Package entrypoint
python -m lorebook
```

## Development

```powershell
# Lint
ruff check .

# Test
pytest -q
```

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
