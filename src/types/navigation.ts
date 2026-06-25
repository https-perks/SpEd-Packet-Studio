export type AppScreen = "dashboard" | "student_setup" | "goals" | "at_a_glance";

export interface NavigationItem {
  readonly id: AppScreen | "data_sheets" | "packet_designer" | "review";
  readonly label: string;
  readonly description: string;
  readonly enabled: boolean;
  readonly requiresProject: boolean;
}
