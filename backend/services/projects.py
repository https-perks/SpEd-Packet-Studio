from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import re
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from backend.config import settings
from backend.models import AtAGlance, Goal, PacketVersion, Project, ServiceArea, Student
from backend.schemas.projects import (
    AtAGlanceDraft,
    AtAGlanceResponse,
    GoalResponse,
    GoalsDraft,
    ProjectDetail,
    ProjectSummary,
    ServiceAreaResponse,
    StepValidation,
    StudentResponse,
    StudentSetupDraft,
    ValidationIssue,
)

AUDIENCE_LABELS = {
    "case_manager": "Case Manager",
    "general_education": "General Education",
    "paraeducator": "Paraeducator",
    "related_services": "Related Services",
    "substitute": "Substitute",
}


def _project_query():
    return select(Project).options(
        selectinload(Project.student),
        selectinload(Project.service_areas),
        selectinload(Project.goals),
        selectinload(Project.at_a_glance),
        selectinload(Project.packet_versions),
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


def _touch(project: Project) -> None:
    project.updated_at = datetime.now(timezone.utc)


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


def _detail(project: Project) -> ProjectDetail:
    draft = _student_setup_from_model(project)
    goals = [
        _goal_response(goal)
        for goal in sorted(project.goals, key=lambda item: item.position)
        if goal.deleted_at is None
    ]
    glance = _at_a_glance_response(project.at_a_glance)
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
        goals=goals,
        at_a_glance=glance,
        student_setup_validation=validate_student_setup(draft),
        goals_validation=validate_goals(goals),
        at_a_glance_validation=validate_at_a_glance(glance),
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
