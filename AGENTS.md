# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

KGE-Gen is a knowledge-graph-guided synthetic data generation platform (前后端分离架构). It consists of:

- **FastAPI backend** (`backend/app.py`) on port 8000
- **Vue 3 + Vite frontend** (`frontend/`) on port 3000 (proxies `/api` to backend)
- **Core Python library** (`graphgen/`) — knowledge graph construction + QA generation
- **CLI tool** (`graphgen_cli.py`) for batch processing

No database or Docker required — all storage is file-based (JSON + NetworkX graphs).

### Environment setup

- **Python 3.10** is required (installed via `deadsnakes` PPA). The venv is at `/workspace/.venv`.
- **Node.js** (system default v22) with npm is used for the frontend.
- A `.env` file is needed in the project root — copy from `.env.example`. Set `MOCK_MODE=True` to run without a real LLM API key.

### Running services

```bash
# Backend
source /workspace/.venv/bin/activate
cd /workspace && uvicorn backend.app:app --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd /workspace/frontend && npm run dev
```

### Default credentials

- Admin: `admin` / `admin123`
- Reviewer: `reviewer` / `reviewer123`

### Running tests

```bash
source /workspace/.venv/bin/activate
cd /workspace && python -m pytest tests/ --timeout=30 -v --ignore=tests/test_parallel_batch.py
```

**Known test issues (pre-existing):**
- `tests/test_parallel_batch.py` has a broken import (`batch_process_parallel` module not found) — skip it.
- 2 async tests (`test_hierarchical_integration.py::test_integration`, `test_hierarchical_quick.py::test_hierarchical_partitioner`) fail because they need `pytest-asyncio` with proper `@pytest.mark.asyncio` markers.
- `test_tree_generator_quick.py::test_tree_generator_serialization` fails due to missing `_serialize_to_format` method.

### Frontend build / lint caveats

- `npx vite build` works for production builds (skips `vue-tsc` type checking).
- The `npm run build` script (`vue-tsc && vite build`) fails because `vue-tsc@1.8.27` is incompatible with Node 22. This is a pre-existing issue.
- ESLint (`npm run lint`) fails because `.eslintrc.js` uses CommonJS `module.exports` but `package.json` declares `"type": "module"`. Rename to `.eslintrc.cjs` to fix if needed.

### API docs

Backend Swagger UI is available at `http://localhost:8000/docs` when the backend is running.
