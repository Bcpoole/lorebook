#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
UI_DIR="$ROOT_DIR/ui"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

if [[ -x "$VENV_PYTHON" ]]; then
  PYTHON_CMD=("$VENV_PYTHON")
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=("python3")
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD=("python")
else
  echo "Python runtime not found. Create .venv or install Python (python3/python on PATH)." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm was not found on PATH." >&2
  exit 1
fi

api_pid=""
vite_pid=""

cleanup() {
  if [[ -n "$api_pid" ]] && kill -0 "$api_pid" >/dev/null 2>&1; then
    kill "$api_pid" >/dev/null 2>&1 || true
  fi
  if [[ -n "$vite_pid" ]] && kill -0 "$vite_pid" >/dev/null 2>&1; then
    kill "$vite_pid" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

echo "Starting FastAPI on http://localhost:8000 ..."
(
  cd "$ROOT_DIR"
  "${PYTHON_CMD[@]}" -m uvicorn lorebook.api.app:app \
    --app-dir src \
    --reload \
    --port 8000 \
    --log-config scripts/uvicorn-log-config.json
) &
api_pid=$!

echo "Starting Vite on http://localhost:5173 ..."
(
  cd "$UI_DIR"
  npm run dev
) &
vite_pid=$!

if ! kill -0 "$api_pid" >/dev/null 2>&1 || ! kill -0 "$vite_pid" >/dev/null 2>&1; then
  echo "Failed to launch one or both servers. API PID: ${api_pid:-0}, Vite PID: ${vite_pid:-0}" >&2
  exit 1
fi

echo "Both servers running. Press Ctrl+C to stop."
wait "$api_pid" "$vite_pid"
