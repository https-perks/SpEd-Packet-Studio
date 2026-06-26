# SpEd Packet Studio

A local-first desktop publishing application for special education service packets.

## Architecture

Tauri desktop shell -> React and TypeScript presentation -> local FastAPI business layer -> SQLAlchemy ORM -> SQLite persistence -> WeasyPrint export engine.

## Current scope

Sprint 4 includes:

- Project Dashboard with create, open, search, duplicate, archive, and restore
- Student Setup with service areas and initial packet audiences
- Goal Builder
- At-a-Glance Builder with live preview
- Data Sheet Builder with reusable progress-monitoring sheet definitions,
  editable table columns, and blank table instance counts
- Packet Designer with a deterministic packet outline and repeated blank data
  table previews
- Review & Export with deterministic local PDF generation through FastAPI and
  WeasyPrint
- Continuous autosave and progressive validation

Each goal stores both its complete IEP statement and a concise data-sheet summary.
The summary is owned by the Goal object and is referenced by the Data Sheet
Builder without duplicating goal language.

Generated PDFs are stored locally under the application data exports folder.
Accommodations and modifications are intentionally separate from At-a-Glance and
are reserved for a future dedicated page/editor.

## Development

Prerequisites: Node.js and pnpm, Rust with Tauri prerequisites, Python 3.11+,
and the native WeasyPrint rendering libraries required for PDF export on your
operating system.

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
