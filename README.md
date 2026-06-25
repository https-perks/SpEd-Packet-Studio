# SpEd Packet Studio

A local-first desktop publishing application for special education service packets.

## Architecture

Tauri desktop shell -> React and TypeScript presentation -> local FastAPI business layer -> SQLAlchemy ORM -> SQLite persistence -> WeasyPrint export engine.

## Current scope

Sprint 1 includes:

- Project Dashboard with create, open, search, duplicate, archive, and restore
- Student Setup with service areas and initial packet audiences
- Goal Builder
- At-a-Glance Builder with live preview
- Continuous autosave and progressive validation

Data sheets, packet design, and export remain reserved for later sprints.

## Development

Prerequisites: Node.js and pnpm, Rust with Tauri prerequisites, and Python 3.11+.

```text
pnpm install
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
pnpm desktop:dev
```

Frontend-only: `pnpm dev`. Backend-only: `python -m backend`.

## Verification

```text
pnpm build
pnpm backend:check
pnpm backend:test
python -m backend.database.initialize
cargo check --manifest-path src-tauri\Cargo.toml
```
