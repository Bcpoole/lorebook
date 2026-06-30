# Lorebook

[![CI](https://github.com/Bcpoole/lorebook/actions/workflows/ci.yml/badge.svg)](https://github.com/Bcpoole/lorebook/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Node.js](https://img.shields.io/badge/node-20.19%2B-339933?logo=nodedotjs&logoColor=white)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Lorebook is a local-first Python app for generating a world setting and companion character through a LangGraph workflow, with a FastAPI backend and a Svelte frontend.

![Pixel art image of a lore book](docs/images/lorebook.png)

## Project Structure

- `src/lorebook/`: Package source (state, nodes, graph, CLI).
- `src/lorebook/api/`: FastAPI app, routes, and persistence helpers.
- `run.py`: Compatibility launcher that exposes the package `app`.
- `ui/`: Svelte + Vite frontend.
- `scripts/dev.ps1`: Starts the backend and frontend together on Windows.
- `scripts/dev.sh`: Starts the backend and frontend together on Linux/macOS.
- `outputs/`: Saved run artifacts and generated assets (gitignored, app-written).
- `user/`: Permanent user-curated content (gitignored). Split into two sub-directories: `user/artefacts/` mirrors `outputs/` for curated run data, and `user/configs/` holds personas and UI assets (backgrounds etc.). The app reads from both but never auto-writes to `user/`.
- `requirements.txt`: Runtime dependencies.
- `requirements-dev.txt`: Dev and test dependencies.
- `AGENTS.md`: Agent/role documentation for the pipeline.

## Quick Start

```powershell
& ./start.ps1
```

## Prerequisites

- Python 3.12+
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

```bash
chmod +x ./scripts/dev.sh
./scripts/dev.sh
```

## Development

```powershell
# If this is a fresh checkout or ui/node_modules is missing
Set-Location .\ui
npm install
Set-Location ..

# Lint
ruff check .

# Test
pytest -q

# Frontend build
Set-Location .\ui
npm run build
Set-Location ..
```

## Local config templates (open-source-safe)

- Prompts load `src/lorebook/config/prompts/blank.py` when present, otherwise `src/lorebook/config/prompts/_template.py`.
- SD styles load from `user/configs/sd/styles.json` first (see `user/configs/sd/_example.json` for the format), then from built-in `src/lorebook/config/sd/styles.py`.
- General Settings includes a toggle to include baseline SD styles in the preset list; if `user/configs/sd/styles.json` is missing, baseline styles are loaded regardless.

## API Endpoints

- `POST /api/run` - blocking workflow run, saves JSON output to `outputs/world/`
- `POST /api/story` - generate or refine structured Story artifacts with setup/instruction/action controls (`generate`, `suggest_next_beat`, `rewrite_opening`, `add_character`, `add_location`, `add_object`, `add_example`)
- `POST /api/story-item` - edit/delete individual story list items (`characters_artifact`, `locations`, `objects`, `examples`) and generate SD prompts/images for each item
- `POST /api/character` - generate one standalone character payload
- `POST /api/save` - save a run with optional story sub-artifact extraction
- `GET /api/gallery` - list saved run previews with search/tag filtering and optional artifact type filter
- `POST /api/character-role` - persist character/persona role changes to a saved run
- `GET /api/stream?raw_idea=...` - SSE stream of per-node updates
- `GET /api/graph` - Mermaid graph definition for the workflow
- `GET /api/artifact/location/{artifact_id}` - retrieve standalone location artifact
- `DELETE /api/artifact/location/{artifact_id}` - delete location artifact and folder
- `GET /api/artifact/object/{artifact_id}` - retrieve standalone object artifact
- `DELETE /api/artifact/object/{artifact_id}` - delete object artifact and folder
- `PATCH /api/story/{id}/update-location` - update story location and auto-create independent artifact
- `PATCH /api/story/{id}/update-object` - update story object and auto-create independent artifact

`POST /api/story` accepts optional `story_setup` (`protagonist`, `opening_preference`, `output_format`, `tone`, `length_target`), `instruction`, `action`, and current `state.story_artifact` for refinement passes. The response includes `generation_quality` (`full`, `repaired`, `fallback`) for UI diagnostics.

Story draft internals are also split into per-section JSON files under `outputs/story/_drafts/<draft>_story_sections/`. List sections are persisted per-item (for example `objects/silver_keycard.json`) to keep section-focused updates resilient. Item image files are co-located with those item JSON files, and item JSON stores `image_name` (filename only).

## Saved Output & Artifact Structure

Artifacts are organized by type with subdirectories and co-located resources:

- **World**: `outputs/world/<run_id>/artifact.json`
- **Character**: `outputs/character/<run_id>/artifact.json` (images: `<run_id>.png`, `<run_id>_2.png`, etc.)
- **Story**: `outputs/story/<run_id>/artifact.json` (includes sub-artifacts: locations, objects, characters_artifact)
- **Location**: `outputs/location/<run_id>/artifact.json` (images: `<run_id>_locations_1.png`, etc.)
- **Object**: `outputs/object/<run_id>/artifact.json` (images: `<run_id>_objects_1.png`, etc.)

**Image Co-location Strategy**: Character images and story entity images (location/object/character sub-artifacts) are written to the same folder as their artifact.json file. Image paths are normalized from volatile fields (`image_path`, `image_data`) to persistent references (`image_file` for characters, `image_name` for story entities). This ensures images aren't lost on re-saves and follow standard naming conventions.

**Story Sub-Artifact Extraction**: When a story artifact is saved, locations, objects, and character details are automatically extracted and saved as separate artifacts if they contain meaningful content (name + description). Each becomes its own gallery entry, indexed by type and order.

Drafts are stored per type under each folder's `_drafts/` subdirectory (e.g., `outputs/world/_drafts/latest.json`).

## User-Curated Directory (`user/`)

Lorebook intentionally separates storage into two roles:

- **`outputs/`**: app-generated working storage. Good for iteration, drafts, and disposable runs; easy to clear/reset.
- **`user/`**: user-owned curated storage. Use this for artifacts/settings you want to keep long-term.

The app reads from both, but **never auto-writes to `user/`**. Today, promoting content from `outputs/` into `user/` is a manual copy step; this separation keeps ephemeral generation output independent from durable user curation.

It is split into two sub-directories:

```
user/
  ├── artefacts/      # Curated run data (mirrors outputs/ structure)
  │   ├── world/      # Same artifact.json format as outputs/world/
  │   ├── character/
  │   ├── story/
  │   ├── location/
  │   └── object/
  └── configs/        # UI configuration and custom assets
      ├── personas/   # Curated personas (meta.json + prompts.json per sub-directory)
      └── backgrounds/# Custom background images for the UI shell
```

The **Gallery**, **Personas**, and **Lore** pages load from both `outputs/` and `user/artefacts/` automatically. If the same artifact ID exists in both, `outputs/` takes priority.

Background management under `user/configs/backgrounds/` is currently paused/not implemented in the active UI flow; treat this folder as reserved for the rework.

### Tracked `user/` scaffold

This repository keeps a tracked scaffold under `user/` using per-folder `README.md` files. Real user content remains gitignored, while these scaffold docs describe what each folder is for and how loading/precedence works.

## Artifact Gallery & Editing

The gallery provides browsing and editing capabilities for all artifact types:

### Gallery Features
- **Tab-based browsing**: Switch between Character, Location, Object, and Story tabs
- **Search & filtering**: Search by name/content, filter by favorites
- **Card preview**: Quick preview with image, title, and summary
- **Modal viewing**: Click cards to open detailed modals for each artifact type

### Artifact Editing (Phase 1)
#### Dedicated Editor Pages
- **Location editor** (`/location/:id`): Full CRUD for location artifacts with atmosphere, accessibility, inhabitants, and history fields
- **Object editor** (`/object/:id`): Full CRUD for object artifacts with material, purpose, origin, and properties
- Features include image upload (base64 encoding), validation, and delete with confirmation

#### Inline Story Sub-Item Editing
- **Expandable sections** in story modal for Locations, Objects, and Characters
- **Toggle edit mode** on any story sub-item without leaving the modal
- **Auto-artifact creation**: Editing a story's location or object automatically creates an independent gallery entry
- **Form validation**: Per-field error messages, required field checks
- **Toast notifications**: User feedback for save/error states

### Gallery Modals
- **StoryArtifactModal**: Displays story with collapsible Locations, Objects, Characters sections
- **LocationModal**: Displays standalone location artifacts with description, atmosphere, inhabitants, history
- **ObjectModal**: Displays standalone object artifacts with description, material, purpose, origin, properties

### How To Use
1. Open the **Gallery** tab in the top navigation
2. Click an artifact card to open its modal
3. For stories: Expand the "Locations" or "Objects" sections and click "Edit" to inline edit
4. Editing a story sub-item automatically creates it as a separate gallery entry
5. Switch tabs to view Character, Location, or Object artifacts independently

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
