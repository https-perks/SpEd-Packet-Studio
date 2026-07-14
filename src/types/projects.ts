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
export type BulkProjectActionKind =
  | "archive"
  | "restore"
  | "duplicate"
  | "assign_theme"
  | "update_template"
  | "update_school_year"
  | "assign_export_location"
  | "export"
  | "delete"
  | "rename";
export type ExportMode = "single_pdf" | "zip_archive";

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
  case_manager_first_name: string;
  case_manager_last_name: string;
  case_manager_phone: string;
  case_manager_email: string;
  case_manager_notes: string;
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

export interface AccommodationDraft {
  id?: string | null;
  content_area: string;
  custom_content_area: string;
  text: string;
  position: number;
}

export interface BehaviorPlanSectionDraft {
  id?: string | null;
  title: string;
  text: string;
  position: number;
}

export interface RelatedServiceProviderDraft {
  id?: string | null;
  name: string;
  email: string;
  phone: string;
  service_area: string;
  position: number;
}

export interface StudentSetupDraft {
  project_name: string;
  school_year: string;
  student: StudentDraft;
  service_areas: ServiceAreaDraft[];
  audiences: Audience[];
  accommodations: AccommodationDraft[];
  behavior_plan: string;
  behavior_plan_sections: BehaviorPlanSectionDraft[];
  related_service_providers: RelatedServiceProviderDraft[];
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
  template_name: string;
  is_template: boolean;
  is_observation_form: boolean;
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

export interface ExportAllResult {
  readonly exports: readonly ExportResult[];
}

export interface PacketVersion {
  readonly id: string;
  readonly name: string;
  readonly audience: string;
}

export interface PacketPageDraft {
  id: string;
  title: string;
  page_type: string;
  enabled: boolean;
  position: number;
}

export interface AssetPlacementDraft {
  id: string;
  label: string;
  page_id: string;
  position: number;
  notes: string;
}

export interface PacketVersionConfig {
  packet_version_id: string;
  pages: PacketPageDraft[];
  asset_placements: AssetPlacementDraft[];
}

export interface ThemeOption {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly category: string;
  readonly default_customization: Partial<ThemeCustomization>;
  readonly is_builtin: boolean;
}

export interface PacketTemplateOption {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly category: string;
  readonly cover_style: string;
  readonly best_for: string;
  readonly page_count_hint: string;
}

export interface PacketTemplateLibraryItem extends PacketTemplateOption {
  base_template_id: string;
  theme_id: string;
  customization: ThemeCustomization;
  is_builtin: boolean;
  is_default: boolean;
  is_hidden: boolean;
}

export interface PacketTemplateLibraryDraft {
  name: string;
  description: string;
  category: string;
  base_template_id: string;
  theme_id: string;
  customization: ThemeCustomization;
}

export interface ThemeCustomization {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  background_color: string;
  card_color: string;
  text_color: string;
  service_area_colors: Record<string, string>;
}

export interface ThemePaletteDraft {
  name: string;
  description: string;
  category: string;
  customization: ThemeCustomization;
}

export interface BrandKit {
  id: string;
  name: string;
  district_name: string;
  school_name: string;
  district_logo_label: string;
  school_logo_label: string;
  logo_relative_path: string;
  logo_filename: string;
  watermark_logo_relative_path: string;
  watermark_logo_filename: string;
  watermark_enabled: boolean;
  default_fonts: string;
  heading_font: string;
  body_font: string;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  preferred_cover_style: string;
  footer_text: string;
  default_filename_template: string;
}

export interface BrandKitLibraryItem extends BrandKit {
  is_default: boolean;
}

export interface BrandKitLibraryDraft {
  name: string;
  district_name: string;
  school_name: string;
  district_logo_label: string;
  school_logo_label: string;
  logo_relative_path: string;
  logo_filename: string;
  watermark_logo_relative_path: string;
  watermark_logo_filename: string;
  watermark_enabled: boolean;
  default_fonts: string;
  heading_font: string;
  body_font: string;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  preferred_cover_style: string;
  footer_text: string;
  default_filename_template: string;
}

export interface ExportSettings {
  filename_template: string;
  last_export_location: string;
  export_mode: ExportMode;
}

export interface CaseManagerProfile {
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  school: string;
  notes: string;
}

export interface AppSettings {
  default_school_year: string;
  default_theme_id: string;
  default_packet_template_id: string;
  default_export_settings: ExportSettings;
  default_packet_pages: PacketPageDraft[];
  default_observation_checklist: string[];
  default_data_sheet_columns: DataSheetColumnDraft[];
  data_sheet_templates: DataSheetDraft[];
  service_area_presets: ServiceAreaDraft[];
  case_manager_profile: CaseManagerProfile;
}

export interface DuplicateOptions {
  student_information: boolean;
  service_areas: boolean;
  goals: boolean;
  at_a_glance: boolean;
  observation_notes: boolean;
  data_sheets: boolean;
  theme: boolean;
  template: boolean;
  packet_layout: boolean;
}

export interface BulkProjectActionResult {
  readonly projects: readonly ProjectSummary[];
  readonly duplicated_projects: readonly ProjectDetail[];
  readonly exports: readonly ExportResult[];
  readonly deleted_project_ids: readonly string[];
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
  readonly case_manager: string;
  readonly service_areas: readonly string[];
  readonly theme_id: string;
  readonly missing_data_sheets: boolean;
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
  readonly accommodations: readonly AccommodationDraft[];
  readonly behavior_plan: string;
  readonly behavior_plan_sections: readonly BehaviorPlanSectionDraft[];
  readonly related_service_providers: readonly RelatedServiceProviderDraft[];
  readonly packet_versions: readonly PacketVersion[];
  readonly packet_builder: readonly PacketVersionConfig[];
  readonly observation_checklist: readonly string[];
  readonly theme_id: string;
  readonly packet_template_id: string;
  readonly theme_customization: ThemeCustomization;
  readonly brand_kit: BrandKit;
  readonly export_settings: ExportSettings;
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
