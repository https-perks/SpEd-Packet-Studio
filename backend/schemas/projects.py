from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from backend.schemas.system import ApiSchema

Audience = Literal[
    "case_manager",
    "general_education",
    "paraeducator",
    "related_services",
    "substitute",
]
DeliveryModel = Literal["push_in", "pull_out", "combined", "other"]


class ValidationIssue(ApiSchema):
    field: str
    message: str


class StepValidation(ApiSchema):
    is_complete: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class ProjectCreate(ApiSchema):
    name: str | None = Field(default=None, max_length=200)


class StudentDraft(ApiSchema):
    name: str = Field(default="", max_length=200)
    initials: str = Field(default="", max_length=12)
    grade: str = Field(default="", max_length=32)
    school: str = Field(default="", max_length=200)
    case_manager: str = Field(default="", max_length=200)
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
    delivery_model: DeliveryModel | None = None
    notes: str = ""
    position: int = Field(default=0, ge=0)

    @field_validator("id", "delivery_model", "minutes_per_week", mode="before")
    @classmethod
    def normalize_blank_optional_values(cls, value: object) -> object:
        return None if value == "" else value


class StudentSetupDraft(ApiSchema):
    project_name: str = Field(default="", max_length=200)
    school_year: str = Field(default="", max_length=20)
    student: StudentDraft = Field(default_factory=StudentDraft)
    service_areas: list[ServiceAreaDraft] = Field(default_factory=list)
    audiences: list[Audience] = Field(default_factory=list)


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


class ExportRequest(ApiSchema):
    packet_version_id: str | None = None
    theme_id: str = "teacher_friendly"


class PacketVersionResponse(ApiSchema):
    id: str
    name: str
    audience: str


class ThemeOption(ApiSchema):
    id: str
    name: str
    description: str


class ThemeSelection(ApiSchema):
    theme_id: str = "teacher_friendly"


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
    current_step: Literal["student_setup", "goals", "at_a_glance", "data_sheets", "complete"]


class ProjectDetail(ApiSchema):
    id: str
    name: str
    school_year: str
    default_export_filename: str
    student: StudentResponse | None
    service_areas: list[ServiceAreaResponse]
    audiences: list[Audience]
    packet_versions: list[PacketVersionResponse]
    theme_id: str
    goals: list[GoalResponse]
    at_a_glance: AtAGlanceResponse
    data_sheets: list[DataSheetResponse]
    student_setup_validation: StepValidation
    goals_validation: StepValidation
    at_a_glance_validation: StepValidation
    data_sheets_validation: StepValidation
    updated_at: datetime
