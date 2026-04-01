# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

KGE-Gen (GraphGen) is a knowledge-graph-guided SFT data generation platform. Architecture: Python FastAPI backend (port 8000) + Vue 3 / Vite frontend (port 3000). No external database — all state is stored in JSON files on disk.

### Services

| Service | Port | Start command |
|---------|------|---------------|
| FastAPI backend | 8000 | `uvicorn backend.app:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 300` |
| Vue frontend (dev) | 3000 | `cd frontend && npm run dev` |

### Running services

- Backend: `uvicorn backend.app:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 300` from the repo root.
- Frontend: `cd frontend && npm run dev` (Vite dev server, proxies `/api` → backend).
- The `.env` file (copy from `.env.example`) must exist. Set `MOCK_MODE=True` to run without a real LLM API key.
- Default login credentials: `admin` / `admin123` (created automatically on first backend start in `cache/users.json`).

### Lint / Test / Build

- **Python tests**: `python -m pytest tests/ --ignore=tests/test_parallel_batch.py` (one test file has a broken import — pre-existing).
- **Frontend lint**: The ESLint config `.eslintrc.js` must be renamed to `.eslintrc.cjs` to work with `"type": "module"` in `package.json`. Run: `cd frontend && mv .eslintrc.js .eslintrc.cjs && npx eslint . --ext .vue,.ts,.tsx --ignore-path .gitignore; mv .eslintrc.cjs .eslintrc.js`. Pre-existing lint warnings/errors exist.
- **TypeScript check**: `vue-tsc` is incompatible with the current Node.js 22 version (pre-existing issue). Use `npx vue-tsc --noEmit` under Node 18/20 if needed.
- **Frontend build**: `cd frontend && npm run build` (runs vue-tsc + vite build).

### Gotchas

- `$HOME/.local/bin` must be on `PATH` for `uvicorn` and other pip-installed scripts.
- The frontend Vite config (`vite.config.ts`) proxies `/api` to `http://localhost:8000` by default. Override with `VITE_BACKEND_URL` env var if the backend runs elsewhere.
- User data is stored in `cache/users.json`; task data in `tasks/`. These directories are auto-created by the backend on startup.
