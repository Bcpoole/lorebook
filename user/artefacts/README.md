# user/artefacts/

Curated artifact storage that mirrors `outputs/` by type.

Purpose:

- Keep important artifacts safe when `outputs/` is cleaned.
- Maintain a hand-picked library of worlds, characters, stories, locations, and objects.

Layout:

- `user/artefacts/world/<run_id>/artifact.json`
- `user/artefacts/character/<run_id>/artifact.json`
- `user/artefacts/story/<run_id>/artifact.json`
- `user/artefacts/location/<run_id>/artifact.json`
- `user/artefacts/object/<run_id>/artifact.json`

Co-locate referenced images in the same `<run_id>/` folder.

Load behavior:

- Gallery/run loaders scan both `outputs/` and `user/artefacts/`.
- If the same run ID exists in both, `outputs/` currently takes precedence.
