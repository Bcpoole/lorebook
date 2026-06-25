# user/configs/sd/

Stable Diffusion style override directory.

- Create any `.json` file here (e.g. `styles.json`) to override built-in style presets.
- Start from `_example.json` and adjust prompts as needed, then save under a new name.
- Files whose names begin with `_` (like `_example.json`) are **ignored** — they are reference/template files only.
- Multiple `.json` files are merged; earlier entries (alphabetical order) take priority on name conflicts.
- User-defined styles appear before built-ins in the style selector.
- General Settings includes a toggle to include or hide baseline built-in styles (if no user styles exist, built-ins are still shown).

Load order:

1. `user/configs/sd/*.json` (excluding `_`-prefixed files)
2. `src/lorebook/config/sd/styles.py`
