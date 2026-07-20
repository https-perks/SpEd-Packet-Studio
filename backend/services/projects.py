from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from datetime import date, datetime, timezone
from functools import lru_cache
import hashlib
from html import escape
from io import BytesIO
import json
import re
from pathlib import Path
from typing import Iterable
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from backend.config import settings
from backend.paths import paths
from backend.generators.pdf import PdfRenderRequest, render_pdf
from backend.models import AtAGlance, DataSheet, Export, Goal, PacketVersion, Project, ServiceArea, Student
from backend.schemas.projects import (
    AccommodationDraft,
    AtAGlanceDraft,
    AtAGlanceResponse,
    AtAGlanceSectionDraft,
    BackupResponse,
    BehaviorPlanSectionDraft,
    BrandKit,
    BrandKitLibraryDraft,
    BrandKitLibraryItem,
    BrandKitLogoUpload,
    BrandLogoUpload,
    BulkProjectAction,
    BulkProjectActionResponse,
    DataSheetDraft,
    DataSheetResponse,
    DataSheetsDraft,
    DEFAULT_SERVICE_AREA_COLORS,
    DuplicateOptions,
    ExportSettings,
    ExportSettingsSelection,
    ExportAllResponse,
    ExportRequest,
    ExportResponse,
    GoalResponse,
    GoalsDraft,
    ObservationChecklistDraft,
    PacketBuilderDraft,
    PacketPageDraft,
    PacketTemplateLibraryDraft,
    PacketTemplateLibraryItem,
    PacketTemplateOption,
    TemplatePreviewRequest,
    PacketVersionDraft,
    PacketVersionResponse,
    PacketVersionConfig,
    AssetPlacementDraft,
    RelatedServiceProviderDraft,
    AppSettings,
    ProjectDetail,
    ProjectSummary,
    ServiceAreaDraft,
    ServiceAreaResponse,
    DataSheetColumnDraft,
    StepValidation,
    StudentResponse,
    StudentSetupDraft,
    ThemeCustomization,
    ThemePaletteDraft,
    ThemeSelection,
    ThemeOption,
    ValidationIssue,
)

AUDIENCE_LABELS = {
    "case_manager": "Case Manager",
    "general_education": "General Education",
    "paraeducator": "Paraeducator",
    "related_services": "Related Services",
    "substitute": "Substitute",
}

DEFAULT_PACKET_VERSION_OPTIONS = [
    PacketVersionDraft(id=None, name=label, audience=audience)
    for audience, label in AUDIENCE_LABELS.items()
]

DEFAULT_DATA_SHEET_COLUMNS = [
    {"id": "date", "title": "Date", "column_type": "date", "position": 0},
    {"id": "trial", "title": "Trial", "column_type": "text", "position": 1},
    {"id": "result", "title": "Result", "column_type": "text", "position": 2},
    {"id": "notes", "title": "Notes", "column_type": "notes", "position": 3},
]

DEFAULT_PACKET_PAGES = [
    {"id": "cover", "title": "Cover Page", "page_type": "cover"},
    {"id": "at_a_glance", "title": "At-a-Glance", "page_type": "at_a_glance"},
    {"id": "accommodations", "title": "Accommodations/Modifications", "page_type": "placeholder"},
    {"id": "accommodations_signature", "title": "Accommodations Signature Page", "page_type": "placeholder"},
    {"id": "behavior", "title": "Behavior Plans", "page_type": "placeholder"},
    {"id": "goal_summary", "title": "Goal Summary", "page_type": "goal_summary"},
    {"id": "services", "title": "Service Areas", "page_type": "services"},
    {"id": "data_collection", "title": "Data Collection", "page_type": "data_collection"},
    {"id": "observations", "title": "Observations & Notes", "page_type": "observations"},
]

DEFAULT_OBSERVATION_CHECKLIST = [
    "Consistently struggling despite accommodations",
    "Social concerns",
    "Accommodations are not sufficient",
    "Student requests additional help",
    "New behavior concerns",
    "Student refusing accommodations",
    "Significant academic improvement",
    "Medical / health concerns",
    "Concerns from parents",
    "Other observations",
]

DEFAULT_ACCOMMODATIONS_TEACHER_NOTE = (
    "In order to help this student be successful, you need to be informed of your "
    "specific responsibilities related to this student and the accommodations, "
    "modifications and supports that must be provided for this student. If you have "
    "any questions or need further information, please talk to the case manager."
)

DEFAULT_ACCOMMODATIONS_SIGNATURE_NOTE = (
    "The following staff have been informed of their specific responsibilities related "
    "to this student and the accommodations, modifications and supports that must be provided."
)

DEFAULT_SERVICE_AREA_PRESETS = [
    ServiceAreaDraft(name="Reading", position=0),
    ServiceAreaDraft(name="Math", position=1),
    ServiceAreaDraft(name="Written Expression", position=2),
    ServiceAreaDraft(name="Social/Emotional/Behavioral", position=3),
    ServiceAreaDraft(name="Self-Help/Independence", position=4),
]

MINIMAL_SERVICE_AREA_COLOR = "#4B5563"

DEFAULT_DATA_SHEET_COLUMN_DRAFTS = [
    DataSheetColumnDraft(**column) for column in DEFAULT_DATA_SHEET_COLUMNS
]

DEFAULT_DATA_SHEET_TEMPLATES = [
    DataSheetDraft(
        id="template_trial_probe",
        title="Skill Probe",
        sheet_type="trial_count",
        goal_ids=[],
        collection_schedule="Weekly",
        blank_instance_count=1,
        columns=[
            DataSheetColumnDraft(id="date", title="Date", column_type="date", position=0),
            DataSheetColumnDraft(id="trial", title="Trial", column_type="text", position=1),
            DataSheetColumnDraft(id="result", title="Result", column_type="text", position=2),
            DataSheetColumnDraft(id="notes", title="Notes", column_type="notes", position=3),
        ],
        notes="Use one row per probe or trial.",
        template_name="Skill Probe",
        is_template=True,
        is_observation_form=False,
        position=0,
    ),
    DataSheetDraft(
        id="template_frequency",
        title="Frequency Tracker",
        sheet_type="frequency",
        goal_ids=[],
        collection_schedule="Daily",
        blank_instance_count=1,
        columns=[
            DataSheetColumnDraft(id="date", title="Date", column_type="date", position=0),
            DataSheetColumnDraft(id="activity", title="Activity / Setting", column_type="text", position=1),
            DataSheetColumnDraft(id="count", title="Count", column_type="number", position=2),
            DataSheetColumnDraft(id="notes", title="Notes", column_type="notes", position=3),
        ],
        notes="Track frequency across settings or instructional blocks.",
        template_name="Frequency Tracker",
        is_template=True,
        is_observation_form=False,
        position=1,
    ),
]

THEME_OPTIONS = [
    ThemeOption(
        id="teacher_friendly",
        name="Teacher Friendly",
        description="Polished blue, teal, green, purple, and orange packet theme.",
        category="Professional",
    ),
    ThemeOption(
        id="minimal",
        name="Minimal",
        description="High-readability theme with very light color for photocopy-friendly packets.",
        category="Minimal",
    ),
    ThemeOption(
        id="district_colors",
        name="District Colors",
        description="Custom district branding palette with editable primary, secondary, and accent colors.",
        category="District",
    ),
    ThemeOption(
        id="field_notes",
        name="Field Notes",
        description="Forest green, warm copper, and paper-inspired neutrals.",
        category="Template",
    ),
    ThemeOption(
        id="editorial_ledger",
        name="Editorial Ledger",
        description="Ink blue, editorial brown, and restrained antique gold.",
        category="Template",
    ),
    ThemeOption(
        id="modular_blocks",
        name="Modular Blocks",
        description="Deep navy, geometric teal, and energetic orange.",
        category="Template",
    ),
    ThemeOption(
        id="alpine_photo",
        name="Alpine Photo",
        description="Alpine navy, dusk blue, and glacial cyan.",
        category="Template",
    ),
    ThemeOption(
        id="mid_century_classroom",
        name="Mid-Century Classroom",
        description="Teal, ochre, brick, and warm classroom-paper neutrals.",
        category="Template",
    ),
    ThemeOption(
        id="typographic_poster",
        name="Typographic",
        description="Poster-style navy type, clay accent, and refined editorial neutrals.",
        category="Template",
    ),
    ThemeOption(
        id="signal_atlas",
        name="Signal",
        description="Dramatic signal navy, technical teal, and high-contrast orange.",
        category="Template",
    ),
]

THEME_TOKENS = {
    "studio": {
        "primary": "#17345f",
        "accent": "#c05f1a",
        "soft": "#eef3f8",
        "border": "#cbd5e1",
        "green": "#5ca04a",
        "purple": "#7a60b4",
        "orange": "#e46f00",
    },
    "teacher_friendly": {
        "primary": "#0f2d55",
        "accent": "#27b8b2",
        "blue": "#1f6fb8",
        "blue_soft": "#eef7ff",
        "teal": "#27b8b2",
        "green": "#73b85a",
        "green_soft": "#f1faed",
        "purple": "#7d66b7",
        "purple_soft": "#f5f1fb",
        "orange": "#ef7900",
        "orange_soft": "#fff4e7",
        "soft": "#f3f7fc",
        "border": "#bdd3ec",
        "text": "#12213a",
    },
    "minimal": {
        "primary": "#111827",
        "accent": "#4b5563",
        "blue": "#1f2937",
        "blue_soft": "#f9fafb",
        "teal": "#374151",
        "green": "#374151",
        "green_soft": "#f9fafb",
        "purple": "#374151",
        "purple_soft": "#f9fafb",
        "orange": "#111827",
        "orange_soft": "#f8fafc",
        "soft": "#ffffff",
        "border": "#d1d5db",
        "text": "#111827",
    },
    "district_colors": {
        "primary": "#0d2848",
        "accent": "#154f85",
        "blue": "#1d6fb8",
        "blue_soft": "#eef4fb",
        "teal": "#154f85",
        "green": "#1d6fb8",
        "green_soft": "#eef4fb",
        "purple": "#154f85",
        "purple_soft": "#eef4fb",
        "orange": "#d89a2b",
        "orange_soft": "#fff7e6",
        "soft": "#ffffff",
        "border": "#c9d6e4",
        "text": "#14233c",
    },
    "field_notes": {
        "primary": "#274c3b",
        "accent": "#b86b3c",
        "blue": "#3f6f61",
        "teal": "#4f8070",
        "green": "#6f8f58",
        "purple": "#6f5a7f",
        "orange": "#d7b56d",
        "soft": "#f4f0e6",
        "card": "#fffdf8",
        "border": "#d8c9a8",
        "text": "#24322b",
    },
    "editorial_ledger": {
        "primary": "#26364a",
        "accent": "#8a5a44",
        "blue": "#3f5f7d",
        "teal": "#557a78",
        "green": "#66785c",
        "purple": "#6f607b",
        "orange": "#c3a354",
        "soft": "#f2efe9",
        "card": "#fffdf9",
        "border": "#d4cec4",
        "text": "#25282d",
    },
    "modular_blocks": {
        "primary": "#17345f",
        "accent": "#00a6a6",
        "blue": "#2563eb",
        "teal": "#00a6a6",
        "green": "#22a06b",
        "purple": "#7654a6",
        "orange": "#e56b2f",
        "soft": "#eef2f5",
        "card": "#ffffff",
        "border": "#b9c5d1",
        "text": "#17212b",
    },
    "alpine_photo": {
        "primary": "#17345f",
        "accent": "#3d759d",
        "blue": "#2d6f9f",
        "teal": "#2bb5c4",
        "green": "#4f8f73",
        "purple": "#665f91",
        "orange": "#2bb5c4",
        "soft": "#eaf1f6",
        "card": "#ffffff",
        "border": "#b8d8ee",
        "text": "#14233c",
    },
    "mid_century_classroom": {
        "primary": "#235c64",
        "accent": "#b6583f",
        "blue": "#235c64",
        "teal": "#235c64",
        "green": "#6f8f58",
        "purple": "#6f5a7f",
        "orange": "#e3b23c",
        "orange_soft": "#fbf0d0",
        "soft": "#f3ead7",
        "card": "#fffdf7",
        "border": "#262626",
        "text": "#262626",
    },
    "typographic_poster": {
        "primary": "#14233c",
        "accent": "#5b7f78",
        "blue": "#14233c",
        "teal": "#5b7f78",
        "green": "#5f7f70",
        "purple": "#5d5a78",
        "orange": "#d5633c",
        "soft": "#f3f0e8",
        "card": "#ffffff",
        "border": "#14233c",
        "text": "#1e2430",
    },
    "signal_atlas": {
        "primary": "#102a43",
        "accent": "#00a6a6",
        "blue": "#102a43",
        "teal": "#00a6a6",
        "green": "#2f8f7a",
        "purple": "#52627a",
        "orange": "#ff8a3d",
        "soft": "#eef3f5",
        "card": "#ffffff",
        "border": "#b8c7d0",
        "text": "#17212b",
    },
    "elementary": {
        "primary": "#24577a",
        "accent": "#35b7a9",
        "blue": "#3182ce",
        "blue_soft": "#ebf8ff",
        "teal": "#35b7a9",
        "green": "#74b84a",
        "green_soft": "#f1faed",
        "purple": "#8a6fd1",
        "purple_soft": "#f5f1fb",
        "orange": "#f08a24",
        "orange_soft": "#fff5e8",
        "soft": "#f7fbff",
        "border": "#bad8f3",
        "text": "#123247",
    },
    "modern": {
        "primary": "#12385f",
        "accent": "#18aeb5",
        "blue": "#2563eb",
        "blue_soft": "#eff6ff",
        "teal": "#18aeb5",
        "green": "#31a36b",
        "green_soft": "#ecfdf5",
        "purple": "#7c3aed",
        "purple_soft": "#f5f3ff",
        "orange": "#f97316",
        "orange_soft": "#fff7ed",
        "soft": "#f5f9fc",
        "border": "#bfdbfe",
        "text": "#102033",
    },
    "professional": {
        "primary": "#1f3f5b",
        "accent": "#64748b",
        "blue": "#2f6690",
        "blue_soft": "#eef4f8",
        "teal": "#4f8a8b",
        "green": "#47785f",
        "green_soft": "#eef7f2",
        "purple": "#625d8f",
        "purple_soft": "#f3f2f8",
        "orange": "#b7652b",
        "orange_soft": "#fbf1e8",
        "soft": "#f6f7f9",
        "border": "#cbd5e1",
        "text": "#17212b",
    },
    "rounded": {
        "primary": "#284b63",
        "accent": "#3cbbb1",
        "blue": "#3b82c4",
        "blue_soft": "#edf7ff",
        "teal": "#3cbbb1",
        "green": "#7bbf54",
        "green_soft": "#f3faee",
        "purple": "#9370db",
        "purple_soft": "#f7f2ff",
        "orange": "#ff8a3d",
        "orange_soft": "#fff3ea",
        "soft": "#f8fbfd",
        "border": "#c7ddea",
        "text": "#1b2c36",
    },
    "classic": {
        "primary": "#17345f",
        "accent": "#b7791f",
        "blue": "#1e4f86",
        "blue_soft": "#f0f5fb",
        "teal": "#2f6f73",
        "green": "#557a46",
        "green_soft": "#f2f6ef",
        "purple": "#63507f",
        "purple_soft": "#f3f0f7",
        "orange": "#b7791f",
        "orange_soft": "#fbf4e7",
        "soft": "#f8f6f0",
        "border": "#d8c9a8",
        "text": "#17253d",
    },
    "flat": {
        "primary": "#22313f",
        "accent": "#00a6a6",
        "blue": "#2563eb",
        "blue_soft": "#f1f5f9",
        "teal": "#00a6a6",
        "green": "#16a34a",
        "green_soft": "#f1f5f9",
        "purple": "#9333ea",
        "purple_soft": "#f1f5f9",
        "orange": "#ea580c",
        "orange_soft": "#f1f5f9",
        "soft": "#f1f5f9",
        "border": "#94a3b8",
        "text": "#0f172a",
    },
}

PACKET_TEMPLATE_OPTIONS = [
    PacketTemplateOption(
        id="modern_professional",
        name="Modern Professional",
        description="Clean layout with geometric accents.",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="district_branding",
        name="District Branding",
        description="Logo-forward layout for district packets.",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="alpine_photo",
        name="Alpine Photo",
        description="Dark cover with mountain-inspired shapes.",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="field_notes",
        name="Field Notes",
        description="Notebook style with warm paper colors.",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="editorial_ledger",
        name="Editorial Ledger",
        description="Editorial layout with ruled sections.",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="modular_blocks",
        name="Modular Blocks",
        description="Block-based layout with strong contrast.",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="mid_century_classroom",
        name="Mid-Century Classroom",
        description="Retro classroom layout with warm shapes.",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="typographic_poster",
        name="Typographic",
        description="Type-focused cover with bold spacing.",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="signal_atlas",
        name="Signal",
        description="Dark technical cover with clean interior pages.",
        page_count_hint="Standard",
    ),
]


FIELD_NOTES_CUSTOMIZATION = ThemeCustomization(
    primary_color="#274c3b",
    secondary_color="#b86b3c",
    accent_color="#d7b56d",
    background_color="#f4f0e6",
    card_color="#fffdf8",
    text_color="#24322b",
)

EDITORIAL_LEDGER_CUSTOMIZATION = ThemeCustomization(
    primary_color="#26364a",
    secondary_color="#8a5a44",
    accent_color="#c3a354",
    background_color="#f2efe9",
    card_color="#fffdf9",
    text_color="#25282d",
)

MODULAR_BLOCKS_CUSTOMIZATION = ThemeCustomization(
    primary_color="#17345f",
    secondary_color="#00a6a6",
    accent_color="#e56b2f",
    background_color="#eef2f5",
    card_color="#ffffff",
    text_color="#17212b",
)

ALPINE_PHOTO_CUSTOMIZATION = ThemeCustomization(
    primary_color="#17345f",
    secondary_color="#3d759d",
    accent_color="#2bb5c4",
    background_color="#eaf1f6",
    card_color="#ffffff",
    text_color="#14233c",
)

MID_CENTURY_CLASSROOM_CUSTOMIZATION = ThemeCustomization(
    primary_color="#235c64",
    secondary_color="#b6583f",
    accent_color="#e3b23c",
    background_color="#f3ead7",
    card_color="#fffdf7",
    text_color="#262626",
)

TYPOGRAPHIC_POSTER_CUSTOMIZATION = ThemeCustomization(
    primary_color="#14233c",
    secondary_color="#5b7f78",
    accent_color="#d5633c",
    background_color="#f3f0e8",
    card_color="#ffffff",
    text_color="#1e2430",
)

SIGNAL_ATLAS_CUSTOMIZATION = ThemeCustomization(
    primary_color="#102a43",
    secondary_color="#00a6a6",
    accent_color="#ff8a3d",
    background_color="#eef3f5",
    card_color="#ffffff",
    text_color="#17212b",
)

TEMPLATE_DEFAULT_THEME_IDS = {
    "alpine_photo": "alpine_photo",
    "district_branding": "district_colors",
    "field_notes": "field_notes",
    "editorial_ledger": "editorial_ledger",
    "modular_blocks": "modular_blocks",
    "mid_century_classroom": "mid_century_classroom",
    "typographic_poster": "typographic_poster",
    "signal_atlas": "signal_atlas",
}


def _project_query():
    return select(Project).options(
        selectinload(Project.student),
        selectinload(Project.service_areas),
        selectinload(Project.goals),
        selectinload(Project.at_a_glance),
        selectinload(Project.data_sheets).selectinload(DataSheet.goals),
        selectinload(Project.packet_versions).selectinload(PacketVersion.exports),
    )


def _student_name(student: Student | None) -> str:
    if student is None:
        return ""
    return " ".join(
        part for part in (student.first_name or "", student.last_name or "") if part
    ).strip()


def _split_name(name: str) -> tuple[str, str]:
    parts = name.strip().split(maxsplit=1)
    return (parts[0], parts[1] if len(parts) > 1 else "") if parts else ("", "")


def derive_initials(name: str) -> str:
    return "".join(part[0].upper() for part in name.split() if part)[:4]


def _case_manager_name(student: Student | None) -> str:
    if student is None:
        return ""
    structured = " ".join(
        part
        for part in (
            student.case_manager_first_name or "",
            student.case_manager_last_name or "",
        )
        if part
    ).strip()
    return structured or (student.case_manager or "")


def suggest_school_year(iep_end_date: date | None) -> str:
    if iep_end_date is None:
        return ""
    start = iep_end_date.year if iep_end_date.month >= 7 else iep_end_date.year - 1
    return f"{start}-{start + 1}"


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-")
    return value.lower() or "student-packet"


def default_export_filename(
    student_name: str, school_year: str, packet_version_name: str = "Service Packet"
) -> str:
    return (
        f"{student_name or 'Student'} - "
        f"{packet_version_name or 'Packet'} - "
        f"{school_year or 'School Year'}.pdf"
    )


def _safe_filename(value: str, extension: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", value).strip(" .-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        cleaned = "Student Packet"
    if not cleaned.lower().endswith(extension.lower()):
        cleaned = f"{Path(cleaned).stem}{extension}"
    return cleaned


def _unique_output_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        next_candidate = directory / f"{stem} ({index}){suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1


def _format_date(value: date | None) -> str:
    return value.isoformat() if value else "Not entered"


def _touch(project: Project) -> None:
    project.updated_at = datetime.now(timezone.utc)


def list_themes() -> list[ThemeOption]:
    overrides = _theme_overrides()
    deleted_builtin_ids = _deleted_builtin_theme_ids()
    builtins = [
        overrides.get(option.id)
        or option.model_copy(
            update={
                "default_customization": _customization_from_tokens(option.id).model_dump(),
                "is_builtin": True,
            }
        )
        for option in THEME_OPTIONS
        if option.id not in deleted_builtin_ids
    ]
    return builtins + _custom_theme_options()


def _library_file(name: str) -> Path:
    path = paths.templates_dir if name == "templates.json" else paths.settings_dir
    path.mkdir(parents=True, exist_ok=True)
    return path / name


def _read_library(name: str) -> dict[str, object]:
    path = _library_file(name)
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _write_library(name: str, value: dict[str, object]) -> None:
    _library_file(name).write_text(
        json.dumps(value, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _app_settings_default() -> AppSettings:
    return AppSettings(
        default_theme_id="teacher_friendly",
        default_packet_template_id="modern_professional",
        default_export_settings=ExportSettings(),
        packet_versions=DEFAULT_PACKET_VERSION_OPTIONS,
        default_packet_pages=_default_packet_pages_from(DEFAULT_PACKET_PAGES),
        default_observation_checklist=DEFAULT_OBSERVATION_CHECKLIST,
        accommodations_teacher_note_enabled=True,
        accommodations_teacher_note_title="Teacher Responsibilities",
        accommodations_teacher_note=DEFAULT_ACCOMMODATIONS_TEACHER_NOTE,
        accommodations_signature_page_enabled=False,
        accommodations_signature_page_title="Accommodations Signature Page",
        accommodations_signature_page_note=DEFAULT_ACCOMMODATIONS_SIGNATURE_NOTE,
        accommodations_signature_line_layout="teacher_coach_date",
        default_data_sheet_columns=DEFAULT_DATA_SHEET_COLUMN_DRAFTS,
        data_sheet_templates=DEFAULT_DATA_SHEET_TEMPLATES,
        service_area_presets=DEFAULT_SERVICE_AREA_PRESETS,
    )


def _default_packet_pages_from(pages: list[dict[str, str]]) -> list[PacketPageDraft]:
    return [
        PacketPageDraft(
            id=str(page["id"]),
            title=str(page["title"]),
            page_type=str(page["page_type"]),
            enabled=True,
            position=position,
        )
        for position, page in enumerate(pages)
    ]


def _merge_default_packet_pages(
    pages: list[PacketPageDraft],
    default_pages: list[PacketPageDraft] | None = None,
) -> list[PacketPageDraft]:
    merged = [page.model_copy(deep=True) for page in pages]
    existing_ids = {page.id for page in merged}
    defaults = default_pages or _default_packet_pages_from(DEFAULT_PACKET_PAGES)
    default_order = [page.id for page in defaults]
    for default_page in defaults:
        if default_page.id in existing_ids:
            continue
        previous_default_ids = default_order[: default_order.index(default_page.id)]
        insert_at = len(merged)
        for index in range(len(merged) - 1, -1, -1):
            if merged[index].id in previous_default_ids:
                insert_at = index + 1
                break
        merged.insert(insert_at, default_page)
        existing_ids.add(default_page.id)
    return [
        page.model_copy(update={"position": position})
        for position, page in enumerate(sorted(merged, key=lambda item: item.position))
    ]


def get_app_settings() -> AppSettings:
    raw = _read_library("app-settings.json")
    defaults = _app_settings_default()
    if not raw:
        return defaults
    try:
        loaded = AppSettings(**raw)
    except ValueError:
        return defaults
    if not loaded.default_packet_pages:
        loaded.default_packet_pages = defaults.default_packet_pages
    else:
        loaded.default_packet_pages = _merge_default_packet_pages(loaded.default_packet_pages)
    if not loaded.default_observation_checklist:
        loaded.default_observation_checklist = defaults.default_observation_checklist
    if not loaded.packet_versions:
        loaded.packet_versions = defaults.packet_versions
    loaded.packet_versions = _normalize_packet_version_options(loaded.packet_versions)
    if not loaded.accommodations_teacher_note:
        loaded.accommodations_teacher_note = defaults.accommodations_teacher_note
    if not loaded.accommodations_teacher_note_title:
        loaded.accommodations_teacher_note_title = defaults.accommodations_teacher_note_title
    if not loaded.accommodations_signature_page_title:
        loaded.accommodations_signature_page_title = defaults.accommodations_signature_page_title
    if not loaded.accommodations_signature_page_note:
        loaded.accommodations_signature_page_note = defaults.accommodations_signature_page_note
    if not loaded.default_data_sheet_columns:
        loaded.default_data_sheet_columns = defaults.default_data_sheet_columns
    if not loaded.data_sheet_templates:
        loaded.data_sheet_templates = defaults.data_sheet_templates
    loaded.default_theme_id = _resolve_theme_id(loaded.default_theme_id)
    if _template_library_item(loaded.default_packet_template_id) is None:
        loaded.default_packet_template_id = "modern_professional"
    return loaded


def _normalize_packet_version_options(
    values: list[PacketVersionDraft],
) -> list[PacketVersionDraft]:
    normalized: list[PacketVersionDraft] = []
    used_audiences: set[str] = set()
    for index, value in enumerate(values):
        name = value.name.strip()
        if not name:
            continue
        base_audience = _audience_slug(value.audience or name, f"packet_{index + 1}")
        audience = base_audience
        suffix = 2
        while audience in used_audiences:
            audience = f"{base_audience}_{suffix}"
            suffix += 1
        used_audiences.add(audience)
        normalized.append(
            PacketVersionDraft(
                id=value.id,
                name=name,
                audience=audience,
            )
        )
    return normalized or [DEFAULT_PACKET_VERSION_OPTIONS[0]]


def save_app_settings(value: AppSettings) -> AppSettings:
    normalized = value.model_copy(deep=True)
    normalized.default_theme_id = _resolve_theme_id(normalized.default_theme_id)
    if _template_library_item(normalized.default_packet_template_id) is None:
        normalized.default_packet_template_id = "modern_professional"
    normalized.default_packet_pages = _merge_default_packet_pages(
        normalized.default_packet_pages or _app_settings_default().default_packet_pages
    )
    normalized.default_observation_checklist = [
        item.strip() for item in normalized.default_observation_checklist if item.strip()
    ] or DEFAULT_OBSERVATION_CHECKLIST
    normalized.packet_versions = _normalize_packet_version_options(
        normalized.packet_versions or DEFAULT_PACKET_VERSION_OPTIONS
    )
    normalized.accommodations_teacher_note = (
        normalized.accommodations_teacher_note.strip()
        or DEFAULT_ACCOMMODATIONS_TEACHER_NOTE
    )
    normalized.accommodations_teacher_note_title = (
        normalized.accommodations_teacher_note_title.strip()
        or "Teacher Responsibilities"
    )
    normalized.accommodations_signature_page_title = (
        normalized.accommodations_signature_page_title.strip()
        or "Accommodations Signature Page"
    )
    normalized.accommodations_signature_page_note = (
        normalized.accommodations_signature_page_note.strip()
        or DEFAULT_ACCOMMODATIONS_SIGNATURE_NOTE
    )
    normalized.default_data_sheet_columns = sorted(
        normalized.default_data_sheet_columns or DEFAULT_DATA_SHEET_COLUMN_DRAFTS,
        key=lambda column: column.position,
    )
    normalized.data_sheet_templates = [
        template.model_copy(
            update={
                "position": position,
                "goal_ids": [],
                "columns": sorted(template.columns or DEFAULT_DATA_SHEET_COLUMN_DRAFTS, key=lambda column: column.position),
                "template_name": template.template_name.strip() or template.title.strip() or "Data Sheet Template",
                "is_template": True,
                "is_observation_form": False,
            }
        )
        for position, template in enumerate(
            sorted(
                [template for template in normalized.data_sheet_templates if template.title.strip() or template.template_name.strip()],
                key=lambda template: template.position,
            )
        )
    ] or DEFAULT_DATA_SHEET_TEMPLATES
    normalized.service_area_presets = sorted(
        normalized.service_area_presets,
        key=lambda area: area.position,
    )
    _write_library("app-settings.json", normalized.model_dump(mode="json"))
    return normalized


def _builtin_theme_ids() -> set[str]:
    return {option.id for option in THEME_OPTIONS}


def _theme_exists(theme_id: str) -> bool:
    return any(item.id == theme_id for item in list_themes())


def _fallback_theme_id() -> str:
    themes = list_themes()
    if any(theme.id == "teacher_friendly" for theme in themes):
        return "teacher_friendly"
    return themes[0].id if themes else "minimal"


def _resolve_theme_id(theme_id: str | None) -> str:
    candidate = str(theme_id or "").strip()
    return candidate if candidate and _theme_exists(candidate) else _fallback_theme_id()


def _theme_library() -> dict[str, object]:
    return _read_library("themes.json")


def _theme_overrides() -> dict[str, ThemeOption]:
    value = _theme_library().get("overrides")
    if not isinstance(value, dict):
        return {}
    output: dict[str, ThemeOption] = {}
    for theme_id, item in value.items():
        if not isinstance(item, dict) or theme_id not in _builtin_theme_ids():
            continue
        try:
            parsed = ThemeOption(**item)
        except ValueError:
            continue
        parsed.id = theme_id
        parsed.is_builtin = True
        output[theme_id] = parsed
    return output


def _deleted_builtin_theme_ids() -> set[str]:
    value = _theme_library().get("deleted_builtin_theme_ids")
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if str(item) in _builtin_theme_ids() and str(item) != "minimal"}


def _custom_theme_options() -> list[ThemeOption]:
    library = _read_library("themes.json")
    items = library.get("items")
    if not isinstance(items, list):
        return []
    output: list[ThemeOption] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            parsed = ThemeOption(**item)
        except ValueError:
            continue
        parsed.is_builtin = False
        output.append(parsed)
    return output


def _save_custom_themes(items: list[ThemeOption]) -> None:
    library = _theme_library()
    _write_library(
        "themes.json",
        {
            "deleted_builtin_theme_ids": list(library.get("deleted_builtin_theme_ids") or []),
            "overrides": library.get("overrides") if isinstance(library.get("overrides"), dict) else {},
            "items": [
                item.model_copy(update={"is_builtin": False}).model_dump(mode="json")
                for item in items
            ],
        },
    )


def _save_theme_library(
    *,
    items: list[ThemeOption] | None = None,
    overrides: dict[str, ThemeOption] | None = None,
    deleted_builtin_theme_ids: set[str] | None = None,
) -> None:
    library = _theme_library()
    current_items = items if items is not None else _custom_theme_options()
    current_overrides = overrides if overrides is not None else _theme_overrides()
    current_deleted = deleted_builtin_theme_ids if deleted_builtin_theme_ids is not None else _deleted_builtin_theme_ids()
    _write_library(
        "themes.json",
        {
            "deleted_builtin_theme_ids": sorted(current_deleted),
            "overrides": {
                theme_id: item.model_copy(update={"id": theme_id, "is_builtin": True}).model_dump(mode="json")
                for theme_id, item in current_overrides.items()
            },
            "items": [
                item.model_copy(update={"is_builtin": False}).model_dump(mode="json")
                for item in current_items
            ],
        },
    )


def create_theme_palette(draft: ThemePaletteDraft) -> ThemeOption:
    item = ThemeOption(
        id=f"palette_{uuid4().hex[:12]}",
        name=draft.name.strip() or "Custom Palette",
        description=draft.description.strip() or "Custom district color palette.",
        category=draft.category.strip() or "Custom",
        default_customization=draft.customization.model_dump(),
        is_builtin=False,
    )
    items = _custom_theme_options()
    items.append(item)
    _save_custom_themes(items)
    return item


def update_theme_palette(theme_id: str, draft: ThemePaletteDraft) -> ThemeOption:
    if theme_id in _builtin_theme_ids():
        if theme_id in _deleted_builtin_theme_ids():
            raise HTTPException(status_code=404, detail="Palette not found.")
        base = next(option for option in THEME_OPTIONS if option.id == theme_id)
        updated = base.model_copy(
            update={
                "name": draft.name.strip() or base.name,
                "description": draft.description.strip() or base.description,
                "category": draft.category.strip() or base.category,
                "default_customization": draft.customization.model_dump(),
                "is_builtin": True,
            }
        )
        overrides = _theme_overrides()
        overrides[theme_id] = updated
        _save_theme_library(overrides=overrides)
        return updated
    items = _custom_theme_options()
    index = next((position for position, item in enumerate(items) if item.id == theme_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Palette not found.")
    updated = items[index].model_copy(
        update={
            "name": draft.name.strip() or "Custom Palette",
            "description": draft.description.strip() or "Custom district color palette.",
            "category": draft.category.strip() or "Custom",
            "default_customization": draft.customization.model_dump(),
            "is_builtin": False,
        }
    )
    items[index] = updated
    _save_custom_themes(items)
    return updated


def delete_theme_palette(theme_id: str) -> None:
    if theme_id == "minimal":
        raise HTTPException(status_code=409, detail="The Minimal palette cannot be deleted.")
    if theme_id in _builtin_theme_ids():
        if theme_id in _deleted_builtin_theme_ids():
            raise HTTPException(status_code=404, detail="Palette not found.")
        deleted = _deleted_builtin_theme_ids()
        deleted.add(theme_id)
        overrides = _theme_overrides()
        overrides.pop(theme_id, None)
        _save_theme_library(overrides=overrides, deleted_builtin_theme_ids=deleted)
        return
    items = _custom_theme_options()
    remaining = [item for item in items if item.id != theme_id]
    if len(remaining) == len(items):
        raise HTTPException(status_code=404, detail="Palette not found.")
    _save_custom_themes(remaining)


def _hidden_builtin_template_ids() -> set[str]:
    value = _read_library("templates.json").get("hidden_builtin_template_ids")
    valid_ids = {template.id for template in PACKET_TEMPLATE_OPTIONS}
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if str(item) in valid_ids}


def _template_default_id(default_id: str | None = None, hidden_ids: set[str] | None = None) -> str:
    hidden = hidden_ids if hidden_ids is not None else _hidden_builtin_template_ids()
    candidate = str(default_id or _read_library("templates.json").get("default_template_id") or "modern_professional")
    custom_ids = [item.id for item in _custom_template_library_items()]
    visible_ids = [template.id for template in PACKET_TEMPLATE_OPTIONS if template.id not in hidden] + custom_ids
    if candidate in visible_ids:
        return candidate
    return visible_ids[0] if visible_ids else "modern_professional"


def _builtin_template_library_items(include_hidden: bool = False) -> list[PacketTemplateLibraryItem]:
    default_id = str(_read_library("templates.json").get("default_template_id") or "modern_professional")
    overrides = _template_overrides()
    hidden_ids = _hidden_builtin_template_ids()
    return [
        (
            overrides.get(template.id)
            or PacketTemplateLibraryItem(
                **template.model_dump(),
                base_template_id=template.id,
                theme_id=TEMPLATE_DEFAULT_THEME_IDS.get(template.id, "teacher_friendly"),
                customization=(
                    FIELD_NOTES_CUSTOMIZATION
                    if template.id == "field_notes"
                    else EDITORIAL_LEDGER_CUSTOMIZATION
                    if template.id == "editorial_ledger"
                    else MODULAR_BLOCKS_CUSTOMIZATION
                    if template.id == "modular_blocks"
                    else ALPINE_PHOTO_CUSTOMIZATION
                    if template.id == "alpine_photo"
                    else MID_CENTURY_CLASSROOM_CUSTOMIZATION
                    if template.id == "mid_century_classroom"
                    else TYPOGRAPHIC_POSTER_CUSTOMIZATION
                    if template.id == "typographic_poster"
                    else SIGNAL_ATLAS_CUSTOMIZATION
                    if template.id == "signal_atlas"
                    else _customization_from_tokens(TEMPLATE_DEFAULT_THEME_IDS.get(template.id, "teacher_friendly"))
                ),
                is_builtin=True,
                is_default=template.id == default_id,
            )
        ).model_copy(
            update={
                "id": template.id,
                "base_template_id": template.id,
                "is_builtin": True,
                "is_default": template.id == default_id,
                "is_hidden": template.id in hidden_ids,
            }
        )
        for template in PACKET_TEMPLATE_OPTIONS
        if include_hidden or template.id not in hidden_ids
    ]


def _template_overrides() -> dict[str, PacketTemplateLibraryItem]:
    library = _read_library("templates.json")
    value = library.get("overrides")
    if not isinstance(value, dict):
        return {}
    valid_base_ids = {template.id for template in PACKET_TEMPLATE_OPTIONS}
    output: dict[str, PacketTemplateLibraryItem] = {}
    for template_id, item in value.items():
        if not isinstance(item, dict) or template_id not in valid_base_ids:
            continue
        try:
            parsed = PacketTemplateLibraryItem(
                **{
                    key: value
                    for key, value in item.items()
                    if key not in {"category", "cover_style", "best_for"}
                }
            )
        except ValueError:
            continue
        parsed.id = template_id
        parsed.base_template_id = template_id
        parsed.is_builtin = True
        output[template_id] = parsed
    return output


def _custom_template_library_items() -> list[PacketTemplateLibraryItem]:
    library = _read_library("templates.json")
    items = library.get("items")
    default_id = str(library.get("default_template_id") or "modern_professional")
    if not isinstance(items, list):
        return []
    output: list[PacketTemplateLibraryItem] = []
    valid_base_ids = {template.id for template in PACKET_TEMPLATE_OPTIONS}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            parsed = PacketTemplateLibraryItem(
                **{
                    key: value
                    for key, value in item.items()
                    if key not in {"category", "cover_style", "best_for"}
                }
            )
        except ValueError:
            continue
        if parsed.base_template_id not in valid_base_ids:
            parsed.base_template_id = "modern_professional"
        parsed.is_builtin = False
        parsed.is_default = parsed.id == default_id
        output.append(parsed)
    return output


def _save_custom_templates(items: list[PacketTemplateLibraryItem], default_id: str | None = None) -> None:
    library = _read_library("templates.json")
    current_default = str(library.get("default_template_id") or "modern_professional")
    hidden_ids = _hidden_builtin_template_ids()
    _write_library(
        "templates.json",
        {
            "default_template_id": _template_default_id(default_id or current_default, hidden_ids),
            "overrides": library.get("overrides") if isinstance(library.get("overrides"), dict) else {},
            "hidden_builtin_template_ids": sorted(hidden_ids),
            "items": [
                item.model_copy(update={"is_builtin": False, "is_default": False}).model_dump(mode="json")
                for item in items
            ],
        },
    )


def _save_template_overrides(overrides: dict[str, PacketTemplateLibraryItem]) -> None:
    library = _read_library("templates.json")
    items = _custom_template_library_items()
    current_default = str(library.get("default_template_id") or "modern_professional")
    hidden_ids = _hidden_builtin_template_ids()
    _write_library(
        "templates.json",
        {
            "default_template_id": _template_default_id(current_default, hidden_ids),
            "hidden_builtin_template_ids": sorted(hidden_ids),
            "overrides": {
                template_id: item.model_copy(
                    update={
                        "id": template_id,
                        "base_template_id": template_id,
                        "is_builtin": True,
                        "is_default": False,
                        "is_hidden": template_id in hidden_ids,
                    }
                ).model_dump(mode="json")
                for template_id, item in overrides.items()
            },
            "items": [
                item.model_copy(update={"is_builtin": False, "is_default": False}).model_dump(mode="json")
                for item in items
            ],
        },
    )


def list_template_library() -> list[PacketTemplateLibraryItem]:
    items = _builtin_template_library_items() + _custom_template_library_items()
    default_id = _template_default_id()
    return [item.model_copy(update={"is_default": item.id == default_id}) for item in items]


def list_hidden_template_library() -> list[PacketTemplateLibraryItem]:
    hidden_ids = _hidden_builtin_template_ids()
    return [
        item.model_copy(update={"is_default": False, "is_hidden": True})
        for item in _builtin_template_library_items(include_hidden=True)
        if item.id in hidden_ids
    ]


def list_packet_templates() -> list[PacketTemplateOption]:
    return [
        PacketTemplateOption(
            id=item.id,
            name=item.name,
            description=item.description,
            page_count_hint=item.page_count_hint,
        )
        for item in list_template_library()
    ]


def _template_library_item(template_id: str) -> PacketTemplateLibraryItem | None:
    items = _builtin_template_library_items(include_hidden=True) + _custom_template_library_items()
    default_id = _template_default_id()
    return next((item.model_copy(update={"is_default": item.id == default_id}) for item in items if item.id == template_id), None)


def _packet_template_base_id(template_id: str) -> str:
    item = _template_library_item(template_id)
    return item.base_template_id if item else template_id


def _customization_for_template(template_id: str) -> ThemeCustomization | None:
    item = _template_library_item(template_id)
    if item and (
        not item.is_builtin
        or template_id in _template_overrides()
        or template_id in {
            "field_notes",
            "editorial_ledger",
            "modular_blocks",
            "alpine_photo",
            "mid_century_classroom",
            "typographic_poster",
            "signal_atlas",
        }
    ):
        return item.customization
    return None


def create_template_library_item(draft: PacketTemplateLibraryDraft) -> PacketTemplateLibraryItem:
    valid_base_ids = {template.id for template in PACKET_TEMPLATE_OPTIONS}
    if draft.base_template_id not in valid_base_ids:
        raise HTTPException(status_code=422, detail="Unknown base packet template.")
    if not _theme_exists(draft.theme_id):
        raise HTTPException(status_code=422, detail="Unknown packet theme.")
    base = next(template for template in PACKET_TEMPLATE_OPTIONS if template.id == draft.base_template_id)
    item = PacketTemplateLibraryItem(
        id=f"custom_{uuid4().hex[:12]}",
        name=draft.name.strip() or "Custom Template",
        description=draft.description.strip() or "Custom packet template.",
        page_count_hint=base.page_count_hint,
        base_template_id=draft.base_template_id,
        theme_id=draft.theme_id,
        customization=draft.customization,
        is_builtin=False,
        is_default=False,
    )
    items = _custom_template_library_items()
    items.append(item)
    _save_custom_templates(items)
    return item


def update_template_library_item(template_id: str, draft: PacketTemplateLibraryDraft) -> PacketTemplateLibraryItem:
    valid_base_ids = {template.id for template in PACKET_TEMPLATE_OPTIONS}
    if draft.base_template_id not in valid_base_ids:
        raise HTTPException(status_code=422, detail="Unknown base packet template.")
    if not _theme_exists(draft.theme_id):
        raise HTTPException(status_code=422, detail="Unknown packet theme.")
    base = next(template for template in PACKET_TEMPLATE_OPTIONS if template.id == draft.base_template_id)
    if any(template.id == template_id for template in PACKET_TEMPLATE_OPTIONS):
        updated = PacketTemplateLibraryItem(
            id=template_id,
            name=draft.name.strip() or base.name,
            description=draft.description.strip() or base.description,
            page_count_hint=base.page_count_hint,
            base_template_id=template_id,
            theme_id=draft.theme_id,
            customization=draft.customization,
            is_builtin=True,
            is_default=False,
        )
        overrides = _template_overrides()
        overrides[template_id] = updated
        _save_template_overrides(overrides)
        return updated
    items = _custom_template_library_items()
    index = next((position for position, item in enumerate(items) if item.id == template_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    updated = items[index].model_copy(
        update={
            "name": draft.name.strip() or "Custom Template",
            "description": draft.description.strip() or "Custom packet template.",
            "page_count_hint": base.page_count_hint,
            "base_template_id": draft.base_template_id,
            "theme_id": draft.theme_id,
            "customization": draft.customization,
        }
    )
    items[index] = updated
    _save_custom_templates(items)
    return updated


def duplicate_template_library_item(template_id: str) -> PacketTemplateLibraryItem:
    source = _template_library_item(template_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    item = source.model_copy(
        update={
            "id": f"custom_{uuid4().hex[:12]}",
            "name": f"{source.name} Copy",
            "is_builtin": False,
            "is_default": False,
        }
    )
    items = _custom_template_library_items()
    items.append(item)
    _save_custom_templates(items)
    return item


def delete_template_library_item(template_id: str) -> None:
    if any(template.id == template_id for template in PACKET_TEMPLATE_OPTIONS):
        hidden_ids = _hidden_builtin_template_ids()
        hidden_ids.add(template_id)
        library = _read_library("templates.json")
        _write_library(
            "templates.json",
            {
                "default_template_id": _template_default_id(library.get("default_template_id"), hidden_ids),
                "overrides": library.get("overrides") if isinstance(library.get("overrides"), dict) else {},
                "hidden_builtin_template_ids": sorted(hidden_ids),
                "items": [
                    item.model_copy(update={"is_builtin": False, "is_default": False}).model_dump(mode="json")
                    for item in _custom_template_library_items()
                ],
            },
        )
        return
    items = _custom_template_library_items()
    remaining = [item for item in items if item.id != template_id]
    if len(remaining) == len(items):
        raise HTTPException(status_code=404, detail="Template not found.")
    default_id = str(_read_library("templates.json").get("default_template_id") or "modern_professional")
    _save_custom_templates(remaining, "modern_professional" if default_id == template_id else default_id)


def set_default_template(template_id: str) -> list[PacketTemplateLibraryItem]:
    if next((item for item in list_template_library() if item.id == template_id), None) is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    _save_custom_templates(_custom_template_library_items(), template_id)
    return list_template_library()


def restore_template_library_item(template_id: str) -> list[PacketTemplateLibraryItem]:
    if not any(template.id == template_id for template in PACKET_TEMPLATE_OPTIONS):
        raise HTTPException(status_code=404, detail="Template not found.")
    hidden_ids = _hidden_builtin_template_ids()
    if template_id not in hidden_ids:
        return list_template_library()
    hidden_ids.remove(template_id)
    library = _read_library("templates.json")
    _write_library(
        "templates.json",
        {
            "default_template_id": _template_default_id(library.get("default_template_id"), hidden_ids),
            "overrides": library.get("overrides") if isinstance(library.get("overrides"), dict) else {},
            "hidden_builtin_template_ids": sorted(hidden_ids),
            "items": [
                item.model_copy(update={"is_builtin": False, "is_default": False}).model_dump(mode="json")
                for item in _custom_template_library_items()
            ],
        },
    )
    return list_template_library()


def _custom_brand_kits() -> list[BrandKitLibraryItem]:
    library = _read_library("brand-kits.json")
    items = library.get("items")
    default_id = str(library.get("default_brand_kit_id") or "")
    if not isinstance(items, list):
        return []
    output: list[BrandKitLibraryItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            parsed = BrandKitLibraryItem(**item)
        except ValueError:
            continue
        parsed.is_default = parsed.id == default_id
        output.append(parsed)
    return output


def _save_brand_kits(items: list[BrandKitLibraryItem], default_id: str | None = None) -> None:
    library = _read_library("brand-kits.json")
    current_default = str(library.get("default_brand_kit_id") or "")
    next_default = current_default if default_id is None else default_id
    _write_library(
        "brand-kits.json",
        {
            "default_brand_kit_id": next_default,
            "items": [
                item.model_copy(update={"is_default": False}).model_dump(mode="json")
                for item in items
            ],
        },
    )


def list_brand_kits() -> list[BrandKitLibraryItem]:
    default_id = str(_read_library("brand-kits.json").get("default_brand_kit_id") or "")
    return [
        item.model_copy(update={"is_default": item.id == default_id})
        for item in _custom_brand_kits()
    ]


def create_brand_kit(draft: BrandKitLibraryDraft) -> BrandKitLibraryItem:
    item = BrandKitLibraryItem(
        id=f"brand_{uuid4().hex[:12]}",
        name=draft.name.strip() or "Brand Kit",
        district_name=draft.district_name,
        school_name=draft.school_name,
        district_logo_label=draft.district_logo_label,
        school_logo_label=draft.school_logo_label,
        logo_relative_path=draft.logo_relative_path,
        logo_filename=draft.logo_filename,
        watermark_logo_relative_path=draft.watermark_logo_relative_path,
        watermark_logo_filename=draft.watermark_logo_filename,
        watermark_enabled=draft.watermark_enabled,
        default_fonts=draft.default_fonts or draft.body_font or draft.heading_font,
        heading_font=draft.heading_font or draft.default_fonts or "Poppins",
        body_font=draft.body_font or draft.default_fonts or "Open Sans",
        primary_color=draft.primary_color,
        secondary_color=draft.secondary_color,
        accent_color=draft.accent_color,
        preferred_cover_style=draft.preferred_cover_style,
        footer_text=draft.footer_text,
        default_filename_template=draft.default_filename_template,
        is_default=False,
    )
    items = _custom_brand_kits()
    items.append(item)
    _save_brand_kits(items)
    return item


def update_brand_kit(brand_kit_id: str, draft: BrandKitLibraryDraft) -> BrandKitLibraryItem:
    items = _custom_brand_kits()
    index = next((position for position, item in enumerate(items) if item.id == brand_kit_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Brand Kit not found.")
    current = items[index]
    updated = current.model_copy(
        update={
            "name": draft.name.strip() or "Brand Kit",
            "district_name": draft.district_name,
            "school_name": draft.school_name,
            "district_logo_label": draft.district_logo_label,
            "school_logo_label": draft.school_logo_label,
            "logo_relative_path": draft.logo_relative_path or current.logo_relative_path,
            "logo_filename": draft.logo_filename or current.logo_filename,
            "watermark_logo_relative_path": draft.watermark_logo_relative_path or current.watermark_logo_relative_path,
            "watermark_logo_filename": draft.watermark_logo_filename or current.watermark_logo_filename,
            "watermark_enabled": draft.watermark_enabled,
            "default_fonts": draft.default_fonts or draft.body_font or draft.heading_font,
            "heading_font": draft.heading_font or draft.default_fonts or current.heading_font,
            "body_font": draft.body_font or draft.default_fonts or current.body_font,
            "primary_color": draft.primary_color,
            "secondary_color": draft.secondary_color,
            "accent_color": draft.accent_color,
            "preferred_cover_style": draft.preferred_cover_style,
            "footer_text": draft.footer_text,
            "default_filename_template": draft.default_filename_template,
        }
    )
    items[index] = updated
    _save_brand_kits(items)
    return updated


def duplicate_brand_kit(brand_kit_id: str) -> BrandKitLibraryItem:
    source = next((item for item in list_brand_kits() if item.id == brand_kit_id), None)
    if source is None:
        raise HTTPException(status_code=404, detail="Brand Kit not found.")
    item = source.model_copy(
        update={
            "id": f"brand_{uuid4().hex[:12]}",
            "name": f"{source.name} Copy",
            "is_default": False,
        }
    )
    items = _custom_brand_kits()
    items.append(item)
    _save_brand_kits(items)
    return item


def delete_brand_kit(brand_kit_id: str) -> None:
    items = _custom_brand_kits()
    remaining = [item for item in items if item.id != brand_kit_id]
    if len(remaining) == len(items):
        raise HTTPException(status_code=404, detail="Brand Kit not found.")
    default_id = str(_read_library("brand-kits.json").get("default_brand_kit_id") or "")
    _save_brand_kits(remaining, "" if default_id == brand_kit_id else default_id)


def set_default_brand_kit(brand_kit_id: str) -> list[BrandKitLibraryItem]:
    if not any(item.id == brand_kit_id for item in list_brand_kits()):
        raise HTTPException(status_code=404, detail="Brand Kit not found.")
    _save_brand_kits(_custom_brand_kits(), brand_kit_id)
    return list_brand_kits()


def upload_brand_kit_logo(upload: BrandKitLogoUpload) -> BrandKitLibraryItem:
    allowed_types = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/svg+xml": ".svg",
    }
    content_type = upload.content_type.lower().split(";")[0].strip()
    if content_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Logo must be a PNG, JPG, or SVG file.")
    try:
        data = base64.b64decode(upload.data_base64, validate=True)
    except (binascii.Error, ValueError) as reason:
        raise HTTPException(status_code=422, detail="Logo data is not valid base64.") from reason
    if not data:
        raise HTTPException(status_code=422, detail="Logo file is empty.")
    if len(data) > 1_500_000:
        raise HTTPException(status_code=422, detail="Logo file must be 1.5 MB or smaller.")
    items = _custom_brand_kits()
    index = next((position for position, item in enumerate(items) if item.id == upload.brand_kit_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Brand Kit not found.")
    extension = allowed_types[content_type]
    logo_dir = paths.brand_kits_dir / upload.brand_kit_id
    logo_dir.mkdir(parents=True, exist_ok=True)
    output_name = "watermark-logo" if upload.logo_kind == "watermark" else "cover-logo"
    output_path = logo_dir / f"{output_name}{extension}"
    output_path.write_bytes(data)
    update = (
        {
            "watermark_logo_relative_path": output_path.relative_to(paths.app_data_dir).as_posix(),
            "watermark_logo_filename": upload.filename,
            "watermark_enabled": True,
        }
        if upload.logo_kind == "watermark"
        else {
            "logo_relative_path": output_path.relative_to(paths.app_data_dir).as_posix(),
            "logo_filename": upload.filename,
        }
    )
    updated = items[index].model_copy(update=update)
    items[index] = updated
    _save_brand_kits(items)
    return updated


def _theme_id(project: Project) -> str:
    value = (project.settings_json or {}).get("theme_id", "teacher_friendly")
    return _resolve_theme_id(str(value))


def _packet_template_id(project: Project) -> str:
    valid_ids = {template.id for template in list_template_library()}
    value = (project.settings_json or {}).get("packet_template_id", "modern_professional")
    return value if value in valid_ids else "modern_professional"


def _theme_customization(project: Project) -> ThemeCustomization:
    value = (project.settings_json or {}).get("theme_customization")
    if isinstance(value, dict):
        return ThemeCustomization(**value)
    return _customization_from_tokens(_theme_id(project))


def _customization_from_tokens(theme_id: str) -> ThemeCustomization:
    custom = next((item for item in _custom_theme_options() if item.id == theme_id), None)
    if custom is not None:
        return ThemeCustomization(**custom.default_customization)
    override = _theme_overrides().get(theme_id)
    if override is not None:
        return ThemeCustomization(**override.default_customization)
    tokens = THEME_TOKENS[theme_id if theme_id in THEME_TOKENS else "teacher_friendly"]
    if theme_id == "minimal":
        return ThemeCustomization(
            primary_color=tokens["primary"],
            secondary_color=tokens["accent"],
            accent_color=tokens.get("orange", tokens["accent"]),
            background_color=tokens["soft"],
            card_color="#ffffff",
            text_color=tokens.get("text", "#12213a"),
            service_area_colors={
                key: MINIMAL_SERVICE_AREA_COLOR for key in DEFAULT_SERVICE_AREA_COLORS
            },
        )
    return ThemeCustomization(
        primary_color=tokens["primary"],
        secondary_color=tokens["accent"],
        accent_color=tokens.get("orange", tokens["accent"]),
        background_color=tokens["soft"],
        card_color=tokens.get("card", "#ffffff"),
        text_color=tokens.get("text", "#12213a"),
        service_area_colors={
            **DEFAULT_SERVICE_AREA_COLORS,
            "Reading": tokens.get("blue", tokens["primary"]),
            "Written Expression": tokens.get("green", tokens["accent"]),
            "Speech/Language": tokens.get("purple", tokens["primary"]),
        },
    )


def _brand_kit(project: Project) -> BrandKit:
    value = (project.settings_json or {}).get("brand_kit")
    if isinstance(value, dict):
        stored = BrandKit(**value)
        if stored.id and stored.id != "personal":
            library_item = next((item for item in list_brand_kits() if item.id == stored.id), None)
            if library_item is not None:
                return BrandKit(**library_item.model_dump(exclude={"is_default"}))
        return stored
    student = project.student
    return BrandKit(
        school_name=student.school if student and student.school else "",
        preferred_cover_style=_packet_template_id(project),
    )


def _export_settings(project: Project) -> ExportSettings:
    value = (project.settings_json or {}).get("export_settings")
    if isinstance(value, dict):
        value = dict(value)
        if value.get("export_mode") in {"multiple_pdfs", "combined_staff_packet"}:
            value["export_mode"] = "zip_archive"
        return ExportSettings(**value)
    return get_app_settings().default_export_settings


def _settings_with(project: Project, **values: object) -> dict[str, object]:
    settings_json = deepcopy(project.settings_json or {})
    settings_json.update(values)
    return settings_json


def _observation_checklist(project: Project) -> list[str]:
    value = (project.settings_json or {}).get("observation_checklist")
    if not isinstance(value, list):
        return get_app_settings().default_observation_checklist
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or get_app_settings().default_observation_checklist


def _packet_version_responses(project: Project) -> list[PacketVersionResponse]:
    return [
        PacketVersionResponse(id=version.id, name=version.name, audience=version.audience)
        for version in sorted(project.packet_versions, key=lambda item: item.created_at)
        if version.deleted_at is None
    ]


def _default_packet_pages() -> list[PacketPageDraft]:
    return get_app_settings().default_packet_pages


def _packet_config(version: PacketVersion) -> PacketVersionConfig:
    settings_json = deepcopy(version.settings_json or {})
    raw_pages = settings_json.get("pages")
    pages = []
    if isinstance(raw_pages, list):
        for index, page in enumerate(raw_pages):
            if isinstance(page, dict):
                pages.append(
                    PacketPageDraft(
                        id=str(page.get("id") or f"page-{index}"),
                        title=str(page.get("title") or "Untitled Page"),
                        page_type=str(page.get("page_type") or page.get("id") or "custom"),
                        enabled=bool(page.get("enabled", True)),
                        position=int(page.get("position") or index),
                        body_text=str(page.get("body_text") or ""),
                    )
                )
    pages = _merge_default_packet_pages(pages, _default_packet_pages())

    raw_assets = settings_json.get("asset_placements")
    assets: list[AssetPlacementDraft] = []
    if isinstance(raw_assets, list):
        for index, asset in enumerate(raw_assets):
            if isinstance(asset, dict):
                assets.append(
                    AssetPlacementDraft(
                        id=str(asset.get("id") or f"asset-{index}"),
                        label=str(asset.get("label") or ""),
                        page_id=str(asset.get("page_id") or ""),
                        position=int(asset.get("position") or index),
                        notes=str(asset.get("notes") or ""),
                    )
                )
    return PacketVersionConfig(
        packet_version_id=version.id,
        pages=pages,
        asset_placements=sorted(assets, key=lambda item: item.position),
    )


def _project_custom_pages(project: Project) -> list[PacketPageDraft]:
    custom_pages: dict[str, PacketPageDraft] = {}
    for version in sorted(project.packet_versions, key=lambda item: item.created_at):
        if version.deleted_at is not None:
            continue
        for page in _packet_config(version).pages:
            if page.page_type == "custom_text" and page.id not in custom_pages:
                custom_pages[page.id] = page.model_copy(deep=True)
    return list(custom_pages.values())


def _merge_project_custom_pages(
    config: PacketVersionConfig,
    custom_pages: list[PacketPageDraft],
) -> PacketVersionConfig:
    existing_ids = {page.id for page in config.pages}
    pages = [page.model_copy(deep=True) for page in config.pages]
    for custom_page in custom_pages:
        if custom_page.id in existing_ids:
            continue
        pages.append(
            custom_page.model_copy(
                update={
                    "enabled": False,
                    "position": len(pages),
                }
            )
        )
    return config.model_copy(
        update={
            "pages": [
                page.model_copy(update={"position": position})
                for position, page in enumerate(sorted(pages, key=lambda item: item.position))
            ]
        }
    )


def _packet_settings_with_project_custom_pages(project: Project) -> dict[str, object]:
    settings_json = _new_packet_version_settings()
    pages = [
        PacketPageDraft(**page)
        for page in settings_json["pages"]
        if isinstance(page, dict)
    ]
    for custom_page in _project_custom_pages(project):
        pages.append(
            custom_page.model_copy(
                update={
                    "enabled": False,
                    "position": len(pages),
                }
            )
        )
    settings_json["pages"] = [
        page.model_dump(mode="json")
        for page in pages
    ]
    return settings_json


def _new_packet_version_settings() -> dict[str, object]:
    return {
        "pages": [
            page.model_dump(mode="json")
            for page in get_app_settings().default_packet_pages
        ],
        "asset_placements": [],
    }


def _packet_builder_configs(project: Project) -> list[PacketVersionConfig]:
    custom_pages = _project_custom_pages(project)
    return [
        _merge_project_custom_pages(_packet_config(version), custom_pages)
        for version in sorted(project.packet_versions, key=lambda item: item.created_at)
        if version.deleted_at is None
    ]


def validate_student_setup(draft: StudentSetupDraft) -> StepValidation:
    issues: list[ValidationIssue] = []
    if not draft.student.name.strip():
        issues.append(
            ValidationIssue(
                field="student.name",
                message="Enter the student's name in Student Information.",
            )
        )
    if not draft.student.grade.strip():
        issues.append(
            ValidationIssue(
                field="student.grade",
                message="Select or enter the student's grade.",
            )
        )
    if draft.student.iep_end_date is None:
        issues.append(
            ValidationIssue(
                field="student.iep_end_date",
                message="Enter the IEP end date.",
            )
        )
    if not any(area.name.strip() for area in draft.service_areas):
        issues.append(
            ValidationIssue(
                field="service_areas",
                message="Add at least one named service area.",
            )
        )
    return StepValidation(is_complete=not issues, issues=issues)


def validate_goals(goals: Iterable[GoalResponse]) -> StepValidation:
    issues: list[ValidationIssue] = []
    goal_list = list(goals)
    if not goal_list:
        issues.append(
            ValidationIssue(field="goals", message="Add at least one annual goal.")
        )
    required = (
        ("title", "Enter a goal title."),
        ("statement", "Enter the complete goal statement."),
        (
            "data_sheet_summary",
            "Enter a concise summary for future data sheets.",
        ),
        ("service_area_id", "Assign the goal to a service area."),
        ("mastery_criteria", "Enter mastery criteria."),
        ("progress_monitoring_method", "Enter a progress-monitoring method."),
    )
    for index, goal in enumerate(goal_list):
        for field, message in required:
            value = getattr(goal, field)
            if value is None or not str(value).strip():
                issues.append(
                    ValidationIssue(field=f"goals.{index}.{field}", message=message)
                )
    return StepValidation(is_complete=not issues, issues=issues)


def validate_at_a_glance(value: AtAGlanceResponse) -> StepValidation:
    has_content = any(
        section.enabled and section.content.strip() for section in value.sections
    )
    issues = [] if has_content else [
        ValidationIssue(
            field="at_a_glance",
            message="Add at least one instructional summary before continuing.",
        )
    ]
    return StepValidation(is_complete=has_content, issues=issues)


def validate_data_sheets(data_sheets: Iterable[DataSheetResponse]) -> StepValidation:
    issues: list[ValidationIssue] = []
    sheet_list = list(data_sheets)
    if not sheet_list:
        issues.append(
            ValidationIssue(
                field="data_sheets",
                message="Add at least one data sheet for progress monitoring.",
            )
        )
    required = (
        ("title", "Enter a data sheet title."),
        ("sheet_type", "Choose a data collection type."),
        ("collection_schedule", "Enter a collection schedule."),
    )
    for index, sheet in enumerate(sheet_list):
        for field, message in required:
            value = getattr(sheet, field)
            if value is None or not str(value).strip():
                issues.append(
                    ValidationIssue(field=f"data_sheets.{index}.{field}", message=message)
                )
        if not sheet.is_observation_form and not sheet.goal_ids:
            issues.append(
                ValidationIssue(
                    field=f"data_sheets.{index}.goal_ids",
                    message="Attach at least one goal.",
                )
            )
        if sheet.blank_instance_count < 1:
            issues.append(
                ValidationIssue(
                    field=f"data_sheets.{index}.blank_instance_count",
                    message="Enter at least one blank table instance for the packet.",
                )
            )
        if not sheet.columns:
            issues.append(
                ValidationIssue(
                    field=f"data_sheets.{index}.columns",
                    message="Add at least one table column.",
                )
            )
        for column_index, column in enumerate(sheet.columns):
            if not column.title.strip():
                issues.append(
                    ValidationIssue(
                        field=f"data_sheets.{index}.columns.{column_index}.title",
                        message="Enter a title for every table column.",
                    )
                )
    return StepValidation(is_complete=not issues, issues=issues)


def _summary(project: Project) -> ProjectSummary:
    student_setup = _student_setup_from_model(project)
    goals = [_goal_response(goal) for goal in project.goals if goal.deleted_at is None]
    glance = _at_a_glance_response(project.at_a_glance)
    data_sheets = _data_sheet_responses(project)
    if not validate_student_setup(student_setup).is_complete:
        current_step = "student_setup"
    elif not validate_goals(goals).is_complete:
        current_step = "goals"
    elif not validate_at_a_glance(glance).is_complete:
        current_step = "at_a_glance"
    elif not validate_data_sheets(data_sheets).is_complete:
        current_step = "data_sheets"
    else:
        current_step = "complete"
    return ProjectSummary(
        id=project.id,
        name=project.name,
        student_name=_student_name(project.student),
        school_year=project.school_year or "",
        grade=project.student.grade if project.student and project.student.grade else "",
        updated_at=project.updated_at,
        archived=project.archived_at is not None,
        case_manager=_case_manager_name(project.student),
        service_areas=[
            area.name
            for area in sorted(project.service_areas, key=lambda item: item.position)
            if area.deleted_at is None
        ],
        theme_id=_theme_id(project),
        missing_data_sheets=not validate_data_sheets(data_sheets).is_complete,
        current_step=current_step,
    )


def _accommodations_from_settings(value: object) -> list[AccommodationDraft]:
    if isinstance(value, list):
        output: list[AccommodationDraft] = []
        for position, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            try:
                parsed = AccommodationDraft(**item)
            except ValueError:
                continue
            output.append(parsed.model_copy(update={"position": parsed.position if parsed.position is not None else position}))
        return sorted(output, key=lambda item: item.position)
    if isinstance(value, str) and value.strip():
        return [
            AccommodationDraft(
                content_area="Other",
                custom_content_area="General",
                text=value.strip(),
                position=0,
            )
        ]
    return []


def _behavior_plan_sections_from_settings(
    sections_value: object,
    legacy_value: object,
) -> list[BehaviorPlanSectionDraft]:
    if isinstance(sections_value, list):
        output: list[BehaviorPlanSectionDraft] = []
        for position, item in enumerate(sections_value):
            if not isinstance(item, dict):
                continue
            try:
                parsed = BehaviorPlanSectionDraft(**item)
            except ValueError:
                continue
            output.append(parsed.model_copy(update={"position": parsed.position if parsed.position is not None else position}))
        return sorted(output, key=lambda item: item.position)
    if isinstance(legacy_value, str) and legacy_value.strip():
        return [
            BehaviorPlanSectionDraft(
                title="Defined Problem Behavior",
                text=legacy_value.strip(),
                position=0,
            )
        ]
    return []


def _behavior_plan_text(sections: list[BehaviorPlanSectionDraft], legacy_value: object) -> str:
    visible = [section for section in sorted(sections, key=lambda item: item.position) if section.text.strip()]
    if visible:
        return "\n\n".join(
            f"{section.title.strip() or 'Behavior Plan'}\n{section.text.strip()}"
            for section in visible
        )
    return str(legacy_value or "")


def _related_service_providers_from_settings(value: object) -> list[RelatedServiceProviderDraft]:
    if not isinstance(value, list):
        return []
    output: list[RelatedServiceProviderDraft] = []
    for position, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        try:
            parsed = RelatedServiceProviderDraft(**item)
        except ValueError:
            continue
        output.append(parsed.model_copy(update={"position": parsed.position if parsed.position is not None else position}))
    return sorted(output, key=lambda item: item.position)


def _student_setup_from_model(project: Project) -> StudentSetupDraft:
    student = project.student
    settings_json = project.settings_json or {}
    behavior_sections = _behavior_plan_sections_from_settings(
        settings_json.get("behavior_plan_sections"),
        settings_json.get("behavior_plan"),
    )
    return StudentSetupDraft(
        project_name=project.name,
        school_year=project.school_year or "",
        student={
            "name": _student_name(student),
            "initials": student.initials if student and student.initials else "",
            "grade": student.grade if student and student.grade else "",
            "school": student.school if student and student.school else "",
            "case_manager": (
                _case_manager_name(student)
            ),
            "case_manager_first_name": (
                student.case_manager_first_name if student and student.case_manager_first_name else ""
            ),
            "case_manager_last_name": (
                student.case_manager_last_name if student and student.case_manager_last_name else ""
            ),
            "case_manager_phone": (
                student.case_manager_phone if student and student.case_manager_phone else ""
            ),
            "case_manager_email": (
                student.case_manager_email if student and student.case_manager_email else ""
            ),
            "case_manager_notes": (
                student.case_manager_notes if student and student.case_manager_notes else ""
            ),
            "iep_end_date": student.iep_end_date if student else None,
        },
        service_areas=[
            {
                "id": area.id,
                "name": area.name,
                "setting": area.setting or "",
                "minutes_per_week": area.minutes,
                "notes": area.notes or "",
                "position": area.position,
            }
            for area in sorted(project.service_areas, key=lambda item: item.position)
            if area.deleted_at is None
        ],
        audiences=[
            version.audience
            for version in project.packet_versions
            if version.deleted_at is None
        ],
        accommodations=_accommodations_from_settings(settings_json.get("accommodations")),
        accommodations_parent_strengths_enabled=bool(settings_json.get("accommodations_parent_strengths_enabled")),
        accommodations_parent_strengths=str(settings_json.get("accommodations_parent_strengths") or ""),
        behavior_plan=_behavior_plan_text(behavior_sections, settings_json.get("behavior_plan")),
        behavior_plan_sections=behavior_sections,
        related_service_providers=_related_service_providers_from_settings(settings_json.get("related_service_providers")),
    )


def _goal_response(goal: Goal) -> GoalResponse:
    return GoalResponse(
        id=goal.id,
        title=goal.title,
        statement=goal.statement,
        data_sheet_summary=goal.data_sheet_summary or "",
        service_area_id=goal.service_area_id,
        mastery_criteria=goal.mastery_criteria or "",
        progress_monitoring_method=goal.progress_monitoring_method or "",
        instructional_notes=goal.notes or "",
        position=goal.position,
    )


def _at_a_glance_response(value: AtAGlance | None) -> AtAGlanceResponse:
    return AtAGlanceResponse(
        id=value.id if value else None,
        sections=sorted(
            deepcopy(value.sections_json) if value else [],
            key=lambda section: section.get("position", 0),
        ),
    )


def _data_sheet_response(sheet: DataSheet) -> DataSheetResponse:
    configuration = deepcopy(sheet.configuration_json or {})
    return DataSheetResponse(
        id=sheet.id,
        title=sheet.title,
        sheet_type=sheet.sheet_type,
        goal_ids=[
            goal.id
            for goal in sorted(sheet.goals, key=lambda item: item.position)
            if goal.deleted_at is None
        ],
        collection_schedule=str(configuration.get("collection_schedule") or ""),
        blank_instance_count=max(1, int(configuration.get("blank_instance_count") or 1)),
        columns=sorted(
            deepcopy(
                configuration.get("columns")
                or [
                    column.model_dump()
                    for column in get_app_settings().default_data_sheet_columns
                ]
            ),
            key=lambda column: column.get("position", 0),
        ),
        notes=str(configuration.get("notes") or ""),
        template_name=str(configuration.get("template_name") or ""),
        is_template=bool(configuration.get("is_template", False)),
        is_observation_form=bool(configuration.get("is_observation_form", False)),
        position=int(configuration.get("position") or 0),
    )


def _data_sheet_responses(project: Project) -> list[DataSheetResponse]:
    return sorted(
        [
            _data_sheet_response(sheet)
            for sheet in project.data_sheets
            if sheet.deleted_at is None
        ],
        key=lambda item: item.position,
    )


def _detail(project: Project) -> ProjectDetail:
    draft = _student_setup_from_model(project)
    goals = [
        _goal_response(goal)
        for goal in sorted(project.goals, key=lambda item: item.position)
        if goal.deleted_at is None
    ]
    glance = _at_a_glance_response(project.at_a_glance)
    data_sheets = _data_sheet_responses(project)
    return ProjectDetail(
        id=project.id,
        name=project.name,
        school_year=project.school_year or "",
        default_export_filename=project.default_export_filename or "",
        student=(
            StudentResponse(
                id=project.student.id,
                **draft.student.model_dump(),
            )
            if project.student
            else None
        ),
        service_areas=[
            ServiceAreaResponse(**area.model_dump())
            for area in draft.service_areas
        ],
        audiences=draft.audiences,
        accommodations=draft.accommodations,
        accommodations_parent_strengths_enabled=draft.accommodations_parent_strengths_enabled,
        accommodations_parent_strengths=draft.accommodations_parent_strengths,
        behavior_plan=draft.behavior_plan,
        behavior_plan_sections=draft.behavior_plan_sections,
        related_service_providers=draft.related_service_providers,
        packet_versions=_packet_version_responses(project),
        packet_builder=_packet_builder_configs(project),
        observation_checklist=_observation_checklist(project),
        theme_id=_theme_id(project),
        packet_template_id=_packet_template_id(project),
        theme_customization=_theme_customization(project),
        brand_kit=_brand_kit(project),
        export_settings=_export_settings(project),
        goals=goals,
        at_a_glance=glance,
        data_sheets=data_sheets,
        student_setup_validation=validate_student_setup(draft),
        goals_validation=validate_goals(goals),
        at_a_glance_validation=validate_at_a_glance(glance),
        data_sheets_validation=validate_data_sheets(data_sheets),
        updated_at=project.updated_at,
    )


def get_project(session: Session, project_id: str) -> Project:
    project = session.scalar(_project_query().where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def list_projects(
    session: Session,
    *,
    archived: bool = False,
    search: str = "",
    grade: str = "",
    school_year: str = "",
    case_manager: str = "",
    service_area: str = "",
    theme_id: str = "",
    missing_data_sheets: bool = False,
) -> list[ProjectSummary]:
    query = _project_query()
    query = query.where(
        Project.archived_at.is_not(None) if archived else Project.archived_at.is_(None)
    )
    if search.strip():
        term = f"%{search.strip()}%"
        query = (
            query.join(Student, Student.project_id == Project.id, isouter=True)
            .join(ServiceArea, ServiceArea.project_id == Project.id, isouter=True)
            .where(
                or_(
                    Project.name.ilike(term),
                    Student.first_name.ilike(term),
                    Student.last_name.ilike(term),
                    Student.initials.ilike(term),
                    Student.grade.ilike(term),
                    Student.school.ilike(term),
                    Student.case_manager.ilike(term),
                    Project.school_year.ilike(term),
                    ServiceArea.name.ilike(term),
                )
            )
        )
    projects = session.scalars(query.order_by(Project.updated_at.desc())).unique()
    summaries = [_summary(project) for project in projects]
    if grade.strip():
        value = grade.strip().lower()
        summaries = [project for project in summaries if value in project.grade.lower()]
    if school_year.strip():
        value = school_year.strip().lower()
        summaries = [project for project in summaries if value in project.school_year.lower()]
    if case_manager.strip():
        value = case_manager.strip().lower()
        summaries = [project for project in summaries if value in project.case_manager.lower()]
    if service_area.strip():
        value = service_area.strip().lower()
        summaries = [
            project
            for project in summaries
            if any(value in area.lower() for area in project.service_areas)
        ]
    if theme_id.strip():
        summaries = [project for project in summaries if project.theme_id == theme_id.strip()]
    if missing_data_sheets:
        summaries = [project for project in summaries if project.missing_data_sheets]
    return summaries


def create_project(session: Session, name: str | None = None) -> ProjectDetail:
    app_defaults = get_app_settings()
    case_manager = app_defaults.case_manager_profile
    settings_json = {
        "theme_id": app_defaults.default_theme_id,
        "packet_template_id": app_defaults.default_packet_template_id,
        "observation_checklist": app_defaults.default_observation_checklist,
        "export_settings": app_defaults.default_export_settings.model_dump(mode="json"),
    }
    project = Project(
        name=name.strip() if name and name.strip() else "Untitled Student Project",
        school_year=app_defaults.default_school_year or None,
        schema_version=settings.schema_version,
        app_version=settings.app_version,
        settings_json=settings_json,
    )
    session.add(project)
    session.flush()
    if any(
        value.strip()
        for value in (
            case_manager.first_name,
            case_manager.last_name,
            case_manager.phone,
            case_manager.email,
            case_manager.school,
            case_manager.notes,
        )
    ):
        project.student = Student(
            project_id=project.id,
            school=case_manager.school.strip() or None,
            case_manager_first_name=case_manager.first_name.strip() or None,
            case_manager_last_name=case_manager.last_name.strip() or None,
            case_manager_phone=case_manager.phone.strip() or None,
            case_manager_email=case_manager.email.strip() or None,
            case_manager_notes=case_manager.notes.strip() or None,
            case_manager=" ".join(
                part
                for part in (
                    case_manager.first_name.strip(),
                    case_manager.last_name.strip(),
                )
                if part
            ).strip()
            or None,
        )
    session.commit()
    session.expire_all()
    return _detail(get_project(session, project.id))


def save_student_setup(
    session: Session, project_id: str, draft: StudentSetupDraft
) -> ProjectDetail:
    project = get_project(session, project_id)
    first_name, last_name = _split_name(draft.student.name)
    if project.student is None:
        project.student = Student(project_id=project.id)
    student = project.student
    student.first_name = first_name
    student.last_name = last_name
    student.initials = draft.student.initials.strip() or derive_initials(draft.student.name)
    student.grade = draft.student.grade.strip() or None
    student.school = draft.student.school.strip() or None
    student.case_manager_first_name = draft.student.case_manager_first_name.strip() or None
    student.case_manager_last_name = draft.student.case_manager_last_name.strip() or None
    student.case_manager_phone = draft.student.case_manager_phone.strip() or None
    student.case_manager_email = draft.student.case_manager_email.strip() or None
    student.case_manager_notes = draft.student.case_manager_notes.strip() or None
    structured_case_manager = " ".join(
        part
        for part in (
            draft.student.case_manager_first_name.strip(),
            draft.student.case_manager_last_name.strip(),
        )
        if part
    ).strip()
    student.case_manager = structured_case_manager or draft.student.case_manager.strip() or None
    student.iep_end_date = draft.student.iep_end_date

    project.school_year = (
        draft.school_year.strip() or suggest_school_year(draft.student.iep_end_date)
    )
    project.name = (
        draft.project_name.strip()
        or " - ".join(
            value
            for value in (draft.student.name.strip(), project.school_year)
            if value
        )
        or "Untitled Student Project"
    )
    project.default_export_filename = default_export_filename(
        draft.student.name, project.school_year or ""
    )
    settings_json = deepcopy(project.settings_json or {})
    settings_json["accommodations"] = [
        item.model_copy(update={"position": position}).model_dump(mode="json")
        for position, item in enumerate(draft.accommodations)
        if item.text.strip()
    ]
    settings_json["accommodations_parent_strengths_enabled"] = (
        draft.accommodations_parent_strengths_enabled
        and bool(draft.accommodations_parent_strengths.strip())
    )
    settings_json["accommodations_parent_strengths"] = draft.accommodations_parent_strengths.strip()
    behavior_sections = [
        item.model_copy(update={"position": position}).model_dump(mode="json")
        for position, item in enumerate(draft.behavior_plan_sections)
        if item.text.strip() or item.title.strip()
    ]
    settings_json["behavior_plan_sections"] = behavior_sections
    settings_json["behavior_plan"] = _behavior_plan_text(
        [BehaviorPlanSectionDraft(**item) for item in behavior_sections],
        draft.behavior_plan,
    ).strip()
    settings_json["related_service_providers"] = [
        provider.model_copy(update={"position": position}).model_dump(mode="json")
        for position, provider in enumerate(draft.related_service_providers)
        if provider.name.strip() or provider.email.strip() or provider.phone.strip()
    ]
    project.settings_json = settings_json
    _touch(project)

    current_areas = {
        area.id: area for area in project.service_areas if area.deleted_at is None
    }
    incoming_ids = {area.id for area in draft.service_areas if area.id}
    for area_id, area in current_areas.items():
        if area_id not in incoming_ids:
            if any(goal.deleted_at is None for goal in area.goals):
                raise HTTPException(
                    status_code=409,
                    detail=f'Cannot remove service area "{area.name}" while goals reference it.',
                )
            session.delete(area)

    for position, value in enumerate(draft.service_areas):
        area = current_areas.get(value.id) if value.id else None
        if area is None:
            area = ServiceArea(project_id=project.id, name="")
            session.add(area)
        area.name = value.name.strip()
        area.setting = value.setting.strip() or None
        area.minutes = value.minutes_per_week
        area.delivery_model = None
        area.notes = value.notes.strip() or None
        area.position = position

    packet_version_options = {
        option.audience: option.name
        for option in get_app_settings().packet_versions
        if option.audience and option.name.strip()
    }
    current_versions = {
        version.audience: version
        for version in project.packet_versions
        if version.deleted_at is None
    }
    selected = set(draft.audiences)
    for audience, version in current_versions.items():
        if audience not in selected:
            session.delete(version)
    for audience in selected:
        if audience not in current_versions:
            session.add(
                PacketVersion(
                    project_id=project.id,
                    name=packet_version_options.get(audience, audience.replace("_", " ").title()),
                    audience=audience,
                    settings_json=_packet_settings_with_project_custom_pages(project),
                )
            )
        else:
            current_versions[audience].name = packet_version_options.get(
                audience,
                current_versions[audience].name,
            )

    session.commit()
    session.expire_all()
    return _detail(get_project(session, project.id))


def save_goals(
    session: Session, project_id: str, draft: GoalsDraft
) -> ProjectDetail:
    project = get_project(session, project_id)
    service_ids = {
        area.id for area in project.service_areas if area.deleted_at is None
    }
    current = {goal.id: goal for goal in project.goals if goal.deleted_at is None}
    incoming_ids = {goal.id for goal in draft.goals if goal.id}
    for goal_id, goal in current.items():
        if goal_id not in incoming_ids:
            session.delete(goal)

    for position, value in enumerate(draft.goals):
        if value.service_area_id and value.service_area_id not in service_ids:
            raise HTTPException(
                status_code=422, detail="A goal references an unavailable service area."
            )
        goal = current.get(value.id) if value.id else None
        if goal is None:
            if not value.service_area_id:
                continue
            goal = Goal(
                project_id=project.id,
                service_area_id=value.service_area_id,
                title="",
                statement="",
            )
            session.add(goal)
        if value.service_area_id:
            goal.service_area_id = value.service_area_id
        goal.title = value.title
        goal.statement = value.statement
        goal.data_sheet_summary = value.data_sheet_summary or None
        goal.mastery_criteria = value.mastery_criteria or None
        goal.progress_monitoring_method = value.progress_monitoring_method or None
        goal.notes = value.instructional_notes or None
        goal.position = position

    _touch(project)
    session.commit()
    session.expire_all()
    return _detail(get_project(session, project.id))


def save_at_a_glance(
    session: Session, project_id: str, draft: AtAGlanceDraft
) -> ProjectDetail:
    project = get_project(session, project_id)
    if project.at_a_glance is None:
        project.at_a_glance = AtAGlance(project_id=project.id, sections_json=[])
    project.at_a_glance.sections_json = [
        section.model_dump() for section in sorted(draft.sections, key=lambda item: item.position)
    ]
    _touch(project)
    session.commit()
    session.expire_all()
    return _detail(get_project(session, project.id))


def save_data_sheets(
    session: Session, project_id: str, draft: DataSheetsDraft
) -> ProjectDetail:
    project = get_project(session, project_id)
    available_goals = {
        goal.id: goal for goal in project.goals if goal.deleted_at is None
    }
    current = {
        sheet.id: sheet for sheet in project.data_sheets if sheet.deleted_at is None
    }
    incoming_ids = {sheet.id for sheet in draft.data_sheets if sheet.id}
    for sheet_id, sheet in current.items():
        if sheet_id not in incoming_ids:
            session.delete(sheet)

    for position, value in enumerate(draft.data_sheets):
        missing_goals = [] if value.is_observation_form else [goal_id for goal_id in value.goal_ids if goal_id not in available_goals]
        if missing_goals:
            raise HTTPException(
                status_code=422,
                detail="A data sheet references an unavailable goal.",
            )
        sheet = current.get(value.id) if value.id else None
        if sheet is None:
            sheet = DataSheet(
                project_id=project.id,
                title="",
                sheet_type=value.sheet_type or "trial_count",
                configuration_json={},
            )
            session.add(sheet)
        sheet.title = value.title
        sheet.sheet_type = value.sheet_type or "trial_count"
        sheet.configuration_json = {
            "collection_schedule": value.collection_schedule,
            "blank_instance_count": value.blank_instance_count,
            "columns": [
                column.model_dump()
                for column in sorted(value.columns, key=lambda item: item.position)
            ],
            "notes": value.notes,
            "template_name": value.template_name,
            "is_template": value.is_template,
            "is_observation_form": value.is_observation_form,
            "position": position,
        }
        sheet.goals = [] if value.is_observation_form else [available_goals[goal_id] for goal_id in value.goal_ids]

    _touch(project)
    session.commit()
    session.expire_all()
    return _detail(get_project(session, project.id))


def save_project_theme(
    session: Session, project_id: str, selection: ThemeSelection
) -> ProjectDetail:
    theme_id = _resolve_theme_id(selection.theme_id)
    valid_templates = {template.id for template in list_template_library()}
    if selection.packet_template_id not in valid_templates:
        raise HTTPException(status_code=422, detail="Unknown packet template.")
    project = get_project(session, project_id)
    settings_json = _settings_with(
        project,
        theme_id=theme_id,
        packet_template_id=selection.packet_template_id,
        theme_customization=selection.customization.model_dump(),
        brand_kit=selection.brand_kit.model_dump(),
    )
    project.settings_json = settings_json
    _touch(project)
    session.commit()
    session.expire_all()
    return _detail(get_project(session, project.id))


def upload_brand_logo(
    session: Session, project_id: str, upload: BrandLogoUpload
) -> ProjectDetail:
    allowed_types = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/svg+xml": ".svg",
    }
    content_type = upload.content_type.lower().split(";")[0].strip()
    if content_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Logo must be a PNG, JPG, or SVG file.")
    try:
        data = base64.b64decode(upload.data_base64, validate=True)
    except (binascii.Error, ValueError) as reason:
        raise HTTPException(status_code=422, detail="Logo data is not valid base64.") from reason
    if not data:
        raise HTTPException(status_code=422, detail="Logo file is empty.")
    if len(data) > 1_500_000:
        raise HTTPException(status_code=422, detail="Logo file must be 1.5 MB or smaller.")

    project = get_project(session, project_id)
    extension = allowed_types[content_type]
    logo_dir = paths.brand_kits_dir / "projects" / project.id
    logo_dir.mkdir(parents=True, exist_ok=True)
    output_path = logo_dir / f"brand-logo{extension}"
    output_path.write_bytes(data)

    brand = _brand_kit(project)
    brand.logo_relative_path = output_path.relative_to(paths.app_data_dir).as_posix()
    brand.logo_filename = upload.filename
    project.settings_json = _settings_with(project, brand_kit=brand.model_dump())
    _touch(project)
    session.commit()
    session.expire_all()
    return _detail(get_project(session, project.id))


def save_export_settings(
    session: Session, project_id: str, selection: ExportSettingsSelection
) -> ProjectDetail:
    project = get_project(session, project_id)
    project.settings_json = _settings_with(
        project,
        export_settings=selection.export_settings.model_dump(),
    )
    _touch(project)
    session.commit()
    session.expire_all()
    return _detail(get_project(session, project.id))


def delete_project(session: Session, project_id: str) -> None:
    project = get_project(session, project_id)
    if project.archived_at is None:
        raise HTTPException(
            status_code=409,
            detail="Archive the project before permanently deleting it.",
        )
    session.delete(project)
    session.commit()


def apply_bulk_project_action(
    session: Session, action: BulkProjectAction
) -> BulkProjectActionResponse:
    unique_ids = list(dict.fromkeys(action.project_ids))
    duplicated: list[ProjectDetail] = []
    exports: list[ExportResponse] = []
    deleted_ids: list[str] = []
    for project_id in unique_ids:
        if action.action == "archive":
            set_archived(session, project_id, True)
        elif action.action == "restore":
            set_archived(session, project_id, False)
        elif action.action == "duplicate":
            duplicated.append(duplicate_project(session, project_id, action.duplicate_options))
        elif action.action == "assign_theme":
            if not action.theme_id:
                raise HTTPException(status_code=422, detail="Select a theme for bulk assignment.")
            if not _theme_exists(action.theme_id):
                raise HTTPException(status_code=422, detail="Unknown packet theme.")
            project = get_project(session, project_id)
            project.settings_json = _settings_with(project, theme_id=action.theme_id)
            _touch(project)
            session.commit()
            session.expire_all()
        elif action.action == "update_template":
            if not action.packet_template_id:
                raise HTTPException(status_code=422, detail="Select a packet template.")
            valid_templates = {template.id for template in list_template_library()}
            if action.packet_template_id not in valid_templates:
                raise HTTPException(status_code=422, detail="Unknown packet template.")
            project = get_project(session, project_id)
            project.settings_json = _settings_with(
                project,
                packet_template_id=action.packet_template_id,
            )
            _touch(project)
            session.commit()
            session.expire_all()
        elif action.action == "update_school_year":
            if action.school_year is None:
                raise HTTPException(status_code=422, detail="Enter a school year.")
            project = get_project(session, project_id)
            project.school_year = action.school_year.strip()
            _touch(project)
            session.commit()
            session.expire_all()
        elif action.action == "assign_export_location":
            if action.export_location is None:
                raise HTTPException(status_code=422, detail="Enter an export location.")
            project = get_project(session, project_id)
            settings = _export_settings(project)
            settings.last_export_location = action.export_location.strip()
            project.settings_json = _settings_with(
                project,
                export_settings=settings.model_dump(),
            )
            _touch(project)
            session.commit()
            session.expire_all()
        elif action.action == "export":
            exports.extend(generate_all_pdf_exports(session, project_id).exports)
        elif action.action == "delete":
            delete_project(session, project_id)
            deleted_ids.append(project_id)
        elif action.action == "rename":
            if len(unique_ids) != 1:
                raise HTTPException(status_code=422, detail="Rename one project at a time.")
            if action.project_name is None or not action.project_name.strip():
                raise HTTPException(status_code=422, detail="Enter a project name.")
            project = get_project(session, project_id)
            project.name = action.project_name.strip()
            _touch(project)
            session.commit()
            session.expire_all()
    summaries = [
        _summary(get_project(session, project_id))
        for project_id in unique_ids
        if action.action not in {"duplicate", "delete"}
    ]
    return BulkProjectActionResponse(
        projects=summaries,
        duplicated_projects=duplicated,
        exports=exports,
        deleted_project_ids=deleted_ids,
    )


def duplicate_project(
    session: Session,
    project_id: str,
    options: DuplicateOptions | None = None,
) -> ProjectDetail:
    source = get_project(session, project_id)
    options = options or DuplicateOptions(
        at_a_glance=True,
        observation_notes=True,
        data_sheets=True,
    )
    settings_json: dict[str, object] = {}
    if options.theme:
        source_settings = deepcopy(source.settings_json or {})
        for key in ("theme_id", "theme_customization", "brand_kit"):
            if key in source_settings:
                settings_json[key] = source_settings[key]
    if options.template:
        source_settings = deepcopy(source.settings_json or {})
        if "packet_template_id" in source_settings:
            settings_json["packet_template_id"] = source_settings["packet_template_id"]
    if options.observation_notes:
        source_settings = deepcopy(source.settings_json or {})
        if "observation_checklist" in source_settings:
            settings_json["observation_checklist"] = source_settings["observation_checklist"]
    source_export_settings = deepcopy(source.settings_json or {}).get("export_settings")
    if isinstance(source_export_settings, dict):
        settings_json["export_settings"] = source_export_settings
    duplicate = Project(
        name=f"{source.name} (Copy)",
        description=source.description,
        school_year=source.school_year if options.student_information else None,
        schema_version=settings.schema_version,
        app_version=settings.app_version,
        default_export_filename=source.default_export_filename if options.student_information else None,
        settings_json=settings_json,
    )
    session.add(duplicate)
    session.flush()

    if options.student_information and source.student:
        duplicate.student = Student(
            first_name=source.student.first_name,
            last_name=source.student.last_name,
            initials=source.student.initials,
            grade=source.student.grade,
            school=source.student.school,
            case_manager=source.student.case_manager,
            iep_start_date=source.student.iep_start_date,
            iep_end_date=source.student.iep_end_date,
        )

    area_map: dict[str, ServiceArea] = {}
    for area in (source.service_areas if options.service_areas else []):
        if area.deleted_at is not None:
            continue
        copied = ServiceArea(
            name=area.name,
            minutes=area.minutes,
            setting=area.setting,
            delivery_model=None,
            notes=area.notes,
            position=area.position,
        )
        duplicate.service_areas.append(copied)
        area_map[area.id] = copied
    session.flush()

    for goal in (source.goals if options.goals else []):
        if goal.deleted_at is not None or goal.service_area_id not in area_map:
            continue
        duplicate.goals.append(
            Goal(
                service_area_id=area_map[goal.service_area_id].id,
                title=goal.title,
                statement=goal.statement,
                data_sheet_summary=goal.data_sheet_summary,
                mastery_criteria=goal.mastery_criteria,
                progress_monitoring_method=goal.progress_monitoring_method,
                notes=goal.notes,
                position=goal.position,
            )
        )
    if options.at_a_glance and source.at_a_glance:
        duplicate.at_a_glance = AtAGlance(
            sections_json=deepcopy(source.at_a_glance.sections_json)
        )
    session.flush()

    goal_map = {
        original.id: copied
        for original, copied in zip(
            [goal for goal in source.goals if goal.deleted_at is None and goal.service_area_id in area_map],
            duplicate.goals,
            strict=False,
        )
    }
    for sheet in (source.data_sheets if options.data_sheets else []):
        if sheet.deleted_at is not None:
            continue
        copied_sheet = DataSheet(
            title=sheet.title,
            sheet_type=sheet.sheet_type,
            configuration_json=deepcopy(sheet.configuration_json),
        )
        copied_sheet.goals = [
            goal_map[goal.id]
            for goal in sheet.goals
            if goal.id in goal_map and goal.deleted_at is None
        ]
        duplicate.data_sheets.append(copied_sheet)
    for version in (source.packet_versions if options.packet_layout else []):
        if version.deleted_at is None:
            duplicate.packet_versions.append(
                PacketVersion(
                    name=version.name,
                    audience=version.audience,
                    settings_json=deepcopy(version.settings_json),
                )
            )
    session.commit()
    session.expire_all()
    return _detail(get_project(session, duplicate.id))


def set_archived(session: Session, project_id: str, archived: bool) -> ProjectSummary:
    project = get_project(session, project_id)
    project.archived_at = datetime.now(timezone.utc) if archived else None
    _touch(project)
    session.commit()
    session.expire_all()
    return _summary(get_project(session, project_id))


def project_detail(session: Session, project_id: str) -> ProjectDetail:
    return _detail(get_project(session, project_id))


def save_observation_checklist(
    session: Session, project_id: str, draft: ObservationChecklistDraft
) -> ProjectDetail:
    project = get_project(session, project_id)
    settings_json = deepcopy(project.settings_json or {})
    settings_json["observation_checklist"] = [
        item.strip() for item in draft.items if item.strip()
    ]
    project.settings_json = settings_json
    _touch(project)
    session.commit()
    session.expire_all()
    return _detail(get_project(session, project_id))


def save_packet_builder(
    session: Session, project_id: str, draft: PacketBuilderDraft
) -> ProjectDetail:
    project = get_project(session, project_id)
    versions = {
        version.id: version
        for version in project.packet_versions
        if version.deleted_at is None
    }
    for config in draft.packet_versions:
        version = versions.get(config.packet_version_id)
        if version is None:
            raise HTTPException(status_code=422, detail="Packet builder references an unavailable packet version.")
        settings_json = deepcopy(version.settings_json or {})
        settings_json["pages"] = [
            page.model_dump()
            for page in sorted(config.pages, key=lambda item: item.position)
        ]
        settings_json["asset_placements"] = [
            asset.model_dump()
            for asset in sorted(config.asset_placements, key=lambda item: item.position)
            if asset.label.strip()
        ]
        version.settings_json = settings_json
    _touch(project)
    session.commit()
    session.expire_all()
    return _detail(get_project(session, project_id))


def _audience_slug(name: str, fallback: str) -> str:
    slug = "".join(
        character.lower() if character.isalnum() else "_"
        for character in name.strip()
    ).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or fallback


def _ensure_export_packet(project: Project, session: Session) -> PacketVersion:
    for version in project.packet_versions:
        if version.deleted_at is None and version.audience == "base_packet":
            return version
    version = PacketVersion(
        project_id=project.id,
        name="Base Packet",
        audience="base_packet",
        settings_json={"deterministic": True},
    )
    session.add(version)
    session.flush()
    project.packet_versions.append(version)
    return version


def _resolve_packet_version(
    project: Project, session: Session, packet_version_id: str | None
) -> PacketVersion:
    if packet_version_id is None:
        return _ensure_export_packet(project, session)
    for version in project.packet_versions:
        if version.id == packet_version_id and version.deleted_at is None:
            return version
    raise HTTPException(status_code=404, detail="Packet version not found.")


def _data_collection_items(detail: ProjectDetail):
    goals_by_id = {goal.id: goal for goal in detail.goals}
    for sheet in detail.data_sheets:
        if sheet.is_observation_form:
            continue
        for goal_id in sheet.goal_ids:
            goal = goals_by_id.get(goal_id)
            if goal is None:
                continue
            for instance in range(1, sheet.blank_instance_count + 1):
                yield sheet, goal, instance


def _service_area_name(detail: ProjectDetail, service_area_id: str | None) -> str:
    for area in detail.service_areas:
        if area.id == service_area_id:
            return area.name
    return "Unassigned"


def _ordered_packet_pages(
    rendered_pages: dict[str, str], packet_config: PacketVersionConfig | None
) -> list[str]:
    if packet_config is None:
        ordered_ids = [str(page["id"]) for page in DEFAULT_PACKET_PAGES]
    else:
        ordered_ids = [
            page.id
            for page in sorted(packet_config.pages, key=lambda item: item.position)
            if page.enabled
        ]
    output: list[str] = []
    for page_id in ordered_ids:
        if page_id == "data_collection":
            output.extend(
                page
                for key, page in rendered_pages.items()
                if key.startswith("data_collection_")
            )
        elif page_id in rendered_pages:
            output.append(rendered_pages[page_id])
            if (
                page_id == "accommodations"
                and "accommodations_signature" in rendered_pages
                and "accommodations_signature" not in ordered_ids
            ):
                output.append(rendered_pages["accommodations_signature"])
    return output


def _font_stack(font_name: str) -> str:
    stacks = {
        "Open Sans": '"Open Sans", "Segoe UI", Arial, sans-serif',
        "Poppins": '"Poppins", "Segoe UI", Arial, sans-serif',
        "Segoe UI": '"Segoe UI", Arial, sans-serif',
        "Arial": 'Arial, sans-serif',
        "Georgia": 'Georgia, "Times New Roman", serif',
        "Times New Roman": '"Times New Roman", Georgia, serif',
    }
    return stacks.get(font_name, stacks["Open Sans"])


def _brand_body_font(brand_kit: BrandKit) -> str:
    return brand_kit.body_font or brand_kit.default_fonts or "Open Sans"


def _brand_heading_font(brand_kit: BrandKit) -> str:
    return brand_kit.heading_font or brand_kit.default_fonts or "Poppins"


def _packet_styles(
    theme_id: str,
    customization: ThemeCustomization | None = None,
    watermark_src: str = "",
    body_font_name: str = "",
    heading_font_name: str = "",
) -> str:
    tokens = dict(THEME_TOKENS.get(theme_id, THEME_TOKENS["teacher_friendly"]))
    if customization is not None:
        tokens.update(
            {
                "primary": customization.primary_color,
                "accent": customization.secondary_color,
                "blue": customization.secondary_color,
                "teal": customization.secondary_color,
                "orange": customization.accent_color,
                "soft": customization.background_color,
                "card": customization.card_color,
                "text": customization.text_color,
            }
        )
    css = """
    @page {
      size: Letter;
      margin: 0.45in;
      @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        color: #8393a8;
        font-size: 9px;
      }
    }
    * { box-sizing: border-box; }
    body {
      color: __TEXT__;
      font-family: __BODY_FONT__;
      font-size: 11px;
      line-height: 1.42;
      margin: 0;
    }
    h1, h2, h3, h4 {
      color: __PRIMARY__;
      font-family: __HEADING_FONT__;
      line-height: 1.12;
      margin: 0;
    }
    h1 { font-size: 42px; letter-spacing: 0.02em; text-transform: uppercase; }
    h2 { font-size: 20px; letter-spacing: 0.01em; margin-bottom: 14px; text-transform: uppercase; }
    h3 { font-size: 13px; margin-bottom: 8px; text-transform: uppercase; }
    h4 { font-size: 11px; margin-bottom: 5px; }
    p { margin: 0 0 7px; }
    ul { margin: 0; padding-left: 16px; }
    li { margin: 0 0 4px; }
    .page {
      background: __CARD__;
      break-after: page;
      box-shadow: 0 3px 14px rgba(15, 45, 85, 0.16);
      min-height: 9.55in;
      padding: 0.08in;
      position: relative;
    }
    .page:last-child { break-after: auto; }
    body.has-watermark .page:not(.cover)::after {
      background: url("__WATERMARK_SRC__") center center / contain no-repeat;
      content: "";
      height: 4.25in;
      left: 50%;
      opacity: 0.04;
      pointer-events: none;
      position: absolute;
      top: 4.775in;
      transform: translate(-50%, -50%);
      width: 4.25in;
      z-index: 20;
    }
    .page-header {
      align-items: center;
      border-bottom: 3px solid __BLUE__;
      display: flex;
      gap: 10px;
      margin-bottom: 16px;
      padding-bottom: 8px;
    }
    .page-header.green { border-color: __GREEN__; }
    .page-header.purple { border-color: __PURPLE__; }
    .page-header.orange { border-color: __ORANGE__; }
    .custom-page-header {
      align-items: center;
      display: flex;
      gap: 0;
      min-height: 0.36in;
      padding: 0.08in 0.12in;
      width: 100%;
    }
    .custom-page-header h2 {
      display: block;
      max-width: none;
      min-width: 0;
      overflow-wrap: anywhere;
      width: 100%;
    }
    .badge {
      align-items: center;
      background: __BLUE__;
      border-radius: 999px;
      color: white;
      display: inline-block;
      font-family: __HEADING_FONT__;
      font-size: 14px;
      font-weight: 800;
      height: 32px;
      justify-content: space-around;
      line-height: 32px;
      overflow: hidden;
      position: relative;
      text-align: center;
      vertical-align: middle;
      width: 32px;
    }
    .badge.green { background: __GREEN__; }
    .badge.purple { background: __PURPLE__; }
    .badge.orange { background: __ORANGE__; }
    .service-icon-badge {
      background-position: center 47%;
      background-repeat: no-repeat;
      background-size: 60% auto;
      color: transparent !important;
      font-size: 0;
    }
    .page-header .service-icon-badge {
      background-size: 42% auto;
      background-position: center center;
    }
    .page-icon-badge {
      color: transparent !important;
      font-size: 0;
    }
    .page-icon-badge img {
      display: block;
      height: 19px;
      margin: 6.5px auto;
      object-fit: contain;
      width: 19px;
    }
    .page-icon-img-observation {
      margin-left: 7.5px !important;
      margin-right: 5.5px !important;
    }
    .page-icon-img-service-info {
      margin-left: 7.5px !important;
      margin-right: 5.5px !important;
    }
    .eyebrow {
      color: __ACCENT__;
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.13em;
      text-transform: uppercase;
    }
    .muted { color: #64748b; }
    .cover {
      align-items: stretch;
      background:
        radial-gradient(circle at 75% 20%, __TEAL__, transparent 20%),
        linear-gradient(135deg, __PRIMARY__ 0%, __BLUE__ 58%, #0a2243 100%);
      color: white;
      display: flex;
      min-height: 9.55in;
      overflow: hidden;
      padding: 0;
    }
    .service-area-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      column-gap: 16px;
      row-gap: 12px;
      margin: 14px 0 20px;
    }
    .service-area-card {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      background: #f8fafc;
      border: 1px solid #dbe5ef;
      border-radius: 10px;
      box-sizing: border-box;
      min-height: 40px;
      height: 40px;
    }
    .service-area-card .mini-dot {
      align-items: center;
      border-radius: 50%;
      display: flex;
      flex: 0 0 30px;
      height: 30px;
      justify-content: center;
      line-height: 0;
      overflow: hidden;
      position: relative;
      width: 30px;
    }
    .service-area-card .mini-dot.blue {
      background: __BLUE__;
    }
    .service-area-card .mini-dot.green {
      background: __GREEN__;
    }
    .service-area-card .mini-dot.purple {
      background: __PURPLE__;
    }
    .service-area-card .mini-dot.orange {
      background: __ORANGE__;
    }
    .service-area-card .mini-dot .service-icon-img {
      display: block;
      height: 58%;
      left: 50%;
      margin: 0;
      object-fit: contain;
      position: absolute;
      top: 50%;
      transform: translate(-50%, -50%);
      width: 58%;
    }
    .service-area-name {
      display: flex;
      align-items: center;
      height: 100%;
      flex: 1;
      font-size: 10pt;
      font-weight: 600;
      line-height: 1.2;
      color: #1f2937;
    }
    .cover-card {
      border: 0;
      border-radius: 0;
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 52px;
      position: relative;
      width: 100%;
    }
    .cover-card h1, .cover-card h2 { color: white; }
    .cover-icon {
      align-items: center;
      background: rgba(255,255,255,0.14);
      border: 2px solid rgba(255,255,255,0.24);
      border-radius: 999px;
      color: #64ddd8;
      display: flex;
      font-family: __HEADING_FONT__;
      font-size: 20px;
      font-weight: 900;
      height: 64px;
      justify-content: center;
      letter-spacing: 0.02em;
      margin: 0 auto 18px;
      position: relative;
      overflow: hidden;
      width: 64px;
    }
    .brand-logo {
      display: block;
      height: 58px;
      margin: 0 auto 18px;
      object-fit: contain;
      width: 90px;
    }
    .cover-logo {
      background: transparent;
      border: 0;
      border-radius: 0;
      box-shadow: none;
      padding: 0;
    }
    .cover-content,
    .cover-bottom {
      position: relative;
      z-index: 2;
    }
    .cover-district-mark {
      display: none;
    }
    .cover-version-footer {
      display: none;
    }
    .cover-kicker {
      color: #64ddd8;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.34em;
      text-transform: uppercase;
    }
    .cover-school {
      color: rgba(255,255,255,0.72);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.18em;
      margin: -2px 0 12px;
      min-height: 12px;
      text-transform: uppercase;
    }
    .cover-year {
      background: __TEAL__;
      color: white;
      display: inline-block;
      font-family: __HEADING_FONT__;
      font-size: 17px;
      font-weight: 800;
      margin: 18px 0 30px;
      padding: 8px 30px;
    }
    .cover-student {
      color: #64ddd8;
      font-family: __HEADING_FONT__;
      font-size: 23px;
      font-weight: 800;
      letter-spacing: 0.02em;
      margin-bottom: 0;
      text-align: center;
      text-transform: uppercase;
    }
    .cover-details {
      align-self: stretch;
      display: block;
      margin: 20px auto 0;
      text-align: center;
      width: 100%;
    }
    .cover-services {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: nowrap;
    width: 100%;
    max-width: 5.9in;
    margin: 18px auto;
    gap: 0;
    }

    .service-chip {
    align-items: center;
    color: white;
    display: inline-flex;
    flex-direction: column;
    flex: 0 0 0.58in;
    width: 0.58in;
    font-size: 6.5px;
    font-weight: 700;
    gap: 5px;
    line-height: 1.05;
    text-align: center;
    text-transform: uppercase;
    box-sizing: border-box;
    }

    .service-chip > span:last-child {
    display: block;
    width: 100%;
    min-height: 24px;
    line-height: 1.05;
    }
    .chip-dot {
    align-items: center;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 999px;
    color: #ffffff;
    display: inline-block;
    height: 46px;
    line-height: 46px;
    position: relative;
    text-align: center;
    width: 46px;
    }
    .cover .chip-dot {
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.25);
      color: white;
    }
    .cover-simple-icon {
      align-items: center;
      display: flex;
      height: 100%;
      justify-content: center;
      width: 100%;
    }
    .cover-simple-icon svg {
      display: block;
      height: 23px;
      width: 23px;
    }
    .service-icon-img {
      display: block;
      object-fit: contain;
    }
    .chip-dot .service-icon-img,
    .badge .service-icon-img,
    .cover-icon .service-icon-img {
      height: 58%;
      left: 50%;
      position: absolute;
      top: 50%;
      transform: translate(-50%, -50%);
      width: 58%;
    }
    .chip-dot .cover-service-icon {
      height: 62%;
      width: 62%;
    }
    .mini-dot {
      align-items: center;
      display: inline-flex;
      justify-content: center;
      line-height: 0;
      overflow: hidden;
      position: relative;
    }
    
    /* ==========================
    5 Services
    ========================== */
    .cover-services.service-count-5 {
      gap: 12px 18px;
      margin: 20px auto 18px;
      max-width: 5.8in;
    }
    .cover-services.service-count-5 .service-chip {
      font-size: 7.8px;
      gap: 6px;
      max-width: 0.75in;
    }
    .cover-services.service-count-5 .chip-dot {
      width: 40px;
      height: 40px;
    }
    /* ==========================
    6 Services
    ========================== */
    .cover-services.service-count-6 {
      gap: 10px 16px;
      margin: 18px auto;
      max-width: 5.8in;
    }
    .cover-services.service-count-6 .service-chip {
      font-size: 7.4px;
      gap: 5px;
      max-width: 0.70in;
    }
    .cover-services.service-count-6 .chip-dot {
      width: 38px;
      height: 38px;
    }
    /* ==========================
    7 Services
    ========================== */
    .cover-services.service-count-7 {
      gap: 8px 12px;
      margin: 16px auto;
      max-width: 5.7in;
    }
    .cover-services.service-count-7 .service-chip {
      font-size: 6.8px;
      gap: 4px;
      max-width: 0.64in;
    }
    .cover-services.service-count-7 .chip-dot {
      width: 34px;
      height: 34px;
    }
    /* ==========================
    8 Services
    ========================== */
    .cover-services.service-count-8 {
      gap: 7px 10px;
      margin: 14px auto;
      max-width: 5.7in;
    }
    .cover-services.service-count-8 .service-chip {
      font-size: 6.4px;
      gap: 3px;
      max-width: 0.60in;
    }
    .cover-services.service-count-8 .chip-dot {
      width: 32px;
      height: 32px;
    }
    .page-header .badge .service-icon-img {
      height: 62%;
      width: 62%;
      left: 50%;
      position: absolute;
      top: 41%;
      transform: translate(-50%, -50%);
    }
    .mountains {
      bottom: 0;
      height: 66px;
      left: 0;
      opacity: 0.28;
      overflow: hidden;
      position: absolute;
      right: 0;
    }
    .mountains:before,
    .mountains:after {
      border-left: 80px solid transparent;
      border-right: 80px solid transparent;
      border-bottom: 56px solid rgba(100, 221, 216, 0.45);
      bottom: 0;
      content: "";
      position: absolute;
    }
    .mountains:before { left: 44px; }
    .mountains:after { right: 54px; border-bottom-color: rgba(255,255,255,0.22); }
    .meta-grid {
      border-collapse: separate;
      border-spacing: 12px;
      margin-left: auto;
      margin-right: auto;
      margin-top: 12px;
      table-layout: fixed;
      width: 520px;
    }
    .meta-box {
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.16);
      border-radius: 10px;
      box-sizing: border-box;
      min-height: 62px;
      min-width: 0;
      overflow: hidden;
      padding: 10px 12px;
      vertical-align: top;
      width: 33.333%;
    }
    .meta-spacer {
      border: 0;
      padding: 0;
      width: 16.667%;
    }
    .meta-label {
      color: rgba(255,255,255,0.7);
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.08em;
      line-height: 1.15;
      margin: 0;
      text-transform: uppercase;
    }
    .meta-value {
      color: white;
      font-size: 12px;
      line-height: 1.25;
      margin: 4px 0 0;
      overflow-wrap: break-word;
      word-break: normal;
    }
    .section {
      background: __CARD__;
      border: 1px solid __BORDER__;
      border-radius: 14px;
      margin-bottom: 11px;
      overflow: hidden;
      padding: 14px;
      overflow-wrap: anywhere;
    }
    .soft-card {
      background: __CARD__;
      border: 1px solid __BORDER__;
      border-radius: 14px;
      overflow: hidden;
      padding: 14px;
      overflow-wrap: anywhere;
    }
    .accommodation-note {
      margin: 0 0 14px;
      overflow-wrap: anywhere;
      padding: 0 0 10px;
    }
    .accommodation-note h3 {
      color: __PRIMARY__;
      margin-bottom: 6px;
    }
    .accommodations-student-details {
      border-bottom: 2px solid __BORDER__;
      color: __TEXT__;
      display: flex;
      gap: 18px;
      margin: -4px 0 14px;
      padding: 0 0 10px;
      overflow-wrap: anywhere;
    }
    .accommodations-parent-strengths {
      border-top: 2px solid __BORDER__;
      margin-top: 16px;
      padding-top: 12px;
    }
    .signature-note {
      color: __TEXT__;
      font-size: 12px;
      line-height: 1.55;
      margin: 0 0 20px;
      max-width: 7.2in;
      overflow-wrap: anywhere;
    }
    .signature-lines {
      display: block;
      margin-top: 12px;
    }
    .signature-row {
      align-items: flex-end;
      display: flex;
      gap: 16px;
      margin-bottom: 31px;
    }
    .signature-header {
      margin-bottom: 14px;
    }
    .signature-header .signature-label {
      margin-bottom: 0;
    }
    .signature-field {
      flex: 1 1 auto;
      min-width: 0;
    }
    .signature-field.date {
      flex: 0 0 1.35in;
    }
    .signature-label {
      color: __TEXT__;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.06em;
      margin-bottom: 16px;
      text-transform: uppercase;
    }
    .signature-line {
      border-bottom: 1.5px solid __TEXT__;
      height: 14px;
      width: 100%;
    }
    .custom-page-body {
      color: __TEXT__;
      font-size: 12px;
      line-height: 1.65;
      min-height: 6.8in;
      overflow-wrap: anywhere;
    }
    .custom-page-body.blank-lines {
      display: block;
      min-height: 6.9in;
    }
    .custom-page-body.blank-lines div {
      border-bottom: 1px solid rgba(0,0,0,0.18);
      height: 0.35in;
      margin: 0;
    }
    .two-col {
      display: grid;
      gap: 14px;
      grid-template-columns: 1fr 1fr;
    }
    .domain-title {
      align-items: center;
      display: flex;
      gap: 9px;
      margin: 14px 0 8px;
    }
    .domain-title .mini-dot {
      align-items: center;
      border-radius: 999px;
      display: inline-flex;
      flex: 0 0 24px;
      height: 24px;
      justify-content: center;
      line-height: 0;
      overflow: hidden;
      position: relative;
      vertical-align: middle;
      width: 24px;
    }
    .domain-title .mini-dot.blue {
      background: __BLUE__;
      color: #ffffff;
    }
    .domain-title .mini-dot.green {
      background: __GREEN__;
      color: #ffffff;
    }
    .domain-title .mini-dot.purple {
      background: __PURPLE__;
      color: #ffffff;
    }
    .domain-title .mini-dot.orange {
      background: __ORANGE__;
      color: #ffffff;
    }
    .domain-title .mini-dot .service-icon-img {
      display: block;
      height: 58%;
      left: 50%;
      margin: 0;
      object-fit: contain;
      position: absolute;
      top: 50%;
      transform: translate(-50%, -50%);
      width: 58%;
    }
    .goal-card {
      background: __CARD__;
      border: 1px solid __BORDER__;
      border-radius: 8px;
      margin-bottom: 8px;
      overflow: hidden;
      padding: 9px 11px;
      overflow-wrap: anywhere;
    }
    .goal-card.green { background: __GREEN_SOFT__; border-color: #bddfb1; }
    .goal-card.purple { background: __PURPLE_SOFT__; border-color: #d5c8ed; }
    table { border-collapse: collapse; width: 100%; }
    th {
      background: __SOFT__;
      color: __PRIMARY__;
      font-weight: 700;
      text-align: left;
      text-transform: uppercase;
      font-size: 8px;
    }
    th, td {
      border: 1px solid __BORDER__;
      padding: 6px 7px;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    .data-row td { height: 28px; }
    .notes-lines {
      background: repeating-linear-gradient(
        to bottom,
        transparent 0,
        transparent 23px,
        rgba(100, 116, 139, 0.34) 24px
      );
      border: 1px solid __BORDER__;
      border-radius: 10px;
      height: 108px;
    }
    .data-collection-table {
      height: 6.35in;
    }
    .data-collection-table table,
    .data-collection-table tbody {
      height: 100%;
    }
    .data-collection-table .data-row td {
      height: auto;
      min-height: 34px;
    }
    .placeholder {
      border: 1px dashed __BORDER__;
      border-radius: 14px;
      color: #64748b;
      padding: 18px;
    }
    .staff-checklist {
      background: __ORANGE_SOFT__;
      border: 1px solid #f3bc78;
      border-radius: 12px;
      padding: 10px 13px;
    }
    .staff-checklist h3 {
      margin-bottom: 7px;
    }
    .observation-page {
      display: flex;
      flex-direction: column;
      min-height: 9.55in;
    }
    .observations-table {
      flex: 0 0 auto;
      height: 6.78in;
    }
    .observations-table table,
    .observations-table tbody {
      height: 100%;
    }
    .observations-table .data-row td {
      height: auto;
      min-height: 34px;
    }
    .check-table {
      border-collapse: collapse;
      table-layout: fixed;
      width: 100%;
    }
    .check-table td {
      border: 0;
      font-size: 9px;
      line-height: 1.18;
      padding: 2px 12px 2px 0;
      overflow-wrap: normal;
      vertical-align: top;
      width: 50%;
      word-break: normal;
    }
    .check-box {
      border: 1px solid __ORANGE__;
      display: inline-block;
      height: 8px;
      margin-right: 5px;
      vertical-align: -1px;
      width: 8px;
    }
    body.template-elementary-friendly .cover {
      background:
        radial-gradient(circle at 86% 18%, rgba(255,255,255,0.28), transparent 24%),
        linear-gradient(145deg, __TEAL__ 0%, __PRIMARY__ 68%, __PURPLE__ 100%);
    }
    body.template-elementary-friendly .cover-card {
      padding: 48px;
    }
    body.template-elementary-friendly .cover-year,
    body.template-elementary-friendly .badge,
    body.template-elementary-friendly .chip-dot {
      border-radius: 18px;
    }
    body.template-elementary-friendly .section,
    body.template-elementary-friendly .soft-card,
    body.template-elementary-friendly .goal-card,
    body.template-elementary-friendly .staff-checklist {
      border-radius: 18px;
    }
    body.template-elementary-friendly th {
      font-size: 9px;
    }
    body.template-minimal {
      color: #111827;
      font-family: Arial, sans-serif;
    }
    body.template-minimal h1,
    body.template-minimal h2,
    body.template-minimal h3,
    body.template-minimal h4 {
      color: #111827;
      font-family: Arial, sans-serif;
      letter-spacing: 0;
    }
    body.template-minimal .cover {
      background: #ffffff;
      border: 2px solid #111827;
      color: #111827;
    }
    body.template-minimal .cover-card h1,
    body.template-minimal .cover-card h2,
    body.template-minimal .cover-kicker,
    body.template-minimal .cover-school,
    body.template-minimal .cover-student,
    body.template-minimal .meta-value {
      color: #111827;
    }
    body.template-minimal .cover-year,
    body.template-minimal .badge,
    body.template-minimal .chip-dot {
      background: #111827;
      color: #ffffff;
    }
    body.template-minimal .service-chip {
      color: #111827;
    }
    body.template-minimal .meta-box,
    body.template-minimal .section,
    body.template-minimal .soft-card,
    body.template-minimal .goal-card,
    body.template-minimal th,
    body.template-minimal td {
      background: #ffffff;
      border-color: #111827;
    }
    body.template-minimal .meta-label {
      color: #374151;
    }
    body.template-minimal .mountains {
      display: none;
    }
    body.template-district-branding .cover {
      background: linear-gradient(180deg, #ffffff 0%, #eef6fb 100%);
      border-top: 18px solid __PRIMARY__;
      color: __TEXT__;
    }
    body.template-district-branding .cover-card h1,
    body.template-district-branding .cover-card h2,
    body.template-district-branding .cover-student {
      color: __PRIMARY__;
    }
    body.template-district-branding .cover-kicker,
    body.template-district-branding .cover-school {
      color: __ACCENT__;
    }
    body.template-district-branding .cover-year {
      background: __PRIMARY__;
    }
    body.template-district-branding .service-chip,
    body.template-district-branding .meta-value {
      color: __TEXT__;
    }
    body.template-district-branding .meta-box {
      background: #ffffff;
      border-color: __BORDER__;
    }
    body.template-district-branding .meta-label {
      color: #64748b;
    }
    body.template-district-branding .mountains {
      opacity: 0.12;
    }
    body.template-contemporary .page-header {
      background: __SOFT__;
      border: 0;
      border-left: 8px solid __ACCENT__;
      border-radius: 14px;
      padding: 12px;
    }
    body.template-contemporary .section,
    body.template-contemporary .soft-card,
    body.template-contemporary .goal-card {
      box-shadow: 0 8px 20px rgba(15, 45, 85, 0.08);
    }
    body.template-contemporary th {
      background: __PRIMARY__;
      color: #ffffff;
    }
    body.template-alpine-photo {
      background: __SOFT__;
      color: __TEXT__;
    }
    body.template-alpine-photo h1,
    body.template-alpine-photo h2,
    body.template-alpine-photo h3,
    body.template-alpine-photo h4 {
      font-family: __HEADING_FONT__;
    }
    body.template-alpine-photo .cover {
      background: linear-gradient(180deg, __ACCENT__ 0%, __PRIMARY__ 62%, #071827 100%);
      color: #ffffff;
      overflow: hidden;
    }
    body.template-alpine-photo .cover:before {
      border-bottom: 5.15in solid rgba(255,255,255,0.18);
      border-left: 3.1in solid transparent;
      border-right: 3.1in solid transparent;
      bottom: 0.88in;
      content: "";
      height: 0;
      position: absolute;
      right: -0.92in;
      width: 0;
      z-index: 0;
    }
    body.template-alpine-photo .cover:after {
      border-bottom: 1.52in solid rgba(240,247,252,0.88);
      border-left: 0.93in solid transparent;
      border-right: 0.93in solid transparent;
      bottom: 4.5in;
      content: "";
      height: 0;
      position: absolute;
      right: 1.25in;
      width: 0;
      z-index: 1;
    }
    body.template-alpine-photo .cover-card {
      justify-content: space-between;
      min-height: 9.55in;
      padding: 0.5in 0.48in 0.34in;
      position: relative;
    }
    body.template-alpine-photo .cover-card:before {
      background: rgba(7,24,39,0.34);
      bottom: 1.03in;
      content: "";
      height: 4.1in;
      position: absolute;
      right: -0.4in;
      transform: skewX(-31deg);
      width: 2.45in;
      z-index: 1;
    }
    body.template-alpine-photo .cover-card:after {
      background: rgba(255,255,255,0.38);
      bottom: 1.54in;
      content: "";
      height: 0.018in;
      left: 0.44in;
      position: absolute;
      right: 0.5in;
      z-index: 2;
    }
    body.template-alpine-photo .cover-content {
      background: rgba(7,24,39,0.78);
      border-left: 0.065in solid __ORANGE__;
      box-sizing: border-box;
      padding: 0.28in 0.3in 0.3in;
      text-align: left;
      width: 4.05in;
      z-index: 3;
    }
    body.template-alpine-photo .cover-icon {
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.36);
      border-radius: 50%;
      box-shadow: none;
      color: #ffffff;
      height: 56px;
      margin: 0 0 16px;
      width: 56px;
    }
    body.template-alpine-photo .brand-logo {
      height: 58px;
      margin: 0 0 16px;
      object-fit: contain;
      width: 94px;
    }
    body.template-alpine-photo .cover-kicker {
      color: __ORANGE__;
      font-size: 9px;
      font-weight: 800;
      letter-spacing: 0.28em;
      margin-bottom: 2px;
      text-align: left;
    }
    body.template-alpine-photo .cover-school {
      color: rgba(255,255,255,0.74);
      font-size: 8px;
      letter-spacing: 0.16em;
      margin: 0 0 0.16in;
      text-align: left;
    }
    body.template-alpine-photo .cover-card h1 {
      color: #ffffff;
      font-size: 47px;
      letter-spacing: 0;
      line-height: 0.9;
      text-align: left;
      text-shadow: 0 2px 0 rgba(0,0,0,0.16);
    }
    body.template-alpine-photo .cover-year {
      background: __ORANGE__;
      color: #ffffff;
      margin: 0.2in 0 0.18in;
      min-width: 1.7in;
      padding: 0.08in 0.16in;
      text-align: left;
    }
    body.template-alpine-photo .cover-student {
      color: #ffffff;
      font-size: 20px;
      letter-spacing: 0;
      margin: 0;
      text-align: left;
    }
    body.template-alpine-photo .cover-district-mark {
      background-color: transparent;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 128 128'%3E%3Cpath d='M78 8A56 56 0 1 0 113 105A49 49 0 0 1 78 8Z' fill='%23eef7ff'/%3E%3C/svg%3E");
      background-position: center;
      background-repeat: no-repeat;
      background-size: contain;
      border: 0;
      border-radius: 0;
      box-shadow: none;
      color: transparent;
      display: block;
      font-size: 0;
      height: 0.9in;
      position: absolute;
      right: 0.92in;
      top: 0.92in;
      width: 0.9in;
      z-index: 2;
    }
    body.template-alpine-photo .cover-district-mark:after {
      display: none;
    }
    body.template-alpine-photo .cover-bottom {
      align-self: center;
      background: rgba(7,24,39,0.86);
      border: 1px solid rgba(255,255,255,0.18);
      border-bottom: 0.08in solid __ORANGE__;
      border-radius: 0;
      box-sizing: border-box;
      color: #ffffff;
      margin-left: auto;
      margin-right: auto;
      padding: 0.14in 0.18in 0.1in;
      width: 5.7in;
      z-index: 4;
    }
    body.template-alpine-photo .cover-details {
      margin: 0;
      text-align: left;
      width: 100%;
    }
    body.template-alpine-photo .cover-services,
    body.template-alpine-photo .cover-services.service-count-5,
    body.template-alpine-photo .cover-services.service-count-6,
    body.template-alpine-photo .cover-services.service-count-7,
    body.template-alpine-photo .cover-services.service-count-8 {
      gap: 0.07in;
      justify-content: center;
      margin: 0 auto 0.1in;
      max-width: none;
    }
    body.template-alpine-photo .cover-services .service-chip,
    body.template-alpine-photo .cover-services.service-count-5 .service-chip,
    body.template-alpine-photo .cover-services.service-count-6 .service-chip,
    body.template-alpine-photo .cover-services.service-count-7 .service-chip,
    body.template-alpine-photo .cover-services.service-count-8 .service-chip {
      color: #ffffff;
      font-size: 6.5px;
      gap: 4px;
      max-width: 0.64in;
      min-width: 0.56in;
      overflow-wrap: anywhere;
    }
    body.template-alpine-photo .cover-services.service-count-7 .service-chip,
    body.template-alpine-photo .cover-services.service-count-8 .service-chip {
      font-size: 5.8px;
      max-width: 0.56in;
      min-width: 0.48in;
    }
    body.template-alpine-photo .cover-services .chip-dot {
      background: rgba(255,255,255,0.1);
      border: 1px solid rgba(255,255,255,0.4);
      color: #ffffff;
      height: 32px;
      width: 32px;
    }
    body.template-alpine-photo .meta-grid {
      border-spacing: 7px;
      left: -0.19in;
      margin: 0 auto;
      position: relative;
      table-layout: fixed;
      width: calc(100% - 14px);
    }
    body.template-alpine-photo .meta-box {
      background: rgba(255,255,255,0.09);
      border: 1px solid rgba(255,255,255,0.22);
      border-radius: 0;
      min-height: 0;
      padding: 7px 8px;
    }
    body.template-alpine-photo .meta-label {
      color: rgba(255,255,255,0.66);
      font-size: 7px;
      letter-spacing: 0.1em;
    }
    body.template-alpine-photo .meta-value {
      color: #ffffff;
      font-size: 9px;
      font-weight: 700;
    }
    body.template-alpine-photo .mountains {
      bottom: 0;
      display: block;
      height: 2.22in;
      left: 0;
      opacity: 1;
      overflow: visible;
      position: absolute;
      right: 0;
      width: auto;
      z-index: 2;
    }
    body.template-alpine-photo .mountains:before {
      border-bottom: 2.02in solid __PRIMARY__;
      border-left: 1.7in solid transparent;
      border-right: 1.7in solid transparent;
      bottom: 0;
      content: "";
      height: 0;
      left: 2.7in;
      position: absolute;
      width: 0;
    }
    body.template-alpine-photo .mountains:after {
      border-bottom: 1.58in solid #071827;
      border-left: 1.42in solid transparent;
      border-right: 1.42in solid transparent;
      bottom: 0;
      content: "";
      height: 0;
      left: 4.65in;
      position: absolute;
      width: 0;
    }
+    /* Field Notes packet template
       Drop this block into _packet_styles() after the shared/base packet CSS.
       Palette token mapping:
       __PRIMARY__ = Primary
       __ACCENT__/__TEAL__/__BLUE__ = Secondary
       __ORANGE__ = Accent
       __SOFT__ = Background
       __CARD__ = Cards
       __TEXT__ = Text
    */

    body.template-field-notes {
      background: __SOFT__;
      color: __TEXT__;
    }

    body.template-field-notes h1,
    body.template-field-notes h2,
    body.template-field-notes h3,
    body.template-field-notes h4 {
      color: __PRIMARY__;
      font-family: __HEADING_FONT__;
    }

    body.template-field-notes .cover {
      background:
        repeating-radial-gradient(
          ellipse at 92% 12%,
          transparent 0,
          transparent 15px,
          rgba(0,0,0,0.035) 16px,
          transparent 17px,
          transparent 30px
        ),
        __SOFT__;
      color: __TEXT__;
      overflow: hidden;
    }

    body.template-field-notes .cover:before {
      background: __PRIMARY__;
      bottom: 0.38in;
      content: "";
      left: 0.38in;
      position: absolute;
      top: 0.38in;
      width: 0.075in;
      z-index: 0;
    }

    body.template-field-notes .cover:after {
      background: __ORANGE__;
      bottom: 0.38in;
      content: "";
      left: 0.56in;
      position: absolute;
      top: 0.38in;
      width: 0.022in;
      z-index: 0;
    }

    body.template-field-notes .cover-card {
      justify-content: space-between;
      padding: 0.56in 0.56in 0.42in 0.86in;
    }

    body.template-field-notes .cover-content {
      text-align: left;
      width: 5.15in;
    }

    body.template-field-notes .cover-icon {
      background: __PRIMARY__;
      border: 2px solid __CARD__;
      border-radius: 50%;
      box-shadow: 0 5px 0 rgba(0,0,0,0.08);
      color: #ffffff;
      height: 58px;
      margin: 0 0 16px;
      width: 58px;
    }

    body.template-field-notes .brand-logo {
      height: 58px;
      margin: 0 0 16px;
      width: 94px;
    }

    body.template-field-notes .cover-kicker {
      color: __ACCENT__;
      font-size: 10px;
      letter-spacing: 0.28em;
      margin-bottom: 2px;
      text-align: left;
    }

    body.template-field-notes .cover-school {
      color: __PRIMARY__;
      font-size: 9px;
      letter-spacing: 0.18em;
      margin: 0 0 20px;
      text-align: left;
    }

    body.template-field-notes .cover-card h1 {
      color: __PRIMARY__;
      font-size: 45px;
      letter-spacing: -0.025em;
      line-height: 0.94;
      text-align: left;
    }

    body.template-field-notes .cover-year {
      background: __ACCENT__;
      border-left: 6px solid __ORANGE__;
      box-shadow: 0 4px 0 rgba(0,0,0,0.08);
      display: inline-block;
      margin: 18px 0 24px;
      min-width: 1.82in;
      padding: 7px 16px;
      text-align: center;
    }

    body.template-field-notes .cover-student {
      border-bottom: 1px solid __PRIMARY__;
      border-top: 1px solid __PRIMARY__;
      color: __TEXT__;
      font-family: __HEADING_FONT__;
      font-size: 24px;
      font-weight: 800;
      letter-spacing: 0.01em;
      margin: 0;
      padding: 12px 0 10px;
      text-align: left;
    }

    body.template-field-notes .cover-bottom {
      background: transparent;
      color: __TEXT__;
      margin: 0;
      padding: 0;
      width: 100%;
    }

    body.template-field-notes .cover-details {
      margin: 0;
      text-align: left;
    }

    body.template-field-notes .cover-services {
      border-collapse: separate;
      border-spacing: 7px 0;
      display: table;
      margin: 0 0 12px;
      table-layout: fixed;
      width: 100%;
    }

    body.template-field-notes .cover-services .service-chip {
      background: __PRIMARY__;
      border-top: 5px solid __ORANGE__;
      color: #ffffff;
      display: table-cell;
      font-size: 7px;
      height: 0.84in;
      max-width: none;
      padding: 8px 6px 6px;
      vertical-align: top;
      width: auto;
    }

    body.template-field-notes .cover-services .chip-dot {
      background: rgba(255,255,255,0.10);
      border: 1px solid rgba(255,255,255,0.42);
      border-radius: 50%;
      color: #ffffff;
      height: 29px;
      margin: 0 auto 5px;
      width: 29px;
    }

    body.template-field-notes .cover-services .service-chip > span:last-child {
      color: #ffffff;
      min-height: 19px;
    }

    body.template-field-notes .meta-grid {
      border-collapse: separate;
      border-spacing: 7px;
      margin: 0;
      table-layout: fixed;
      width: 100%;
    }

    body.template-field-notes .meta-box {
      background: __CARD__;
      border: 1px solid rgba(0,0,0,0.16);
      border-radius: 0;
      box-shadow: 0 3px 0 rgba(0,0,0,0.06);
      color: __TEXT__;
      min-height: 0;
      padding: 9px 10px;
    }

    body.template-field-notes .meta-label {
      color: __ACCENT__;
      font-size: 7px;
      letter-spacing: 0.13em;
    }

    body.template-field-notes .meta-value {
      color: __TEXT__;
      font-size: 10px;
      font-weight: 700;
    }

    body.template-field-notes .meta-spacer {
      width: 12.5%;
    }

    body.template-field-notes .mountains {
      display: none;
    }

    /* Interior pages */
    body.template-field-notes .page:not(.cover) {
      background:
        linear-gradient(90deg, __PRIMARY__ 0, __PRIMARY__ 0.065in, transparent 0.065in),
        repeating-linear-gradient(180deg, transparent 0, transparent 0.31in, rgba(0,0,0,0.025) 0.32in),
        __SOFT__;
      box-shadow: none;
      padding-left: 0.19in;
    }

    body.template-field-notes .page-header {
      background: transparent;
      border: 0;
      border-bottom: 2px solid __PRIMARY__;
      border-radius: 0;
      margin-bottom: 15px;
      padding: 4px 0 9px;
    }

    body.template-field-notes .page-header:after {
      background: __ORANGE__;
      bottom: -5px;
      content: "";
      height: 3px;
      left: 0;
      position: absolute;
      width: 0.82in;
    }

    body.template-field-notes .page-header .badge,
    body.template-field-notes .page-header .badge.green,
    body.template-field-notes .page-header .badge.purple,
    body.template-field-notes .page-header .badge.orange {
      background: __PRIMARY__;
      border: 1.5px solid __PRIMARY__;
      border-radius: 50%;
      color: #ffffff;
    }

    body.template-field-notes .section,
    body.template-field-notes .soft-card,
    body.template-field-notes .goal-card {
      background: __CARD__;
      border: 1px solid rgba(0,0,0,0.16);
      border-left: 5px solid __ACCENT__;
      border-radius: 0;
      box-shadow: 0 3px 0 rgba(0,0,0,0.05);
    }

    body.template-field-notes .goal-card.green,
    body.template-field-notes .goal-card.purple {
      background: __CARD__;
      border-color: rgba(0,0,0,0.16);
      border-left-color: __ACCENT__;
    }

    body.template-field-notes .domain-title .mini-dot,
    body.template-field-notes .domain-title .mini-dot.blue,
    body.template-field-notes .domain-title .mini-dot.green,
    body.template-field-notes .domain-title .mini-dot.purple,
    body.template-field-notes .domain-title .mini-dot.orange {
      background: __PRIMARY__;
      border-radius: 50%;
      color: #ffffff;
    }

    body.template-field-notes th {
      background: __PRIMARY__;
      color: #ffffff;
      font-size: 8px;
      letter-spacing: 0.05em;
    }

    body.template-field-notes th,
    body.template-field-notes td {
      border-color: rgba(0,0,0,0.20);
    }

    body.template-field-notes .notes-lines {
      background:
        repeating-linear-gradient(
          to bottom,
          transparent 0,
          transparent 23px,
          rgba(0,0,0,0.18) 24px
        ),
        __CARD__;
      border-radius: 0;
    }

    body.template-field-notes .staff-checklist {
      background: __CARD__;
      border: 1px solid rgba(0,0,0,0.16);
      border-left: 5px solid __ORANGE__;
      border-radius: 0;
    }

    body.template-field-notes .check-box {
      border-color: __ORANGE__;
    }
+    /* Editorial Ledger - Service Index revision
       Drop this block into _packet_styles() after the shared/base packet CSS.
       Palette token mapping:
       __PRIMARY__ = Primary
       __ACCENT__ = Secondary
       __ORANGE__ = Accent
       __SOFT__ = Background
       __CARD__ = Cards
       __TEXT__ = Text
    */

    body.template-editorial-ledger {
      background: __SOFT__;
      color: __TEXT__;
    }

    body.template-editorial-ledger h1,
    body.template-editorial-ledger h2,
    body.template-editorial-ledger h3,
    body.template-editorial-ledger h4 {
      color: __PRIMARY__;
      font-family: Georgia, "Times New Roman", serif;
      letter-spacing: 0;
    }

    body.template-editorial-ledger .cover {
      background: __CARD__;
      color: __TEXT__;
      overflow: hidden;
    }

    body.template-editorial-ledger .cover-card {
      justify-content: flex-start;
      padding: 0.42in 0.42in 0.38in;
    }

    body.template-editorial-ledger .cover-card:before {
      background: __PRIMARY__;
      content: "";
      height: 0.025in;
      left: 0.12in;
      position: absolute;
      right: 0.12in;
      top: 0.18in;
    }

    body.template-editorial-ledger .cover-content {
      border: 0;
      height: 6.45in;
      padding: 0;
      position: relative;
      text-align: left;
      width: 100%;
    }

    body.template-editorial-ledger .cover-content:after {
      color: __PRIMARY__;
      content: attr(data-year-mark);
      font-family: Georgia, "Times New Roman", serif;
      font-size: 112px;
      font-weight: 700;
      line-height: 0.8;
      opacity: 0.065;
      position: absolute;
      right: -0.08in;
      top: 0.02in;
      z-index: 0;
    }

    body.template-editorial-ledger .cover-icon,
    body.template-editorial-ledger .brand-logo {
      display: none;
    }

    body.template-editorial-ledger .cover-kicker {
      color: __PRIMARY__;
      font-size: 7.5px;
      font-weight: 700;
      left: 0;
      letter-spacing: 0.22em;
      margin: 0;
      position: absolute;
      top: 0;
      text-align: left;
      text-transform: uppercase;
    }

    body.template-editorial-ledger .cover-school {
      color: __ACCENT__;
      font-size: 7.5px;
      font-weight: 500;
      letter-spacing: 0.05em;
      margin: 0;
      position: absolute;
      right: 0;
      text-align: right;
      text-transform: none;
      top: 0;
    }

    body.template-editorial-ledger .cover-card h1 {
      color: __PRIMARY__;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 47px;
      font-weight: 700;
      left: 0.15in;
      letter-spacing: -0.035em;
      line-height: 0.9;
      margin: 0;
      position: absolute;
      text-align: left;
      text-transform: none;
      top: 1.78in;
      width: 4.05in;
      z-index: 2;
    }

    body.template-editorial-ledger .cover-card h1:before {
      color: __ACCENT__;
      content: "STUDENT SERVICES EDITION";
      display: block;
      font-family: __BODY_FONT__;
      font-size: 8px;
      font-weight: 700;
      letter-spacing: 0.24em;
      margin-bottom: 0.14in;
      text-transform: uppercase;
    }

    body.template-editorial-ledger .cover-card h1:after {
      color: __TEXT__;
      content: "A concise working reference for services, goals, accommodations, data collection, and staff communication.";
      display: block;
      font-family: __BODY_FONT__;
      font-size: 9px;
      font-weight: 400;
      letter-spacing: 0;
      line-height: 1.55;
      margin-top: 0.18in;
      width: 3.8in;
    }

    body.template-editorial-ledger .cover-year {
      background: transparent;
      color: __ACCENT__;
      font-family: __BODY_FONT__;
      font-size: 7.5px;
      font-weight: 500;
      letter-spacing: 0.05em;
      margin: 0;
      padding: 0;
      position: absolute;
      right: 0;
      text-align: right;
      top: 0;
      white-space: nowrap;
    }

    body.template-editorial-ledger .cover-student {
      border-bottom: 1px solid __PRIMARY__;
      border-top: 1px solid __PRIMARY__;
      color: __PRIMARY__;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 27px;
      font-weight: 400;
      left: 0.15in;
      letter-spacing: 0;
      margin: 0;
      padding: 0.38in 0 0.17in;
      position: absolute;
      text-align: left;
      text-transform: none;
      top: 4.72in;
      width: 4.25in;
    }

    body.template-editorial-ledger .cover-student:before {
      color: __ACCENT__;
      content: "PREPARED FOR";
      font-family: __BODY_FONT__;
      font-size: 7px;
      font-weight: 700;
      left: 0;
      letter-spacing: 0.18em;
      position: absolute;
      top: 0.13in;
    }

    body.template-editorial-ledger .cover-bottom {
      background: transparent;
      bottom: 0.22in;
      color: __TEXT__;
      left: 0.42in;
      margin: 0;
      padding: 0;
      position: absolute;
      right: 0.42in;
      top: 0;
      width: auto;
      z-index: 3;
    }

    body.template-editorial-ledger .cover-details {
      height: 100%;
      margin: 0;
      position: relative;
      text-align: left;
      width: 100%;
    }

    body.template-editorial-ledger .cover-services,
    body.template-editorial-ledger .cover-services.service-count-5,
    body.template-editorial-ledger .cover-services.service-count-6,
    body.template-editorial-ledger .cover-services.service-count-7,
    body.template-editorial-ledger .cover-services.service-count-8 {
      border: 0;
      border-left: 0.035in solid __ORANGE__;
      display: block;
      margin: 0;
      max-width: none;
      padding: 0.03in 0 0 0.18in;
      position: absolute;
      right: 0;
      top: 2.67in;
      width: 2.08in;
    }

    body.template-editorial-ledger .cover-services:before {
      color: __PRIMARY__;
      content: "SERVICE INDEX";
      display: block;
      font-family: __BODY_FONT__;
      font-size: 8px;
      font-weight: 800;
      letter-spacing: 0.18em;
      margin-bottom: 0.12in;
      text-transform: uppercase;
    }

    body.template-editorial-ledger .cover-services .service-chip,
    body.template-editorial-ledger .cover-services.service-count-5 .service-chip,
    body.template-editorial-ledger .cover-services.service-count-6 .service-chip,
    body.template-editorial-ledger .cover-services.service-count-7 .service-chip,
    body.template-editorial-ledger .cover-services.service-count-8 .service-chip {
      border-bottom: 1px solid rgba(0,0,0,0.18);
      color: __TEXT__;
      display: block;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 9.5px;
      font-weight: 400;
      letter-spacing: 0;
      line-height: 1.12;
      margin: 0;
      max-width: none;
      min-height: 0;
      padding: 0.08in 0 0.07in;
      text-align: left;
      text-transform: none;
      width: 100%;
    }

    body.template-editorial-ledger .cover-services .service-chip + .service-chip {
      border-left: 0;
    }

    body.template-editorial-ledger .cover-services .chip-dot {
      display: none;
    }

    body.template-editorial-ledger .cover-services .service-chip > span:last-child {
      color: __TEXT__;
      display: block;
      min-height: 0;
      width: 100%;
    }

    body.template-editorial-ledger .meta-grid {
      border-collapse: collapse;
      border: 1px solid rgba(38,54,74,0.42);
      bottom: 0.22in;
      left: 0;
      margin: 0;
      position: absolute;
      table-layout: fixed;
      width: 100%;
    }

    body.template-editorial-ledger .meta-box {
      background: __CARD__;
      border: 0;
      border-left: 1px solid rgba(38,54,74,0.34);
      border-radius: 0;
      color: __TEXT__;
      height: 0.76in;
      min-height: 0;
      padding: 0.16in 0.14in 0.1in;
      vertical-align: top;
      width: 25%;
    }

    body.template-editorial-ledger .meta-grid td:first-child,
    body.template-editorial-ledger .meta-grid tr:nth-child(2) td:nth-child(2) {
      border-left: 0;
    }

    body.template-editorial-ledger .meta-label {
      color: __ACCENT__;
      font-size: 6.4px;
      letter-spacing: 0.16em;
    }

    body.template-editorial-ledger .meta-value {
      color: __PRIMARY__;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 9.2px;
      font-weight: 700;
      line-height: 1.2;
      margin-top: 0.08in;
    }

    body.template-editorial-ledger .meta-spacer {
      display: none;
    }

    body.template-editorial-ledger .mountains {
      display: none;
    }

    /* Interior pages */

    body.template-editorial-ledger .page:not(.cover) {
      background: __CARD__;
      border-top: 0.11in solid __PRIMARY__;
      box-shadow: none;
      padding: 0.12in 0.08in 0.08in;
    }

    body.template-editorial-ledger .page-header {
      align-items: flex-start;
      background: transparent;
      border: 0;
      border-bottom: 1px solid __PRIMARY__;
      border-radius: 0;
      margin-bottom: 16px;
      padding: 5px 0 10px;
    }

    body.template-editorial-ledger .page-header .badge {
      background: transparent;
      border: 1px solid __ACCENT__;
      border-radius: 0;
      color: __ACCENT__;
    }

    body.template-editorial-ledger .page-header h2 {
      color: __PRIMARY__;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 23px;
      font-weight: 700;
      text-transform: none;
    }

    body.template-editorial-ledger .eyebrow {
      color: __ACCENT__;
      font-size: 7px;
      letter-spacing: 0.18em;
    }

    body.template-editorial-ledger .section,
    body.template-editorial-ledger .soft-card,
    body.template-editorial-ledger .goal-card {
      background: __CARD__;
      border: 0;
      border-bottom: 1px solid rgba(0,0,0,0.18);
      border-radius: 0;
      box-shadow: none;
      padding: 12px 0;
    }

    body.template-editorial-ledger .domain-title {
      border-top: 3px solid __ORANGE__;
      margin-top: 18px;
      padding-top: 8px;
    }

    body.template-editorial-ledger .domain-title .mini-dot,
    body.template-editorial-ledger .badge,
    body.template-editorial-ledger .badge.green,
    body.template-editorial-ledger .badge.purple,
    body.template-editorial-ledger .badge.orange {
      background: transparent;
      border: 1px solid __ACCENT__;
      border-radius: 0;
      color: __ACCENT__;
    }

    body.template-editorial-ledger th {
      background: __PRIMARY__;
      color: #ffffff;
      font-family: __BODY_FONT__;
      font-size: 7px;
      letter-spacing: 0.10em;
    }

    body.template-editorial-ledger th,
    body.template-editorial-ledger td {
      border-color: rgba(0,0,0,0.24);
    }

    body.template-editorial-ledger .staff-checklist {
      background: __SOFT__;
      border: 0;
      border-left: 0.06in solid __ORANGE__;
      border-radius: 0;
    }

    body.template-editorial-ledger .staff-checklist h3 {
      color: __PRIMARY__;
      font-family: Georgia, "Times New Roman", serif;
      text-transform: none;
    }

    body.template-editorial-ledger .notes-lines {
      border-radius: 0;
    }

    body.template-editorial-ledger .cover-district-mark {
      color: __PRIMARY__;
      display: block;
      font-family: __BODY_FONT__;
      font-size: 7.5px;
      font-weight: 700;
      left: 0.42in;
      letter-spacing: 0.22em;
      position: absolute;
      text-transform: uppercase;
      top: 0.42in;
      z-index: 4;
    }

    body.template-editorial-ledger .cover-district-mark:after {
      content: " - SPECIAL EDUCATION";
    }

    body.template-editorial-ledger .cover-version-footer {
      bottom: 0.08in;
      color: __ACCENT__;
      display: block;
      font-size: 7px;
      font-weight: 700;
      left: 0.42in;
      letter-spacing: 0.16em;
      position: absolute;
      text-transform: uppercase;
      z-index: 4;
    }

    body.template-editorial-ledger .cover-kicker,
    body.template-editorial-ledger .cover-school {
      display: none;
    }

    body.template-editorial-ledger .cover-year:before {
      content: "Academic Year ";
    }

    body.template-editorial-ledger .page-header .badge,
    body.template-editorial-ledger .page-header .badge.green,
    body.template-editorial-ledger .page-header .badge.purple,
    body.template-editorial-ledger .page-header .badge.orange,
    body.template-editorial-ledger .domain-title .mini-dot {
      background: __PRIMARY__;
      border-color: __PRIMARY__;
      color: #ffffff;
    }

    /* Modular Blocks */
    body.template-modular-blocks {
      background: __SOFT__;
      color: __TEXT__;
    }

    body.template-modular-blocks h1,
    body.template-modular-blocks h2,
    body.template-modular-blocks h3,
    body.template-modular-blocks h4 {
      color: __PRIMARY__;
      font-family: __HEADING_FONT__;
    }

    body.template-modular-blocks .cover {
      background: __SOFT__;
      color: __TEXT__;
      overflow: hidden;
    }

    body.template-modular-blocks .cover-card {
      background: __SOFT__;
      display: block;
      padding: 0;
      position: relative;
    }

    body.template-modular-blocks .cover-card:before {
      background: __PRIMARY__;
      content: "";
      height: 1.08in;
      left: 0.42in;
      position: absolute;
      right: 0.42in;
      top: 0.42in;
      z-index: 0;
    }

    body.template-modular-blocks .cover-card:after {
      background: __ORANGE__;
      content: "";
      height: 0.16in;
      left: 0.42in;
      position: absolute;
      top: 4.63in;
      width: 1.78in;
      z-index: 4;
    }

    body.template-modular-blocks .cover-content {
      background: __CARD__;
      border: 0.025in solid __PRIMARY__;
      box-sizing: border-box;
      height: 4.37in;
      left: 0.42in;
      padding: 1.32in 0.34in 0.3in;
      position: absolute;
      text-align: left;
      top: 0.42in;
      width: 4.42in;
      z-index: 2;
    }

    body.template-modular-blocks .cover-content:before {
      background: __ACCENT__;
      content: "";
      height: 0.28in;
      position: absolute;
      right: -0.025in;
      top: 1.08in;
      width: 1.42in;
    }

    body.template-modular-blocks .cover-icon,
    body.template-modular-blocks .brand-logo {
      background: transparent;
      border: 0;
      border-radius: 0;
      box-shadow: none;
      height: 0.58in;
      left: 0.3in;
      margin: 0;
      object-fit: contain;
      padding: 0;
      position: absolute;
      top: 0.25in;
      width: 0.78in;
    }

    body.template-modular-blocks .cover-icon {
      align-items: center;
      background: __ACCENT__;
      color: #ffffff;
      display: flex;
      justify-content: center;
      width: 0.58in;
    }

    body.template-modular-blocks .cover-kicker {
      color: __ORANGE__;
      font-size: 8.5px;
      font-weight: 800;
      letter-spacing: 0.22em;
      margin: 0 0 0.15in;
      text-align: left;
    }

    body.template-modular-blocks .cover-school {
      color: __ACCENT__;
      font-size: 7.5px;
      font-weight: 800;
      letter-spacing: 0.16em;
      margin: 0 0 0.16in;
      text-align: left;
    }

    body.template-modular-blocks .cover-card h1 {
      color: __PRIMARY__;
      font-size: 45px;
      font-weight: 800;
      letter-spacing: 0;
      line-height: 0.88;
      margin: 0;
      text-align: left;
    }

    body.template-modular-blocks .cover-year {
      background: __PRIMARY__;
      color: #ffffff;
      display: inline-block;
      font-family: __HEADING_FONT__;
      font-size: 13px;
      font-weight: 800;
      margin: 0.25in 0 0.2in;
      min-width: 1.78in;
      padding: 0.1in 0.18in;
      text-align: left;
    }

    body.template-modular-blocks .cover-student {
      color: __PRIMARY__;
      font-size: 17px;
      font-weight: 800;
      letter-spacing: 0;
      margin: 0;
      text-align: left;
      text-transform: uppercase;
    }

    body.template-modular-blocks .cover-district-mark {
      display: none;
    }

    body.template-modular-blocks .cover-bottom,
    body.template-modular-blocks .cover-details {
      background: transparent;
      border: 0;
      height: auto;
      margin: 0;
      padding: 0;
      position: static;
      width: auto;
    }

    body.template-modular-blocks .cover-services,
    body.template-modular-blocks .cover-services.service-count-5,
    body.template-modular-blocks .cover-services.service-count-6,
    body.template-modular-blocks .cover-services.service-count-7,
    body.template-modular-blocks .cover-services.service-count-8 {
      align-content: flex-start;
      background: __PRIMARY__;
      box-sizing: border-box;
      display: flex;
      flex-wrap: wrap;
      gap: 0;
      left: 4.86in;
      margin: 0;
      min-height: 3.25in;
      padding: 0.22in 0.18in;
      position: absolute;
      top: 1.17in;
      width: 2.32in;
      z-index: 3;
    }

    body.template-modular-blocks .cover-services:before {
      color: #ffffff;
      content: "SERVICE AREAS";
      display: block;
      flex: 0 0 100%;
      font-family: __HEADING_FONT__;
      font-size: 8px;
      font-weight: 800;
      letter-spacing: 0.18em;
      margin-bottom: 0.12in;
      text-align: left;
    }

    body.template-modular-blocks .cover-services .service-chip,
    body.template-modular-blocks .cover-services.service-count-5 .service-chip,
    body.template-modular-blocks .cover-services.service-count-6 .service-chip,
    body.template-modular-blocks .cover-services.service-count-7 .service-chip,
    body.template-modular-blocks .cover-services.service-count-8 .service-chip {
      align-items: center;
      background: rgba(255,255,255,0.08);
      border: 0;
      border-bottom: 1px solid rgba(255,255,255,0.24);
      box-sizing: border-box;
      color: #ffffff;
      display: flex;
      flex: 0 0 100%;
      flex-direction: row;
      font-size: 7.5px;
      gap: 0.08in;
      line-height: 1.08;
      margin: 0;
      max-width: none;
      min-height: 0.38in;
      overflow: hidden;
      padding: 0.05in;
      text-align: left;
      width: 100%;
    }

    body.template-modular-blocks .cover-services .service-chip:nth-child(2n+1) {
      background: rgba(255,255,255,0.14);
    }

    body.template-modular-blocks .cover-services.service-count-7 .service-chip,
    body.template-modular-blocks .cover-services.service-count-8 .service-chip {
      font-size: 6.7px;
      min-height: 0.31in;
      padding-bottom: 0.035in;
      padding-top: 0.035in;
    }

    body.template-modular-blocks .cover-services .chip-dot {
      background: __ACCENT__;
      border: 0;
      border-radius: 0;
      color: #ffffff;
      flex: 0 0 0.28in;
      height: 0.28in;
      padding: 0.045in;
      width: 0.28in;
    }

    body.template-modular-blocks .cover-services.service-count-7 .chip-dot,
    body.template-modular-blocks .cover-services.service-count-8 .chip-dot {
      flex-basis: 0.24in;
      height: 0.24in;
      width: 0.24in;
    }

    body.template-modular-blocks .cover-services .service-chip > span:last-child {
      display: block;
      min-height: 0;
      min-width: 0;
      overflow-wrap: anywhere;
      width: auto;
    }

    body.template-modular-blocks .meta-grid {
      border-collapse: separate;
      border-spacing: 0.07in;
      bottom: 0.58in;
      left: 0.04in;
      margin: 0;
      position: absolute;
      table-layout: fixed;
      width: 7.24in;
      z-index: 3;
    }

    body.template-modular-blocks .meta-box {
      background: __CARD__;
      border: 0.018in solid __PRIMARY__;
      border-radius: 0;
      color: __TEXT__;
      height: 0.73in;
      min-height: 0;
      padding: 0.1in 0.12in;
      vertical-align: top;
    }

    body.template-modular-blocks .meta-box:nth-child(2n) {
      border-top: 0.1in solid __ACCENT__;
    }

    body.template-modular-blocks .meta-label {
      color: __ORANGE__;
      font-size: 6.5px;
      font-weight: 800;
      letter-spacing: 0.13em;
    }

    body.template-modular-blocks .meta-value {
      color: __TEXT__;
      font-size: 9px;
      font-weight: 700;
      line-height: 1.15;
      margin-top: 0.05in;
    }

    body.template-modular-blocks .meta-spacer {
      visibility: hidden;
    }

    body.template-modular-blocks .mountains {
      background: __PRIMARY__;
      bottom: 0;
      display: block;
      height: 1.12in;
      left: auto;
      opacity: 1;
      overflow: visible;
      position: absolute;
      right: 0;
      width: 3.12in;
      z-index: 1;
    }

    body.template-modular-blocks .mountains:before {
      background: __ACCENT__;
      border: 0;
      bottom: 0.1in;
      content: "";
      height: 0.84in;
      left: -0.68in;
      position: absolute;
      transform: skewX(-24deg);
      width: 1.58in;
    }

    body.template-modular-blocks .mountains:after {
      background: __ORANGE__;
      border: 0;
      bottom: 0;
      content: "";
      height: 0.62in;
      left: -1.5in;
      position: absolute;
      transform: skewX(-24deg);
      width: 0.9in;
    }

    body.template-modular-blocks .page:not(.cover) {
      background:
        linear-gradient(90deg, __PRIMARY__ 0, __PRIMARY__ 0.16in, transparent 0.16in),
        __SOFT__;
      padding-left: 0.28in;
    }

    body.template-modular-blocks .page-header {
      background: __PRIMARY__;
      border: 0;
      border-radius: 0;
      margin-bottom: 0.16in;
      min-height: 0.5in;
      padding: 0.1in 0.14in;
      position: relative;
    }

    body.template-modular-blocks .page-header:after {
      background: __ORANGE__;
      bottom: 0;
      content: "";
      height: 0.09in;
      position: absolute;
      right: 0;
      width: 0.72in;
    }

    body.template-modular-blocks .page-header h2 {
      color: #ffffff;
      margin: 0;
    }

    body.template-modular-blocks .page-header .badge,
    body.template-modular-blocks .page-header .badge.green,
    body.template-modular-blocks .page-header .badge.purple,
    body.template-modular-blocks .page-header .badge.orange {
      background: __ACCENT__;
      border-radius: 0;
      color: #ffffff;
    }

    body.template-modular-blocks .eyebrow {
      color: __ORANGE__;
    }

    body.template-modular-blocks .section,
    body.template-modular-blocks .soft-card,
    body.template-modular-blocks .goal-card {
      background: __CARD__;
      border: 1px solid rgba(0,0,0,0.16);
      border-left: 0.1in solid __ACCENT__;
      border-radius: 0;
      box-shadow: none;
    }

    body.template-modular-blocks .section:nth-of-type(even),
    body.template-modular-blocks .goal-card:nth-of-type(even) {
      border-left-color: __ORANGE__;
    }

    body.template-modular-blocks .goal-card.green,
    body.template-modular-blocks .goal-card.purple {
      background: __CARD__;
      border-color: rgba(0,0,0,0.16);
      border-left-color: __ACCENT__;
    }

    body.template-modular-blocks .domain-title {
      background: __PRIMARY__;
      color: #ffffff;
      margin: 0.12in 0 0.06in;
      min-height: 0.34in;
      padding: 0.06in 0.09in;
    }

    body.template-modular-blocks .domain-title h3,
    body.template-modular-blocks .domain-title h4 {
      color: #ffffff;
    }

    body.template-modular-blocks .domain-title .mini-dot,
    body.template-modular-blocks .domain-title .mini-dot.blue,
    body.template-modular-blocks .domain-title .mini-dot.green,
    body.template-modular-blocks .domain-title .mini-dot.purple,
    body.template-modular-blocks .domain-title .mini-dot.orange {
      background: __ACCENT__;
      border-radius: 0;
      color: #ffffff;
    }

    body.template-modular-blocks th {
      background: __PRIMARY__;
      color: #ffffff;
      font-size: 8px;
      letter-spacing: 0.06em;
    }

    body.template-modular-blocks th:nth-child(2n) {
      background: __ACCENT__;
    }

    body.template-modular-blocks th,
    body.template-modular-blocks td {
      border-color: rgba(0,0,0,0.2);
    }

    body.template-modular-blocks .notes-lines {
      background:
        repeating-linear-gradient(
          to bottom,
          __CARD__ 0,
          __CARD__ 23px,
          rgba(0,0,0,0.18) 24px
        );
      border: 1px solid rgba(0,0,0,0.2);
      border-left: 0.1in solid __ORANGE__;
      border-radius: 0;
    }

    body.template-modular-blocks .staff-checklist {
      background: __CARD__;
      border: 1px solid rgba(0,0,0,0.2);
      border-left: 0.1in solid __ORANGE__;
      border-radius: 0;
    }

    body.template-modular-blocks .staff-checklist h3 {
      color: __PRIMARY__;
    }

    body.template-mid-century-classroom {
      background: __SOFT__;
      color: __TEXT__;
    }
    body.template-mid-century-classroom h1,
    body.template-mid-century-classroom h2,
    body.template-mid-century-classroom h3,
    body.template-mid-century-classroom h4 {
      color: __PRIMARY__;
    }
    body.template-mid-century-classroom .cover {
      background:
        radial-gradient(circle at 87% 13%, __ORANGE__ 0, __ORANGE__ 0.44in, transparent 0.46in),
        linear-gradient(135deg, __SOFT__ 0%, __SOFT__ 66%, rgba(255,255,255,0.36) 66%, rgba(255,255,255,0.36) 100%);
      color: __TEXT__;
    }
    body.template-mid-century-classroom .cover-card {
      padding: 0.48in;
    }
    body.template-mid-century-classroom .cover-card:before {
      background: __PRIMARY__;
      content: "";
      height: 2.58in;
      left: -0.42in;
      position: absolute;
      top: 1.08in;
      transform: rotate(-7deg);
      width: 4.52in;
      z-index: 0;
    }
    body.template-mid-century-classroom .cover-card:after {
      background: __ACCENT__;
      bottom: 0.22in;
      content: "";
      height: 1.4in;
      position: absolute;
      right: -0.44in;
      transform: rotate(6deg);
      width: 3.7in;
      z-index: 0;
    }
    body.template-mid-century-classroom .cover-content {
      background: __CARD__;
      border: 0.025in solid __TEXT__;
      box-shadow: 0.12in 0.12in 0 __ORANGE__;
      padding: 0.36in;
      position: absolute;
      right: 0.5in;
      text-align: left;
      top: 0.74in;
      width: 4.76in;
    }
    body.template-mid-century-classroom .cover-icon {
      background: __ORANGE__;
      border: 0.018in solid __TEXT__;
      border-radius: 50%;
      color: __TEXT__;
      display: flex;
      height: 0.64in;
      line-height: 0;
      margin: 0 0 0.18in;
      width: 0.64in;
    }
    body.template-mid-century-classroom .brand-logo {
      height: 0.64in;
      margin: 0 0 0.18in;
      width: 1.0in;
    }
    body.template-mid-century-classroom .cover-kicker {
      color: __ACCENT__;
      font-size: 9px;
      font-weight: 800;
      letter-spacing: 0.2em;
      margin: 0 0 0.04in;
      text-align: left;
    }
    body.template-mid-century-classroom .cover-school {
      color: __TEXT__;
      font-size: 8px;
      font-weight: 700;
      letter-spacing: 0.13em;
      margin: 0 0 0.16in;
      text-align: left;
    }
    body.template-mid-century-classroom .cover-card h1 {
      color: __PRIMARY__;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 48px;
      letter-spacing: -0.035em;
      line-height: 0.88;
      text-align: left;
      text-transform: none;
    }
    body.template-mid-century-classroom .cover-year {
      background: __ACCENT__;
      color: #ffffff;
      display: inline-block;
      font-size: 15px;
      margin: 0.22in 0 0.18in;
      padding: 0.08in 0.18in;
    }
    body.template-mid-century-classroom .cover-student {
      color: __TEXT__;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 19px;
      font-weight: 700;
      letter-spacing: 0;
      margin: 0;
      text-align: left;
      text-transform: none;
    }
    body.template-mid-century-classroom .cover-bottom {
      background: transparent;
      margin: 0;
      padding: 0;
      position: static;
    }
    body.template-mid-century-classroom .cover-services,
    body.template-mid-century-classroom .cover-services.service-count-5,
    body.template-mid-century-classroom .cover-services.service-count-6,
    body.template-mid-century-classroom .cover-services.service-count-7,
    body.template-mid-century-classroom .cover-services.service-count-8 {
      background: __PRIMARY__;
      bottom: 1.48in;
      display: flex;
      flex-wrap: wrap;
      gap: 0.08in;
      justify-content: center;
      left: 0.5in;
      margin: 0;
      padding: 0.16in;
      position: absolute;
      width: 4.15in;
      z-index: 2;
    }
    body.template-mid-century-classroom .cover-services.service-count-1 {
      width: 1.05in;
    }
    body.template-mid-century-classroom .cover-services.service-count-2 {
      width: 2.05in;
    }
    body.template-mid-century-classroom .cover-services.service-count-3 {
      width: 3.05in;
    }
    body.template-mid-century-classroom .service-chip,
    body.template-mid-century-classroom .cover-services.service-count-5 .service-chip,
    body.template-mid-century-classroom .cover-services.service-count-6 .service-chip,
    body.template-mid-century-classroom .cover-services.service-count-7 .service-chip,
    body.template-mid-century-classroom .cover-services.service-count-8 .service-chip {
      color: #ffffff;
      display: inline-flex;
      flex: 0 0 0.72in;
      font-size: 6.7px;
      gap: 4px;
      line-height: 1.05;
      padding: 0;
      width: 0.72in;
    }
    body.template-mid-century-classroom .chip-dot {
      background: __ORANGE__;
      border: 0.015in solid #ffffff;
      border-radius: 50%;
      color: __TEXT__;
      height: 0.34in;
      line-height: 0;
      width: 0.34in;
    }
    body.template-mid-century-classroom .cover-service-icon {
      height: 58%;
      width: 58%;
    }
    body.template-mid-century-classroom .meta-grid {
      border-spacing: 0.06in;
      bottom: 0.44in;
      left: 0.44in;
      margin: 0;
      position: absolute;
      table-layout: fixed;
      width: 5.86in;
      z-index: 2;
    }
    body.template-mid-century-classroom .meta-spacer {
      display: none;
    }
    body.template-mid-century-classroom .meta-box {
      background: __CARD__;
      border: 0.018in solid __TEXT__;
      border-radius: 0;
      min-height: 0.72in;
      padding: 0.11in;
      width: 1.28in;
    }
    body.template-mid-century-classroom .meta-box:nth-child(2n) {
      background: __ORANGE__;
    }
    body.template-mid-century-classroom .meta-label {
      color: __ACCENT__;
      font-size: 7px;
      letter-spacing: 0.1em;
    }
    body.template-mid-century-classroom .meta-box:nth-child(2n) .meta-label {
      color: __PRIMARY__;
    }
    body.template-mid-century-classroom .meta-value {
      color: __TEXT__;
      font-size: 10px;
      font-weight: 700;
    }
    body.template-mid-century-classroom .cover-version-footer {
      bottom: 0.18in;
      color: __ACCENT__;
      display: block;
      font-size: 7px;
      font-weight: 800;
      left: 0.5in;
      letter-spacing: 0.14em;
      position: absolute;
      text-transform: uppercase;
      z-index: 3;
    }
    body.template-mid-century-classroom .mountains {
      display: block;
      height: 1.34in;
      left: 0;
      position: absolute;
      top: 0;
      width: 100%;
      z-index: 1;
    }
    body.template-mid-century-classroom .mountains:before {
      background: __ACCENT__;
      content: "";
      height: 0.22in;
      left: 0.48in;
      position: absolute;
      top: 0.34in;
      transform: rotate(-3deg);
      width: 2.16in;
    }
    body.template-mid-century-classroom .mountains:after {
      background: __ORANGE__;
      content: "";
      height: 0.22in;
      position: absolute;
      right: 0.72in;
      top: 0.58in;
      transform: rotate(4deg);
      width: 1.56in;
    }
    body.template-mid-century-classroom .page:not(.cover) {
      background:
        linear-gradient(90deg, __PRIMARY__ 0 0.12in, transparent 0.12in),
        linear-gradient(135deg, transparent 0 78%, rgba(227,178,60,0.12) 78% 100%),
        __CARD__;
      border-top: 0.06in solid __PRIMARY__;
      padding-left: 0.22in;
    }
    body.template-mid-century-classroom .page-header {
      background: __SOFT__;
      border: 0.02in solid __TEXT__;
      border-radius: 0;
      box-shadow: 0.05in 0.05in 0 __ORANGE__;
      margin-bottom: 0.16in;
      padding: 0.09in 0.12in;
    }
    body.template-mid-century-classroom .page-header .badge,
    body.template-mid-century-classroom .badge {
      background: __ORANGE__;
      border: 0.015in solid __TEXT__;
      border-radius: 50%;
      color: __TEXT__;
    }
    body.template-mid-century-classroom .page-header h2 {
      color: __PRIMARY__;
      font-family: Georgia, "Times New Roman", serif;
      letter-spacing: -0.02em;
      text-transform: none;
    }
    body.template-mid-century-classroom .eyebrow {
      color: __ACCENT__;
    }
    body.template-mid-century-classroom .section,
    body.template-mid-century-classroom .soft-card,
    body.template-mid-century-classroom .goal-card {
      background: __CARD__;
      border: 0.018in solid __TEXT__;
      border-radius: 0;
      box-shadow: 0.04in 0.04in 0 rgba(182,88,63,0.22);
    }
    body.template-mid-century-classroom .section h3,
    body.template-mid-century-classroom .goal-card h4 {
      color: __PRIMARY__;
      font-family: Georgia, "Times New Roman", serif;
      text-transform: none;
    }
    body.template-mid-century-classroom .goal-card.green,
    body.template-mid-century-classroom .goal-card.purple,
    body.template-mid-century-classroom .goal-card.orange {
      border-color: __TEXT__;
    }
    body.template-mid-century-classroom .domain-title {
      border-bottom: 0.025in solid __ACCENT__;
      padding-bottom: 0.06in;
    }
    body.template-mid-century-classroom .domain-title .mini-dot,
    body.template-mid-century-classroom .service-area-card .mini-dot {
      background: __ORANGE__;
      border: 0.012in solid __TEXT__;
      color: __TEXT__;
    }
    body.template-mid-century-classroom .service-area-card {
      background: __SOFT__;
      border: 0.015in solid __TEXT__;
      border-radius: 0;
    }
    body.template-mid-century-classroom th {
      background: __PRIMARY__;
      color: #ffffff;
      font-size: 8px;
      letter-spacing: 0.06em;
    }
    body.template-mid-century-classroom th,
    body.template-mid-century-classroom td {
      border-color: #d6c8ad;
    }
    body.template-mid-century-classroom .staff-checklist {
      background: #fff7e3;
      border-color: __ORANGE__;
      border-radius: 0;
    }
    body.template-mid-century-classroom .staff-checklist h3 {
      color: __ACCENT__;
    }

    body.template-typographic-poster {
      background: __SOFT__;
      color: __TEXT__;
    }
    body.template-typographic-poster .cover {
      background: __SOFT__;
      color: __TEXT__;
    }
    body.template-typographic-poster .cover-card {
      display: block;
      padding: 0.46in;
    }
    body.template-typographic-poster .cover-card:before {
      content: "";
      display: none;
    }
    body.template-typographic-poster .typographic-watermark {
      color: rgba(0,0,0,0.045);
      font-family: __HEADING_FONT__;
      font-size: 4.7in;
      font-weight: 900;
      left: 0.12in;
      letter-spacing: -0.18in;
      line-height: 0.82;
      max-width: 6.3in;
      opacity: 1;
      position: absolute;
      top: 0.42in;
      z-index: 0;
    }
    body.template-typographic-poster .typographic-watermark.logo {
      height: 4.2in;
      left: 1.25in;
      object-fit: contain;
      opacity: 0.055;
      top: 0.9in;
      width: 5.45in;
    }
    body.template-typographic-poster .cover-card:after {
      background: __ORANGE__;
      content: "";
      height: 0.2in;
      left: 0.46in;
      position: absolute;
      right: 0.46in;
      top: 4.7in;
      z-index: 1;
    }
    body.template-typographic-poster .cover-content {
      left: 0.46in;
      position: absolute;
      text-align: left;
      top: 0.48in;
      width: 6.95in;
      z-index: 2;
    }
    body.template-typographic-poster .cover-icon,
    body.template-typographic-poster .brand-logo {
      display: none;
    }
    body.template-typographic-poster .cover-kicker {
      color: __ACCENT__;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.26em;
      margin: 0 0 0.12in;
      text-align: left;
    }
    body.template-typographic-poster .cover-school {
      color: __TEXT__;
      font-size: 8px;
      font-weight: 700;
      letter-spacing: 0.16em;
      margin: 0 0 0.2in;
      text-align: left;
    }
    body.template-typographic-poster .cover-card h1 {
      color: __PRIMARY__;
      font-family: __HEADING_FONT__;
      font-size: 65px;
      font-weight: 900;
      letter-spacing: -0.06em;
      line-height: 0.78;
      text-align: left;
    }
    body.template-typographic-poster .cover-year {
      background: transparent;
      border-bottom: 0.03in solid __PRIMARY__;
      color: __ORANGE__;
      font-size: 20px;
      margin: 0.28in 0 0.16in;
      padding: 0 0 0.07in;
      text-align: left;
    }
    body.template-typographic-poster .cover-student {
      color: __TEXT__;
      font-family: __HEADING_FONT__;
      font-size: 22px;
      font-weight: 900;
      letter-spacing: 0.01em;
      margin: 0;
      text-align: left;
      text-transform: uppercase;
    }
    body.template-typographic-poster .cover-bottom {
      background: transparent;
      margin: 0;
      padding: 0;
      position: static;
    }
    body.template-typographic-poster .cover-services,
    body.template-typographic-poster .cover-services.service-count-5,
    body.template-typographic-poster .cover-services.service-count-6,
    body.template-typographic-poster .cover-services.service-count-7,
    body.template-typographic-poster .cover-services.service-count-8 {
      bottom: 1.8in;
      display: block;
      left: 0.46in;
      margin: 0;
      max-width: none;
      padding-left: 0.18in;
      position: absolute;
      width: 2.35in;
      z-index: 2;
    }
    body.template-typographic-poster .cover-services:before {
      color: __ACCENT__;
      content: "SERVICE AREAS";
      display: block;
      font-family: __HEADING_FONT__;
      font-size: 8px;
      font-weight: 900;
      letter-spacing: 0.19em;
      margin-bottom: 0.1in;
    }
    body.template-typographic-poster .service-chip,
    body.template-typographic-poster .cover-services.service-count-5 .service-chip,
    body.template-typographic-poster .cover-services.service-count-6 .service-chip,
    body.template-typographic-poster .cover-services.service-count-7 .service-chip,
    body.template-typographic-poster .cover-services.service-count-8 .service-chip {
      border-bottom: 1px solid rgba(0,0,0,0.22);
      color: __TEXT__;
      display: block;
      font-size: 8px;
      font-weight: 800;
      line-height: 1.2;
      max-width: none;
      padding: 0.07in 0;
      text-align: left;
      width: 100%;
    }
    body.template-typographic-poster .cover-services .chip-dot {
      display: none;
    }
    body.template-typographic-poster .meta-grid {
      border-collapse: collapse;
      bottom: 0.46in;
      left: 2.98in;
      margin: 0;
      position: absolute;
      table-layout: fixed;
      width: 4.48in;
      z-index: 2;
    }
    body.template-typographic-poster .meta-box {
      background: __CARD__;
      border: 0.018in solid __PRIMARY__;
      border-radius: 0;
      min-height: 0.74in;
      padding: 0.1in;
      width: 25%;
    }
    body.template-typographic-poster .meta-box:first-child {
      background: __PRIMARY__;
    }
    body.template-typographic-poster .meta-box:first-child .meta-label,
    body.template-typographic-poster .meta-box:first-child .meta-value {
      color: #ffffff;
    }
    body.template-typographic-poster .meta-label {
      color: __ACCENT__;
      font-size: 7px;
      letter-spacing: 0.12em;
    }
    body.template-typographic-poster .meta-value {
      color: __TEXT__;
      font-size: 10px;
      font-weight: 900;
    }
    body.template-typographic-poster .cover-version-footer {
      bottom: 0.24in;
      color: __SOFT__;
      display: block;
      font-size: 7px;
      font-weight: 800;
      left: 0.46in;
      letter-spacing: 0.14em;
      position: absolute;
      text-transform: uppercase;
      z-index: 3;
    }
    body.template-typographic-poster .mountains {
      background: __PRIMARY__;
      bottom: 0;
      display: block;
      height: 1.1in;
      left: 0;
      opacity: 1;
      overflow: visible;
      position: absolute;
      width: 2.46in;
      z-index: 0;
    }
    body.template-typographic-poster .mountains:before {
      background: __ACCENT__;
      border: 0;
      content: "";
      height: 0.68in;
      left: 1.72in;
      position: absolute;
      top: -0.34in;
      transform: skewX(-28deg);
      width: 1.15in;
    }
    body.template-typographic-poster .mountains:after {
      background: __ORANGE__;
      border: 0;
      content: "";
      height: 0.42in;
      left: 2.62in;
      position: absolute;
      top: -0.22in;
      transform: skewX(-28deg);
      width: 0.74in;
    }
    body.template-typographic-poster .page:not(.cover) {
      background:
        linear-gradient(90deg, __PRIMARY__ 0 0.13in, transparent 0.13in),
        linear-gradient(180deg, transparent 0 92%, rgba(213,99,60,0.12) 92% 100%),
        __SOFT__;
      border-top: 0.06in solid __PRIMARY__;
      padding-left: 0.24in;
    }
    body.template-typographic-poster .page-header {
      background: transparent;
      border-bottom: 0.04in solid __ORANGE__;
      gap: 0.1in;
      margin-bottom: 0.16in;
      padding-bottom: 0.08in;
    }
    body.template-typographic-poster .page-header .badge,
    body.template-typographic-poster .badge {
      background: __PRIMARY__;
      border-radius: 0;
      color: #ffffff;
    }
    body.template-typographic-poster .page-header h2 {
      color: __PRIMARY__;
      font-family: __HEADING_FONT__;
      font-size: 24px;
      font-weight: 900;
      letter-spacing: -0.03em;
    }
    body.template-typographic-poster .eyebrow {
      color: __ACCENT__;
      font-weight: 900;
    }
    body.template-typographic-poster .section,
    body.template-typographic-poster .soft-card,
    body.template-typographic-poster .goal-card {
      background: __CARD__;
      border: 0;
      border-left: 0.06in solid __ORANGE__;
      border-radius: 0;
      box-shadow: 0 0.035in 0 rgba(20,35,60,0.12);
    }
    body.template-typographic-poster .section h3,
    body.template-typographic-poster .goal-card h4 {
      color: __PRIMARY__;
      font-family: __HEADING_FONT__;
      font-weight: 900;
      letter-spacing: -0.01em;
    }
    body.template-typographic-poster .domain-title {
      border-bottom: 0.02in solid rgba(20,35,60,0.24);
      padding-bottom: 0.06in;
    }
    body.template-typographic-poster .domain-title .mini-dot,
    body.template-typographic-poster .service-area-card .mini-dot {
      background: __PRIMARY__;
      border-radius: 0;
      color: #ffffff;
    }
    body.template-typographic-poster .service-area-card {
      background: __CARD__;
      border: 0;
      border-bottom: 1px solid rgba(0,0,0,0.2);
      border-radius: 0;
    }
    body.template-typographic-poster th {
      background: __PRIMARY__;
      color: #ffffff;
      font-size: 8px;
      letter-spacing: 0.08em;
    }
    body.template-typographic-poster th,
    body.template-typographic-poster td {
      border-color: rgba(20,35,60,0.28);
    }
    body.template-typographic-poster .staff-checklist {
      background: __CARD__;
      border: 0.02in solid __ORANGE__;
      border-radius: 0;
    }
    body.template-typographic-poster .staff-checklist h3 {
      color: __PRIMARY__;
    }

    body.template-signal-atlas {
      background: __SOFT__;
      color: __TEXT__;
    }
    body.template-signal-atlas h1,
    body.template-signal-atlas h2,
    body.template-signal-atlas h3,
    body.template-signal-atlas h4 {
      color: __PRIMARY__;
      font-family: __HEADING_FONT__;
    }
    body.template-signal-atlas .cover {
      background: linear-gradient(180deg, __PRIMARY__ 0%, __PRIMARY__ 67%, __SOFT__ 67%, __SOFT__ 100%);
      color: #ffffff;
      overflow: hidden;
    }
    body.template-signal-atlas .cover:before {
      border: 0.025in solid rgba(255,255,255,0.18);
      border-radius: 50%;
      content: "";
      height: 3.9in;
      position: absolute;
      right: -1.15in;
      top: -0.65in;
      width: 3.9in;
      z-index: 0;
    }
    body.template-signal-atlas .cover:after {
      border: 0.018in solid rgba(255,255,255,0.12);
      border-radius: 50%;
      content: "";
      height: 2.95in;
      position: absolute;
      right: -0.68in;
      top: -0.18in;
      width: 2.95in;
      z-index: 0;
    }
    body.template-signal-atlas .cover-card {
      display: block;
      min-height: 9.55in;
      padding: 0.48in;
      position: relative;
    }
    body.template-signal-atlas .cover-card:before {
      background: repeating-linear-gradient(90deg, transparent 0, transparent 0.23in, rgba(255,255,255,0.075) 0.235in, rgba(255,255,255,0.075) 0.245in);
      content: "";
      height: 5.45in;
      left: 0;
      position: absolute;
      right: 0;
      top: 0;
      z-index: 0;
    }
    body.template-signal-atlas .cover-card:after {
      background: radial-gradient(circle, __ORANGE__ 0, __ORANGE__ 0.095in, transparent 0.105in) 0 50% / 0.34in 0.34in repeat-x;
      content: "";
      height: 0.34in;
      left: 0.48in;
      position: absolute;
      top: 5.83in;
      width: 2.08in;
      z-index: 1;
    }
    body.template-signal-atlas .cover-content {
      left: 0.5in;
      position: absolute;
      top: 0.55in;
      width: 5.62in;
      z-index: 3;
    }
    body.template-signal-atlas .cover-content:before {
      color: rgba(255,255,255,0.06);
      content: attr(data-student-initials);
      font-family: __HEADING_FONT__;
      font-size: 3.65in;
      font-weight: 900;
      left: -0.12in;
      letter-spacing: -0.18in;
      line-height: 0.8;
      position: absolute;
      top: 0.18in;
      z-index: -1;
    }
    body.template-signal-atlas .cover-icon {
      background: transparent;
      border: 0.018in solid rgba(255,255,255,0.46);
      border-radius: 0;
      box-shadow: none;
      color: __ORANGE__;
      height: 0.62in;
      margin: 0 0 0.2in;
      object-fit: contain;
      width: 0.62in;
    }
    body.template-signal-atlas .brand-logo {
      background: transparent;
      border: 0;
      border-radius: 0;
      box-shadow: none;
      height: 0.62in;
      margin: 0 0 0.2in;
      object-fit: contain;
      width: 0.9in;
    }
    body.template-signal-atlas .cover-kicker {
      color: __ORANGE__;
      font-size: 9px;
      font-weight: 800;
      letter-spacing: 0.28em;
      margin: 0 0 0.04in;
      text-align: left;
    }
    body.template-signal-atlas .cover-school {
      color: rgba(255,255,255,0.7);
      font-size: 8px;
      font-weight: 700;
      letter-spacing: 0.16em;
      margin: 0 0 0.2in;
      text-align: left;
    }
    body.template-signal-atlas .cover-card h1 {
      color: #ffffff;
      font-size: 62px;
      letter-spacing: -0.06em;
      line-height: 0.78;
      text-align: left;
    }
    body.template-signal-atlas .cover-year {
      background: transparent;
      border-left: 0.12in solid __ACCENT__;
      color: #ffffff;
      font-size: 18px;
      margin: 0.32in 0 0.18in;
      padding: 0.02in 0 0.02in 0.16in;
      text-align: left;
    }
    body.template-signal-atlas .cover-student {
      color: __ORANGE__;
      font-size: 20px;
      font-weight: 800;
      letter-spacing: 0.01em;
      margin: 0;
      text-align: left;
    }
    body.template-signal-atlas .cover-bottom {
      background: transparent;
      border: 0;
      margin: 0;
      padding: 0;
      position: static;
    }
    body.template-signal-atlas .cover-services,
    body.template-signal-atlas .cover-services.service-count-5,
    body.template-signal-atlas .cover-services.service-count-6,
    body.template-signal-atlas .cover-services.service-count-7,
    body.template-signal-atlas .cover-services.service-count-8 {
      background: __CARD__;
      border-top: 0.12in solid __ACCENT__;
      bottom: 1.72in;
      display: block;
      left: 0.48in;
      margin: 0;
      max-width: none;
      padding: 0.18in 0.18in 0.14in;
      position: absolute;
      width: 2.18in;
      z-index: 4;
    }
    body.template-signal-atlas .cover-services:before {
      color: __PRIMARY__;
      content: "SERVICE AREAS";
      display: block;
      font-family: __HEADING_FONT__;
      font-size: 8px;
      font-weight: 800;
      letter-spacing: 0.17em;
      margin-bottom: 0.08in;
    }
    body.template-signal-atlas .service-chip,
    body.template-signal-atlas .cover-services.service-count-5 .service-chip,
    body.template-signal-atlas .cover-services.service-count-6 .service-chip,
    body.template-signal-atlas .cover-services.service-count-7 .service-chip,
    body.template-signal-atlas .cover-services.service-count-8 .service-chip {
      border-bottom: 1px solid rgba(0,0,0,0.18);
      color: __TEXT__;
      display: block;
      font-size: 7.6px;
      font-weight: 700;
      line-height: 1.15;
      max-width: none;
      padding: 0.055in 0;
      text-align: left;
      width: 100%;
    }
    body.template-signal-atlas .chip-dot {
      display: none;
    }
    body.template-signal-atlas .meta-grid {
      border-collapse: separate;
      border-spacing: 0.05in;
      bottom: 0.5in;
      left: 3.06in;
      margin: 0;
      position: absolute;
      table-layout: fixed;
      width: 4.0in;
      z-index: 4;
    }
    body.template-signal-atlas .meta-box {
      background: __CARD__;
      border: 0.018in solid __PRIMARY__;
      border-radius: 0;
      min-height: 0.72in;
      overflow: hidden;
      padding: 0.1in 0.11in;
      width: 25%;
    }
    body.template-signal-atlas .meta-box:nth-child(2n) {
      border-top: 0.12in solid __ORANGE__;
    }
    body.template-signal-atlas .meta-label {
      color: __ACCENT__;
      font-size: 7px;
      letter-spacing: 0.11em;
    }
    body.template-signal-atlas .meta-value {
      color: __TEXT__;
      font-size: 10px;
      font-weight: 800;
      overflow-wrap: anywhere;
      word-break: normal;
    }
    body.template-signal-atlas .mountains {
      background:
        radial-gradient(circle at 0.72in 0.72in, __PRIMARY__ 0, __PRIMARY__ 0.7in, transparent 0.71in),
        radial-gradient(circle at 1.72in 0.62in, __ACCENT__ 0, __ACCENT__ 0.5in, transparent 0.51in),
        radial-gradient(circle at 2.5in 0.88in, __ORANGE__ 0, __ORANGE__ 0.31in, transparent 0.32in);
      bottom: 0.12in;
      display: block;
      height: 1.46in;
      left: 0.08in;
      position: absolute;
      width: 3.05in;
      z-index: 1;
    }
    body.template-signal-atlas .mountains:before {
      border: 0.025in solid __ACCENT__;
      border-radius: 50%;
      content: "";
      height: 1.08in;
      left: 1.04in;
      position: absolute;
      top: -0.02in;
      width: 1.08in;
    }
    body.template-signal-atlas .mountains:after {
      border: 0.018in solid __ORANGE__;
      border-radius: 50%;
      content: "";
      height: 0.62in;
      left: 2.12in;
      position: absolute;
      top: 0.26in;
      width: 0.62in;
    }
    body.template-signal-atlas .cover-version-footer {
      bottom: 0.18in;
      color: __PRIMARY__;
      display: block;
      font-size: 7px;
      font-weight: 800;
      letter-spacing: 0.08em;
      left: auto;
      position: absolute;
      right: 0.48in;
      text-transform: uppercase;
      z-index: 5;
    }
    body.template-signal-atlas .page:not(.cover) {
      background:
        linear-gradient(90deg, __PRIMARY__ 0, __PRIMARY__ 0.19in, transparent 0.19in),
        linear-gradient(180deg, rgba(0,0,0,0.02), transparent 1.6in),
        __CARD__;
      padding-left: 0.29in;
    }
    body.template-signal-atlas .page:not(.cover):before {
      content: "";
      display: none;
    }
    body.template-signal-atlas .signal-page-mark {
      color: rgba(0,0,0,0.055);
      font-family: __HEADING_FONT__;
      font-size: 1.42in;
      font-weight: 900;
      line-height: 1;
      pointer-events: none;
      position: absolute;
      right: 0.52in;
      text-align: right;
      top: 0.44in;
      transform: none;
      z-index: 1;
    }
    body.template-signal-atlas .page-header {
      background: transparent;
      border: 0;
      border-bottom: 0.035in solid __PRIMARY__;
      border-radius: 0;
      margin-bottom: 0.16in;
      padding: 0.08in 0.02in 0.1in;
      position: relative;
      z-index: 2;
    }
    body.template-signal-atlas .page-header:after {
      background: __ORANGE__;
      bottom: -0.035in;
      content: "";
      height: 0.035in;
      left: 0;
      position: absolute;
      width: 1.18in;
    }
    body.template-signal-atlas .page-header .badge,
    body.template-signal-atlas .page-header .badge.green,
    body.template-signal-atlas .page-header .badge.purple,
    body.template-signal-atlas .page-header .badge.orange {
      background: __PRIMARY__;
      border-radius: 0;
      color: __ORANGE__;
    }
    body.template-signal-atlas .eyebrow {
      color: __ACCENT__;
    }
    body.template-signal-atlas .section,
    body.template-signal-atlas .soft-card,
    body.template-signal-atlas .goal-card {
      background: __CARD__;
      border: 1px solid rgba(0,0,0,0.16);
      border-radius: 0;
      box-shadow: none;
      position: relative;
    }
    body.template-signal-atlas .section:before,
    body.template-signal-atlas .soft-card:before,
    body.template-signal-atlas .goal-card:before {
      background: __ACCENT__;
      content: "";
      height: 0.12in;
      left: -1px;
      position: absolute;
      top: -1px;
      width: 0.58in;
    }
    body.template-signal-atlas .goal-card.green,
    body.template-signal-atlas .goal-card.purple {
      background: __CARD__;
      border-color: rgba(0,0,0,0.16);
    }
    body.template-signal-atlas .domain-title {
      border-left: 0.1in solid __ORANGE__;
      margin: 0.14in 0 0.08in;
      padding-left: 0.1in;
    }
    body.template-signal-atlas .domain-title .mini-dot,
    body.template-signal-atlas .domain-title .mini-dot.blue,
    body.template-signal-atlas .domain-title .mini-dot.green,
    body.template-signal-atlas .domain-title .mini-dot.purple,
    body.template-signal-atlas .domain-title .mini-dot.orange {
      background: __PRIMARY__;
      border-radius: 0;
      color: __ORANGE__;
    }
    body.template-signal-atlas th {
      background: __PRIMARY__;
      color: #ffffff;
      font-size: 8px;
      letter-spacing: 0.06em;
    }
    body.template-signal-atlas th:nth-child(2n) {
      background: __ACCENT__;
    }
    body.template-signal-atlas th,
    body.template-signal-atlas td {
      border-color: rgba(0,0,0,0.2);
    }
    body.template-signal-atlas .notes-lines {
      background: repeating-linear-gradient(to bottom, transparent 0, transparent 23px, rgba(0,0,0,0.2) 24px);
      border: 1px solid rgba(0,0,0,0.2);
      border-left: 0.1in solid __ORANGE__;
      border-radius: 0;
    }
    body.template-signal-atlas .staff-checklist {
      background: __CARD__;
      border: 1px solid rgba(0,0,0,0.2);
      border-left: 0.1in solid __ORANGE__;
      border-radius: 0;
    }

    body.template-modern-professional {
      background: #eef3f7;
      color: #14233c;
    }
    body.template-modern-professional h1,
    body.template-modern-professional h2,
    body.template-modern-professional h3,
    body.template-modern-professional h4 {
      color: #0d2848;
      font-family: __HEADING_FONT__;
      letter-spacing: 0.01em;
    }
    body.template-modern-professional .cover {
      background: #ffffff !important;
      color: #14233c;
    }
    body.template-modern-professional .cover-card {
      background:
        linear-gradient(132deg, #ffffff 0%, #ffffff 58%, #e9f8f8 58%, #e9f8f8 100%);
    }
    body.template-modern-professional .cover:before {
      border-left: 5.55in solid transparent;
      border-bottom: 3.05in solid #0d2848;
      bottom: 0;
      content: "";
      position: absolute;
      right: 0;
      width: 0;
      z-index: 0;
    }
    body.template-modern-professional .cover:after {
      border-left: 3.8in solid transparent;
      border-bottom: 1.18in solid #0f8b8d;
      bottom: 0;
      content: "";
      position: absolute;
      right: 0;
      z-index: 1;
    }
    body.template-modern-professional .cover-card {
      justify-content: space-between;
      padding: 0.55in 0.58in 0.38in;
    }
    body.template-modern-professional .cover-content {
      text-align: left;
      width: 4.35in;
    }
    body.template-modern-professional .cover-icon {
      background: #0f8b8d;
      border: 0;
      border-radius: 15px;
      box-shadow: 0 8px 18px rgba(15,139,141,0.22);
      color: #ffffff;
      height: 58px;
      margin: 0 0 18px;
      width: 58px;
    }
    body.template-modern-professional .brand-logo {
      height: 58px;
      margin: 0 0 18px;
      width: 92px;
    }
    body.template-modern-professional .cover-card h1 {
      color: #0d2848;
      font-size: 46px;
      letter-spacing: -0.02em;
      line-height: 0.96;
      text-align: left;
    }
    body.template-modern-professional .cover-kicker {
      color: #0f8b8d;
      font-size: 11px;
      letter-spacing: 0.22em;
      text-align: left;
    }
    body.template-modern-professional .cover-school {
      color: #5d7284;
      font-size: 9px;
      letter-spacing: 0.14em;
      text-align: left;
    }
    body.template-modern-professional .cover-year {
      background: #0f8b8d;
      box-shadow: 0 5px 0 rgba(13,40,72,0.12);
      display: inline-block;
      margin: 20px 0 18px;
      min-width: 1.8in;
      text-align: center;
    }
    body.template-modern-professional .cover-student {
      color: #0f8b8d;
      font-size: 18px;
      margin-top: 6px;
      text-align: left;
    }
    body.template-modern-professional .cover-bottom {
      background: #0d2848;
      border-bottom: 0.13in solid #0f8b8d;
      border-radius: 14px 14px 0 0;
      color: #ffffff;
      margin: 0;
      padding: 0.16in 0.24in 0.1in;
      width: 100%;
    }
    body.template-modern-professional .cover-services {
      gap: 10px;
      justify-content: center;
      margin: 0 0 10px;
    }
    body.template-modern-professional .service-chip {
      font-size: 7.5px;
      gap: 5px;
      max-width: 0.72in;
    }
    body.template-modern-professional .cover-bottom .service-chip,
    body.template-modern-professional .cover-bottom .meta-label,
    body.template-modern-professional .cover-bottom .meta-value {
      color: #ffffff;
    }
    body.template-modern-professional .chip-dot {
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.38);
      border-radius: 15px;
      color: #43c0bd;
      font-size: 14px;
      height: 36px;
      width: 36px;
    }
    body.template-modern-professional .meta-grid {
      border-collapse: separate;
      border-spacing: 8px;
      margin-left: auto;
      margin-right: auto;
      margin-top: 0;
      width: 5.45in;
    }
    body.template-modern-professional .meta-box {
      background: rgba(255,255,255,0.08);
      border-color: rgba(255,255,255,0.24);
      border-radius: 8px;
      min-height: 0;
      padding: 8px 9px;
    }
    body.template-modern-professional .meta-label {
      font-size: 7.5px;
    }
    body.template-modern-professional .meta-value {
      font-size: 10px;
    }
    body.template-modern-professional .mountains {
      display: none;
    }
    body.template-modern-professional .page:not(.cover) {
      background:
        linear-gradient(90deg, #0d2848 0%, #0d2848 1.6%, transparent 1.6%, transparent 100%),
        linear-gradient(180deg, rgba(67,192,189,0.06), transparent 1.6in),
        #ffffff;
      border-top: 0.04in solid #0d2848;
      padding-left: 0.2in;
    }
    body.template-modern-professional .page-header {
      background: #f4fafb;
      border: 1px solid #c9dce7;
      border-bottom: 4px solid #0f8b8d;
      border-radius: 10px;
      margin-bottom: 14px;
      padding: 10px 12px;
    }
    body.template-modern-professional .page-header .badge {
      background: #0d2848;
      border-radius: 10px;
      color: #43c0bd;
    }
    body.template-modern-professional .page-header.green,
    body.template-modern-professional .page-header.purple,
    body.template-modern-professional .page-header.orange {
      border-bottom-color: #0f8b8d;
    }
    body.template-modern-professional .page-header h2 {
      color: #0d2848;
      margin-bottom: 0;
    }
    body.template-modern-professional .eyebrow {
      color: #0f8b8d;
    }
    body.template-modern-professional .section,
    body.template-modern-professional .soft-card,
    body.template-modern-professional .goal-card {
      background: #ffffff;
      border: 1px solid #c9dce7;
      border-left: 6px solid #0f8b8d;
      border-radius: 10px;
      box-shadow: 0 5px 14px rgba(13,40,72,0.06);
    }
    body.template-modern-professional .goal-card.green,
    body.template-modern-professional .goal-card.purple {
      background: #ffffff;
      border-color: #c9dce7;
      border-left-color: #0f8b8d;
    }
    body.template-modern-professional .domain-title .mini-dot,
    body.template-modern-professional .badge,
    body.template-modern-professional .badge.green,
    body.template-modern-professional .badge.purple,
    body.template-modern-professional .badge.orange {
      background: #0d2848;
      color: #43c0bd;
    }
    body.template-modern-professional th {
      background: #0d2848;
      color: #ffffff;
      font-size: 8px;
      letter-spacing: 0.04em;
    }
    body.template-modern-professional th,
    body.template-modern-professional td {
      border-color: #c9dce7;
    }
    body.template-modern-professional .staff-checklist {
      background: #f4fafb;
      border-color: #0f8b8d;
      border-left: 6px solid #0f8b8d;
    }
    body.template-modern-professional .staff-checklist h3 {
      color: #0d2848;
    }
    body.template-district-branding .cover {
      background: #ffffff;
      border-bottom: 18px solid __ORANGE__;
      border-top: 18px solid __PRIMARY__;
      color: __TEXT__;
    }
    body.template-district-branding .cover:before {
      color: __BORDER__;
      content: "";
      font-family: __HEADING_FONT__;
      font-size: 13px;
      font-weight: 800;
      left: -60px;
      letter-spacing: 0.24em;
      position: absolute;
      text-transform: uppercase;
      top: 180px;
      transform: rotate(-90deg);
      z-index: 0;
    }
    body.template-district-branding .cover:after {
      display: none;
    }
    body.template-district-branding .cover-card {
      justify-content: space-between;
      padding: 42px 48px 34px;
    }
    body.template-district-branding .cover-content {
      text-align: center;
      width: 100%;
    }
    body.template-district-branding .cover-icon {
      background: __PRIMARY__;
      border-color: __PRIMARY__;
      color: #ffffff;
      display: block;
      line-height: 60px;
      margin-left: auto;
      margin-right: auto;
      text-align: center;
    }
    body.template-district-branding .cover-card h1,
    body.template-district-branding .cover-student {
      color: __PRIMARY__;
      text-align: center;
    }
    body.template-district-branding .cover-kicker,
    body.template-district-branding .cover-school {
      color: __ORANGE__;
      text-align: center;
    }
    body.template-district-branding .cover-year {
      background: __ORANGE__;
      display: block;
      margin-left: auto;
      margin-right: auto;
      max-width: 250px;
      text-align: center;
    }
    body.template-district-branding .cover-district-mark {
      color: __BORDER__;
      display: block;
      font-family: __HEADING_FONT__;
      font-size: 13px;
      font-weight: 800;
      left: -64px;
      letter-spacing: 0.22em;
      position: absolute;
      text-transform: uppercase;
      top: 178px;
      transform: rotate(-90deg);
      z-index: 1;
      white-space: nowrap;
    }
    body.template-district-branding .cover-bottom {
      background: linear-gradient(90deg, __PRIMARY__, __BLUE__);
      border-bottom: 18px solid __ORANGE__;
      margin-left: -48px;
      margin-right: -48px;
      padding: 0.18in 0.48in 0.22in;
      width: auto;
    }
    body.template-district-branding .cover-services {
      border-collapse: separate;
      display: table;
      margin: 0 auto 0.18in;
      table-layout: fixed;
      width: 4.4in;
    }
    body.template-district-branding .cover-services.service-count-1 {
      width: 1.1in;
    }
    body.template-district-branding .cover-services.service-count-2 {
      width: 2.35in;
    }
    body.template-district-branding .cover-services.service-count-3 {
      width: 3.45in;
    }
    body.template-district-branding .cover-services.service-count-4 {
      width: 4.55in;
    }
    body.template-district-branding .cover-services:empty {
      display: none;
    }
    body.template-district-branding .cover-services .service-chip {
      display: table-cell;
      padding: 0 8px;
      vertical-align: top;
      width: 25%;
    }
    body.template-district-branding .cover-services.service-count-5,
    body.template-district-branding .cover-services.service-count-6,
    body.template-district-branding .cover-services.service-count-7,
    body.template-district-branding .cover-services.service-count-8 {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px 10px;
    width: 5.5in;
    }

    body.template-district-branding .cover-services.service-count-5 .service-chip,
    body.template-district-branding .cover-services.service-count-6 .service-chip,
    body.template-district-branding .cover-services.service-count-7 .service-chip,
    body.template-district-branding .cover-services.service-count-8 .service-chip {
    display: inline-flex;
    padding: 0;
    width: 0.62in;
    }
    body.template-district-branding .cover-services .service-chip span:last-child {
      display: block;
      line-height: 1.12;
      margin: 0;
    }
    body.template-district-branding .service-chip {
      color: #ffffff;
      font-size: 8px;
      gap: 6px;
      max-width: 0.9in;
    }
    body.template-district-branding .cover-bottom,
    body.template-district-branding .cover-bottom .service-chip,
    body.template-district-branding .cover-bottom .meta-label,
    body.template-district-branding .cover-bottom .meta-value {
      color: #ffffff;
    }
    body.template-district-branding .chip-dot {
      background: __BLUE__;
      border-color: rgba(255,255,255,0.35);
      color: #ffffff;
      display: block;
      height: 42px;
      line-height: 42px;
      margin: 0 auto 6px;
      text-align: center;
      width: 42px;
    }
    body.template-district-branding .meta-grid {
      border-spacing: 12px;
      margin-left: auto;
      margin-right: auto;
      table-layout: fixed;
      width: 5.45in;
    }
    body.template-district-branding .meta-box {
      background: rgba(255,255,255,0.08);
      border-color: rgba(255,255,255,0.28);
    }
    body.template-district-branding .page:not(.cover) {
      border-top: 10px solid __PRIMARY__;
    }
    body.template-district-branding .page-header {
      border-bottom-color: __ORANGE__;
    }
    body.template-alpine-photo .page:not(.cover) {
      background:
        linear-gradient(90deg, #071827 0 0.18in, transparent 0.18in),
        linear-gradient(180deg, rgba(20,159,227,0.06), transparent 1.6in),
        __CARD__;
    }
    body.template-alpine-photo .page-header {
      background: #0d1f35;
      border: 0;
      border-left: 7px solid __ORANGE__;
      border-radius: 0 12px 12px 0;
      color: #ffffff;
      padding: 11px 13px;
    }
    body.template-alpine-photo .page-header h2,
    body.template-alpine-photo .page-header .eyebrow {
      color: #ffffff;
    }
    body.template-alpine-photo .section,
    body.template-alpine-photo .soft-card,
    body.template-alpine-photo .goal-card {
      border-color: #b8d8ee;
      border-left: 5px solid __ORANGE__;
    }
    body.template-alpine-photo .goal-card.green,
    body.template-alpine-photo .goal-card.purple {
      background: __CARD__;
      border-color: #b8d8ee;
      border-left-color: __ORANGE__;
    }
    body.template-alpine-photo th {
      background: #0d1f35;
      color: #ffffff;
    }
    .cover .chip-dot,
    .cover-bottom .chip-dot {
      color: #ffffff !important;
    }
    .page-header .badge,
    .page-header .badge.blue,
    .page-header .badge.green,
    .page-header .badge.purple,
    .page-header .badge.orange {
      color: #ffffff !important;
    }
    .page-header .badge.service-icon-badge {
      background-size: 67% auto !important;
      background-position: center center !important;
      background-repeat: no-repeat !important;
    }
    .custom-packet-page .custom-page-header {
      align-items: center !important;
      display: flex !important;
      min-height: 0.36in !important;
      padding: 0.08in 0.12in !important;
      width: 100% !important;
    }
    .custom-packet-page .custom-page-header h2 {
      display: block !important;
      font-size: 18px;
      line-height: 1.25;
      max-width: none !important;
      width: 100% !important;
    }
    """
    return (
        css.replace("__PRIMARY__", tokens["primary"])
        .replace("__ACCENT__", tokens["accent"])
        .replace("__BLUE__", tokens.get("blue", tokens["primary"]))
        .replace("__TEAL__", tokens.get("teal", tokens["accent"]))
        .replace("__GREEN__", tokens.get("green", "#73b85a"))
        .replace("__GREEN_SOFT__", tokens.get("green_soft", "#f1faed"))
        .replace("__PURPLE__", tokens.get("purple", "#7d66b7"))
        .replace("__PURPLE_SOFT__", tokens.get("purple_soft", "#f5f1fb"))
        .replace("__ORANGE__", tokens.get("orange", "#ef7900"))
        .replace("__ORANGE_SOFT__", tokens.get("orange_soft", "#fff4e7"))
        .replace("__TEXT__", tokens.get("text", "#12213a"))
        .replace("__BORDER__", tokens["border"])
        .replace("__SOFT__", tokens["soft"])
        .replace("__CARD__", tokens.get("card", "#ffffff"))
        .replace("__WATERMARK_SRC__", watermark_src.replace("\\", "/"))
        .replace("__BODY_FONT__", _font_stack(body_font_name))
        .replace("__HEADING_FONT__", _font_stack(heading_font_name))
    )


def _table(headers: list[str], rows: list[list[str]], *, blank_rows: int = 0) -> str:
    body_rows = rows + [["" for _ in headers] for _ in range(blank_rows)]
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{escape(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(
            '<tr class="data-row">'
            + "".join(f"<td>{escape(cell)}</td>" for cell in row)
            + "</tr>"
            for row in body_rows
        )
        + "</tbody></table>"
    )


def _checklist_table(items: list[str]) -> str:
    rows = []
    for index in range(0, len(items), 2):
        first = items[index]
        second = items[index + 1] if index + 1 < len(items) else ""
        rows.append(
            "<tr>"
            f'<td><span class="check-box"></span>{escape(first)}</td>'
            + (
                f'<td><span class="check-box"></span>{escape(second)}</td>'
                if second
                else "<td></td>"
            )
            + "</tr>"
        )
    return '<table class="check-table"><tbody>' + "".join(rows) + "</tbody></table>"


def _domain_class(value: str) -> str:
    lowered = value.lower()
    if any(term in lowered for term in ("writing", "written", "expression")):
        return "green"
    if any(term in lowered for term in ("speech", "language", "communication")):
        return "purple"
    return "blue"


def _service_area_color_key(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if "math" in lowered:
        return "Math"
    if "read" in lowered:
        return "Reading"
    if "written" in lowered or "writing" in lowered or "expression" in lowered:
        return "Written Expression"
    if "social" in lowered or "emotional" in lowered or "behavior" in lowered or lowered in {"s e b", "seb"}:
        return "S/E/B"
    if "self" in lowered or "independence" in lowered or "independent" in lowered or lowered in {"sh i", "shi"}:
        return "SH/I"
    if "communication" in lowered:
        return "Communication"
    if "speech" in lowered or "language" in lowered:
        return "Speech/Language"
    return value


def _service_area_icon_color(
    value: str,
    customization: ThemeCustomization | None,
    *,
    theme_id: str = "",
) -> str:
    if theme_id == "minimal":
        return MINIMAL_SERVICE_AREA_COLOR
    colors = dict(DEFAULT_SERVICE_AREA_COLORS)
    if customization is not None:
        custom_colors = customization.service_area_colors or {}
        colors.update(custom_colors)
        if "Speech-Language" in custom_colors:
            colors["Speech/Language"] = custom_colors["Speech-Language"]
        if "Social/Emotional/Behavioral" in custom_colors:
            colors["S/E/B"] = custom_colors["Social/Emotional/Behavioral"]
        if "Self-Help/Independence" in custom_colors:
            colors["SH/I"] = custom_colors["Self-Help/Independence"]
    key = _service_area_color_key(value)
    return colors.get(value) or colors.get(key) or "#2563EB"


def _service_area_icon_style(
    value: str,
    customization: ThemeCustomization | None,
    *,
    theme_id: str = "",
) -> str:
    return f"background-color: {_service_area_icon_color(value, customization, theme_id=theme_id)};"


def _service_icon_key(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if "written" in lowered or "writing" in lowered or "expression" in lowered:
        return "written-expression"
    if "speech" in lowered or "language" in lowered:
        return "speech-lang"
    if "communication" in lowered:
        return "communication"
    if "social" in lowered or "emotional" in lowered or "behavior" in lowered:
        return "s-e-b"
    if "self" in lowered or "independence" in lowered or "independent" in lowered:
        return "sh-i"
    if "math" in lowered:
        return "math"
    if "read" in lowered:
        return "reading"
    return "other"


@lru_cache(maxsize=4)
def _cover_icon_markup() -> str:
    icon_path = paths.builtin_assets_dir / "cover-icon" / "cover.svg"
    return _svg_icon_img(icon_path, "service-icon-img cover-fallback-icon", "#ffffff")


@lru_cache(maxsize=64)
def _service_icon_img_markup(icon_key: str, class_name: str, color: str, trim_container: bool = False) -> str:
    icon_path = paths.builtin_assets_dir / "service-icons" / f"{icon_key}.svg"
    if not icon_path.exists() and icon_key != "other":
        return _service_icon_img_markup("other", class_name, color, trim_container)
    return _svg_icon_img(icon_path, class_name, color, trim_container=trim_container)


def _svg_icon_source(
    icon_path: Path,
    color: str,
    *,
    trim_container: bool = False,
    preserve_fill_none_classes: bool = True,
) -> str:
    try:
        svg = icon_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    svg = re.sub(r"<\?xml[^>]*>\s*", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>\s*", "", svg, flags=re.IGNORECASE)
    svg = re.sub(r"<script\b.*?</script>", "", svg, flags=re.IGNORECASE | re.DOTALL)
    svg = re.sub(r"\sxmlns=\"[^\"]*\"", "", svg, count=0)
    svg = re.sub(r"\s(?:width|height)=\"[^\"]*\"", "", svg, count=0)
    if trim_container:
        svg = re.sub(r"<path\b[^>]*/>\s*", "", svg, count=1, flags=re.IGNORECASE | re.DOTALL)
    svg = re.sub(r"\sfill=\"(?!none\")[^\"]*\"", "", svg, flags=re.IGNORECASE)
    svg = re.sub(r"\sstroke=\"(?!none\")[^\"]*\"", "", svg, flags=re.IGNORECASE)
    svg = re.sub(
        r"<svg\b",
        f'<svg preserveAspectRatio="xMidYMid meet" fill="{color}" color="{color}" xmlns="http://www.w3.org/2000/svg"',
        svg,
        count=1,
    )
    if preserve_fill_none_classes:
        recolor_style = (
            f"path:not(.cls-1),polygon:not(.cls-1),polyline:not(.cls-1),rect:not(.cls-1),"
            f"circle:not(.cls-1),ellipse:not(.cls-1),line:not(.cls-1){{fill:{color}!important;}}"
            f"[stroke]:not([stroke='none']){{stroke:{color}!important;}}"
            ".cls-1{fill:none!important;}"
        )
    else:
        recolor_style = (
            f"path,polygon,polyline,rect,circle,ellipse,line{{fill:{color}!important;}}"
            f"[stroke]:not([stroke='none']){{stroke:{color}!important;}}"
        )
    svg = re.sub(r"(<svg\b[^>]*>)", rf"\1<style>{recolor_style}</style>", svg, count=1)
    return svg.strip()


def _svg_icon_img(
    icon_path: Path,
    class_name: str,
    color: str,
    *,
    trim_container: bool = False,
    preserve_fill_none_classes: bool = True,
) -> str:
    svg = _svg_icon_source(
        icon_path,
        color,
        trim_container=trim_container,
        preserve_fill_none_classes=preserve_fill_none_classes,
    )
    if not svg:
        return ""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img class="{class_name}" src="data:image/svg+xml;base64,{encoded}" alt="">'


def _svg_icon_data_uri(
    icon_path: Path,
    color: str,
    *,
    trim_container: bool = False,
    preserve_fill_none_classes: bool = True,
) -> str:
    svg = _svg_icon_source(
        icon_path,
        color,
        trim_container=trim_container,
        preserve_fill_none_classes=preserve_fill_none_classes,
    )
    if not svg:
        return ""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _service_icon_img(value: str, *, class_name: str = "service-icon-img", color: str = "#0f2d55", trim_container: bool = False) -> str:
    markup = _service_icon_img_markup(_service_icon_key(value), class_name, color, trim_container)
    return markup or escape(_service_symbol(value))


def _service_icon_background(value: str, *, color: str = "#ffffff", trim_container: bool = False) -> str:
    icon_key = _service_icon_key(value)
    icon_path = paths.builtin_assets_dir / "service-icons" / f"{icon_key}.svg"
    if not icon_path.exists() and icon_key != "other":
        icon_path = paths.builtin_assets_dir / "service-icons" / "other.svg"
    uri = _svg_icon_data_uri(icon_path, color, trim_container=trim_container)
    return f"background-image: url({uri});" if uri else ""


def _page_icon_img(icon_key: str, *, color: str = "#ffffff") -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", icon_key.lower()).strip("-")
    icon_path = paths.builtin_assets_dir / "page-icons" / f"{normalized}.svg"
    if not icon_path.exists():
        return ""
    class_name = f"page-icon-img page-icon-img-{normalized}"
    return _svg_icon_img(
        icon_path,
        class_name,
        color,
        trim_container=False,
        preserve_fill_none_classes=False,
    )


def _service_icon_color(domain_class: str) -> str:
    return {
        "green": "#73b85a",
        "purple": "#7d66b7",
        "orange": "#ef7900",
    }.get(domain_class, "#0f2d55")


def _service_symbol(value: str) -> str:
    lowered = value.lower()
    if any(term in lowered for term in ("writing", "written", "expression")):
        return "W"
    if any(term in lowered for term in ("speech", "language", "communication")):
        return "S"
    return "R"


def _team_contacts_html(
    student: StudentResponse | None,
    providers: list[RelatedServiceProviderDraft] | None = None,
) -> str:
    visible_providers = [
        provider
        for provider in sorted(providers or [], key=lambda item: item.position)
        if provider.name.strip() or provider.email.strip() or provider.phone.strip()
    ]
    case_manager_name = student.case_manager if student and student.case_manager else "Not entered"
    case_manager_rows = [
        f"<p><strong>Case Manager:</strong> {escape(case_manager_name)}</p>",
        f"<p><strong>School:</strong> {escape(student.school if student and student.school else 'Not entered')}</p>",
    ]
    if student and student.case_manager_phone:
        case_manager_rows.append(f"<p><strong>Phone:</strong> {escape(student.case_manager_phone)}</p>")
    if student and student.case_manager_email:
        case_manager_rows.append(f"<p><strong>Email:</strong> {escape(student.case_manager_email)}</p>")
    if student and student.case_manager_notes:
        case_manager_rows.append(
            f"<p><strong>Notes:</strong> {escape(student.case_manager_notes).replace(chr(10), '<br>')}</p>"
        )
    provider_cards = "".join(
        f"""
        <div style="break-inside: avoid; border: 1px solid #c8d7e6; border-radius: 10px; margin-top: 8px; padding: 10px 12px;">
          <p style="margin: 0 0 4px;"><strong>{escape(provider.service_area or 'Related Service')}</strong></p>
          <p style="margin: 0;">{escape(provider.name or 'Not entered')}</p>
          {f'<p style="margin: 4px 0 0;"><strong>Email:</strong> {escape(provider.email)}</p>' if provider.email else ''}
          {f'<p style="margin: 4px 0 0;"><strong>Phone:</strong> {escape(provider.phone)}</p>' if provider.phone else ''}
        </div>
        """
        for provider in visible_providers
    )
    providers_section = (
        f"""
        <div style="border-top: 2px solid #e1ebf4; margin-top: 14px; padding-top: 12px;">
          <h4 style="font-size: 11px; letter-spacing: 0.12em; margin: 0 0 8px; text-transform: uppercase;">Related Service Providers</h4>
          {provider_cards}
        </div>
        """
        if provider_cards
        else ""
    )
    return (
        '<div class="soft-card" style="margin-top: 18px;">'
        "<h3>Team Contacts</h3>"
        '<div style="break-inside: avoid;">'
        "<h4 style=\"font-size: 11px; letter-spacing: 0.12em; margin: 0 0 8px; text-transform: uppercase;\">Case Manager</h4>"
        + "".join(case_manager_rows)
        + "</div>"
        + providers_section
        + "</div>"
    )


def _accommodation_area_label(item: AccommodationDraft) -> str:
    if item.content_area == "Other":
        return item.custom_content_area.strip() or "Other"
    return item.content_area.strip() or "Instructional"


def _accommodations_html(items: list[AccommodationDraft]) -> str:
    visible = [item for item in sorted(items, key=lambda value: value.position) if item.text.strip()]
    if not visible:
        return '<div class="placeholder">No accommodations or modifications entered.</div>'
    return "".join(
        f"""
        <article class="section">
          <h3>{escape(_accommodation_area_label(item))}</h3>
          <p>{escape(item.text).replace(chr(10), "<br>")}</p>
        </article>
        """
        for item in visible
    )


def _accommodations_teacher_note_html(settings: AppSettings) -> str:
    if not settings.accommodations_teacher_note_enabled:
        return ""
    title = settings.accommodations_teacher_note_title.strip() or "Teacher Responsibilities"
    note = settings.accommodations_teacher_note.strip() or DEFAULT_ACCOMMODATIONS_TEACHER_NOTE
    return f"""
    <article class="accommodation-note accommodations-teacher-note">
      <h3>{escape(title)}</h3>
      <p>{escape(note).replace(chr(10), "<br>")}</p>
    </article>
    """


def _parent_strengths_html(detail: ProjectDetail) -> str:
    if (
        not detail.accommodations_parent_strengths_enabled
        or not detail.accommodations_parent_strengths.strip()
    ):
        return ""
    return f"""
    <article class="accommodation-note accommodations-parent-strengths">
      <h3>Parent Perception of Student Strengths</h3>
      <p>{escape(detail.accommodations_parent_strengths).replace(chr(10), "<br>")}</p>
    </article>
    """


def _accommodations_student_details_html(student: StudentResponse | None) -> str:
    student_name = student.name if student and student.name else "Student"
    iep_end = _format_date(student.iep_end_date if student else None)
    return f"""
    <div class="accommodations-student-details">
      <span><strong>Student:</strong> {escape(student_name)}</span>
      <span><strong>IEP End:</strong> {escape(iep_end)}</span>
    </div>
    """


def _custom_packet_page_html(page: PacketPageDraft, signal_page_mark_html: str) -> str:
    title = page.title.strip() or "Custom Page"
    body_text = page.body_text.strip()
    blank_lines = "".join("<div></div>" for _ in range(18))
    body_html = (
        f'<article class="custom-page-body"><p>{escape(body_text).replace(chr(10), "<br>")}</p></article>'
        if body_text
        else f'<article class="custom-page-body blank-lines">{blank_lines}</article>'
    )
    return f"""
    <section class="page custom-packet-page">
      {signal_page_mark_html}
      <div class="page-header green custom-page-header">
        <h2>{escape(title)}</h2>
      </div>
      {body_html}
    </section>
    """


def _accommodations_signature_page_html(
    detail: ProjectDetail,
    settings: AppSettings,
    signal_page_mark_html: str,
) -> str:
    if (
        not settings.accommodations_signature_page_enabled
        or not any(item.text.strip() for item in detail.accommodations)
    ):
        return ""
    title = (
        settings.accommodations_signature_page_title.strip()
        or "Accommodations Signature Page"
    )
    note = (
        settings.accommodations_signature_page_note.strip()
        or DEFAULT_ACCOMMODATIONS_SIGNATURE_NOTE
    )
    if settings.accommodations_signature_line_layout == "staff_position_date":
        fields = [
            ("Staff Member:", ""),
            ("Position:", ""),
            ("Date:", "date"),
        ]
        row_count = 15
    else:
        fields = [
            ("Staff Member:", ""),
            ("Date:", "date"),
        ]
        row_count = 15

    row_html = ""
    header_html = "".join(
        f"""
        <div class="signature-field {field_class}">
          <div class="signature-label">{escape(label)}</div>
        </div>
        """
        for label, field_class in fields
    )
    row_html = f'<div class="signature-row signature-header">{header_html}</div>'
    for _ in range(row_count):
        field_html = "".join(
            f"""
            <div class="signature-field {field_class}">
              <div class="signature-line"></div>
            </div>
            """
            for _, field_class in fields
        )
        row_html += f'<div class="signature-row">{field_html}</div>'

    return f"""
    <section class="page">
      {signal_page_mark_html}
      <div class="page-header green">
        <span class="badge green page-icon-badge">{_page_icon_img("accommodations")}</span>
        <h2>{escape(title)}</h2>
      </div>
      {_accommodations_student_details_html(detail.student)}
      <p class="signature-note">{escape(note).replace(chr(10), "<br>")}</p>
      <div class="signature-lines">{row_html}</div>
    </section>
    """


def _behavior_plan_html(items: list[BehaviorPlanSectionDraft], legacy_text: str) -> str:
    visible = [item for item in sorted(items, key=lambda value: value.position) if item.text.strip()]
    if visible:
        return "".join(
            f"""
            <article class="section">
              <h3>{escape(item.title.strip() or "Behavior Plan")}</h3>
              <p>{escape(item.text).replace(chr(10), "<br>")}</p>
            </article>
            """
            for item in visible
        )
    if legacy_text.strip():
        return f'<article class="section"><p>{escape(legacy_text).replace(chr(10), "<br>")}</p></article>'
    return '<div class="soft-card" style="text-align: center; padding: 76px 28px;"><h2 style="color: #73b85a;">No Behavior Intervention Plan</h2><p>No behavior plan content entered.</p></div>'


def _build_packet_html(
    detail: ProjectDetail,
    *,
    theme_id: str,
    packet_template_id: str,
    packet_version_name: str,
    packet_config: PacketVersionConfig | None = None,
    customization: ThemeCustomization | None = None,
) -> str:
    app_settings = get_app_settings()
    student = detail.student
    student_name = student.name if student else "Student"
    service_names = sorted({area.name for area in detail.service_areas if area.name})
    student_initials = (
        student.initials
        if student and student.initials
        else derive_initials(student_name)
    )

    rendered_pages: dict[str, str] = {}
    cover_chips = "".join(
        f"""
        <div class="service-chip">
          <span class="chip-dot">
            {_service_icon_img(name, class_name="service-icon-img cover-service-icon", color="#ffffff", trim_container=False)}
          </span>
          <span>{escape(name)}</span>
        </div>
        """
        for name in service_names[:8]
    )
    service_count = min(len(service_names), 8)
    district_mark = (
        detail.brand_kit.district_name
        or detail.brand_kit.school_name
        or (student.school if student and student.school else "")
        or "District Branding"
    )
    school_year = detail.school_year or "School Year"
    cover_year_mark = (
        str(student.iep_end_date.year)[-2:]
        if student and student.iep_end_date
        else ""
    )
    watermark_src = (
        detail.brand_kit.watermark_logo_relative_path
        if detail.brand_kit.watermark_enabled and detail.brand_kit.watermark_logo_relative_path
        else ""
    )
    signal_page_mark_html = (
        f'<div class="signal-page-mark">{escape(cover_year_mark)}</div>'
        if packet_template_id == "signal_atlas" and cover_year_mark
        else ""
    )
    body_classes = [f"template-{packet_template_id.replace('_', '-')}"]
    if watermark_src:
        body_classes.append("has-watermark")
    fallback_cover_icon = _cover_icon_markup()
    identity_html = f'<div class="cover-icon">{fallback_cover_icon or "SP"}</div>'
    typographic_watermark_html = ""
    if detail.brand_kit.logo_relative_path:
        logo_src = detail.brand_kit.logo_relative_path.replace("\\", "/")
        identity_html = f'<img class="brand-logo cover-logo" src="{escape(logo_src)}" alt="">'
    if packet_template_id == "typographic_poster":
        if detail.brand_kit.logo_relative_path:
            logo_src = detail.brand_kit.logo_relative_path.replace("\\", "/")
            typographic_watermark_html = (
                f'<img class="typographic-watermark logo" src="{escape(logo_src)}" alt="">'
            )
        else:
            initials = (
                student.initials
                if student and student.initials
                else derive_initials(student_name)
            )
            typographic_watermark_html = (
                f'<div class="typographic-watermark text">{escape(initials or "SP")}</div>'
            )
    cover_version_footer_html = ""
    if packet_template_id in {"editorial_ledger", "mid_century_classroom", "typographic_poster", "signal_atlas"}:
        cover_version_footer_html = (
            f'<p class="cover-version-footer">Packet version: {escape(packet_version_name)}</p>'
        )
    if packet_template_id == "editorial_ledger":
        cover_meta_html = f"""
        <table class="meta-grid editorial-meta-grid" aria-label="Student packet details">
          <tbody>
            <tr>
              <td class="meta-box"><p class="meta-label">Grade</p><p class="meta-value">{escape(student.grade if student else "Not entered")}</p></td>
              <td class="meta-box"><p class="meta-label">IEP end</p><p class="meta-value">{escape(_format_date(student.iep_end_date if student else None))}</p></td>
              <td class="meta-box"><p class="meta-label">School</p><p class="meta-value">{escape(student.school if student and student.school else "Not entered")}</p></td>
              <td class="meta-box"><p class="meta-label">Case manager</p><p class="meta-value">{escape(student.case_manager if student and student.case_manager else "Not entered")}</p></td>
            </tr>
          </tbody>
        </table>
        """
    elif packet_template_id == "mid_century_classroom":
        cover_meta_html = f"""
        <table class="meta-grid" aria-label="Student packet details">
          <tbody>
            <tr>
              <td class="meta-box"><p class="meta-label">Grade</p><p class="meta-value">{escape(student.grade if student else "Not entered")}</p></td>
              <td class="meta-box"><p class="meta-label">IEP end</p><p class="meta-value">{escape(_format_date(student.iep_end_date if student else None))}</p></td>
              <td class="meta-box"><p class="meta-label">School</p><p class="meta-value">{escape(student.school if student and student.school else "Not entered")}</p></td>
              <td class="meta-box"><p class="meta-label">Case manager</p><p class="meta-value">{escape(student.case_manager if student and student.case_manager else "Not entered")}</p></td>
            </tr>
          </tbody>
        </table>
        """
    elif packet_template_id == "typographic_poster":
        cover_meta_html = f"""
        <table class="meta-grid" aria-label="Student packet details">
          <tbody>
            <tr>
              <td class="meta-box"><p class="meta-label">Grade</p><p class="meta-value">{escape(student.grade if student else "Not entered")}</p></td>
              <td class="meta-box"><p class="meta-label">IEP end</p><p class="meta-value">{escape(_format_date(student.iep_end_date if student else None))}</p></td>
              <td class="meta-box"><p class="meta-label">School</p><p class="meta-value">{escape(student.school if student and student.school else "Not entered")}</p></td>
              <td class="meta-box"><p class="meta-label">Case manager</p><p class="meta-value">{escape(student.case_manager if student and student.case_manager else "Not entered")}</p></td>
            </tr>
          </tbody>
        </table>
        """
    elif packet_template_id == "signal_atlas":
        cover_meta_html = f"""
        <table class="meta-grid" aria-label="Student packet details">
          <tbody>
            <tr>
              <td class="meta-box"><p class="meta-label">Grade</p><p class="meta-value">{escape(student.grade if student else "Not entered")}</p></td>
              <td class="meta-box"><p class="meta-label">IEP end</p><p class="meta-value">{escape(_format_date(student.iep_end_date if student else None))}</p></td>
              <td class="meta-box"><p class="meta-label">School</p><p class="meta-value">{escape(student.school if student and student.school else "Not entered")}</p></td>
              <td class="meta-box"><p class="meta-label">Case manager</p><p class="meta-value">{escape(_case_manager_name(student) or "Not entered")}</p></td>
            </tr>
          </tbody>
        </table>
        """
    else:
        cover_meta_html = f"""
        <table class="meta-grid" aria-label="Student packet details">
          <tbody>
            <tr>
              <td class="meta-box" colspan="2"><p class="meta-label">Grade</p><p class="meta-value">{escape(student.grade if student else "Not entered")}</p></td>
              <td class="meta-box" colspan="2"><p class="meta-label">IEP end</p><p class="meta-value">{escape(_format_date(student.iep_end_date if student else None))}</p></td>
              <td class="meta-box" colspan="2"><p class="meta-label">School</p><p class="meta-value">{escape(student.school if student and student.school else "Not entered")}</p></td>
            </tr>
            <tr>
              <td class="meta-spacer"></td>
              <td class="meta-box" colspan="2"><p class="meta-label">Case manager</p><p class="meta-value">{escape(student.case_manager if student and student.case_manager else "Not entered")}</p></td>
              <td class="meta-box" colspan="2"><p class="meta-label">Version</p><p class="meta-value">{escape(packet_version_name)}</p></td>
              <td class="meta-spacer"></td>
            </tr>
          </tbody>
        </table>
        """
    rendered_pages["cover"] = (
        f"""
        <section class="page cover">
          <div class="cover-card">
            <div class="cover-district-mark">{escape(district_mark)}</div>
            {typographic_watermark_html}
            <div class="cover-content" data-year-mark="{escape(cover_year_mark)}" data-student-initials="{escape(student_initials or "SP")}">
              {identity_html}
              <p class="cover-kicker">Special Education</p>
              <p class="cover-school">{escape(detail.brand_kit.school_name or (student.school if student and student.school else ""))}</p>
              <h1>Service<br>Packet</h1>
              <div class="cover-year">{escape(school_year)}</div>
              <p class="cover-student">{escape(student_name)}</p>
            </div>
            <div class="cover-bottom">
              <div class="cover-details">
              <div class="cover-services service-count-{service_count}">{cover_chips}</div>
              {cover_meta_html}
              </div>
            </div>
            {cover_version_footer_html}
            <div class="mountains"></div>
          </div>
        </section>
        """
    )

    glance_sections = [
        section
        for section in detail.at_a_glance.sections
        if section.enabled and section.content.strip()
    ]
    rendered_pages["at_a_glance"] = (
        f"""
        <section class="page">
          {signal_page_mark_html}
          <div class="page-header">
            <span class="badge page-icon-badge">{_page_icon_img("at-a-glance")}</span>
            <h2>At-a-Glance</h2>
          </div>
        """
        + "".join(
            f"""
            <article class="section">
              <h3>{escape(section.title)}</h3>
              <p>{escape(section.content).replace(chr(10), "<br>")}</p>
            </article>
            """
            for section in glance_sections
        )
        + "</section>"
    )

    if any(item.text.strip() for item in detail.accommodations):
        rendered_pages["accommodations"] = (
            f"""
            <section class="page">
              {signal_page_mark_html}
              <div class="page-header green">
                <span class="badge green page-icon-badge">{_page_icon_img("accommodations")}</span>
                <h2>Accommodations/Modifications</h2>
              </div>
              {_accommodations_student_details_html(student)}
              {_accommodations_teacher_note_html(app_settings)}
              {_accommodations_html(detail.accommodations)}
              {_parent_strengths_html(detail)}
            </section>
            """
        )
        signature_page_html = _accommodations_signature_page_html(
            detail,
            app_settings,
            signal_page_mark_html,
        )
        if signature_page_html:
            rendered_pages["accommodations_signature"] = signature_page_html
    if detail.behavior_plan.strip() or any(item.text.strip() for item in detail.behavior_plan_sections):
        rendered_pages["behavior"] = (
            f"""
            <section class="page">
              {signal_page_mark_html}
              <div class="page-header green">
                <span class="badge green page-icon-badge">{_page_icon_img("behavior-plan")}</span>
                <h2>Behavior Support</h2>
              </div>
              {_behavior_plan_html(detail.behavior_plan_sections, detail.behavior_plan)}
            </section>
            """
        )

    goal_sections: list[str] = []
    for area in detail.service_areas:
        area_goals = [goal for goal in detail.goals if goal.service_area_id == area.id]
        if not area_goals:
            continue
        domain_class = _domain_class(area.name)
        goal_sections.append(
            f"""
            <div class="domain-title">
            <span class="mini-dot {domain_class}" style="{_service_area_icon_style(area.name, customization, theme_id=theme_id)}">
                {_service_icon_img(area.name, color="#ffffff")}
            </span>
            <h3>{escape(area.name)}</h3>
            </div>
            """
        )
        goal_sections.extend(
            f"""
            <article class="goal-card {domain_class}">
              <h4>{escape(goal.title)}</h4>
              <p>{escape(goal.statement).replace(chr(10), "<br>")}</p>
            </article>
            """
            for goal in area_goals
        )
    rendered_pages["goal_summary"] = (
        f"""
        <section class="page">
          {signal_page_mark_html}
          <div class="page-header">
            <span class="badge page-icon-badge">{_page_icon_img("goal-summary")}</span>
            <h2>Goal Summary</h2>
          </div>
        """
        + "".join(goal_sections)
        + "</section>"
    )
    rendered_pages["services"] = (
        f"""
        <section class="page">
        {signal_page_mark_html}
        <div class="page-header">
            <span class="badge page-icon-badge">{_page_icon_img("service-info")}</span>
            <h2>Service Information</h2>
        </div>

        <h3>Service Areas</h3>

        <div class="service-area-grid">
        """
        + "".join(
            f"""
            <div class="service-area-card">
            <span class="mini-dot {_domain_class(area.name)}" style="{_service_area_icon_style(area.name, customization, theme_id=theme_id)}">
                {_service_icon_img(area.name, color="#ffffff")}
            </span>
            <span class="service-area-name">{escape(area.name)}</span>
            </div>
            """
            for area in detail.service_areas
        )
        + """
        </div>

        <h3 style="margin-top: 18px;">Weekly Service Minutes</h3>
        """
        + _table(
            ["Service", "Minutes per week", "Setting"],
            [
                [
                    area.name,
                    str(area.minutes_per_week) if area.minutes_per_week is not None else "Not entered",
                    area.setting or "Not entered",
                ]
                for area in detail.service_areas
            ],
        )
        + _team_contacts_html(student, detail.related_service_providers)
        + "</section>"
    )
    for sheet, goal, instance in _data_collection_items(detail):
        service_name = _service_area_name(detail, goal.service_area_id)
        domain_class = _domain_class(service_name)
        rendered_pages[f"data_collection_{sheet.id}_{goal.id}_{instance}"] = (
            f"""
            <section class="page">
              {signal_page_mark_html}
              <div class="page-header {domain_class}">
                <span class="badge {domain_class} service-icon-badge" style="{_service_area_icon_style(service_name, customization, theme_id=theme_id)} {_service_icon_background(service_name, color="#ffffff")}">&nbsp;</span>
                <h2>Data Collection</h2>
              </div>
              <h3>{escape(service_name)}</h3>
              <p><strong>{escape(goal.title)}:</strong> {escape(goal.data_sheet_summary)}</p>
              <p class="muted">{escape(sheet.title)} - {escape(sheet.collection_schedule)} - Table {instance} of {sheet.blank_instance_count}</p>
              <div class="data-collection-table">
                {_table([column.title for column in sheet.columns], [], blank_rows=17)}
              </div>
              <h3 style="margin-top: 12px;">Notes / Observations</h3>
              <div class="notes-lines"></div>
            </section>
            """
        )

    observation_forms = [sheet for sheet in detail.data_sheets if sheet.is_observation_form]
    checklist_items = detail.observation_checklist or DEFAULT_OBSERVATION_CHECKLIST
    checklist_html = f"""
      <div class="staff-checklist" style="margin-top: 12px;">
        <h3 style="color: #ef7900;">Things Staff Need To Tell {escape(student.case_manager_first_name if student and student.case_manager_first_name else "The Case Manager")}</h3>
        {_checklist_table(checklist_items)}
      </div>
    """

    if observation_forms:
        rendered_pages["observations"] = "".join(
            f"""
            <section class="page observation-page">
              {signal_page_mark_html}
              <div class="page-header orange">
                <span class="badge orange page-icon-badge">{_page_icon_img("observation")}</span>
                <h2>{escape(sheet.title or "Observation Sheet")}</h2>
              </div>
              <p class="muted">{escape(sheet.collection_schedule or "General observation form")}</p>
              <div class="observations-table">
                {_table([column.title for column in sheet.columns], [], blank_rows=17)}
              </div>
              {f'<div class="soft-card" style="margin-top: 8px;"><p>{escape(sheet.notes)}</p></div>' if sheet.notes else ''}
              {checklist_html if index == len(observation_forms) - 1 else ''}
            </section>
            """
            for index, sheet in enumerate(observation_forms)
        )
    else:
        rendered_pages["observations"] = (
            f"""
            <section class="page observation-page">
              {signal_page_mark_html}
              <div class="page-header orange">
                <span class="badge orange page-icon-badge">{_page_icon_img("observation")}</span>
                <h2>Observations & Notes</h2>
              </div>
              <div class="observations-table">
                {_table(["Date", "Setting / Context", "Observation", "Follow-up / Action"], [], blank_rows=17)}
              </div>
              {checklist_html}
            </section>
            """
        )

    if packet_config is not None:
        for page in packet_config.pages:
            if page.page_type == "custom_text" and page.id not in rendered_pages:
                rendered_pages[page.id] = _custom_packet_page_html(
                    page,
                    signal_page_mark_html,
                )

    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(detail.name)}</title><style>{_packet_styles(theme_id, customization or detail.theme_customization, watermark_src, _brand_body_font(detail.brand_kit), _brand_heading_font(detail.brand_kit))}</style>"
        f"</head><body class=\"{escape(' '.join(body_classes))}\">"
        + "".join(_ordered_packet_pages(rendered_pages, packet_config))
        + "</body></html>"
    )
    terminology = {
        "ese": ("ESE", "Exceptional Student Education"),
        "ess": ("ESS", "Exceptional Student Services"),
        "sped": ("SpEd", "Special Education"),
    }[app_settings.terminology_preference or "sped"]
    acronym, full_title = terminology
    return (
        html.replace("SPECIAL EDUCATION", full_title.upper())
        .replace("Special Education", full_title)
        .replace("SpEd", acronym)
    )


def _render_export_filename(
    custom_filename: str,
    detail: ProjectDetail,
    *,
    packet_version_name: str,
    extension: str = ".pdf",
    include_packet_version_for_custom: bool = False,
) -> str:
    student_name = detail.student.name if detail.student else ""
    rendered = custom_filename.strip()
    if rendered:
        stem = Path(rendered).stem if Path(rendered).suffix else rendered
        if include_packet_version_for_custom:
            stem = f"{stem} - {packet_version_name}"
        return _safe_filename(stem, extension)
    return _safe_filename(
        default_export_filename(student_name, detail.school_year, packet_version_name),
        extension,
    )


def _export_directory(detail: ProjectDetail, project_id: str) -> Path:
    configured = detail.export_settings.last_export_location.strip()
    if configured:
        path = Path(configured).expanduser()
        if path.exists() and path.is_dir():
            return path
    export_dir = paths.cache_dir / "generated-exports" / project_id
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def _export_path_for_response(export: Export) -> Path:
    absolute = (export.metadata_json or {}).get("absolute_path")
    if isinstance(absolute, str) and absolute:
        return Path(absolute)
    return paths.app_data_dir / export.relative_path


def _export_response(export: Export, project_id: str) -> ExportResponse:
    export_path = _export_path_for_response(export)
    return ExportResponse(
        id=export.id,
        filename=export_path.name,
        relative_path=export.relative_path,
        absolute_path=str(export_path.resolve()),
        generated_at=export.generated_at,
        content_hash=export.content_hash,
        size_bytes=export_path.stat().st_size if export_path.exists() else 0,
        download_url=f"/projects/{project_id}/exports/{export.id}/download",
    )


def _ensure_export_ready(detail: ProjectDetail) -> None:
    if not (
        detail.student_setup_validation.is_complete
        and detail.goals_validation.is_complete
        and detail.at_a_glance_validation.is_complete
        and detail.data_sheets_validation.is_complete
    ):
        raise HTTPException(
            status_code=409,
            detail="Complete all packet sections before exporting.",
        )


def _render_packet_pdf_bytes(
    detail: ProjectDetail,
    packet: PacketVersion,
    *,
    theme_id: str,
    packet_template_id: str,
) -> bytes:
    base_template_id = _packet_template_base_id(packet_template_id)
    html = _build_packet_html(
        detail,
        theme_id=theme_id,
        packet_template_id=base_template_id,
        packet_version_name=packet.name,
        packet_config=_packet_config(packet),
        customization=_customization_for_template(packet_template_id),
    )
    try:
        return render_pdf(PdfRenderRequest(html=html, base_url=str(paths.app_data_dir)))
    except RuntimeError as reason:
        raise HTTPException(status_code=503, detail=str(reason)) from reason


def _sample_template_project_detail(draft: TemplatePreviewRequest) -> ProjectDetail:
    sample_student = StudentResponse(
        id="sample_student",
        name="Cecilia Halpert",
        initials="CH",
        grade="5",
        school="Scranton Elementary",
        case_manager="Jim Halpert",
        case_manager_first_name="Jim",
        case_manager_last_name="Halpert",
        case_manager_phone="(555) 010-2045",
        case_manager_email="jhalpert@example.org",
        case_manager_notes="Best reached before school or during planning.",
        iep_end_date=date(2027, 2, 18),
    )
    service_areas = [
        ServiceAreaResponse(
            id="reading",
            name="Reading",
            setting="Special Education",
            minutes_per_week=180,
            notes="Small-group fluency and comprehension instruction.",
            position=0,
        ),
        ServiceAreaResponse(
            id="math",
            name="Math",
            setting="Regular Education",
            minutes_per_week=90,
            notes="In-class computation support.",
            position=1,
        ),
        ServiceAreaResponse(
            id="written_expression",
            name="Written Expression",
            setting="Special Education",
            minutes_per_week=60,
            notes="Planning, drafting, and revising support.",
            position=2,
        ),
    ]
    goals = [
        GoalResponse(
            id="reading_goal",
            title="Reading Fluency",
            statement="Given instructional-level passages, Jordan will read 95 words per minute with 95% accuracy across three consecutive trials by the IEP end date.",
            data_sheet_summary="3 consecutive passages at 95 WPM w/ 95% accuracy.",
            service_area_id="reading",
            mastery_criteria="95 WPM with 95% accuracy for 3 consecutive trials",
            progress_monitoring_method="Curriculum-based oral reading fluency probes",
            instructional_notes="Preview vocabulary and provide repeated reading practice.",
            position=0,
        ),
        GoalResponse(
            id="math_goal",
            title="Math Computation",
            statement="Given mixed computation problems, Jordan will solve addition, subtraction, multiplication, and division problems with 85% accuracy across four trials.",
            data_sheet_summary="4 computation probes at 85% accuracy.",
            service_area_id="math",
            mastery_criteria="85% accuracy across four trials",
            progress_monitoring_method="Weekly computation probes",
            instructional_notes="Allow scratch paper and model one example before independent work.",
            position=1,
        ),
        GoalResponse(
            id="writing_goal",
            title="Written Response",
            statement="Given a grade-level prompt and planning organizer, Jordan will write a complete paragraph with topic sentence, three details, and closing sentence in 4 of 5 opportunities.",
            data_sheet_summary="4/5 paragraphs with topic, 3 details, and closing.",
            service_area_id="written_expression",
            mastery_criteria="4 of 5 writing opportunities",
            progress_monitoring_method="Monthly writing samples",
            instructional_notes="Use graphic organizers and sentence frames as needed.",
            position=2,
        ),
    ]
    at_a_glance = AtAGlanceResponse(
        id="sample_glance",
        sections=[
            AtAGlanceSectionDraft(id="strengths", title="Student Strengths", content="Creative thinker\nStrong oral participation\nEnjoys science and hands-on tasks", enabled=True, position=0),
            AtAGlanceSectionDraft(id="needs", title="Areas of Need", content="Reading fluency\nMath fact automaticity\nWritten organization", enabled=True, position=1),
            AtAGlanceSectionDraft(id="strategies", title="Effective Strategies", content="Offer brief directions\nCheck for understanding\nUse visual organizers", enabled=True, position=2),
            AtAGlanceSectionDraft(id="reminders", title="Staff Reminders", content="Praise effort and persistence. Provide private redirection when needed.", enabled=True, position=3),
        ],
    )
    data_sheets = [
        DataSheetResponse(
            id="reading_sheet",
            title="Reading Fluency Probe",
            sheet_type="trial_count",
            goal_ids=["reading_goal"],
            collection_schedule="Every other week",
            blank_instance_count=2,
            columns=[
                DataSheetColumnDraft(id="date", title="Date", column_type="date", position=0),
                DataSheetColumnDraft(id="passage", title="Passage", column_type="text", position=1),
                DataSheetColumnDraft(id="wpm", title="WPM", column_type="number", position=2),
                DataSheetColumnDraft(id="accuracy", title="Accuracy", column_type="number", position=3),
                DataSheetColumnDraft(id="notes", title="Notes", column_type="notes", position=4),
            ],
            notes="Track passage level and prompting.",
            template_name="Fluency Probe",
            is_template=True,
            is_observation_form=False,
            position=0,
        ),
        DataSheetResponse(
            id="math_sheet",
            title="Computation Chart",
            sheet_type="trial_count",
            goal_ids=["math_goal"],
            collection_schedule="Weekly",
            blank_instance_count=1,
            columns=[
                DataSheetColumnDraft(id="date", title="Date", column_type="date", position=0),
                DataSheetColumnDraft(id="score", title="Score", column_type="number", position=1),
                DataSheetColumnDraft(id="support", title="Support", column_type="text", position=2),
                DataSheetColumnDraft(id="notes", title="Notes", column_type="notes", position=3),
            ],
            notes="Record strategy used.",
            template_name="Computation Probe",
            is_template=True,
            is_observation_form=False,
            position=1,
        ),
        DataSheetResponse(
            id="observation_sheet",
            title="Classroom Observation Sheet",
            sheet_type="notes",
            goal_ids=[],
            collection_schedule="As needed",
            blank_instance_count=1,
            columns=[
                DataSheetColumnDraft(id="date", title="Date", column_type="date", position=0),
                DataSheetColumnDraft(id="context", title="Setting / Context", column_type="text", position=1),
                DataSheetColumnDraft(id="observation", title="Observation", column_type="notes", position=2),
                DataSheetColumnDraft(id="follow_up", title="Follow-up / Action", column_type="notes", position=3),
            ],
            notes="Use for staff notes that are not tied to one goal.",
            template_name="Observation Form",
            is_template=True,
            is_observation_form=True,
            position=2,
        ),
    ]
    packet_pages = _default_packet_pages_from(DEFAULT_PACKET_PAGES)
    packet_config = PacketVersionConfig(
        packet_version_id="sample_packet",
        pages=packet_pages,
        asset_placements=[],
    )
    now = datetime.now(timezone.utc)
    return ProjectDetail(
        id="sample_template_project",
        name="Sample Student - 2026-2027",
        school_year="2026-2027",
        default_export_filename="Cecilia Halpert - Sample Packet.pdf",
        student=sample_student,
        service_areas=service_areas,
        audiences=["case_manager", "general_education", "paraeducator"],
        accommodations=[
            AccommodationDraft(
                id="sample_accommodation_instructional",
                content_area="Instructional",
                text="Provide visual directions and chunked assignments.\nCheck for understanding before transitions.",
                position=0,
            ),
            AccommodationDraft(
                id="sample_accommodation_assessment",
                content_area="Classroom Assessment",
                text="Allow extended time for written responses and independent reading tasks.",
                position=1,
            ),
        ],
        behavior_plan=(
            "Use pre-correction before independent work.\n"
            "Offer a brief break after sustained effort.\n"
            "Notify the case manager if avoidance increases across settings."
        ),
        behavior_plan_sections=[
            BehaviorPlanSectionDraft(
                id="sample_behavior_problem",
                title="Defined Problem Behavior",
                text="Avoidance during lengthy independent reading or writing tasks.",
                position=0,
            ),
            BehaviorPlanSectionDraft(
                id="sample_behavior_prevention",
                title="Prevention Strategies",
                text="Preview directions, chunk assignments, and offer a brief check-in before independent work.",
                position=1,
            ),
            BehaviorPlanSectionDraft(
                id="sample_behavior_response",
                title="Response Strategies",
                text="Use calm redirection, offer a reset break, and notify the case manager if concerns continue.",
                position=2,
            ),
        ],
        packet_versions=[
            PacketVersionResponse(id="sample_packet", name="Staff Packet", audience="base_packet")
        ],
        packet_builder=[packet_config],
        observation_checklist=DEFAULT_OBSERVATION_CHECKLIST,
        theme_id=_resolve_theme_id(draft.theme_id),
        packet_template_id=draft.base_template_id,
        theme_customization=draft.customization,
        brand_kit=BrandKit(
            id="sample_brand",
            name="Sample District",
            district_name="Scranton School District",
            school_name="Scranton Elementary",
            heading_font="Poppins",
            body_font="Open Sans",
        ),
        export_settings=ExportSettings(),
        goals=goals,
        at_a_glance=at_a_glance,
        data_sheets=data_sheets,
        student_setup_validation=StepValidation(is_complete=True, issues=[]),
        goals_validation=validate_goals(goals),
        at_a_glance_validation=validate_at_a_glance(at_a_glance),
        data_sheets_validation=validate_data_sheets(data_sheets),
        updated_at=now,
    )


def preview_template_library_item(draft: TemplatePreviewRequest) -> bytes:
    valid_base_ids = {template.id for template in PACKET_TEMPLATE_OPTIONS}
    if draft.base_template_id not in valid_base_ids:
        raise HTTPException(status_code=422, detail="Unknown base packet template.")
    theme_id = _resolve_theme_id(draft.theme_id)
    detail = _sample_template_project_detail(draft)
    html = _build_packet_html(
        detail,
        theme_id=theme_id,
        packet_template_id=draft.base_template_id,
        packet_version_name="Staff Packet",
        packet_config=detail.packet_builder[0],
        customization=draft.customization,
    )
    try:
        return render_pdf(PdfRenderRequest(html=html, base_url=str(paths.app_data_dir)))
    except RuntimeError as reason:
        raise HTTPException(status_code=503, detail=str(reason)) from reason


def preview_pdf(
    session: Session, project_id: str, request: ExportRequest | None = None
) -> bytes:
    request = request or ExportRequest()
    valid_templates = {template.id for template in list_template_library()}
    if request.packet_template_id and request.packet_template_id not in valid_templates:
        raise HTTPException(status_code=422, detail="Unknown packet template.")
    project = get_project(session, project_id)
    detail = _detail(project)
    _ensure_export_ready(detail)
    packet = _resolve_packet_version(project, session, request.packet_version_id)
    return _render_packet_pdf_bytes(
        detail,
        packet,
        theme_id=_resolve_theme_id(request.theme_id or detail.theme_id),
        packet_template_id=request.packet_template_id or detail.packet_template_id,
    )


def generate_pdf_export(
    session: Session, project_id: str, request: ExportRequest | None = None
) -> ExportResponse:
    request = request or ExportRequest()
    if request.export_mode == "zip_archive":
        return generate_zip_export(session, project_id, request)
    valid_templates = {template.id for template in list_template_library()}
    if request.packet_template_id and request.packet_template_id not in valid_templates:
        raise HTTPException(status_code=422, detail="Unknown packet template.")
    project = get_project(session, project_id)
    detail = _detail(project)
    _ensure_export_ready(detail)

    packet = _resolve_packet_version(project, session, request.packet_version_id)
    theme_id = _resolve_theme_id(request.theme_id or detail.theme_id)
    packet_template_id = request.packet_template_id or detail.packet_template_id
    pdf_bytes = _render_packet_pdf_bytes(
        detail,
        packet,
        theme_id=theme_id,
        packet_template_id=packet_template_id,
    )
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    generated_at = datetime.now(timezone.utc)
    filename = _render_export_filename(
        request.filename_template
        if request.filename_template is not None
        else detail.export_settings.filename_template,
        detail,
        packet_version_name=packet.name,
    )
    export_dir = _export_directory(detail, project.id)
    export_dir.mkdir(parents=True, exist_ok=True)
    output_path = _unique_output_path(export_dir, filename)
    output_path.write_bytes(pdf_bytes)

    data_root = paths.app_data_dir.resolve()
    relative_path = (
        output_path.relative_to(data_root).as_posix()
        if data_root in output_path.resolve().parents or output_path.resolve() == data_root
        else output_path.name
    )
    export = Export(
        packet_version_id=packet.id,
        format="pdf",
        relative_path=relative_path,
        content_hash=content_hash,
        generated_at=generated_at,
        metadata_json={
            "page_count_source": "deterministic_packet_builder",
            "schema_version": settings.schema_version,
            "theme_id": theme_id,
            "packet_template_id": packet_template_id,
            "packet_version_id": packet.id,
            "export_mode": request.export_mode,
            "filename_template": request.filename_template or detail.export_settings.filename_template,
            "absolute_path": str(output_path.resolve()),
        },
    )
    session.add(export)
    _touch(project)
    session.commit()
    session.expire_all()
    refreshed = get_project(session, project_id)
    packet = _resolve_packet_version(refreshed, session, packet.id)
    latest = max(packet.exports, key=lambda item: item.generated_at)
    return _export_response(latest, project_id)


def generate_zip_export(
    session: Session, project_id: str, request: ExportRequest | None = None
) -> ExportResponse:
    request = request or ExportRequest(export_mode="zip_archive")
    valid_templates = {template.id for template in list_template_library()}
    if request.packet_template_id and request.packet_template_id not in valid_templates:
        raise HTTPException(status_code=422, detail="Unknown packet template.")
    project = get_project(session, project_id)
    detail = _detail(project)
    _ensure_export_ready(detail)
    versions = [version for version in project.packet_versions if version.deleted_at is None]
    if not versions:
        versions = [_ensure_export_packet(project, session)]

    theme_id = _resolve_theme_id(request.theme_id or detail.theme_id)
    packet_template_id = request.packet_template_id or detail.packet_template_id
    custom_name = (
        request.filename_template
        if request.filename_template is not None
        else detail.export_settings.filename_template
    )
    generated_at = datetime.now(timezone.utc)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for version in versions:
            pdf_bytes = _render_packet_pdf_bytes(
                detail,
                version,
                theme_id=theme_id,
                packet_template_id=packet_template_id,
            )
            pdf_name = _render_export_filename(
                custom_name,
                detail,
                packet_version_name=version.name,
                include_packet_version_for_custom=bool(custom_name and custom_name.strip()),
            )
            archive.writestr(pdf_name, pdf_bytes)
    zip_bytes = buffer.getvalue()
    content_hash = hashlib.sha256(zip_bytes).hexdigest()
    zip_filename = _render_export_filename(
        custom_name,
        detail,
        packet_version_name="All Packet Versions",
        extension=".zip",
    )
    export_dir = _export_directory(detail, project.id)
    export_dir.mkdir(parents=True, exist_ok=True)
    output_path = _unique_output_path(export_dir, zip_filename)
    output_path.write_bytes(zip_bytes)
    packet = versions[0]
    data_root = paths.app_data_dir.resolve()
    relative_path = (
        output_path.relative_to(data_root).as_posix()
        if data_root in output_path.resolve().parents or output_path.resolve() == data_root
        else output_path.name
    )
    export = Export(
        packet_version_id=packet.id,
        format="zip",
        relative_path=relative_path,
        content_hash=content_hash,
        generated_at=generated_at,
        metadata_json={
            "page_count_source": "deterministic_packet_builder",
            "schema_version": settings.schema_version,
            "theme_id": theme_id,
            "packet_template_id": packet_template_id,
            "export_mode": "zip_archive",
            "filename_template": custom_name,
            "absolute_path": str(output_path.resolve()),
        },
    )
    session.add(export)
    _touch(project)
    session.commit()
    session.expire_all()
    return _export_response(export, project_id)


def generate_all_pdf_exports(
    session: Session, project_id: str, request: ExportRequest | None = None
) -> ExportAllResponse:
    request = request or ExportRequest()
    project = get_project(session, project_id)
    versions = [version for version in project.packet_versions if version.deleted_at is None]
    if not versions:
        versions = [_ensure_export_packet(project, session)]
    exports = [
        generate_pdf_export(
            session,
            project_id,
            ExportRequest(
                packet_version_id=version.id,
                theme_id=request.theme_id,
                packet_template_id=request.packet_template_id,
                filename_template=request.filename_template,
                export_mode=request.export_mode,
            ),
        )
        for version in versions
    ]
    return ExportAllResponse(exports=exports)


def get_export_path(session: Session, project_id: str, export_id: str) -> Path:
    project = get_project(session, project_id)
    export = None
    for version in project.packet_versions:
        for candidate in version.exports:
            if candidate.id == export_id:
                export = candidate
                break
    if export is None:
        raise HTTPException(status_code=404, detail="Export not found.")
    path = _export_path_for_response(export).resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file not found.")
    return path


def create_project_backup(session: Session, project_id: str) -> BackupResponse:
    project = get_project(session, project_id)
    detail = _detail(project)
    created_at = datetime.now(timezone.utc)
    filename = (
        f"{_slug(detail.name)}-backup-"
        f"{created_at.strftime('%Y%m%d-%H%M%S')}.json"
    )
    backup_dir = paths.backups_dir / project.id
    backup_dir.mkdir(parents=True, exist_ok=True)
    output_path = backup_dir / filename
    payload = {
        "backup_version": 1,
        "schema_version": settings.schema_version,
        "created_at": created_at.isoformat(),
        "project": detail.model_dump(mode="json"),
    }
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    relative_path = output_path.relative_to(paths.app_data_dir).as_posix()
    return BackupResponse(
        filename=filename,
        relative_path=relative_path,
        absolute_path=str(output_path.resolve()),
        created_at=created_at,
        size_bytes=output_path.stat().st_size,
    )
