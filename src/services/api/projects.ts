import type {
  AtAGlanceSection,
  BackupResult,
  DataSheetDraft,
  ExportResult,
  ThemeOption,
  GoalDraft,
  ProjectDetail,
  ProjectSummary,
  StudentSetupDraft,
} from "../../types/projects";
import { API_BASE_URL, apiGet, apiRequest } from "./client";

export function listProjects(
  options: { archived?: boolean; search?: string; signal?: AbortSignal } = {},
) {
  const params = new URLSearchParams({
    archived: String(options.archived ?? false),
    search: options.search ?? "",
  });
  return apiGet<ProjectSummary[]>(`/projects?${params}`, { signal: options.signal });
}

export function createProject(name?: string) {
  return apiRequest<ProjectDetail>("/projects", {
    method: "POST",
    body: { name: name ?? null },
  });
}

export function getProject(projectId: string, signal?: AbortSignal) {
  return apiGet<ProjectDetail>(`/projects/${projectId}`, { signal });
}

export function saveStudentSetup(
  projectId: string,
  value: StudentSetupDraft,
  signal?: AbortSignal,
) {
  const { name, initials, grade, school, case_manager, iep_end_date } = value.student;
  return apiRequest<ProjectDetail>(`/projects/${projectId}/student-setup`, {
    method: "PUT",
    body: {
      ...value,
      student: { name, initials, grade, school, case_manager, iep_end_date },
    },
    signal,
  });
}

export function saveGoals(
  projectId: string,
  goals: readonly GoalDraft[],
  signal?: AbortSignal,
) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/goals`, {
    method: "PUT",
    body: { goals },
    signal,
  });
}

export function saveAtAGlance(
  projectId: string,
  sections: readonly AtAGlanceSection[],
  signal?: AbortSignal,
) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/at-a-glance`, {
    method: "PUT",
    body: { sections },
    signal,
  });
}

export function saveDataSheets(
  projectId: string,
  dataSheets: readonly DataSheetDraft[],
  signal?: AbortSignal,
) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/data-sheets`, {
    method: "PUT",
    body: { data_sheets: dataSheets },
    signal,
  });
}

export function listThemes() {
  return apiGet<ThemeOption[]>("/projects/themes");
}

export function saveProjectTheme(projectId: string, themeId: string) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/theme`, {
    method: "PUT",
    body: { theme_id: themeId },
  });
}

export function generatePdfExport(
  projectId: string,
  options: { packetVersionId?: string | null; themeId?: string } = {},
) {
  return apiRequest<ExportResult>(`/projects/${projectId}/exports/pdf`, {
    method: "POST",
    body: {
      packet_version_id: options.packetVersionId ?? null,
      theme_id: options.themeId ?? "teacher_friendly",
    },
  });
}

export function createProjectBackup(projectId: string) {
  return apiRequest<BackupResult>(`/projects/${projectId}/backup`, {
    method: "POST",
  });
}

export function exportDownloadUrl(exportResult: ExportResult) {
  return `${API_BASE_URL}${exportResult.download_url}`;
}

export function duplicateProject(projectId: string) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/duplicate`, {
    method: "POST",
  });
}

export function archiveProject(projectId: string) {
  return apiRequest<ProjectSummary>(`/projects/${projectId}/archive`, {
    method: "POST",
  });
}

export function restoreProject(projectId: string) {
  return apiRequest<ProjectSummary>(`/projects/${projectId}/restore`, {
    method: "POST",
  });
}
