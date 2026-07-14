from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend.database.session import get_session
from backend.schemas.projects import (
    AtAGlanceDraft,
    AppSettings,
    BackupResponse,
    BrandKitLibraryDraft,
    BrandKitLibraryItem,
    BrandKitLogoUpload,
    BrandLogoUpload,
    BulkProjectAction,
    BulkProjectActionResponse,
    DataSheetsDraft,
    DuplicateOptions,
    ExportAllResponse,
    ExportSettingsSelection,
    ExportRequest,
    ExportResponse,
    GoalsDraft,
    ObservationChecklistDraft,
    PacketBuilderDraft,
    PacketTemplateLibraryDraft,
    PacketTemplateLibraryItem,
    PacketTemplateOption,
    TemplatePreviewRequest,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    StudentSetupDraft,
    ThemePaletteDraft,
    ThemeOption,
    ThemeSelection,
)
from backend.services import projects

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/app-settings", response_model=AppSettings)
def get_app_settings() -> AppSettings:
    return projects.get_app_settings()


@router.put("/app-settings", response_model=AppSettings)
def save_app_settings(value: AppSettings) -> AppSettings:
    return projects.save_app_settings(value)


@router.get("/themes", response_model=list[ThemeOption])
def list_themes() -> list[ThemeOption]:
    return projects.list_themes()


@router.post("/themes", response_model=ThemeOption, status_code=201)
def create_theme_palette(value: ThemePaletteDraft) -> ThemeOption:
    return projects.create_theme_palette(value)


@router.put("/themes/{theme_id}", response_model=ThemeOption)
def update_theme_palette(theme_id: str, value: ThemePaletteDraft) -> ThemeOption:
    return projects.update_theme_palette(theme_id, value)


@router.delete("/themes/{theme_id}", status_code=204)
def delete_theme_palette(theme_id: str) -> None:
    projects.delete_theme_palette(theme_id)


@router.get("/packet-templates", response_model=list[PacketTemplateOption])
def list_packet_templates() -> list[PacketTemplateOption]:
    return projects.list_packet_templates()


@router.get("/template-library", response_model=list[PacketTemplateLibraryItem])
def list_template_library() -> list[PacketTemplateLibraryItem]:
    return projects.list_template_library()


@router.get("/template-library/hidden", response_model=list[PacketTemplateLibraryItem])
def list_hidden_template_library() -> list[PacketTemplateLibraryItem]:
    return projects.list_hidden_template_library()


@router.post("/template-library", response_model=PacketTemplateLibraryItem, status_code=201)
def create_template_library_item(value: PacketTemplateLibraryDraft) -> PacketTemplateLibraryItem:
    return projects.create_template_library_item(value)


@router.put("/template-library/{template_id}", response_model=PacketTemplateLibraryItem)
def update_template_library_item(
    template_id: str,
    value: PacketTemplateLibraryDraft,
) -> PacketTemplateLibraryItem:
    return projects.update_template_library_item(template_id, value)


@router.post("/template-library/{template_id}/duplicate", response_model=PacketTemplateLibraryItem, status_code=201)
def duplicate_template_library_item(template_id: str) -> PacketTemplateLibraryItem:
    return projects.duplicate_template_library_item(template_id)


@router.post("/template-library/{template_id}/default", response_model=list[PacketTemplateLibraryItem])
def set_default_template(template_id: str) -> list[PacketTemplateLibraryItem]:
    return projects.set_default_template(template_id)


@router.post("/template-library/{template_id}/restore", response_model=list[PacketTemplateLibraryItem])
def restore_template_library_item(template_id: str) -> list[PacketTemplateLibraryItem]:
    return projects.restore_template_library_item(template_id)


@router.delete("/template-library/{template_id}", status_code=204)
def delete_template_library_item(template_id: str) -> None:
    projects.delete_template_library_item(template_id)


@router.post("/template-library/preview")
def preview_template_library_item(value: TemplatePreviewRequest) -> Response:
    return Response(
        projects.preview_template_library_item(value),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="template-preview.pdf"'},
    )


@router.get("/brand-kits", response_model=list[BrandKitLibraryItem])
def list_brand_kits() -> list[BrandKitLibraryItem]:
    return projects.list_brand_kits()


@router.post("/brand-kits", response_model=BrandKitLibraryItem, status_code=201)
def create_brand_kit(value: BrandKitLibraryDraft) -> BrandKitLibraryItem:
    return projects.create_brand_kit(value)


@router.put("/brand-kits/{brand_kit_id}", response_model=BrandKitLibraryItem)
def update_brand_kit(
    brand_kit_id: str,
    value: BrandKitLibraryDraft,
) -> BrandKitLibraryItem:
    return projects.update_brand_kit(brand_kit_id, value)


@router.post("/brand-kits/{brand_kit_id}/duplicate", response_model=BrandKitLibraryItem, status_code=201)
def duplicate_brand_kit(brand_kit_id: str) -> BrandKitLibraryItem:
    return projects.duplicate_brand_kit(brand_kit_id)


@router.post("/brand-kits/{brand_kit_id}/default", response_model=list[BrandKitLibraryItem])
def set_default_brand_kit(brand_kit_id: str) -> list[BrandKitLibraryItem]:
    return projects.set_default_brand_kit(brand_kit_id)


@router.post("/brand-kits/logo", response_model=BrandKitLibraryItem, status_code=201)
def upload_brand_kit_logo(value: BrandKitLogoUpload) -> BrandKitLibraryItem:
    return projects.upload_brand_kit_logo(value)


@router.delete("/brand-kits/{brand_kit_id}", status_code=204)
def delete_brand_kit(brand_kit_id: str) -> None:
    projects.delete_brand_kit(brand_kit_id)


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    archived: bool = False,
    search: str = Query(default="", max_length=200),
    grade: str = Query(default="", max_length=32),
    school_year: str = Query(default="", max_length=20),
    case_manager: str = Query(default="", max_length=200),
    service_area: str = Query(default="", max_length=160),
    theme_id: str = Query(default="", max_length=80),
    missing_data_sheets: bool = False,
    session: Session = Depends(get_session),
) -> list[ProjectSummary]:
    return projects.list_projects(
        session,
        archived=archived,
        search=search,
        grade=grade,
        school_year=school_year,
        case_manager=case_manager,
        service_area=service_area,
        theme_id=theme_id,
        missing_data_sheets=missing_data_sheets,
    )


@router.post("/bulk-action", response_model=BulkProjectActionResponse)
def apply_bulk_project_action(
    value: BulkProjectAction,
    session: Session = Depends(get_session),
) -> BulkProjectActionResponse:
    return projects.apply_bulk_project_action(session, value)


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


@router.post("/{project_id}/brand-kit/logo", response_model=ProjectDetail, status_code=201)
def upload_brand_logo(
    project_id: str,
    value: BrandLogoUpload,
    session: Session = Depends(get_session),
) -> ProjectDetail:
    return projects.upload_brand_logo(session, project_id, value)


@router.put("/{project_id}/export-settings", response_model=ProjectDetail)
def save_export_settings(
    project_id: str,
    value: ExportSettingsSelection,
    session: Session = Depends(get_session),
) -> ProjectDetail:
    return projects.save_export_settings(session, project_id, value)


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


@router.post("/{project_id}/exports/preview")
def preview_pdf_export(
    project_id: str,
    value: ExportRequest | None = None,
    session: Session = Depends(get_session),
) -> Response:
    return Response(
        projects.preview_pdf(session, project_id, value),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="packet-preview.pdf"'},
    )


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
    media_type = "application/zip" if path.suffix.lower() == ".zip" else "application/pdf"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.post("/{project_id}/duplicate", response_model=ProjectDetail, status_code=201)
def duplicate_project(
    project_id: str,
    value: DuplicateOptions | None = None,
    session: Session = Depends(get_session),
) -> ProjectDetail:
    return projects.duplicate_project(session, project_id, value)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    session: Session = Depends(get_session),
) -> None:
    projects.delete_project(session, project_id)


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
