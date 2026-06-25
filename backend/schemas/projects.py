from datetime import date, datetime
from typing import Literal

from pydantic import Field

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


class ServiceAreaDraft(ApiSchema):
    id: str | None = None
    name: str = Field(default="", max_length=160)
    setting: str = Field(default="", max_length=200)
    minutes_per_week: int | None = Field(default=None, ge=0, le=10080)
    delivery_model: DeliveryModel | None = None
    notes: str = ""
    position: int = Field(default=0, ge=0)


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


class ProjectSummary(ApiSchema):
    id: str
    name: str
    student_name: str
    school_year: str
    grade: str
    updated_at: datetime
    archived: bool
    current_step: Literal["student_setup", "goals", "at_a_glance", "complete"]


class ProjectDetail(ApiSchema):
    id: str
    name: str
    school_year: str
    default_export_filename: str
    student: StudentResponse | None
    service_areas: list[ServiceAreaResponse]
    audiences: list[Audience]
    goals: list[GoalResponse]
    at_a_glance: AtAGlanceResponse
    student_setup_validation: StepValidation
    goals_validation: StepValidation
    at_a_glance_validation: StepValidation
    updated_at: datetime
