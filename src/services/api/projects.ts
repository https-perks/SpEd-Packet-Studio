import type {
  AtAGlanceSection,
  GoalDraft,
  ProjectDetail,
  ProjectSummary,
  StudentSetupDraft,
} from "../../types/projects";
import { apiGet, apiRequest } from "./client";

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
  return apiRequest<ProjectDetail>(`/projects/${projectId}/student-setup`, {
    method: "PUT",
    body: value,
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
