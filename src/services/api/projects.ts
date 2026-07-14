import type {
  AppSettings,
  AtAGlanceSection,
  BackupResult,
  BrandKitLibraryDraft,
  BrandKitLibraryItem,
  BulkProjectActionKind,
  BulkProjectActionResult,
  DataSheetDraft,
  DuplicateOptions,
  ExportMode,
  ExportAllResult,
  ExportSettings,
  ExportResult,
  ThemeOption,
  ThemePaletteDraft,
  GoalDraft,
  PacketTemplateLibraryDraft,
  PacketTemplateLibraryItem,
  PacketTemplateOption,
  ProjectDetail,
  PacketVersionConfig,
  ProjectSummary,
  StudentSetupDraft,
} from "../../types/projects";
import { API_BASE_URL, apiGet, apiRequest } from "./client";

export function listProjects(
  options: {
    archived?: boolean;
    search?: string;
    grade?: string;
    schoolYear?: string;
    caseManager?: string;
    serviceArea?: string;
    themeId?: string;
    missingDataSheets?: boolean;
    signal?: AbortSignal;
  } = {},
) {
  const params = new URLSearchParams({
    archived: String(options.archived ?? false),
    search: options.search ?? "",
    grade: options.grade ?? "",
    school_year: options.schoolYear ?? "",
    case_manager: options.caseManager ?? "",
    service_area: options.serviceArea ?? "",
    theme_id: options.themeId ?? "",
    missing_data_sheets: String(options.missingDataSheets ?? false),
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
  const {
    name,
    initials,
    grade,
    school,
    case_manager,
    case_manager_first_name,
    case_manager_last_name,
    case_manager_phone,
    case_manager_email,
    case_manager_notes,
    iep_end_date,
  } = value.student;
  return apiRequest<ProjectDetail>(`/projects/${projectId}/student-setup`, {
    method: "PUT",
    body: {
      ...value,
      student: {
        name,
        initials,
        grade,
        school,
        case_manager,
        case_manager_first_name,
        case_manager_last_name,
        case_manager_phone,
        case_manager_email,
        case_manager_notes,
        iep_end_date,
      },
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

export function savePacketBuilder(
  projectId: string,
  packetVersions: readonly PacketVersionConfig[],
  signal?: AbortSignal,
) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/packet-builder`, {
    method: "PUT",
    body: { packet_versions: packetVersions },
    signal,
  });
}

export function listThemes() {
  return apiGet<ThemeOption[]>("/projects/themes");
}

export function getAppSettings() {
  return apiGet<AppSettings>("/projects/app-settings");
}

export function saveAppSettings(value: AppSettings) {
  return apiRequest<AppSettings>("/projects/app-settings", {
    method: "PUT",
    body: value,
  });
}

export function createThemePalette(value: ThemePaletteDraft) {
  return apiRequest<ThemeOption>("/projects/themes", {
    method: "POST",
    body: value,
  });
}

export function updateThemePalette(themeId: string, value: ThemePaletteDraft) {
  return apiRequest<ThemeOption>(`/projects/themes/${themeId}`, {
    method: "PUT",
    body: value,
  });
}

export function deleteThemePalette(themeId: string) {
  return apiRequest<void>(`/projects/themes/${themeId}`, {
    method: "DELETE",
  });
}

export function listPacketTemplates() {
  return apiGet<PacketTemplateOption[]>("/projects/packet-templates");
}

export function listTemplateLibrary() {
  return apiGet<PacketTemplateLibraryItem[]>("/projects/template-library");
}

export function listHiddenTemplateLibrary() {
  return apiGet<PacketTemplateLibraryItem[]>("/projects/template-library/hidden");
}

export function createTemplateLibraryItem(value: PacketTemplateLibraryDraft) {
  return apiRequest<PacketTemplateLibraryItem>("/projects/template-library", {
    method: "POST",
    body: value,
  });
}

export function updateTemplateLibraryItem(templateId: string, value: PacketTemplateLibraryDraft) {
  return apiRequest<PacketTemplateLibraryItem>(`/projects/template-library/${templateId}`, {
    method: "PUT",
    body: value,
  });
}

export function duplicateTemplateLibraryItem(templateId: string) {
  return apiRequest<PacketTemplateLibraryItem>(`/projects/template-library/${templateId}/duplicate`, {
    method: "POST",
  });
}

export function setDefaultTemplateLibraryItem(templateId: string) {
  return apiRequest<PacketTemplateLibraryItem[]>(`/projects/template-library/${templateId}/default`, {
    method: "POST",
  });
}

export function restoreTemplateLibraryItem(templateId: string) {
  return apiRequest<PacketTemplateLibraryItem[]>(`/projects/template-library/${templateId}/restore`, {
    method: "POST",
  });
}

export function deleteTemplateLibraryItem(templateId: string) {
  return apiRequest<void>(`/projects/template-library/${templateId}`, {
    method: "DELETE",
  });
}

export async function previewTemplateLibraryItem(value: PacketTemplateLibraryDraft) {
  const response = await fetch(`${API_BASE_URL}/projects/template-library/preview`, {
    method: "POST",
    headers: {
      Accept: "application/pdf",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(value),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    throw new Error(typeof body?.detail === "string" ? body.detail : "The template preview could not be created.");
  }
  return response.blob();
}

export function listBrandKits() {
  return apiGet<BrandKitLibraryItem[]>("/projects/brand-kits");
}

export function createBrandKit(value: BrandKitLibraryDraft) {
  return apiRequest<BrandKitLibraryItem>("/projects/brand-kits", {
    method: "POST",
    body: value,
  });
}

export function updateBrandKit(brandKitId: string, value: BrandKitLibraryDraft) {
  return apiRequest<BrandKitLibraryItem>(`/projects/brand-kits/${brandKitId}`, {
    method: "PUT",
    body: value,
  });
}

export function duplicateBrandKit(brandKitId: string) {
  return apiRequest<BrandKitLibraryItem>(`/projects/brand-kits/${brandKitId}/duplicate`, {
    method: "POST",
  });
}

export function setDefaultBrandKit(brandKitId: string) {
  return apiRequest<BrandKitLibraryItem[]>(`/projects/brand-kits/${brandKitId}/default`, {
    method: "POST",
  });
}

export function deleteBrandKit(brandKitId: string) {
  return apiRequest<void>(`/projects/brand-kits/${brandKitId}`, {
    method: "DELETE",
  });
}

export function uploadBrandKitLogo(value: {
  brandKitId: string;
  filename: string;
  contentType: string;
  dataBase64: string;
  logoKind?: "cover" | "watermark";
}) {
  return apiRequest<BrandKitLibraryItem>("/projects/brand-kits/logo", {
    method: "POST",
    body: {
      brand_kit_id: value.brandKitId,
      filename: value.filename,
      content_type: value.contentType,
      data_base64: value.dataBase64,
      logo_kind: value.logoKind ?? "cover",
    },
  });
}

export function saveProjectTheme(
  projectId: string,
  value: Pick<ProjectDetail, "theme_id" | "packet_template_id" | "theme_customization" | "brand_kit">,
) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/theme`, {
    method: "PUT",
    body: {
      theme_id: value.theme_id,
      packet_template_id: value.packet_template_id,
      customization: value.theme_customization,
      brand_kit: value.brand_kit,
    },
  });
}

export function uploadBrandLogo(projectId: string, value: {
  filename: string;
  contentType: string;
  dataBase64: string;
}) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/brand-kit/logo`, {
    method: "POST",
    body: {
      filename: value.filename,
      content_type: value.contentType,
      data_base64: value.dataBase64,
    },
  });
}

export function saveExportSettings(projectId: string, exportSettings: ExportSettings) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/export-settings`, {
    method: "PUT",
    body: { export_settings: exportSettings },
  });
}

export function saveObservationChecklist(
  projectId: string,
  items: readonly string[],
  signal?: AbortSignal,
) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/observation-checklist`, {
    method: "PUT",
    body: { items },
    signal,
  });
}

export function generatePdfExport(
  projectId: string,
  options: {
    packetVersionId?: string | null;
    themeId?: string;
    packetTemplateId?: string | null;
    filenameTemplate?: string | null;
    exportMode?: ExportMode;
  } = {},
) {
  return apiRequest<ExportResult>(`/projects/${projectId}/exports/pdf`, {
    method: "POST",
    body: {
      packet_version_id: options.packetVersionId ?? null,
      theme_id: options.themeId ?? "",
      packet_template_id: options.packetTemplateId ?? null,
      filename_template: options.filenameTemplate ?? null,
      export_mode: options.exportMode ?? "single_pdf",
    },
  });
}

export function generateAllPdfExports(
  projectId: string,
  options: {
    themeId?: string;
    packetTemplateId?: string | null;
    filenameTemplate?: string | null;
    exportMode?: ExportMode;
  } = {},
) {
  return apiRequest<ExportAllResult>(`/projects/${projectId}/exports/pdf/all`, {
    method: "POST",
    body: {
      packet_version_id: null,
      theme_id: options.themeId ?? "",
      packet_template_id: options.packetTemplateId ?? null,
      filename_template: options.filenameTemplate ?? null,
      export_mode: options.exportMode ?? "zip_archive",
    },
  });
}

export async function previewPdfExport(
  projectId: string,
  options: {
    packetVersionId?: string | null;
    themeId?: string;
    packetTemplateId?: string | null;
    filenameTemplate?: string | null;
    exportMode?: ExportMode;
  } = {},
) {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/exports/preview`, {
    method: "POST",
    headers: {
      Accept: "application/pdf",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      packet_version_id: options.packetVersionId ?? null,
      theme_id: options.themeId ?? "",
      packet_template_id: options.packetTemplateId ?? null,
      filename_template: options.filenameTemplate ?? null,
      export_mode: options.exportMode ?? "single_pdf",
    }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    throw new Error(typeof body?.detail === "string" ? body.detail : "The PDF preview could not be created.");
  }
  return response.blob();
}

export function createProjectBackup(projectId: string) {
  return apiRequest<BackupResult>(`/projects/${projectId}/backup`, {
    method: "POST",
  });
}

export function exportDownloadUrl(exportResult: ExportResult) {
  return `${API_BASE_URL}${exportResult.download_url}`;
}

export function duplicateProject(projectId: string, options?: DuplicateOptions) {
  return apiRequest<ProjectDetail>(`/projects/${projectId}/duplicate`, {
    method: "POST",
    body: options ?? undefined,
  });
}

export function applyBulkProjectAction(
  projectIds: readonly string[],
  action: BulkProjectActionKind,
  options: {
    themeId?: string | null;
    packetTemplateId?: string | null;
    schoolYear?: string | null;
    exportLocation?: string | null;
    projectName?: string | null;
    duplicateOptions?: DuplicateOptions;
  } = {},
) {
  return apiRequest<BulkProjectActionResult>("/projects/bulk-action", {
    method: "POST",
    body: {
      project_ids: projectIds,
      action,
      theme_id: options.themeId ?? null,
      packet_template_id: options.packetTemplateId ?? null,
      school_year: options.schoolYear ?? null,
      export_location: options.exportLocation ?? null,
      project_name: options.projectName ?? null,
      duplicate_options: options.duplicateOptions,
    },
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

export function deleteProject(projectId: string) {
  return apiRequest<void>(`/projects/${projectId}`, {
    method: "DELETE",
  });
}
