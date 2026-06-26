export type AppScreen =
  | "dashboard"
  | "student_setup"
  | "goals"
  | "at_a_glance"
  | "data_sheets"
  | "packet_designer"
  | "review";

export interface NavigationItem {
  readonly id: AppScreen;
  readonly label: string;
  readonly description: string;
  readonly enabled: boolean;
  readonly requiresProject: boolean;
}
