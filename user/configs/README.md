# user/configs/

Curated user settings and UI assets that should survive cleanup of `outputs/`.

Use this for stable personalization and environment-level defaults:

- `personas/` for persona packs (`meta.json` + `prompts.json`)
- `sd/` for style overrides (`styles.json`)
- `backgrounds/` is reserved for a background-feature rework (currently not active)

Like `user/artefacts/`, this directory is read by the app and intended for long-term user-owned data.
