from __future__ import annotations

from .graph import app


def main() -> None:
    print("Lorebook workflow is ready.")
    print("Import `app` from lorebook.workflow.graph and invoke it with an initial state.")
    _ = app
