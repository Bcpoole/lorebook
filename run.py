from pathlib import Path
import sys

# Keep the original top-level entry script working while code lives in src/.
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lorebook import app


if __name__ == "__main__":
    print("Lorebook workflow is ready.")
    print("Import `app` from lorebook.graph and invoke it with an initial state.")