# SpEd Packet Studio

A local-first desktop publishing application for special education service packets.

On first launch, districts choose their preferred program terminology: SpEd
(Special Education), ESE (Exceptional Student Education), or ESS (Exceptional
Student Services). The choice is stored in Local AppData and controls the
visible product name, interface language, and generated packet terminology.
The Windows application identity and data directory remain stable across
terminology changes so upgrades never split or lose user data.

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
  Alpine Photo, Field Notes, and Editorial Ledger
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

Generated PDFs are staged under the disposable application cache until the user
chooses an export destination.
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

## Windows application-data and packaging contract

Installed builds treat the installation and Tauri resource directories as
read-only. Mutable files live below `%LOCALAPPDATA%\SpEd Packet Studio` in
`data`, `settings`, `templates`, `brand-kits`, `imports`, `backups`, `logs`,
`cache`, and `temp`. Generated working exports use `cache\exports`; the native
Save As flow still copies the final PDF or ZIP to the destination selected by
the user. Built-in assets and templates are bundled resources and are never
modified.

Tauri resolves and creates these directories, then defines
`SPED_PACKET_APP_DATA_DIR`, `SPED_PACKET_RESOURCE_DIR`,
`SPED_PACKET_CACHE_DIR`, `SPED_PACKET_TEMP_DIR`, `SPED_PACKET_LOG_DIR`,
`PACKET_STUDIO_API_HOST`, and `PACKET_STUDIO_API_PORT` for a backend process
launched from that environment. `scripts/dev.mjs` provides the same contract
using `.dev-data` while developing. Python also uses the Windows `LOCALAPPDATA`
environment value as its safe fallback; it never falls back to the executable
or current-working directory.

On first launch, a bundled seed database is copied to `data` if present. A
previous repository/install-adjacent `data` directory is copied once without
overwriting newer AppData files; the old database is backed up first and a
marker is written to `settings\.legacy-data-migration-v1.json`. Pending schema
migrations create a timestamped database copy in `backups`.

Development verification:

```text
pnpm desktop:dev
.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
pnpm build
cargo check --manifest-path src-tauri\Cargo.toml
```

Install build prerequisites, prepare the bundled WeasyPrint native runtime, and
create the frozen backend:

```text
.venv\Scripts\python.exe -m pip install -r backend\requirements-build.txt
pnpm native:prepare
pnpm sidecar:build
src-tauri\binaries\sped-packet-backend-x86_64-pc-windows-msvc.exe --self-test
```

`pnpm native:prepare` copies the Windows GTK/Pango/Cairo runtime needed by
WeasyPrint into `packaging\windows\weasyprint-native\bin`. The sidecar build
prefers that bundled folder, then `WEASYPRINT_NATIVE_BIN`, then common GTK
runtime install locations and `PATH`. The build fails rather than creating a
backend that depends silently on the build PC.

Create traditional Windows installers:

```text
pnpm desktop:build
# Or individually:
pnpm windows:nsis
pnpm windows:msi
pnpm windows:verify
```

Release builds launch the backend through Tauri's sidecar API, disable Uvicorn
reload mode, reserve `127.0.0.1:8765`, and wait up to 30 seconds for the
versioned `/api/v1/health` response before showing the application. Startup
failures display a native Windows error with the backend log location. Standard
output and error are captured in
`%LOCALAPPDATA%\SpEd Packet Studio\logs\backend-sidecar.stdout.log` and
`backend-sidecar.stderr.log`; Python application logging uses `backend.log`.
The sidecar is stopped during application shutdown. Its frozen worker also
watches the Tauri parent PID so it exits after a desktop-process crash.

NSIS uses per-machine mode and installs program files beneath
`C:\Program Files\SpEd Packet Studio`; installation therefore requests
administrator approval, while normal application use is supported as a
standard Windows user. The NSIS output is:

```text
src-tauri\target\release\bundle\nsis\SpEd Packet Studio_<version>_x64-setup.exe
```

The frozen runtime includes CPython, FastAPI, Uvicorn, SQLAlchemy, SQLite,
Pydantic, WeasyPrint and its Python dependencies, plus the bundled
GTK/Pango/Cairo, GLib, GObject, HarfBuzz, Fontconfig, FreeType, image,
compression, and related DLLs prepared under
`packaging\windows\weasyprint-native\bin`. Application resources include
built-in templates, SVG icons, generated custom-font coverage, frontend assets,
and Windows icons. Database migration modules are discovered through the backend
import graph and exercised by the frozen verification startup.

Create an MSIX after reserving the app in Partner Center:

```text
$env:MSIX_IDENTITY_NAME='value from Partner Center'
$env:MSIX_PUBLISHER='CN=value from Partner Center'
$env:MSIX_PUBLISHER_DISPLAY_NAME='Publisher display name'
pnpm msix:build
```

The MSIX version defaults to the value in `version.json` with a fourth `.0`
component. Set `MSIX_VERSION` only when Partner Center requires a different
four-part package revision.

For a signed sideload build, additionally set `MSIX_CERTIFICATE_PATH`,
`MSIX_CERTIFICATE_PASSWORD`, and optionally `MSIX_TIMESTAMP_URL`. The
certificate subject must match `MSIX_PUBLISHER`. Store identity values must
match the reserved Partner Center product; see
`packaging\windows\msix.env.example`. Do not commit PFX files or passwords.

Install each artifact as a standard user, launch it from a working directory
outside the install folder, generate a PDF to a chosen destination, and verify
that the install tree is unchanged and all runtime files are beneath AppData.

For a clean-machine acceptance test, copy only the generated installer to a
Windows 10/11 x64 VM with no Python, Node.js, Rust, GTK, repository, or virtual
environment. Install with administrator approval, sign in as a standard user,
launch from the Start menu, create a project, import a PNG/SVG logo, generate a
PDF, close the app, and confirm no `sped-packet-backend.exe` process remains.
Verify all mutable files are beneath `%LOCALAPPDATA%\SpEd Packet Studio` and
then install the next version over the first to confirm the `data`, `settings`,
`templates`, and `brand-kits` directories are preserved.
## Release version

Edit the `version` value in `version.json` before creating a Windows release:

```json
{
  "version": "1.0.0"
}
```

`BUILD-WINDOWS-RELEASE.cmd` synchronizes that value into the frontend package,
Tauri configuration, Rust package and lockfile, and backend health response
before it runs tests or builds the installer. Versions must use three numeric
parts, such as `1.0.0` or `1.2.3`.
