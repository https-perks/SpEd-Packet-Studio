export type Audience =
  | "case_manager"
  | "general_education"
  | "paraeducator"
  | "related_services"
  | "substitute";

export type DeliveryModel = "push_in" | "pull_out" | "combined" | "other";
export type WorkflowStep = "student_setup" | "goals" | "at_a_glance" | "complete";

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
  readonly goals: readonly (GoalDraft & { readonly id: string })[];
  readonly at_a_glance: {
    readonly id: string | null;
    readonly sections: readonly AtAGlanceSection[];
  };
  readonly student_setup_validation: StepValidation;
  readonly goals_validation: StepValidation;
  readonly at_a_glance_validation: StepValidation;
  readonly updated_at: string;
}
