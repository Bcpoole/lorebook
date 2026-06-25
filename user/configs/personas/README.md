# user/configs/personas/

Curated persona storage.

Format: `user/configs/personas/<persona_id>/meta.json` and `prompts.json`  
Avatar files should be co-located and referenced by filename in `meta.json`.

Load priority for duplicate persona IDs: `outputs/personas/` first, then this directory.
