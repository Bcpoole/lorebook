# Current Failing Issues Report

Generated: 2026-06-19

## 1) Python lint (`python -m ruff check .`) — **FAILED**

### `src/lorebook/api/routes/experimentation.py`
- `282:30` — Python 3.10 syntax error: escape sequence in nested f-string (requires Python 3.12).
- `282:49` — Python 3.10 syntax error: escape sequence in nested f-string (requires Python 3.12).
- `448:64` — Python 3.10 syntax error: escape sequence in nested f-string (requires Python 3.12).

### `src/lorebook/api/routes/personas_crud.py`
- `4:47` — `F401` unused import: `UploadFile`.
- `4:59` — `F401` unused import: `File`.
- `9:57` — `F401` unused import: `PersonaPrompt`.

### `src/lorebook/api/storage.py`
- `1020:17` — `F821` undefined name: `_find_run_by_id`.

Ruff summary: **7 errors total** (3 fixable automatically by Ruff).

---

## 2) Backend tests (`python -m pytest -q`) — **FAILED**

### Failing tests
1. `tests/test_experimentation.py::test_save_and_load_round_trip`
   - Assertion failed because loaded config contains extra key:
   - `general.addCopyTagOnDuplicate = True`
   - Expected payload did not include that key.

2. `tests/test_experimentation.py::test_save_multiple_times_overwrites`
   - Same mismatch on loaded config:
   - `general.addCopyTagOnDuplicate = True` appears in response but not in expected payload.

Pytest summary: **2 failed, 62 passed, 1 warning**.

---

## 3) Frontend build (`npm run build` in `ui/`) — **FAILED**

- Error: `'vite' is not recognized as an internal or external command`.
- Likely cause: frontend dependencies are not installed (`ui/node_modules` missing or incomplete).

---

## 4) Frontend tests (`npm test` in `ui/`) — **FAILED**

- Error: `'vitest' is not recognized as an internal or external command`.
- Likely cause: frontend dependencies are not installed (`ui/node_modules` missing or incomplete).
