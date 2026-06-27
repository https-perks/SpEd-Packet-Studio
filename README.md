# SpEd Packet Studio

A local-first desktop publishing application for special education service packets.

## Architecture

Tauri desktop shell -> React and TypeScript presentation -> local FastAPI business layer -> SQLAlchemy ORM -> SQLite persistence -> WeasyPrint export engine.

## Version 1.0 scope

Version 1.0 is feature-complete for producing local special education service
packets without external software.

The guided workflow is:

1. Student Setup
2. At-a-Glance Builder
3. Goal Builder
4. Data Sheet Builder
5. Observation Sheets
6. Packet Designer
7. Review & Export

Included:

- Project Dashboard with create, open, search, duplicate, archive, and restore
- Student profile, service areas, service minutes, delivery model, and setting
  management
- At-a-Glance editable sections with visibility, ordering, live preview,
  autosave, and validation
- Goal creation, editing, deletion, duplication, service-area assignment,
  ordering, autosave, and validation
- Data Sheet Builder with reusable templates, goal linking, editable table
  columns, blank table instance counts, autosave, and validation
- Observation Sheets as a separate workflow from goal data collection, including
  custom observation tables and customizable "Things Staff Need To Tell..."
  checklist items
- Packet Designer with per-version page visibility, page ordering, live preview,
  autosave, and theme application
- Review & Export with full validation, selected-version export, export-all
  packet versions, deterministic PDF export, and local JSON backup support
- Local SQLite project storage and local PDF export storage

Each goal stores both its complete IEP statement and a concise data-sheet summary.
The summary is owned by the Goal object and is referenced by the Data Sheet
Builder without duplicating goal language.

Generated PDFs are stored locally under the application data exports folder.
Project backups are stored locally as JSON.

Accommodations/modifications, behavior-plan editing, uploaded visual assets, and
Canva-style granular page editing are intentionally post-1.0 editor features.
The current Packet Designer stores page visibility/order and applies the selected
theme, but does not yet provide freeform layout editing.

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
.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
.venv\Scripts\python.exe -m compileall backend
cargo check --manifest-path src-tauri\Cargo.toml
```

WeasyPrint may emit GLib-GIO warnings on Windows when it inspects registered UWP
file handlers. These warnings do not block PDF generation when the PDF file is
created successfully.
