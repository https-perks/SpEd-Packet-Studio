# SpEd Packet Studio

A local-first desktop publishing application for special education service packets.

## Architecture

Tauri desktop shell -> React and TypeScript presentation -> local FastAPI business layer -> SQLAlchemy ORM -> SQLite persistence -> WeasyPrint export engine.

## Version 1.6 scope

Version 1.6 continues the productivity and personalization expansion while
preserving the guided Version 1 workflow. The emphasis is now on reusable
settings, cleaner export behavior, and packet content that is easier for staff
to scan.

Included in the current 1.6 build:

- Dashboard advanced filters for grade, school year, case manager, service area,
  and projects missing data sheets
- Multi-project selection with bulk archive, restore, duplicate, export, rename,
  and delete actions
- Dedicated Archive view with restore, duplicate, export, rename, and permanent
  delete support
- Duplicate wizard options for choosing which project sections carry forward
- Packet template library with preview, edit, hide/restore for built-in
  templates, and custom template support
- Focused packet templates, including Modern Professional, District Branding,
  Mountain Illustrated, and other designed packet layouts
- Template-specific PDF styling so cover, section headers, cards, service icons,
  and data pages share a cohesive visual language
- Theme palette management with editable colors, including service-area icon
  colors for goal summary, service information, and data collection pages
- Brand Kit management with cover logo upload, watermark logo upload, font
  selection, footer text, and optional application during export
- Service-area icon support using local SVG assets, with fallback icons when a
  service area has no matching asset
- Student Setup support pages for structured accommodations/modifications and
  structured behavior-plan sections
- Related service provider management from the Case Manager card, with provider
  contacts included in the Service Information page
- Observation Sheets as a separate workflow from goal data collection, including
  custom observation tables and customizable "Things Staff Need To Tell..."
  checklist items
- Data Sheet Template settings with a reusable template library, editable table
  columns, left/right column ordering, collection type, and staff notes
- Data Sheet Builder template application, goal linking, local column editing,
  collection schedule, packet table count, and notes for staff
- Packet Designer per-version page visibility and pointer-based page ordering
- Empty accommodations and behavior pages are skipped from Packet Designer and
  generated exports until content exists
- Review & Export with PDF preview, single PDF export, ZIP archive export for all
  versions, and a native Windows Save As flow for file name and location
- Local JSON backup support

Still planned for later versions:

- Template import/export and sharing
- Template thumbnail caching and deeper performance work
- Uploaded asset placement in a future visual page editor
- Manual data table column width control
- Canva-style granular page editing

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

Accommodations/modifications and behavior plans are now structured Student Setup
content. Uploaded visual assets and Canva-style granular page editing remain
future editor features. The current Packet Designer stores page visibility/order
and applies the selected template/theme, but does not yet provide freeform layout
editing.

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
