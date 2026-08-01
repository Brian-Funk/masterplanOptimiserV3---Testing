# MasterplanOptimiserV3 — Testing

Standalone automated test suite for the MasterplanOptimiserV3 stack.

This repository is licensed under `AGPL-3.0-only`. See [LICENSE](LICENSE),
[third-party notices](THIRD-PARTY-NOTICES.md), [branding](BRANDING.md) and the
[contribution-provenance record](COPYRIGHT-AND-CONTRIBUTION-PROVENANCE.md).

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

# Select exact source checkouts when discovery would be ambiguous
set MP_OPT_APP_ROOT=C:\path\to\App-Public
set MP_OPT_SERVER_ROOT=C:\path\to\Server-Public

# Run Python backend tests in product-isolated environments
.venv-server\Scripts\python -m pytest server_backend/ -v
.venv-desktop\Scripts\python -m pytest desktop_backend/ -v

# Run frontend tests
npx vitest run --config vitest.config.server.ts
npx vitest run --config vitest.config.desktop.ts
```

## How It Works

- Repository roots come from `MP_OPT_APP_ROOT` and `MP_OPT_SERVER_ROOT`, or from
  unambiguous bounded checkout discovery.
- Desktop and Server Python tests use separate virtual environments populated
  from the exact source checkout's committed requirement and constraint files.
- Frontend tests reference sibling repo source via Vitest path aliases
- No changes are needed in the App, Server, or Docs repos
- Backend tests use SQLite in-memory databases for speed
- Server tests bypass passkey auth by injecting session records directly
