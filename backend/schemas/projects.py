from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from backend.schemas.system import ApiSchema

Audience = str
DEFAULT_SERVICE_AREA_COLORS = {
    "Math": "#22C55E",
    "Reading": "#2563EB",
    "Written Expression": "#8B5CF6",
    "S/E/B": "#F59E0B",
    "SH/I": "#E11D48",
    "Communication": "#06B6D4",
    "Speech/Language": "#6366F1",
}


class ValidationIssue(ApiSchema):
    field: str
    message: str


class StepValidation(ApiSchema):
    is_complete: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class ProjectCreate(ApiSchema):
    name: str | None = Field(default=None, max_length=200)


class ProjectSearchFilters(ApiSchema):
    archived: bool = False
    search: str = Field(default="", max_length=200)
    grade: str = Field(default="", max_length=32)
    school_year: str = Field(default="", max_length=20)
    case_manager: str = Field(default="", max_length=200)
    service_area: str = Field(default="", max_length=160)
    theme_id: str = Field(default="", max_length=80)
    missing_data_sheets: bool = False


class DuplicateOptions(ApiSchema):
    student_information: bool = True
    service_areas: bool = True
    goals: bool = True
    at_a_glance: bool = False
    observation_notes: bool = False
    data_sheets: bool = False
    theme: bool = True
    template: bool = True
    packet_layout: bool = True


class BulkProjectAction(ApiSchema):
    project_ids: list[str] = Field(default_factory=list, min_length=1)
    action: Literal[
        "archive",
        "restore",
        "duplicate",
        "assign_theme",
        "update_template",
        "update_school_year",
        "assign_export_location",
        "export",
        "delete",
        "rename",
    ]
    theme_id: str | None = None
    packet_template_id: str | None = None
    school_year: str | None = Field(default=None, max_length=20)
    export_location: str | None = Field(default=None, max_length=1024)
    project_name: str | None = Field(default=None, max_length=240)
    duplicate_options: DuplicateOptions = Field(default_factory=DuplicateOptions)


class StudentDraft(ApiSchema):
    name: str = Field(default="", max_length=200)
    initials: str = Field(default="", max_length=12)
    grade: str = Field(default="", max_length=32)
    school: str = Field(default="", max_length=200)
    case_manager: str = Field(default="", max_length=200)
    case_manager_first_name: str = Field(default="", max_length=100)
    case_manager_last_name: str = Field(default="", max_length=100)
    case_manager_phone: str = Field(default="", max_length=80)
    case_manager_email: str = Field(default="", max_length=200)
    case_manager_notes: str = Field(default="", max_length=1000)
    iep_end_date: date | None = None

    @field_validator("iep_end_date", mode="before")
    @classmethod
    def normalize_blank_date(cls, value: object) -> object:
        return None if value == "" else value


class ServiceAreaDraft(ApiSchema):
    id: str | None = None
    name: str = Field(default="", max_length=160)
    setting: str = Field(default="", max_length=200)
    minutes_per_week: int | None = Field(default=None, ge=0, le=10080)
    notes: str = ""
    position: int = Field(default=0, ge=0)

    @field_validator("id", "minutes_per_week", mode="before")
    @classmethod
    def normalize_blank_optional_values(cls, value: object) -> object:
        return None if value == "" else value


class AccommodationDraft(ApiSchema):
    id: str | None = None
    content_area: str = Field(default="Instructional", max_length=120)
    custom_content_area: str = Field(default="", max_length=160)
    text: str = Field(default="", max_length=5000)
    position: int = Field(default=0, ge=0)

    @field_validator("id", mode="before")
    @classmethod
    def normalize_blank_id(cls, value: object) -> object:
        return None if value == "" else value


class BehaviorPlanSectionDraft(ApiSchema):
    id: str | None = None
    title: str = Field(default="", max_length=180)
    text: str = Field(default="", max_length=5000)
    position: int = Field(default=0, ge=0)

    @field_validator("id", mode="before")
    @classmethod
    def normalize_blank_id(cls, value: object) -> object:
        return None if value == "" else value


class RelatedServiceProviderDraft(ApiSchema):
    id: str | None = None
    name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=80)
    service_area: str = Field(default="Speech/Language Pathologist", max_length=200)
    position: int = Field(default=0, ge=0)

    @field_validator("id", mode="before")
    @classmethod
    def normalize_blank_id(cls, value: object) -> object:
        return None if value == "" else value


class StudentSetupDraft(ApiSchema):
    project_name: str = Field(default="", max_length=200)
    school_year: str = Field(default="", max_length=20)
    student: StudentDraft = Field(default_factory=StudentDraft)
    service_areas: list[ServiceAreaDraft] = Field(default_factory=list)
    audiences: list[Audience] = Field(default_factory=list)
    accommodations: list[AccommodationDraft] = Field(default_factory=list)
    accommodations_parent_strengths_enabled: bool = False
    accommodations_parent_strengths: str = Field(default="", max_length=5000)
    behavior_plan: str = Field(default="", max_length=10000)
    behavior_plan_sections: list[BehaviorPlanSectionDraft] = Field(default_factory=list)
    related_service_providers: list[RelatedServiceProviderDraft] = Field(default_factory=list)


class GoalDraft(ApiSchema):
    id: str | None = None
    title: str = Field(default="", max_length=240)
    statement: str = ""
    data_sheet_summary: str = ""
    service_area_id: str | None = None
    mastery_criteria: str = ""
    progress_monitoring_method: str = ""
    instructional_notes: str = ""
    position: int = Field(default=0, ge=0)


class GoalsDraft(ApiSchema):
    goals: list[GoalDraft] = Field(default_factory=list)


class AtAGlanceSectionDraft(ApiSchema):
    id: str = Field(max_length=80)
    title: str = Field(max_length=120)
    content: str = ""
    enabled: bool = True
    position: int = Field(default=0, ge=0)


class AtAGlanceDraft(ApiSchema):
    sections: list[AtAGlanceSectionDraft] = Field(default_factory=list)


class StudentResponse(StudentDraft):
    id: str


class ServiceAreaResponse(ServiceAreaDraft):
    id: str


class GoalResponse(GoalDraft):
    id: str


class AtAGlanceResponse(ApiSchema):
    id: str | None = None
    sections: list[AtAGlanceSectionDraft] = Field(default_factory=list)


DataSheetType = Literal["trial_count", "frequency", "duration", "rubric", "notes"]
DataSheetColumnType = Literal["text", "number", "date", "checkbox", "notes"]


class DataSheetColumnDraft(ApiSchema):
    id: str = Field(max_length=80)
    title: str = Field(default="", max_length=120)
    column_type: DataSheetColumnType = "text"
    position: int = Field(default=0, ge=0)


class DataSheetDraft(ApiSchema):
    id: str | None = None
    title: str = Field(default="", max_length=240)
    sheet_type: DataSheetType | None = None
    goal_ids: list[str] = Field(default_factory=list)
    collection_schedule: str = Field(default="", max_length=240)
    blank_instance_count: int = Field(default=1, ge=1, le=100)
    columns: list[DataSheetColumnDraft] = Field(default_factory=list)
    notes: str = ""
    template_name: str = Field(default="", max_length=160)
    is_template: bool = False
    is_observation_form: bool = False
    position: int = Field(default=0, ge=0)


class DataSheetsDraft(ApiSchema):
    data_sheets: list[DataSheetDraft] = Field(default_factory=list)


class DataSheetResponse(DataSheetDraft):
    id: str


class ExportResponse(ApiSchema):
    id: str
    filename: str
    relative_path: str
    absolute_path: str
    generated_at: datetime
    content_hash: str
    size_bytes: int
    download_url: str


class ExportAllResponse(ApiSchema):
    exports: list[ExportResponse] = Field(default_factory=list)


class ExportRequest(ApiSchema):
    packet_version_id: str | None = None
    theme_id: str = "teacher_friendly"
    packet_template_id: str | None = None
    filename_template: str | None = Field(default=None, max_length=240)
    export_mode: Literal["single_pdf", "zip_archive"] = "single_pdf"


class PacketVersionResponse(ApiSchema):
    id: str
    name: str
    audience: str


class PacketVersionDraft(ApiSchema):
    id: str | None = Field(default=None, max_length=80)
    name: str = Field(default="", max_length=200)
    audience: str = Field(default="", max_length=120)


class PacketPageDraft(ApiSchema):
    id: str = Field(max_length=80)
    title: str = Field(max_length=160)
    page_type: str = Field(max_length=80)
    enabled: bool = True
    position: int = Field(default=0, ge=0)
    body_text: str = Field(default="", max_length=10000)


class AssetPlacementDraft(ApiSchema):
    id: str = Field(max_length=80)
    label: str = Field(default="", max_length=160)
    page_id: str = Field(default="", max_length=80)
    position: int = Field(default=0, ge=0)
    notes: str = ""


class PacketVersionConfig(ApiSchema):
    packet_version_id: str
    pages: list[PacketPageDraft] = Field(default_factory=list)
    asset_placements: list[AssetPlacementDraft] = Field(default_factory=list)


class PacketBuilderDraft(ApiSchema):
    packet_versions: list[PacketVersionConfig] = Field(default_factory=list)


class ThemeOption(ApiSchema):
    id: str
    name: str
    description: str
    category: str = "Built-in"
    default_customization: dict[str, object] = Field(default_factory=dict)
    is_builtin: bool = True


class PacketTemplateOption(ApiSchema):
    id: str
    name: str
    description: str
    page_count_hint: str


class ThemeCustomization(ApiSchema):
    primary_color: str = Field(default="#0f2d55", max_length=24)
    secondary_color: str = Field(default="#27b8b2", max_length=24)
    accent_color: str = Field(default="#ef7900", max_length=24)
    background_color: str = Field(default="#f3f7fc", max_length=24)
    card_color: str = Field(default="#ffffff", max_length=24)
    text_color: str = Field(default="#12213a", max_length=24)
    service_area_colors: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_SERVICE_AREA_COLORS))


class ThemePaletteDraft(ApiSchema):
    name: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=400)
    category: str = Field(default="Custom", max_length=120)
    customization: ThemeCustomization = Field(default_factory=ThemeCustomization)


class BrandKit(ApiSchema):
    id: str = Field(default="personal", max_length=80)
    name: str = Field(default="Personal Brand Kit", max_length=160)
    district_name: str = Field(default="", max_length=200)
    school_name: str = Field(default="", max_length=200)
    district_logo_label: str = Field(default="", max_length=200)
    school_logo_label: str = Field(default="", max_length=200)
    logo_relative_path: str = Field(default="", max_length=1024)
    logo_filename: str = Field(default="", max_length=255)
    watermark_logo_relative_path: str = Field(default="", max_length=1024)
    watermark_logo_filename: str = Field(default="", max_length=255)
    watermark_enabled: bool = False
    default_fonts: str = Field(default="", max_length=200)
    heading_font: str = Field(default="", max_length=200)
    body_font: str = Field(default="", max_length=200)
    primary_color: str = Field(default="#0f2d55", max_length=24)
    secondary_color: str = Field(default="#27b8b2", max_length=24)
    accent_color: str = Field(default="#ef7900", max_length=24)
    preferred_cover_style: str = Field(default="modern_professional", max_length=80)
    footer_text: str = Field(default="", max_length=300)
    default_filename_template: str = Field(
        default="",
        max_length=240,
    )


class ExportSettings(ApiSchema):
    filename_template: str = Field(
        default="",
        max_length=240,
    )
    last_export_location: str = Field(default="", max_length=1024)
    export_mode: Literal["single_pdf", "zip_archive"] = "single_pdf"


class ThemeSelection(ApiSchema):
    theme_id: str = "teacher_friendly"
    packet_template_id: str = "modern_professional"
    customization: ThemeCustomization = Field(default_factory=ThemeCustomization)
    brand_kit: BrandKit = Field(default_factory=BrandKit)


class BrandLogoUpload(ApiSchema):
    filename: str = Field(max_length=255)
    content_type: str = Field(max_length=100)
    data_base64: str


class PacketTemplateLibraryItem(PacketTemplateOption):
    base_template_id: str = "modern_professional"
    theme_id: str = "teacher_friendly"
    customization: ThemeCustomization = Field(default_factory=ThemeCustomization)
    is_builtin: bool = False
    is_default: bool = False
    is_hidden: bool = False


class PacketTemplateLibraryDraft(ApiSchema):
    name: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=300)
    base_template_id: str = Field(default="modern_professional", max_length=80)
    theme_id: str = Field(default="teacher_friendly", max_length=80)
    customization: ThemeCustomization = Field(default_factory=ThemeCustomization)


class TemplatePreviewRequest(PacketTemplateLibraryDraft):
    pass


class BrandKitLibraryItem(BrandKit):
    is_default: bool = False


class BrandKitLibraryDraft(ApiSchema):
    name: str = Field(default="Brand Kit", max_length=160)
    district_name: str = Field(default="", max_length=200)
    school_name: str = Field(default="", max_length=200)
    district_logo_label: str = Field(default="", max_length=200)
    school_logo_label: str = Field(default="", max_length=200)
    logo_relative_path: str = Field(default="", max_length=1024)
    logo_filename: str = Field(default="", max_length=255)
    watermark_logo_relative_path: str = Field(default="", max_length=1024)
    watermark_logo_filename: str = Field(default="", max_length=255)
    watermark_enabled: bool = False
    default_fonts: str = Field(default="", max_length=200)
    heading_font: str = Field(default="", max_length=200)
    body_font: str = Field(default="", max_length=200)
    primary_color: str = Field(default="#0f2d55", max_length=24)
    secondary_color: str = Field(default="#27b8b2", max_length=24)
    accent_color: str = Field(default="#ef7900", max_length=24)
    preferred_cover_style: str = Field(default="modern_professional", max_length=80)
    footer_text: str = Field(default="", max_length=300)
    default_filename_template: str = Field(default="", max_length=240)


class BrandKitLogoUpload(BrandLogoUpload):
    brand_kit_id: str = Field(max_length=80)
    logo_kind: Literal["cover", "watermark"] = "cover"


class ExportSettingsSelection(ApiSchema):
    export_settings: ExportSettings = Field(default_factory=ExportSettings)


class ObservationChecklistDraft(ApiSchema):
    items: list[str] = Field(default_factory=list)


class CaseManagerProfile(ApiSchema):
    first_name: str = Field(default="", max_length=100)
    last_name: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=200)
    school: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=1000)


class AppSettings(ApiSchema):
    terminology_preference: Literal["sped", "ese", "ess"] | None = None
    default_school_year: str = Field(default="", max_length=20)
    default_theme_id: str = Field(default="teacher_friendly", max_length=80)
    default_packet_template_id: str = Field(default="modern_professional", max_length=80)
    default_export_settings: ExportSettings = Field(default_factory=ExportSettings)
    packet_versions: list[PacketVersionDraft] = Field(default_factory=list)
    default_packet_pages: list[PacketPageDraft] = Field(default_factory=list)
    default_observation_checklist: list[str] = Field(default_factory=list)
    accommodations_teacher_note_enabled: bool = True
    accommodations_teacher_note_title: str = Field(default="Teacher Responsibilities", max_length=160)
    accommodations_teacher_note: str = Field(default="", max_length=2000)
    accommodations_signature_page_enabled: bool = False
    accommodations_signature_page_title: str = Field(default="Accommodations Signature Page", max_length=160)
    accommodations_signature_page_note: str = Field(default="", max_length=2000)
    accommodations_signature_line_layout: Literal["teacher_coach_date", "staff_position_date"] = "teacher_coach_date"
    default_data_sheet_columns: list[DataSheetColumnDraft] = Field(default_factory=list)
    data_sheet_templates: list[DataSheetDraft] = Field(default_factory=list)
    service_area_presets: list[ServiceAreaDraft] = Field(default_factory=list)
    case_manager_profile: CaseManagerProfile = Field(default_factory=CaseManagerProfile)


class BackupResponse(ApiSchema):
    filename: str
    relative_path: str
    absolute_path: str
    created_at: datetime
    size_bytes: int


class ProjectSummary(ApiSchema):
    id: str
    name: str
    student_name: str
    school_year: str
    grade: str
    updated_at: datetime
    archived: bool
    case_manager: str = ""
    service_areas: list[str] = Field(default_factory=list)
    theme_id: str = "teacher_friendly"
    missing_data_sheets: bool = False
    current_step: Literal["student_setup", "goals", "at_a_glance", "data_sheets", "complete"]


class BulkProjectActionResponse(ApiSchema):
    projects: list[ProjectSummary] = Field(default_factory=list)
    duplicated_projects: list[ProjectDetail] = Field(default_factory=list)
    exports: list[ExportResponse] = Field(default_factory=list)
    deleted_project_ids: list[str] = Field(default_factory=list)


class ProjectDetail(ApiSchema):
    id: str
    name: str
    school_year: str
    default_export_filename: str
    student: StudentResponse | None
    service_areas: list[ServiceAreaResponse]
    audiences: list[Audience]
    accommodations: list[AccommodationDraft] = Field(default_factory=list)
    accommodations_parent_strengths_enabled: bool = False
    accommodations_parent_strengths: str = ""
    behavior_plan: str = ""
    behavior_plan_sections: list[BehaviorPlanSectionDraft] = Field(default_factory=list)
    related_service_providers: list[RelatedServiceProviderDraft] = Field(default_factory=list)
    packet_versions: list[PacketVersionResponse]
    packet_builder: list[PacketVersionConfig] = Field(default_factory=list)
    observation_checklist: list[str] = Field(default_factory=list)
    theme_id: str
    packet_template_id: str
    theme_customization: ThemeCustomization
    brand_kit: BrandKit
    export_settings: ExportSettings
    goals: list[GoalResponse]
    at_a_glance: AtAGlanceResponse
    data_sheets: list[DataSheetResponse]
    student_setup_validation: StepValidation
    goals_validation: StepValidation
    at_a_glance_validation: StepValidation
    data_sheets_validation: StepValidation
    updated_at: datetime
