from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database.session import get_session
from backend.schemas.projects import (
    AtAGlanceDraft,
    GoalsDraft,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    StudentSetupDraft,
)
from backend.services import projects

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    archived: bool = False,
    search: str = Query(default="", max_length=200),
    session: Session = Depends(get_session),
) -> list[ProjectSummary]:
    return projects.list_projects(session, archived=archived, search=search)


@router.post("", response_model=ProjectDetail, status_code=201)
def create_project(
    value: ProjectCreate, session: Session = Depends(get_session)
) -> ProjectDetail:
    return projects.create_project(session, value.name)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: str, session: Session = Depends(get_session)
) -> ProjectDetail:
    return projects.project_detail(session, project_id)


@router.put("/{project_id}/student-setup", response_model=ProjectDetail)
def save_student_setup(
    project_id: str,
    value: StudentSetupDraft,
    session: Session = Depends(get_session),
) -> ProjectDetail:
    return projects.save_student_setup(session, project_id, value)


@router.put("/{project_id}/goals", response_model=ProjectDetail)
def save_goals(
    project_id: str,
    value: GoalsDraft,
    session: Session = Depends(get_session),
) -> ProjectDetail:
    return projects.save_goals(session, project_id, value)


@router.put("/{project_id}/at-a-glance", response_model=ProjectDetail)
def save_at_a_glance(
    project_id: str,
    value: AtAGlanceDraft,
    session: Session = Depends(get_session),
) -> ProjectDetail:
    return projects.save_at_a_glance(session, project_id, value)


@router.post("/{project_id}/duplicate", response_model=ProjectDetail, status_code=201)
def duplicate_project(
    project_id: str, session: Session = Depends(get_session)
) -> ProjectDetail:
    return projects.duplicate_project(session, project_id)


@router.post("/{project_id}/archive", response_model=ProjectSummary)
def archive_project(
    project_id: str, session: Session = Depends(get_session)
) -> ProjectSummary:
    return projects.set_archived(session, project_id, True)


@router.post("/{project_id}/restore", response_model=ProjectSummary)
def restore_project(
    project_id: str, session: Session = Depends(get_session)
) -> ProjectSummary:
    return projects.set_archived(session, project_id, False)
