from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
from html import escape
import json
import re
from pathlib import Path
from typing import Iterable

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
    DataSheetResponse,
    DataSheetsDraft,
    ExportAllResponse,
    ExportRequest,
    ExportResponse,
    GoalResponse,
    GoalsDraft,
    ObservationChecklistDraft,
    PacketBuilderDraft,
    PacketPageDraft,
    PacketVersionResponse,
    PacketVersionConfig,
    AssetPlacementDraft,
    ProjectDetail,
    ProjectSummary,
    ServiceAreaResponse,
    StepValidation,
    StudentResponse,
    StudentSetupDraft,
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

THEME_OPTIONS = [
    ThemeOption(
        id="teacher_friendly",
        name="Teacher Friendly",
        description="Polished blue, teal, green, purple, and orange Version 1 packet theme.",
    ),
    ThemeOption(
        id="studio",
        name="Studio Legacy",
        description="Simple legacy packet theme.",
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


def suggest_school_year(iep_end_date: date | None) -> str:
    if iep_end_date is None:
        return ""
    start = iep_end_date.year if iep_end_date.month >= 7 else iep_end_date.year - 1
    return f"{start}-{start + 1}"


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-")
    return value.lower() or "student-packet"


def default_export_filename(student_name: str, school_year: str) -> str:
    pieces = [student_name, school_year, "service-packet"]
    return "-".join(_slug(piece) for piece in pieces if piece) + ".pdf"


def _delivery_label(value: str | None) -> str:
    if not value:
        return "Not selected"
    return " ".join(part.capitalize() for part in value.split("_"))


def _format_date(value: date | None) -> str:
    return value.isoformat() if value else "Not entered"


def _touch(project: Project) -> None:
    project.updated_at = datetime.now(timezone.utc)


def list_themes() -> list[ThemeOption]:
    return THEME_OPTIONS


def _theme_id(project: Project) -> str:
    value = (project.settings_json or {}).get("theme_id", "teacher_friendly")
    return value if value in THEME_TOKENS else "teacher_friendly"


def _observation_checklist(project: Project) -> list[str]:
    value = (project.settings_json or {}).get("observation_checklist")
    if not isinstance(value, list):
        return DEFAULT_OBSERVATION_CHECKLIST
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or DEFAULT_OBSERVATION_CHECKLIST


def _packet_version_responses(project: Project) -> list[PacketVersionResponse]:
    return [
        PacketVersionResponse(id=version.id, name=version.name, audience=version.audience)
        for version in sorted(project.packet_versions, key=lambda item: item.created_at)
        if version.deleted_at is None
    ]


def _default_packet_pages() -> list[PacketPageDraft]:
    return [
        PacketPageDraft(
            id=str(page["id"]),
            title=str(page["title"]),
            page_type=str(page["page_type"]),
            enabled=True,
            position=position,
        )
        for position, page in enumerate(DEFAULT_PACKET_PAGES)
    ]


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
    if not validate_student_setup(student_setup).is_complete:
        current_step = "student_setup"
    elif not validate_goals(goals).is_complete:
        current_step = "goals"
    elif not validate_at_a_glance(glance).is_complete:
        current_step = "at_a_glance"
    elif not validate_data_sheets(_data_sheet_responses(project)).is_complete:
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
                student.case_manager if student and student.case_manager else ""
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
            deepcopy(configuration.get("columns") or DEFAULT_DATA_SHEET_COLUMNS),
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
    session: Session, *, archived: bool = False, search: str = ""
) -> list[ProjectSummary]:
    query = _project_query()
    query = query.where(
        Project.archived_at.is_not(None) if archived else Project.archived_at.is_(None)
    )
    if search.strip():
        term = f"%{search.strip()}%"
        query = (
            query.join(Student, Student.project_id == Project.id, isouter=True)
            .where(
                or_(
                    Project.name.ilike(term),
                    Student.first_name.ilike(term),
                    Student.last_name.ilike(term),
                    Project.school_year.ilike(term),
                )
            )
        )
    projects = session.scalars(query.order_by(Project.updated_at.desc())).unique()
    return [_summary(project) for project in projects]


def create_project(session: Session, name: str | None = None) -> ProjectDetail:
    project = Project(
        name=name.strip() if name and name.strip() else "Untitled Student Project",
        schema_version=settings.schema_version,
        app_version=settings.app_version,
        settings_json={},
    )
    session.add(project)
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
    student.case_manager = draft.student.case_manager.strip() or None
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
                    settings_json={},
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
    if selection.theme_id not in THEME_TOKENS:
        raise HTTPException(status_code=422, detail="Unknown packet theme.")
    project = get_project(session, project_id)
    settings_json = deepcopy(project.settings_json or {})
    settings_json["theme_id"] = selection.theme_id
    project.settings_json = settings_json
    _touch(project)
    session.commit()
    session.expire_all()
    return _detail(get_project(session, project.id))


def duplicate_project(session: Session, project_id: str) -> ProjectDetail:
    source = get_project(session, project_id)
    duplicate = Project(
        name=f"{source.name} (Copy)",
        description=source.description,
        school_year=source.school_year,
        schema_version=settings.schema_version,
        app_version=settings.app_version,
        default_export_filename=source.default_export_filename,
        settings_json=deepcopy(source.settings_json),
    )
    session.add(duplicate)
    session.flush()

    if source.student:
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
    for area in source.service_areas:
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

    for goal in source.goals:
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
    if source.at_a_glance:
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
    for sheet in source.data_sheets:
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
    for version in source.packet_versions:
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


def _packet_styles(theme_id: str) -> str:
    tokens = THEME_TOKENS.get(theme_id, THEME_TOKENS["teacher_friendly"])
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
      font-family: "Open Sans", "Segoe UI", Arial, sans-serif;
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
      background: #ffffff;
      break-after: page;
      box-shadow: 0 3px 14px rgba(15, 45, 85, 0.16);
      min-height: 9.55in;
      padding: 0.08in;
      position: relative;
    }
    .page:last-child { break-after: auto; }
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
        radial-gradient(circle at 75% 20%, rgba(39, 184, 178, 0.34), transparent 20%),
        linear-gradient(135deg, #0f2d55 0%, #123d73 58%, #0a2243 100%);
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
    .cover-kicker {
      color: #64ddd8;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.34em;
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
      border: 1px solid __BORDER__;
      border-radius: 14px;
      margin-bottom: 11px;
      overflow: hidden;
      padding: 14px;
      overflow-wrap: anywhere;
    }
    .soft-card {
      background: __SOFT__;
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
      background: #fbfdff;
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


def _build_packet_html(
    detail: ProjectDetail,
    *,
    theme_id: str,
    packet_version_name: str,
    packet_config: PacketVersionConfig | None = None,
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
    rendered_pages["cover"] = (
        f"""
        <section class="page cover">
          <div class="cover-card">
            <p class="cover-kicker">Special Education</p>
            <h1>Service<br>Packet</h1>
            <div class="cover-year">{escape(detail.school_year or "School Year")}</div>
            <div class="cover-details">
              <p class="cover-student">{escape(student_name)}</p>
              <div class="cover-services">{cover_chips}</div>
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
        + f"""
          <div class="soft-card" style="margin-top: 18px;">
            <h3>Team Contacts</h3>
            <p><strong>Case Manager:</strong> {escape(student.case_manager if student and student.case_manager else "Not entered")}</p>
            <p><strong>School:</strong> {escape(student.school if student and student.school else "Not entered")}</p>
          </div>
        """
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
        f"<title>{escape(detail.name)}</title><style>{_packet_styles(theme_id)}</style>"
        "</head><body>"
        + "".join(_ordered_packet_pages(rendered_pages, packet_config))
        + "</body></html>"
    )


def _export_response(export: Export, project_id: str) -> ExportResponse:
    export_path = settings.data_dir / export.relative_path
    return ExportResponse(
        id=export.id,
        filename=Path(export.relative_path).name,
        relative_path=export.relative_path,
        absolute_path=str(export_path.resolve()),
        generated_at=export.generated_at,
        content_hash=export.content_hash,
        size_bytes=export_path.stat().st_size if export_path.exists() else 0,
        download_url=f"/projects/{project_id}/exports/{export.id}/download",
    )


def generate_pdf_export(
    session: Session, project_id: str, request: ExportRequest | None = None
) -> ExportResponse:
    request = request or ExportRequest()
    if request.theme_id not in THEME_TOKENS:
        raise HTTPException(status_code=422, detail="Unknown packet theme.")
    project = get_project(session, project_id)
    detail = _detail(project)
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

    packet = _resolve_packet_version(project, session, request.packet_version_id)
    html = _build_packet_html(
        detail,
        theme_id=request.theme_id,
        packet_version_name=packet.name,
        packet_config=_packet_config(packet),
    )
    try:
        pdf_bytes = render_pdf(PdfRenderRequest(html=html, base_url=str(settings.data_dir)))
    except RuntimeError as reason:
        raise HTTPException(status_code=503, detail=str(reason)) from reason
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    filename = detail.default_export_filename or default_export_filename(
        detail.student.name if detail.student else "", detail.school_year
    )
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    generated_at = datetime.now(timezone.utc)
    output_stem = Path(filename).stem
    output_suffix = Path(filename).suffix or ".pdf"
    timestamp = generated_at.strftime("%Y%m%d-%H%M%S")
    filename = f"{output_stem}-{timestamp}{output_suffix}"
    export_dir = settings.data_dir / "exports" / project.id
    export_dir.mkdir(parents=True, exist_ok=True)
    output_path = export_dir / filename
    output_path.write_bytes(pdf_bytes)

    export = Export(
        packet_version_id=packet.id,
        format="pdf",
        relative_path=output_path.relative_to(settings.data_dir).as_posix(),
        content_hash=content_hash,
        generated_at=generated_at,
        metadata_json={
            "page_count_source": "deterministic_packet_builder",
            "schema_version": settings.schema_version,
            "theme_id": request.theme_id,
            "packet_version_id": packet.id,
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
            ExportRequest(packet_version_id=version.id, theme_id=request.theme_id),
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
    path = (settings.data_dir / export.relative_path).resolve()
    data_root = settings.data_dir.resolve()
    if data_root not in path.parents and path != data_root:
        raise HTTPException(status_code=400, detail="Export path is invalid.")
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
