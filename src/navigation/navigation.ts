import type { NavigationItem } from "../types/navigation";
export const navigationItems: readonly NavigationItem[] = [
  { id: "dashboard", label: "Dashboard", description: "Manage projects", enabled: true, requiresProject: false },
  { id: "student_setup", label: "Student Setup", description: "Profile and services", enabled: true, requiresProject: true },
  { id: "goals", label: "Goal Builder", description: "Annual goals", enabled: true, requiresProject: true },
  { id: "at_a_glance", label: "At-a-Glance", description: "Instructional summary", enabled: true, requiresProject: true },
  { id: "data_sheets", label: "Data Sheets", description: "Sprint 2", enabled: false, requiresProject: true },
  { id: "packet_designer", label: "Packet Designer", description: "Sprint 3", enabled: false, requiresProject: true },
  { id: "review", label: "Review & Export", description: "Sprint 4", enabled: false, requiresProject: true },
] as const;
