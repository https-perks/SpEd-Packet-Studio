from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from datetime import date, datetime, timezone
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
from backend.generators.pdf import PdfRenderRequest, render_pdf
from backend.models import AtAGlance, DataSheet, Export, Goal, PacketVersion, Project, ServiceArea, Student
from backend.schemas.projects import (
    AtAGlanceDraft,
    AtAGlanceResponse,
    BackupResponse,
    BrandKit,
    BrandKitLibraryDraft,
    BrandKitLibraryItem,
    BrandKitLogoUpload,
    BrandLogoUpload,
    BulkProjectAction,
    BulkProjectActionResponse,
    DataSheetResponse,
    DataSheetsDraft,
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
    PacketVersionResponse,
    PacketVersionConfig,
    AssetPlacementDraft,
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

DEFAULT_SERVICE_AREA_PRESETS = [
    ServiceAreaDraft(name="Reading", position=0),
    ServiceAreaDraft(name="Math", position=1),
    ServiceAreaDraft(name="Written Expression", position=2),
    ServiceAreaDraft(name="Social/Emotional/Behavioral", position=3),
    ServiceAreaDraft(name="Self-Help/Independence", position=4),
]

DEFAULT_DATA_SHEET_COLUMN_DRAFTS = [
    DataSheetColumnDraft(**column) for column in DEFAULT_DATA_SHEET_COLUMNS
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
        description="Clean geometric cover, minimal accents, and strong readability.",
        category="Secondary",
        cover_style="Large title with simple service badges",
        best_for="Middle and high school packets",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="district_branding",
        name="District Branding",
        description="Adds school and district brand-kit text to the cover and footer.",
        category="District",
        cover_style="Logo-ready cover with prominent school identity",
        best_for="District-standard packets",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="mountain_illustrated",
        name="Mountain Illustrated",
        description="Layered mountain landscape, strong teal ribbon, and centered service badges.",
        category="Illustrated",
        cover_style="Light illustrated cover with mountain horizon",
        best_for="Warm professional packets with visual personality",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="elementary_pop",
        name="Elementary Pop",
        description="Bright playful type, soft confetti accents, and large approachable badges.",
        category="Elementary",
        cover_style="Colorful friendly cover with large service blocks",
        best_for="Elementary teams and approachable staff packets",
        page_count_hint="Expanded",
    ),
    PacketTemplateOption(
        id="alpine_photo",
        name="Alpine Photo",
        description="Dark geometric frame with a high-contrast alpine-inspired image panel.",
        category="Secondary",
        cover_style="Dark angled cover with image-style panel",
        best_for="Middle and high school packets with a bold cover",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="botanical_frame",
        name="Botanical Frame",
        description="Elegant green frame, calm typography, and soft botanical accents.",
        category="Classic",
        cover_style="Centered serif cover with leafy border",
        best_for="Polished parent and team copies",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="chalkboard",
        name="Chalkboard",
        description="High-contrast chalkboard style with handwritten-inspired dividers.",
        category="Creative",
        cover_style="Dark chalkboard cover with sketched section marks",
        best_for="Casual internal packets and teacher-facing copies",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="soft_organic",
        name="Soft Organic",
        description="Cream background, rounded cards, warm neutrals, and subtle organic shapes.",
        category="Friendly",
        cover_style="Soft neutral cover with rounded service cards",
        best_for="Elementary and team collaboration packets",
        page_count_hint="Standard",
    ),
    PacketTemplateOption(
        id="purple_dot",
        name="Purple Dot",
        description="Clean editorial layout with a dotted accent field and purple section system.",
        category="Modern",
        cover_style="White cover with purple dot field and footer band",
        best_for="Speech, related services, and concise digital packets",
        page_count_hint="Compact",
    ),
]


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


def _delivery_label(value: str | None) -> str:
    if not value:
        return "Not selected"
    return " ".join(part.capitalize() for part in value.split("_"))


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
    path = settings.data_dir / "library"
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
        default_packet_pages=_default_packet_pages_from(DEFAULT_PACKET_PAGES),
        default_observation_checklist=DEFAULT_OBSERVATION_CHECKLIST,
        default_data_sheet_columns=DEFAULT_DATA_SHEET_COLUMN_DRAFTS,
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
    if not loaded.default_observation_checklist:
        loaded.default_observation_checklist = defaults.default_observation_checklist
    if not loaded.default_data_sheet_columns:
        loaded.default_data_sheet_columns = defaults.default_data_sheet_columns
    loaded.default_theme_id = _resolve_theme_id(loaded.default_theme_id)
    if _template_library_item(loaded.default_packet_template_id) is None:
        loaded.default_packet_template_id = "modern_professional"
    return loaded


def save_app_settings(value: AppSettings) -> AppSettings:
    normalized = value.model_copy(deep=True)
    normalized.default_theme_id = _resolve_theme_id(normalized.default_theme_id)
    if _template_library_item(normalized.default_packet_template_id) is None:
        normalized.default_packet_template_id = "modern_professional"
    normalized.default_packet_pages = sorted(
        normalized.default_packet_pages or _app_settings_default().default_packet_pages,
        key=lambda page: page.position,
    )
    normalized.default_observation_checklist = [
        item.strip() for item in normalized.default_observation_checklist if item.strip()
    ] or DEFAULT_OBSERVATION_CHECKLIST
    normalized.default_data_sheet_columns = sorted(
        normalized.default_data_sheet_columns or DEFAULT_DATA_SHEET_COLUMN_DRAFTS,
        key=lambda column: column.position,
    )
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


def _builtin_template_library_items() -> list[PacketTemplateLibraryItem]:
    default_id = str(_read_library("templates.json").get("default_template_id") or "modern_professional")
    overrides = _template_overrides()
    return [
        (
            overrides.get(template.id)
            or PacketTemplateLibraryItem(
                **template.model_dump(),
                base_template_id=template.id,
                theme_id="teacher_friendly",
                customization=_customization_from_tokens("teacher_friendly"),
                is_builtin=True,
                is_default=template.id == default_id,
            )
        ).model_copy(
            update={
                "id": template.id,
                "base_template_id": template.id,
                "is_builtin": True,
                "is_default": template.id == default_id,
            }
        )
        for template in PACKET_TEMPLATE_OPTIONS
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
            parsed = PacketTemplateLibraryItem(**item)
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
            parsed = PacketTemplateLibraryItem(**item)
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
    _write_library(
        "templates.json",
        {
            "default_template_id": default_id or current_default,
            "overrides": library.get("overrides") if isinstance(library.get("overrides"), dict) else {},
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
    _write_library(
        "templates.json",
        {
            "default_template_id": current_default,
            "overrides": {
                template_id: item.model_copy(
                    update={
                        "id": template_id,
                        "base_template_id": template_id,
                        "is_builtin": True,
                        "is_default": False,
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
    default_id = str(_read_library("templates.json").get("default_template_id") or "modern_professional")
    return [item.model_copy(update={"is_default": item.id == default_id}) for item in items]


def list_packet_templates() -> list[PacketTemplateOption]:
    return [
        PacketTemplateOption(
            id=item.id,
            name=item.name,
            description=item.description,
            category=item.category,
            cover_style=item.cover_style,
            best_for=item.best_for,
            page_count_hint=item.page_count_hint,
        )
        for item in list_template_library()
    ]


def _template_library_item(template_id: str) -> PacketTemplateLibraryItem | None:
    return next((item for item in list_template_library() if item.id == template_id), None)


def _packet_template_base_id(template_id: str) -> str:
    item = _template_library_item(template_id)
    return item.base_template_id if item else template_id


def _customization_for_template(template_id: str) -> ThemeCustomization | None:
    item = _template_library_item(template_id)
    if item and (not item.is_builtin or template_id in _template_overrides()):
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
        category=draft.category.strip() or "Custom",
        cover_style=base.cover_style,
        best_for=base.best_for,
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
            category=draft.category.strip() or base.category,
            cover_style=base.cover_style,
            best_for=base.best_for,
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
            "category": draft.category.strip() or "Custom",
            "cover_style": base.cover_style,
            "best_for": base.best_for,
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
        raise HTTPException(status_code=409, detail="Built-in templates cannot be deleted.")
    items = _custom_template_library_items()
    remaining = [item for item in items if item.id != template_id]
    if len(remaining) == len(items):
        raise HTTPException(status_code=404, detail="Template not found.")
    default_id = str(_read_library("templates.json").get("default_template_id") or "modern_professional")
    _save_custom_templates(remaining, "modern_professional" if default_id == template_id else default_id)


def set_default_template(template_id: str) -> list[PacketTemplateLibraryItem]:
    if _template_library_item(template_id) is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    _save_custom_templates(_custom_template_library_items(), template_id)
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
        default_fonts=draft.default_fonts,
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
            "default_fonts": draft.default_fonts,
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
    logo_dir = settings.data_dir / "assets" / "brand-kits" / upload.brand_kit_id
    logo_dir.mkdir(parents=True, exist_ok=True)
    output_name = "watermark-logo" if upload.logo_kind == "watermark" else "cover-logo"
    output_path = logo_dir / f"{output_name}{extension}"
    output_path.write_bytes(data)
    update = (
        {
            "watermark_logo_relative_path": output_path.relative_to(settings.data_dir).as_posix(),
            "watermark_logo_filename": upload.filename,
            "watermark_enabled": True,
        }
        if upload.logo_kind == "watermark"
        else {
            "logo_relative_path": output_path.relative_to(settings.data_dir).as_posix(),
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
    return ThemeCustomization(
        primary_color=tokens["primary"],
        secondary_color=tokens["accent"],
        accent_color=tokens.get("orange", tokens["accent"]),
        background_color=tokens["soft"],
        card_color="#ffffff",
        text_color=tokens.get("text", "#12213a"),
        service_area_colors={
            "Reading": tokens.get("blue", tokens["primary"]),
            "Written Expression": tokens.get("green", tokens["accent"]),
            "Speech/Language": tokens.get("purple", tokens["primary"]),
        },
    )


def _brand_kit(project: Project) -> BrandKit:
    value = (project.settings_json or {}).get("brand_kit")
    if isinstance(value, dict):
        return BrandKit(**value)
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
                    )
                )
    existing_ids = {page.id for page in pages}
    pages.extend(page for page in _default_packet_pages() if page.id not in existing_ids)
    pages = sorted(pages, key=lambda item: item.position)

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


def _new_packet_version_settings() -> dict[str, object]:
    return {
        "pages": [
            page.model_dump(mode="json")
            for page in get_app_settings().default_packet_pages
        ],
        "asset_placements": [],
    }


def _packet_builder_configs(project: Project) -> list[PacketVersionConfig]:
    return [
        _packet_config(version)
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


def _student_setup_from_model(project: Project) -> StudentSetupDraft:
    student = project.student
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
                "delivery_model": area.delivery_model,
                "notes": area.notes or "",
                "position": area.position,
            }
            for area in sorted(project.service_areas, key=lambda item: item.position)
            if area.deleted_at is None
        ],
        audiences=[
            version.audience
            for version in project.packet_versions
            if version.audience in AUDIENCE_LABELS and version.deleted_at is None
        ],
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
        area.delivery_model = value.delivery_model
        area.notes = value.notes.strip() or None
        area.position = position

    current_versions = {
        version.audience: version
        for version in project.packet_versions
        if version.deleted_at is None
    }
    selected = set(draft.audiences)
    for audience, version in current_versions.items():
        if audience in AUDIENCE_LABELS and audience not in selected:
            session.delete(version)
    for audience in selected:
        if audience not in current_versions:
            session.add(
                PacketVersion(
                    project_id=project.id,
                    name=AUDIENCE_LABELS[audience],
                    audience=audience,
                    settings_json=_new_packet_version_settings(),
                )
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
    logo_dir = settings.data_dir / "assets" / project.id
    logo_dir.mkdir(parents=True, exist_ok=True)
    output_path = logo_dir / f"brand-logo{extension}"
    output_path.write_bytes(data)

    brand = _brand_kit(project)
    brand.logo_relative_path = output_path.relative_to(settings.data_dir).as_posix()
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
            delivery_model=area.delivery_model,
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


def _packet_styles(
    theme_id: str,
    customization: ThemeCustomization | None = None,
    watermark_src: str = "",
    font_name: str = "",
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
      font-family: "Poppins", "Segoe UI", Arial, sans-serif;
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
      background: url("__WATERMARK_SRC__") center center / 3.15in auto no-repeat;
      bottom: 0.35in;
      content: "";
      left: 0.35in;
      opacity: 0.055;
      position: absolute;
      right: 0.35in;
      top: 0.35in;
      z-index: 0;
    }
    body.has-watermark .page:not(.cover) > * {
      position: relative;
      z-index: 1;
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
    .badge {
      align-items: center;
      background: __BLUE__;
      border-radius: 999px;
      color: white;
      display: inline-flex;
      font-family: "Poppins", "Segoe UI", Arial, sans-serif;
      font-size: 14px;
      font-weight: 800;
      height: 32px;
      justify-content: center;
      width: 32px;
    }
    .badge.green { background: __GREEN__; }
    .badge.purple { background: __PURPLE__; }
    .badge.orange { background: __ORANGE__; }
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
      font-family: "Poppins", "Segoe UI", Arial, sans-serif;
      font-size: 20px;
      font-weight: 900;
      height: 64px;
      justify-content: center;
      letter-spacing: 0.02em;
      margin: 0 auto 18px;
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
      font-family: "Poppins", "Segoe UI", Arial, sans-serif;
      font-size: 17px;
      font-weight: 800;
      margin: 18px 0 30px;
      padding: 8px 30px;
    }
    .cover-student {
      color: #64ddd8;
      font-family: "Poppins", "Segoe UI", Arial, sans-serif;
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
      align-items: flex-start;
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      justify-content: center;
      margin: 26px 0 22px;
    }
    .service-chip {
      align-items: center;
      color: white;
      display: inline-flex;
      flex-direction: column;
      font-size: 9px;
      font-weight: 700;
      gap: 7px;
      max-width: 86px;
      text-align: center;
      text-transform: uppercase;
    }
    .chip-dot {
      align-items: center;
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.25);
      border-radius: 999px;
      color: #64ddd8;
      display: inline-flex;
      font-size: 18px;
      height: 46px;
      justify-content: center;
      width: 46px;
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
    .two-col {
      display: grid;
      gap: 14px;
      grid-template-columns: 1fr 1fr;
    }
    .domain-title {
      align-items: center;
      display: flex;
      gap: 7px;
      margin: 14px 0 8px;
    }
    .domain-title .mini-dot {
      border-radius: 999px;
      display: inline-block;
      height: 14px;
      width: 14px;
    }
    .mini-dot.blue { background: __BLUE__; }
    .mini-dot.green { background: __GREEN__; }
    .mini-dot.purple { background: __PURPLE__; }
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
    body.template-mountain-illustrated .cover {
      background:
        radial-gradient(circle at 50% 10%, rgba(255, 244, 194, 0.7), rgba(255,255,255,0.36) 12%, transparent 24%),
        radial-gradient(circle at 50% 18%, rgba(255,255,255,0.9), transparent 31%),
        linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(239, 252, 252, 0.9) 40%, rgba(178, 224, 224, 0.94) 61%, rgba(54, 127, 133, 0.97) 78%, rgba(3, 50, 57, 1) 100%),
        linear-gradient(145deg, #ffffff 0%, #d9f4f1 100%);
      color: __TEXT__;
      min-height: 10.1in;
    }
    body.template-mountain-illustrated .cover-card {
      min-height: 10.1in;
    }
    body.template-mountain-illustrated .cover:before,
    body.template-mountain-illustrated .cover:after {
      bottom: 0;
      content: "";
      position: absolute;
      width: 0;
      z-index: 0;
    }
    body.template-mountain-illustrated .cover:before {
      border-left: 3.25in solid transparent;
      border-right: 3.05in solid transparent;
      border-bottom: 2.1in solid rgba(128, 202, 211, 0.52);
      left: -1.3in;
    }
    body.template-mountain-illustrated .cover:after {
      border-left: 3.6in solid transparent;
      border-right: 2.75in solid transparent;
      border-bottom: 2.26in solid rgba(28, 130, 155, 0.44);
      right: -1.15in;
    }
    body.template-mountain-illustrated .cover-card:before,
    body.template-mountain-illustrated .cover-card:after {
      content: "";
      display: none;
    }
    body.template-mountain-illustrated .cover-content {
      margin-top: 0.1in;
      position: relative;
      text-align: center;
      z-index: 3;
    }
    body.template-mountain-illustrated .cover-content:before,
    body.template-mountain-illustrated .cover-content:after {
      border-top: 2px solid rgba(11, 114, 133, 0.42);
      border-radius: 999px 999px 0 0;
      content: "";
      height: 0.12in;
      position: absolute;
      top: -0.1in;
      width: 0.24in;
    }
    body.template-mountain-illustrated .cover-content:before {
      right: 1.15in;
      transform: rotate(-14deg);
    }
    body.template-mountain-illustrated .cover-content:after {
      right: 0.88in;
      transform: rotate(14deg);
    }
    body.template-mountain-illustrated .cover-card h1,
    body.template-mountain-illustrated .cover-card h2,
    body.template-mountain-illustrated .cover-student {
      color: __PRIMARY__;
      text-align: center;
    }
    body.template-mountain-illustrated .cover-kicker,
    body.template-mountain-illustrated .cover-school {
      color: #0b7285;
      text-align: center;
    }
    body.template-mountain-illustrated .cover-year {
      background: linear-gradient(90deg, #0f766e, __TEAL__);
      box-shadow: 0 4px 0 rgba(15, 45, 85, 0.12);
      display: block;
      margin-left: auto;
      margin-right: auto;
      max-width: 280px;
      text-align: center;
    }
    body.template-mountain-illustrated .service-chip,
    body.template-mountain-illustrated .meta-value {
      color: __PRIMARY__;
    }
    body.template-mountain-illustrated .chip-dot {
      background: __PRIMARY__;
      color: #ffffff;
    }
    body.template-mountain-illustrated .cover-icon {
      background: linear-gradient(135deg, #09345a, #13b7b4);
      border-color: rgba(255,255,255,0.8);
      color: #ffffff;
      box-shadow: 0 8px 22px rgba(7, 61, 88, 0.22);
    }
    body.template-mountain-illustrated .brand-logo {
      filter: drop-shadow(0 6px 10px rgba(7,61,88,0.18));
    }
    body.template-mountain-illustrated .meta-box {
      background: rgba(255,255,255,0.16);
      border-color: rgba(255,255,255,0.26);
    }
    body.template-mountain-illustrated .meta-label {
      color: #9fe7ea;
    }
    body.template-mountain-illustrated .cover-bottom {
      background: transparent;
      border-top: 0;
      color: #ffffff;
      margin: 0 -52px -52px;
      padding: 0.18in 0.52in 0.26in;
      position: relative;
      z-index: 4;
    }
    body.template-mountain-illustrated .cover-bottom:before {
      display: none;
    }
    body.template-mountain-illustrated .cover-bottom:after {
      display: none;
    }
    body.template-mountain-illustrated .cover-details {
      margin-top: 0;
      position: relative;
      z-index: 5;
    }
    body.template-mountain-illustrated .cover-services {
      margin: 0 0 0.16in;
    }
    body.template-mountain-illustrated .cover-bottom .service-chip,
    body.template-mountain-illustrated .cover-bottom .meta-value {
      color: #ffffff;
    }
    body.template-mountain-illustrated .cover-bottom .chip-dot {
      background: rgba(8, 43, 67, 0.92);
      border-color: rgba(255,255,255,0.28);
      box-shadow: 0 5px 14px rgba(0,0,0,0.2);
      color: #ffffff;
    }
    body.template-mountain-illustrated .cover-bottom .meta-grid {
      margin-top: 0;
    }
    body.template-mountain-illustrated .mountains {
      background:
        repeating-linear-gradient(90deg, rgba(3, 54, 60, 0.0) 0 0.18in, rgba(3, 54, 60, 0.5) 0.18in 0.21in, rgba(3, 54, 60, 0.0) 0.21in 0.36in);
      bottom: -0.02in;
      height: 2.72in;
      opacity: 0.95;
      z-index: 1;
    }
    body.template-mountain-illustrated .mountains:before {
      border-left-width: 2.35in;
      border-right-width: 2.25in;
      border-bottom-width: 1.66in;
      border-bottom-color: rgba(5, 94, 101, 0.94);
      left: -0.1in;
    }
    body.template-mountain-illustrated .mountains:after {
      border-left-width: 2.8in;
      border-right-width: 2.65in;
      border-bottom-width: 1.86in;
      border-bottom-color: rgba(30, 125, 151, 0.88);
      right: -0.45in;
    }
    body.template-elementary-pop .cover {
      background:
        radial-gradient(circle at 9% 9%, rgba(239,121,0,0.18), transparent 18%),
        radial-gradient(circle at 88% 15%, rgba(39,184,178,0.18), transparent 17%),
        radial-gradient(circle at 18% 82%, rgba(125,102,183,0.16), transparent 20%),
        #fffaf1;
      color: __TEXT__;
    }
    body.template-elementary-pop .cover-card h1 {
      color: __PRIMARY__;
      font-size: 42px;
      letter-spacing: 0.02em;
      text-align: center;
    }
    body.template-elementary-pop .cover-card h2,
    body.template-elementary-pop .cover-student {
      color: #3f7f7d;
      text-align: center;
    }
    body.template-elementary-pop .cover-kicker,
    body.template-elementary-pop .cover-school {
      color: #3f7f7d;
      text-align: center;
    }
    body.template-elementary-pop .cover-year,
    body.template-elementary-pop .badge,
    body.template-elementary-pop .chip-dot {
      border-radius: 999px;
    }
    body.template-elementary-pop .cover-icon {
      background: #db7347;
      border-color: rgba(255,255,255,0.9);
      color: #ffffff;
      box-shadow: 0 8px 18px rgba(217, 115, 71, 0.22);
    }
    body.template-elementary-pop .service-chip,
    body.template-elementary-pop .meta-value {
      color: __TEXT__;
    }
    body.template-elementary-pop .chip-dot {
      background: __ORANGE__;
      color: #ffffff;
    }
    body.template-elementary-pop .meta-box,
    body.template-elementary-pop .section,
    body.template-elementary-pop .soft-card,
    body.template-elementary-pop .goal-card {
      border-radius: 18px;
    }
    body.template-elementary-pop .meta-box {
      background: rgba(255,250,240,0.88);
      border-color: rgba(214,155,45,0.32);
    }
    body.template-elementary-pop .meta-label {
      color: #9a5b20;
    }
    body.template-elementary-pop .mountains {
      opacity: 0.18;
    }
    body.template-alpine-photo .cover {
      background:
        linear-gradient(112deg, #071827 0%, #102a43 56%, transparent 57%),
        linear-gradient(155deg, transparent 0 58%, rgba(255,255,255,0.1) 58% 62%, transparent 62%),
        radial-gradient(circle at 83% 47%, rgba(255,255,255,0.54), transparent 16%),
        linear-gradient(160deg, #1f6fb8 0%, #0d1f35 100%);
      color: white;
    }
    body.template-alpine-photo .cover-card {
      justify-content: center;
      padding-right: 240px;
    }
    body.template-alpine-photo .cover-year {
      background: #149fe3;
      margin-left: 0;
    }
    body.template-alpine-photo .cover-details {
      margin-left: 0;
      text-align: left;
      width: 420px;
    }
    body.template-alpine-photo .cover-student,
    body.template-alpine-photo .cover-services {
      justify-content: flex-start;
      text-align: left;
    }
    body.template-alpine-photo .meta-grid {
      margin-left: 0;
    }
    body.template-alpine-photo .mountains {
      height: 220px;
      left: auto;
      opacity: 0.52;
      width: 310px;
    }
    body.template-botanical-frame .cover {
      background:
        radial-gradient(circle at 6% 7%, rgba(85,122,70,0.18), transparent 16%),
        radial-gradient(circle at 92% 87%, rgba(85,122,70,0.14), transparent 18%),
        #fbfbf5;
      border: 8px solid rgba(85,122,70,0.55);
      color: #2f463c;
    }
    body.template-botanical-frame .cover-card h1,
    body.template-botanical-frame .cover-card h2,
    body.template-botanical-frame .cover-student {
      color: #2f463c;
      font-family: Georgia, "Times New Roman", serif;
      text-align: center;
    }
    body.template-botanical-frame .cover-kicker,
    body.template-botanical-frame .cover-school {
      color: #557a46;
      text-align: center;
    }
    body.template-botanical-frame .cover-year {
      background: #557a46;
      display: block;
      margin-left: auto;
      margin-right: auto;
      max-width: 220px;
      text-align: center;
    }
    body.template-botanical-frame .cover-icon {
      background: #62786e;
      border-color: rgba(255,255,255,0.9);
      color: #ffffff;
      box-shadow: 0 8px 18px rgba(63, 84, 76, 0.18);
    }
    body.template-botanical-frame .service-chip,
    body.template-botanical-frame .meta-value {
      color: #2f463c;
    }
    body.template-botanical-frame .chip-dot {
      background: #557a46;
      color: #ffffff;
    }
    body.template-botanical-frame .meta-box {
      background: rgba(255,255,255,0.72);
      border-color: rgba(85,122,70,0.35);
    }
    body.template-botanical-frame .meta-label {
      color: #557a46;
    }
    body.template-botanical-frame .mountains {
      display: none;
    }
    body.template-chalkboard {
      background: #f7f7f3;
      color: #172033;
    }
    body.template-chalkboard .cover {
      background:
        linear-gradient(135deg, rgba(255,255,255,0.06) 0 25%, transparent 25% 50%, rgba(255,255,255,0.04) 50% 75%, transparent 75%),
        #1f2933;
      border: 8px solid #475569;
      color: #f8fafc;
    }
    body.template-chalkboard .cover-card h1,
    body.template-chalkboard .cover-card h2,
    body.template-chalkboard .cover-student,
    body.template-chalkboard .cover-kicker,
    body.template-chalkboard .cover-school {
      color: #f8fafc;
      text-align: center;
    }
    body.template-chalkboard .cover-year {
      background: transparent;
      border: 2px solid rgba(255,255,255,0.58);
      display: block;
      margin-left: auto;
      margin-right: auto;
      max-width: 220px;
      text-align: center;
    }
    body.template-chalkboard .meta-box {
      background: transparent;
      border: 1px solid rgba(255,255,255,0.32);
    }
    body.template-chalkboard .mountains {
      opacity: 0.12;
    }
    body.template-soft-organic .cover {
      background:
        radial-gradient(circle at 87% 11%, rgba(204,168,119,0.28), transparent 20%),
        radial-gradient(circle at 11% 88%, rgba(204,168,119,0.22), transparent 19%),
        #fbf6ed;
      color: #4a3f34;
    }
    body.template-soft-organic .cover-card h1,
    body.template-soft-organic .cover-card h2,
    body.template-soft-organic .cover-student {
      color: #5f4d3e;
      font-family: Georgia, "Times New Roman", serif;
      text-align: center;
    }
    body.template-soft-organic .cover-kicker,
    body.template-soft-organic .cover-school {
      color: #7b9274;
      text-align: center;
    }
    body.template-soft-organic .cover-year {
      background: #9b7f5f;
      border-radius: 3px;
      display: block;
      margin-left: auto;
      margin-right: auto;
      max-width: 220px;
      text-align: center;
    }
    body.template-soft-organic .service-chip,
    body.template-soft-organic .meta-value {
      color: #4a3f34;
    }
    body.template-soft-organic .chip-dot {
      background: #7b9274;
      color: #ffffff;
    }
    body.template-soft-organic .meta-box,
    body.template-soft-organic .section,
    body.template-soft-organic .soft-card,
    body.template-soft-organic .goal-card {
      border-radius: 18px;
    }
    body.template-soft-organic .mountains {
      display: none;
    }
    body.template-purple-dot .cover {
      background:
        radial-gradient(circle, rgba(126, 87, 194, 0.42) 0 2px, transparent 2px) right center / 18px 18px no-repeat,
        linear-gradient(90deg, #ffffff 0%, #ffffff 64%, #f3e8ff 64%, #ffffff 100%);
      color: #101827;
    }
    body.template-purple-dot .cover-card h1,
    body.template-purple-dot .cover-card h2 {
      color: #101827;
      font-size: 36px;
    }
    body.template-purple-dot .cover-student {
      color: #101827;
      text-align: left;
    }
    body.template-purple-dot .cover-kicker,
    body.template-purple-dot .cover-school {
      color: #6d3fc0;
    }
    body.template-purple-dot .cover-year,
    body.template-purple-dot .chip-dot,
    body.template-purple-dot .page-header {
      background: #6d3fc0;
      color: #ffffff;
    }
    body.template-purple-dot .service-chip,
    body.template-purple-dot .meta-value {
      color: #101827;
    }
    body.template-purple-dot .meta-box {
      background: #6d3fc0;
      border: 0;
    }
    body.template-purple-dot .meta-label,
    body.template-purple-dot .meta-value {
      color: #ffffff;
    }
    body.template-purple-dot .mountains {
      display: none;
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
      font-family: "Poppins", "Segoe UI", Arial, sans-serif;
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
      font-family: "Poppins", "Segoe UI", Arial, sans-serif;
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
      font-family: "Poppins", "Segoe UI", Arial, sans-serif;
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
    body.template-mountain-illustrated .page:not(.cover) {
      background:
        linear-gradient(180deg, rgba(255,255,255,0.96), rgba(239,252,252,0.82)),
        __CARD__;
      border-bottom: 10px solid rgba(8, 125, 135, 0.28);
    }
    body.template-mountain-illustrated .page-header {
      background: linear-gradient(90deg, rgba(8, 125, 135, 0.12), transparent);
      border-bottom-color: #087d87;
      border-radius: 14px 14px 0 0;
      padding: 10px 12px;
    }
    body.template-mountain-illustrated .section,
    body.template-mountain-illustrated .soft-card,
    body.template-mountain-illustrated .goal-card {
      background: rgba(255,255,255,0.88);
      border-color: rgba(8, 125, 135, 0.28);
      box-shadow: 0 5px 14px rgba(8, 73, 88, 0.08);
    }
    body.template-mountain-illustrated th {
      background: #e1f4f6;
      color: #073d58;
    }
    body.template-elementary-pop .page:not(.cover) {
      background:
        radial-gradient(circle at 94% 4%, rgba(239,121,0,0.09), transparent 14%),
        radial-gradient(circle at 4% 96%, rgba(39,184,178,0.09), transparent 15%),
        #fffdf8;
    }
    body.template-elementary-pop .page-header {
      background: #fff7e8;
      border: 1px solid rgba(214,155,45,0.28);
      border-bottom: 4px solid __ORANGE__;
      border-radius: 18px;
      padding: 10px 12px;
    }
    body.template-elementary-pop .section,
    body.template-elementary-pop .soft-card,
    body.template-elementary-pop .goal-card,
    body.template-elementary-pop .staff-checklist {
      background: rgba(255,250,240,0.92);
      border-color: rgba(214,155,45,0.3);
      box-shadow: 0 5px 12px rgba(217,120,83,0.08);
    }
    body.template-elementary-pop th {
      background: #fff0d8;
      color: #275769;
    }
    body.template-alpine-photo .page:not(.cover) {
      background:
        linear-gradient(90deg, #071827 0 0.18in, transparent 0.18in),
        #ffffff;
    }
    body.template-alpine-photo .page-header {
      background: #0d1f35;
      border: 0;
      border-left: 7px solid #149fe3;
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
      border-left: 5px solid #149fe3;
    }
    body.template-alpine-photo th {
      background: #0d1f35;
      color: #ffffff;
    }
    body.template-botanical-frame .page:not(.cover) {
      background:
        radial-gradient(circle at 0 0, rgba(111,143,106,0.1), transparent 18%),
        radial-gradient(circle at 100% 100%, rgba(111,143,106,0.08), transparent 18%),
        #fbfaf5;
      border: 1px solid rgba(111,143,106,0.3);
    }
    body.template-botanical-frame .page-header {
      border: 1px solid rgba(111,143,106,0.35);
      border-bottom: 4px solid #6f8f6a;
      border-radius: 2px;
      justify-content: center;
      padding: 12px;
      text-align: center;
    }
    body.template-botanical-frame .page-header h2,
    body.template-botanical-frame h3 {
      font-family: Georgia, "Times New Roman", serif;
      letter-spacing: 0.04em;
    }
    body.template-botanical-frame .section,
    body.template-botanical-frame .soft-card,
    body.template-botanical-frame .goal-card {
      background: rgba(255,255,255,0.75);
      border-color: rgba(111,143,106,0.35);
      border-radius: 2px;
    }
    body.template-botanical-frame th {
      background: #edf4e9;
      color: #3f544c;
    }
    body.template-chalkboard .page:not(.cover) {
      background: #fbfbf7;
      border: 4px solid #1f2933;
    }
    body.template-chalkboard .page-header {
      background: #1f2933;
      border: 0;
      border-radius: 8px;
      color: #f8fafc;
      padding: 12px;
    }
    body.template-chalkboard .page-header h2,
    body.template-chalkboard .page-header .eyebrow {
      color: #f8fafc;
    }
    body.template-chalkboard .section,
    body.template-chalkboard .soft-card,
    body.template-chalkboard .goal-card {
      border: 2px dashed #475569;
      border-radius: 8px;
      box-shadow: none;
    }
    body.template-chalkboard th {
      background: #1f2933;
      color: #f8fafc;
    }
    body.template-soft-organic .page:not(.cover) {
      background:
        radial-gradient(circle at 98% 8%, rgba(204,168,119,0.11), transparent 16%),
        #fbf6ed;
    }
    body.template-soft-organic .page-header {
      background: rgba(255,255,255,0.65);
      border: 1px solid rgba(155,127,95,0.22);
      border-bottom: 4px solid #9b7f5f;
      border-radius: 22px;
      padding: 12px 14px;
    }
    body.template-soft-organic .section,
    body.template-soft-organic .soft-card,
    body.template-soft-organic .goal-card {
      background: rgba(255,255,255,0.72);
      border-color: rgba(155,127,95,0.22);
    }
    body.template-soft-organic th {
      background: #f1e4d0;
      color: #5f4d3e;
    }
    body.template-purple-dot .page:not(.cover) {
      background:
        radial-gradient(circle, rgba(126, 87, 194, 0.16) 0 1.5px, transparent 1.5px) right top / 16px 16px,
        #ffffff;
    }
    body.template-purple-dot .section,
    body.template-purple-dot .soft-card,
    body.template-purple-dot .goal-card {
      border-left: 6px solid #6d3fc0;
      border-radius: 0 12px 12px 0;
    }
    body.template-purple-dot th {
      background: #6d3fc0;
      color: #ffffff;
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
        .replace("__BODY_FONT__", _font_stack(font_name))
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


def _service_symbol(value: str) -> str:
    lowered = value.lower()
    if any(term in lowered for term in ("writing", "written", "expression")):
        return "W"
    if any(term in lowered for term in ("speech", "language", "communication")):
        return "S"
    return "R"


def _team_contacts_html(student: StudentResponse | None) -> str:
    if student is None:
        return """
          <div class="soft-card" style="margin-top: 18px;">
            <h3>Team Contacts</h3>
            <p><strong>Case Manager:</strong> Not entered</p>
          </div>
        """
    case_manager_name = student.case_manager or "Not entered"
    rows = [
        f"<p><strong>Case Manager:</strong> {escape(case_manager_name)}</p>",
        f"<p><strong>School:</strong> {escape(student.school or 'Not entered')}</p>",
    ]
    if student.case_manager_phone:
        rows.append(f"<p><strong>Phone:</strong> {escape(student.case_manager_phone)}</p>")
    if student.case_manager_email:
        rows.append(f"<p><strong>Email:</strong> {escape(student.case_manager_email)}</p>")
    if student.case_manager_notes:
        rows.append(
            f"<p><strong>Notes:</strong> {escape(student.case_manager_notes).replace(chr(10), '<br>')}</p>"
        )
    return (
        '<div class="soft-card" style="margin-top: 18px;">'
        "<h3>Team Contacts</h3>"
        + "".join(rows)
        + "</div>"
    )


def _build_packet_html(
    detail: ProjectDetail,
    *,
    theme_id: str,
    packet_template_id: str,
    packet_version_name: str,
    packet_config: PacketVersionConfig | None = None,
    customization: ThemeCustomization | None = None,
) -> str:
    student = detail.student
    student_name = student.name if student else "Student"
    service_names = sorted({area.name for area in detail.service_areas if area.name})

    rendered_pages: dict[str, str] = {}
    cover_chips = "".join(
        f"""
        <div class="service-chip">
          <span class="chip-dot">{escape(_service_symbol(name))}</span>
          <span>{escape(name)}</span>
        </div>
        """
        for name in service_names[:4]
    )
    service_count = min(len(service_names), 4)
    district_mark = (
        detail.brand_kit.district_name
        or detail.brand_kit.school_name
        or "District Branding"
    )
    watermark_src = (
        detail.brand_kit.watermark_logo_relative_path
        if detail.brand_kit.watermark_enabled and detail.brand_kit.watermark_logo_relative_path
        else ""
    )
    body_classes = [f"template-{packet_template_id.replace('_', '-')}"]
    if watermark_src:
        body_classes.append("has-watermark")
    identity_html = '<div class="cover-icon">SP</div>'
    if detail.brand_kit.logo_relative_path:
        logo_src = detail.brand_kit.logo_relative_path.replace("\\", "/")
        identity_html = f'<img class="brand-logo cover-logo" src="{escape(logo_src)}" alt="">'
    rendered_pages["cover"] = (
        f"""
        <section class="page cover">
          <div class="cover-card">
            <div class="cover-district-mark">{escape(district_mark)}</div>
            <div class="cover-content">
              {identity_html}
              <p class="cover-kicker">Special Education</p>
              <p class="cover-school">{escape(detail.brand_kit.school_name or (student.school if student and student.school else ""))}</p>
              <h1>Service<br>Packet</h1>
              <div class="cover-year">{escape(detail.school_year or "School Year")}</div>
              <p class="cover-student">{escape(student_name)}</p>
            </div>
            <div class="cover-bottom">
              <div class="cover-details">
              <div class="cover-services service-count-{service_count}">{cover_chips}</div>
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
              </div>
            </div>
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
        """
        <section class="page">
          <div class="page-header">
            <span class="badge">A</span>
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

    rendered_pages["accommodations"] = (
        """
        <section class="page">
          <div class="page-header green">
            <span class="badge green">A</span>
            <h2>Accommodations/Modifications</h2>
          </div>
          <div class="placeholder">Reserved for the future accommodations/modifications editor.</div>
        </section>
        """
    )
    rendered_pages["behavior"] = (
        """
        <section class="page">
          <div class="page-header green">
            <span class="badge green">B</span>
            <h2>Behavior Support</h2>
          </div>
          <div class="soft-card" style="text-align: center; padding: 76px 28px;">
            <h2 style="color: #73b85a;">No Behavior Intervention Plan</h2>
            <p>Behavior support content will be added alongside the future accommodations/modifications workflow.</p>
          </div>
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
              <span class="mini-dot {domain_class}"></span>
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
        """
        <section class="page">
          <div class="page-header">
            <span class="badge">G</span>
            <h2>Goal Summary</h2>
          </div>
        """
        + "".join(goal_sections)
        + "</section>"
    )

    rendered_pages["services"] = (
        """
        <section class="page">
          <div class="page-header">
            <span class="badge">S</span>
            <h2>Service Information</h2>
          </div>
          <h3>Service Areas</h3>
        """
        + "".join(
            f"""
            <div class="domain-title">
              <span class="mini-dot {_domain_class(area.name)}"></span>
              <strong>{escape(area.name)}</strong>
            </div>
            """
            for area in detail.service_areas
        )
        + """
          <h3 style="margin-top: 18px;">Weekly Service Minutes</h3>
        """
        + _table(
            ["Service", "Minutes per week", "Delivery", "Setting"],
            [
                [
                    area.name,
                    str(area.minutes_per_week) if area.minutes_per_week is not None else "Not entered",
                    _delivery_label(area.delivery_model),
                    area.setting or "Not entered",
                ]
                for area in detail.service_areas
            ],
        )
        + _team_contacts_html(student)
        + "</section>"
    )

    for sheet, goal, instance in _data_collection_items(detail):
        service_name = _service_area_name(detail, goal.service_area_id)
        domain_class = _domain_class(service_name)
        rendered_pages[f"data_collection_{sheet.id}_{goal.id}_{instance}"] = (
            f"""
            <section class="page">
              <div class="page-header {domain_class}">
                <span class="badge {domain_class}">D</span>
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
        <h3 style="color: #ef7900;">Things Staff Need To Tell {escape(student.case_manager if student and student.case_manager else "The Case Manager")}</h3>
        {_checklist_table(checklist_items)}
      </div>
    """

    if observation_forms:
        rendered_pages["observations"] = "".join(
            f"""
            <section class="page observation-page">
              <div class="page-header orange">
                <span class="badge orange">O</span>
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
              <div class="page-header orange">
                <span class="badge orange">N</span>
                <h2>Observations & Notes</h2>
              </div>
              <div class="observations-table">
                {_table(["Date", "Setting / Context", "Observation", "Follow-up / Action"], [], blank_rows=17)}
              </div>
              {checklist_html}
            </section>
            """
        )

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(detail.name)}</title><style>{_packet_styles(theme_id, customization or detail.theme_customization, watermark_src, detail.brand_kit.default_fonts)}</style>"
        f"</head><body class=\"{escape(' '.join(body_classes))}\">"
        + "".join(_ordered_packet_pages(rendered_pages, packet_config))
        + "</body></html>"
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
    export_dir = settings.data_dir / "exports" / project_id
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def _export_path_for_response(export: Export) -> Path:
    absolute = (export.metadata_json or {}).get("absolute_path")
    if isinstance(absolute, str) and absolute:
        return Path(absolute)
    return settings.data_dir / export.relative_path


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
        return render_pdf(PdfRenderRequest(html=html, base_url=str(settings.data_dir)))
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

    data_root = settings.data_dir.resolve()
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
    data_root = settings.data_dir.resolve()
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
    backup_dir = settings.data_dir / "backups" / project.id
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
    relative_path = output_path.relative_to(settings.data_dir).as_posix()
    return BackupResponse(
        filename=filename,
        relative_path=relative_path,
        absolute_path=str(output_path.resolve()),
        created_at=created_at,
        size_bytes=output_path.stat().st_size,
    )
