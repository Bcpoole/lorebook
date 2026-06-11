# Lorebook

Small Python project for generating a world setting and companion character through a LangGraph workflow.

## Project Structure

- `run.py`: Main workflow script.
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
```

## Run

```powershell
python run.py
```

## Development

```powershell
# Lint
ruff check .

# Test
pytest -q
```

## Next Improvements

- Add robust response validation for `call_local_llm`.
- Implement real asset export in `save_assets_node`.
- Add automated tests for routing and node outputs.
