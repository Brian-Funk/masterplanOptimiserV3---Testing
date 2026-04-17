# MasterplanOptimiserV3 — Testing

Standalone automated test suite for the MasterplanOptimiserV3 stack.

## Structure

```
server_backend/     — Phase 1: Server (FastAPI + PostgreSQL) backend API tests
desktop_backend/    — Phase 2: Desktop (FastAPI + SQLite) backend API tests
server_frontend/    — Phase 3: Server (Next.js) frontend component tests
desktop_frontend/   — Phase 4: Desktop (Next.js) frontend component tests
```

## Setup

```bash
# One-time setup
setup.bat           # Windows: creates venv, installs Python + Node deps

# Run Python backend tests
.venv\Scripts\activate
pytest server_backend/ -v
pytest desktop_backend/ -v

# Run frontend tests
npx vitest run --config vitest.config.server.ts
npx vitest run --config vitest.config.desktop.ts
```

## How It Works

- Python tests import from sibling project repos via `sys.path` in `conftest.py`
- Frontend tests reference sibling repo source via Vitest path aliases
- No changes are needed in the App, Server, or Docs repos
- Backend tests use SQLite in-memory databases for speed
- Server tests bypass passkey auth by injecting session records directly
