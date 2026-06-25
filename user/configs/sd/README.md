# user/configs/sd/

Stable Diffusion style override directory.

- Create `styles.json` here to override built-in style presets.
- Start from `_example.json` and adjust prompts as needed.
- User-defined styles appear before built-ins in the style selector.
- General Settings includes a toggle to include or hide baseline built-in styles (if no user styles exist, built-ins are still shown).

Load order:

1. `user/configs/sd/styles.json`
2. `src/lorebook/config/sd/styles.py`
