# AGENTS

This repository currently uses a single workflow script in `run.py` that orchestrates a small lore/character generation pipeline.

## Agent Roles in `run.py`

1. `loremaster_node`
- Expands a raw idea into world-setting structure and rules.

2. `character_designer_node`
- Designs a companion character from the world setting.

3. `editor_node`
- Critiques quality and consistency.
- Returns pass/fail, routing to revise or save.

4. `save_assets_node`
- Terminal step for export logic.

## Notes

- LLM calls are made through `call_local_llm` to a local endpoint at `http://localhost:5001/api/v1/generate`.
- Add validation and retry handling before production use.
- Add file export implementation inside `save_assets_node`.
