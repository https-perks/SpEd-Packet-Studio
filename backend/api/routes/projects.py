from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database.session import get_session
from backend.schemas.projects import (
    AtAGlanceDraft,
    BackupResponse,
    DataSheetsDraft,
    ExportAllResponse,
    ExportRequest,
    ExportResponse,
    GoalsDraft,
    ObservationChecklistDraft,
    PacketBuilderDraft,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    StudentSetupDraft,
    ThemeOption,
    ThemeSelection,
)
from backend.services import projects

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/themes", response_model=list[ThemeOption])
def list_themes() -> list[ThemeOption]:
    return projects.list_themes()


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


@router.put("/{project_id}/data-sheets", response_model=ProjectDetail)
def save_data_sheets(
    project_id: str,
    value: DataSheetsDraft,
    session: Session = Depends(get_session),
) -> ProjectDetail:
    return projects.save_data_sheets(session, project_id, value)


@router.put("/{project_id}/theme", response_model=ProjectDetail)
def save_project_theme(
    project_id: str,
    value: ThemeSelection,
    session: Session = Depends(get_session),
) -> ProjectDetail:
    return projects.save_project_theme(session, project_id, value)


@router.put("/{project_id}/observation-checklist", response_model=ProjectDetail)
def save_observation_checklist(
    project_id: str,
    value: ObservationChecklistDraft,
    session: Session = Depends(get_session),
) -> ProjectDetail:
    return projects.save_observation_checklist(session, project_id, value)


@router.put("/{project_id}/packet-builder", response_model=ProjectDetail)
def save_packet_builder(
    project_id: str,
    value: PacketBuilderDraft,
    session: Session = Depends(get_session),
) -> ProjectDetail:
    return projects.save_packet_builder(session, project_id, value)


@router.post("/{project_id}/exports/pdf", response_model=ExportResponse, status_code=201)
def generate_pdf_export(
    project_id: str,
    value: ExportRequest | None = None,
    session: Session = Depends(get_session),
) -> ExportResponse:
    return projects.generate_pdf_export(session, project_id, value)


@router.post("/{project_id}/exports/pdf/all", response_model=ExportAllResponse, status_code=201)
def generate_all_pdf_exports(
    project_id: str,
    value: ExportRequest | None = None,
    session: Session = Depends(get_session),
) -> ExportAllResponse:
    return projects.generate_all_pdf_exports(session, project_id, value)


@router.post("/{project_id}/backup", response_model=BackupResponse, status_code=201)
def create_project_backup(
    project_id: str,
    session: Session = Depends(get_session),
) -> BackupResponse:
    return projects.create_project_backup(session, project_id)


@router.get("/{project_id}/exports/{export_id}/download")
def download_export(
    project_id: str,
    export_id: str,
    session: Session = Depends(get_session),
) -> FileResponse:
    path = projects.get_export_path(session, project_id, export_id)
    return FileResponse(path, media_type="application/pdf", filename=path.name)


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
