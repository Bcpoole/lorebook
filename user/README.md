# user/

`user/` is the curated, long-lived side of Lorebook storage.

- Use `outputs/` as the app-generated working area. It is intentionally easy to clear/reset.
- Use `user/` for artifacts and settings you want to keep across resets, experiments, or cleanup of `outputs/`.

The app reads from both locations, but does not auto-write to `user/`. Today, moving something from `outputs/` to `user/` is a manual copy step (a future "save to user" flow is planned).

This folder is gitignored for normal runtime content; only scaffold docs/templates are tracked.
