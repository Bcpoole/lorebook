# AGENTS

This repository uses a package layout under `src/lorebook/` with a compatibility launcher in `run.py`.

- Core graph composition lives in `src/lorebook/workflow/graph.py`.
- Node implementations live in `src/lorebook/workflow/nodes.py`.
- Workflow state, synchronous execution, and streaming live under `src/lorebook/workflow/`.
- Story, character, image, and page-agent behavior live in their corresponding feature packages.
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
- `routes/workflow.py` — workflow run, step, streaming, and review endpoints
- `routes/stories.py` — story generation and story-item endpoints
- `routes/characters.py` — character generation, relationships, and role endpoints
- `routes/images.py` — character image generation and SD style endpoints
- `routes/gallery.py` — gallery and saved-run lookup endpoints
- `routes/page_agent.py` — page-level creative agent endpoint
- `routes/system.py` — health and draft endpoints
- `routes/stream.py` — `GET /api/stream?raw_idea=...` — SSE per-node streaming
- `routes/graph.py` — `GET /api/graph` — Mermaid diagram of the workflow
- `routes/save.py` — `POST /api/save` — save run with story sub-artifact extraction
- `routes/artifacts.py` — GET/DELETE for location and object artifacts

The Svelte+Vite frontend lives in `ui/`. Run both together with `scripts/dev.ps1` (Windows) or `scripts/dev.sh` (Linux/macOS).

### Frontend dependency prerequisite

Before running frontend commands (`npm run build`, `npm run dev`, `npm test`) in a fresh environment, install UI dependencies first:

```powershell
Set-Location .\ui
npm install
```

## Frontend Architecture

### Gallery System
The gallery component (`ui/src/lib/GalleryPage.svelte`) provides unified browsing and editing for all artifact types:

- **Tabs**: Character, Location, Object, Story (switchable)
- **Search/filter**: Full-text search, tag filtering, favorites
- **Card display**: Image preview, title, summary with hover states
- **Modal system**: Type-specific modals for viewing and editing

### Artifact Components (Phase 1)

#### Editors
- `LocationEditPanel.svelte` - Form component for editing location artifacts (atmosphere, accessibility, inhabitants, history)
- `ObjectEditPanel.svelte` - Form component for editing object artifacts (material, purpose, origin, properties)
- Both include file upload with base64 encoding, validation, and error display

#### Pages (Dedicated Views)
- `LocationPage.svelte` - Read-only location display with edit toggle
- `ObjectPage.svelte` - Read-only object display with edit toggle

#### Inline Editors (Story Context)
- `LocationEditItem.svelte` - Compact inline editor for story locations
- `ObjectEditItem.svelte` - Compact inline editor for story objects
- Both support toggle between read-only summary and editable form
- Automatic independent artifact creation on save

#### Modals
- `StoryArtifactModal.svelte` - Story display with expandable Locations/Objects/Characters sections
- `LocationModal.svelte` - Standalone location artifact display
- `ObjectModal.svelte` - Standalone object artifact display

### Editing Workflow
1. **Browse gallery** - Click tab to filter by artifact type
2. **Open modal** - Click card to view artifact details
3. **For stories**:
   - Expand "Locations" or "Objects" sections
   - Click "Edit" on any sub-item to toggle inline edit mode
   - Save to update story and auto-create independent artifact
4. **For locations/objects**:
   - Click "Edit" button to open edit panel modal
   - Make changes and save
   - Changes persist to artifact folder

### Data Handling
- **Images**: Base64 data URIs stored in `image_data` field, can be extracted to files on export
- **Form state**: Structured clone pattern prevents accidental mutations
- **Validation**: Per-field error messages, required field checks
- **Feedback**: Toast notifications for save/error states

## Artifact Storage Strategy

All artifacts (world, character, story, location, object) follow a unified persistence pattern across two root directories: `outputs/` (app-written) and `user/` (user-curated, read-only for the app).

### Directory Structure
```
outputs/               ← app auto-writes here
  ├── world/
  │   ├── {run_id}/
  │   │   ├── artifact.json       # state.world_setting, state.characters
  │   │   ├── {run_id}.png        # character 1 image
  │   │   └── {run_id}_2.png      # character 2 image
  │   └── _drafts/latest.json
  ├── character/
  │   ├── {run_id}/
  │   │   ├── artifact.json       # standalone character(s)
  │   │   └── {run_id}.png        # character image
  │   └── _drafts/latest.json
  ├── story/
  │   ├── {run_id}/
  │   │   ├── artifact.json       # full story artifact
  │   │   ├── {run_id}_characters_artifact_1.png
  │   │   ├── {run_id}_locations_1.png
  │   │   └── {run_id}_objects_1.png
  │   └── _drafts/latest.json
  ├── location/
  │   ├── {run_id}/
  │   │   ├── artifact.json       # story_artifact with locations[0]
  │   │   └── {run_id}_locations_1.png
  │   └── _drafts/latest.json
  └── object/
      ├── {run_id}/
      │   ├── artifact.json       # story_artifact with objects[0]
      │   └── {run_id}_objects_1.png
      └── _drafts/latest.json

user/                  ← user places content here manually; app never auto-writes
  ├── artefacts/       # Curated run data (same artifact.json format as outputs/)
  │   ├── world/
  │   ├── character/
  │   ├── story/
  │   ├── location/
  │   └── object/
  └── configs/         # UI configuration and custom assets
      ├── personas/    # Persona sub-directories (meta.json + prompts.json)
      ├── sd/          # Custom SD styles (copy _example.json → styles.json to activate)
      └── backgrounds/ # Custom UI background images
```

### Image Co-location
- Character images (`character.image_file`) are named `{run_id}`, `{run_id}_2`, etc.
- Story entity images (`location.image_name`, `object.image_name`) are named `{run_id}_{section}_{index}.{ext}`
- Images are extracted from volatile fields (`image_data`, `image_prompt`, etc.) at save time
- Only persistent references (`image_file`, `image_name`) are written to disk

### Story Sub-Artifact Extraction
When `POST /api/save` receives a story artifact with metadata `source: "story"`:
1. Each location with name + description becomes a separate location artifact
2. Each object with name + description becomes a separate object artifact
3. Each character_artifact with summary + details becomes a separate character artifact
4. Names are auto-derived from item names or sequential labels (e.g., `story_location_1_sky_dock`)
5. Gallery viewers can filter by type and explore created artifacts independently

### Artifact Editing & Persistence (Phase 1)
- **Inline editing**: Story sub-items (locations/objects) can be edited inline without leaving the story modal
- **Auto-creation**: When a story sub-item is edited and saved, an independent artifact is automatically created in the gallery
- **Full CRUD**: Dedicated editor pages for Location and Object artifacts support create, read, update, delete
- **Atomic operations**: Each edit creates new artifact folder with self-contained content (metadata + co-located images)

## Notes

- LLM calls are made through `call_local_llm` to a local endpoint at `http://localhost:5001`.
- `LOREBOOK_LLM_ENDPOINT` env var overrides the default endpoint.
- Add file export implementation inside `save_assets_node`.
- Generated outputs go to `outputs/` (gitignored, app-written).

## User Directory (`user/`)

The `user/` directory is a permanent, gitignored sibling of `outputs/` for user-curated content. The app **reads** from it but never auto-writes to it.

### Structure

```
user/
  ├── artefacts/      # Curated run data — mirrors outputs/ structure
  │   ├── world/
  │   ├── character/
  │   ├── story/
  │   ├── location/
  │   └── object/
  └── configs/        # UI configuration and custom assets
      ├── personas/   # Curated personas (meta.json + prompts.json per subdirectory)
      ├── sd/         # Custom SD styles — copy `_example.json` → `styles.json` to activate
      └── backgrounds/# Reserved for background-feature rework (currently paused)
```

### Load Priority
- Gallery, Personas page, and Lore pages scan **both** `outputs/` and `user/artefacts/`.
- If the same artifact run ID exists in both, `outputs/` takes priority.
- `outputs/personas/` takes priority over `user/configs/personas/` for the same persona ID.

### API
- `POST /api/user-assets/upload/background` — upload a background image (stores to `user/configs/backgrounds/`)
- `GET /api/user-assets/list/backgrounds` — list uploaded backgrounds
- `DELETE /api/user-assets/backgrounds/{filename}` — remove a background
- `/user-assets/` — static file mount serving `user/configs/`

**SD styles**: place `styles.json` in `user/configs/sd/` (see `_example.json` for format). Load order: `user/configs/sd/styles.json` → `src/lorebook/config/sd/styles.py`.
