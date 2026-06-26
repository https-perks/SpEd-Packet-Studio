export type Audience =
  | "case_manager"
  | "general_education"
  | "paraeducator"
  | "related_services"
  | "substitute";

export type DeliveryModel = "push_in" | "pull_out" | "combined" | "other";
export type WorkflowStep =
  | "student_setup"
  | "goals"
  | "at_a_glance"
  | "data_sheets"
  | "complete";
export type DataSheetType = "trial_count" | "frequency" | "duration" | "rubric" | "notes";
export type DataSheetColumnType = "text" | "number" | "date" | "checkbox" | "notes";

export interface ValidationIssue {
  readonly field: string;
  readonly message: string;
}

export interface StepValidation {
  readonly is_complete: boolean;
  readonly issues: readonly ValidationIssue[];
}

export interface StudentDraft {
  name: string;
  initials: string;
  grade: string;
  school: string;
  case_manager: string;
  iep_end_date: string | null;
}

export interface ServiceAreaDraft {
  id?: string | null;
  name: string;
  setting: string;
  minutes_per_week: number | null;
  delivery_model: DeliveryModel | null;
  notes: string;
  position: number;
}

export interface StudentSetupDraft {
  project_name: string;
  school_year: string;
  student: StudentDraft;
  service_areas: ServiceAreaDraft[];
  audiences: Audience[];
}

export interface GoalDraft {
  id?: string | null;
  title: string;
  statement: string;
  data_sheet_summary: string;
  service_area_id: string | null;
  mastery_criteria: string;
  progress_monitoring_method: string;
  instructional_notes: string;
  position: number;
}

export interface AtAGlanceSection {
  id: string;
  title: string;
  content: string;
  enabled: boolean;
  position: number;
}

export interface DataSheetDraft {
  id?: string | null;
  title: string;
  sheet_type: DataSheetType | null;
  goal_ids: string[];
  collection_schedule: string;
  blank_instance_count: number;
  columns: DataSheetColumnDraft[];
  notes: string;
  position: number;
}

export interface DataSheetColumnDraft {
  id: string;
  title: string;
  column_type: DataSheetColumnType;
  position: number;
}

export interface ExportResult {
  readonly id: string;
  readonly filename: string;
  readonly relative_path: string;
  readonly absolute_path: string;
  readonly generated_at: string;
  readonly content_hash: string;
  readonly size_bytes: number;
  readonly download_url: string;
}

export interface PacketVersion {
  readonly id: string;
  readonly name: string;
  readonly audience: string;
}

export interface ThemeOption {
  readonly id: string;
  readonly name: string;
  readonly description: string;
}

export interface BackupResult {
  readonly filename: string;
  readonly relative_path: string;
  readonly absolute_path: string;
  readonly created_at: string;
  readonly size_bytes: number;
}

export interface ProjectSummary {
  readonly id: string;
  readonly name: string;
  readonly student_name: string;
  readonly school_year: string;
  readonly grade: string;
  readonly updated_at: string;
  readonly archived: boolean;
  readonly current_step: WorkflowStep;
}

export interface ProjectDetail {
  readonly id: string;
  readonly name: string;
  readonly school_year: string;
  readonly default_export_filename: string;
  readonly student: (StudentDraft & { readonly id: string }) | null;
  readonly service_areas: readonly (ServiceAreaDraft & { readonly id: string })[];
  readonly audiences: readonly Audience[];
  readonly packet_versions: readonly PacketVersion[];
  readonly theme_id: string;
  readonly goals: readonly (GoalDraft & { readonly id: string })[];
  readonly at_a_glance: {
    readonly id: string | null;
    readonly sections: readonly AtAGlanceSection[];
  };
  readonly data_sheets: readonly (DataSheetDraft & { readonly id: string })[];
  readonly student_setup_validation: StepValidation;
  readonly goals_validation: StepValidation;
  readonly at_a_glance_validation: StepValidation;
  readonly data_sheets_validation: StepValidation;
  readonly updated_at: string;
}
