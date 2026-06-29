# SpEd Packet Studio

A local-first desktop publishing application for special education service packets.

## Architecture

Tauri desktop shell -> React and TypeScript presentation -> local FastAPI business layer -> SQLAlchemy ORM -> SQLite persistence -> WeasyPrint export engine.

## Version 1.5 scope

Version 1.5 begins the productivity and personalization expansion while keeping
the Version 1 guided workflow intact. The focus is reducing repetitive work
without turning the app into a freeform page editor.

Included in the current 1.5 foundation:

- Dashboard advanced filters for grade, school year, case manager, service area,
  and projects missing data sheets
- Multi-project selection with bulk archive, restore, duplicate, export, rename,
  and delete actions
- Dedicated archive cleanup through permanent delete after a project has already
  been archived, including selected-project cleanup in Archive view
- Duplicate wizard options for choosing which project sections carry forward
- Template library preview for built-in packet templates
- Additional built-in packet templates: Modern Professional, Elementary
  Friendly, Minimal, District Branding, and Contemporary
- Theme gallery metadata with Elementary Friendly and Minimal theme additions
- Theme color customization for primary, secondary, accent, background, card,
  text, and service-area colors in the packet rendering layer
- Brand Kit fields and local logo upload support in the packet rendering layer
- Export settings for plain custom filenames, export mode, and selected save
  folder
- Native Windows folder picker support for export destinations
- ZIP archive export for all packet versions

Still planned for later 1.5 passes:

- Dashboard-level Brand Kit library management
- Dashboard-level template editing and user-created templates
- Template import/export and sharing
- Full template create/rename/archive/delete management
- Template thumbnails and larger template library management
- Thumbnail caching and deeper performance work

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
- Review & Export with full validation, selected-version export, PDF preview,
  deterministic PDF/ZIP export, and local JSON backup support
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
