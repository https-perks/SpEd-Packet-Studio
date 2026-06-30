import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ValidationSummary } from "../components/workflow/ValidationSummary";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import {
  createProjectBackup,
  exportDownloadUrl,
  generatePdfExport,
  listBrandKits,
  listTemplateLibrary,
  previewPdfExport,
  saveExportSettings,
  saveProjectTheme,
} from "../services/api/projects";
import type {
  BackupResult,
  BrandKit,
  BrandKitLibraryItem,
  ExportMode,
  ExportSettings,
  ExportResult,
  PacketTemplateLibraryItem,
  ProjectDetail,
  StepValidation,
} from "../types/projects";

const emptyBrandKit: BrandKit = {
  id: "personal",
  name: "No Brand Kit",
  district_name: "",
  school_name: "",
  district_logo_label: "",
  school_logo_label: "",
  logo_relative_path: "",
  logo_filename: "",
  watermark_logo_relative_path: "",
  watermark_logo_filename: "",
  watermark_enabled: false,
  default_fonts: "",
  primary_color: "#0f2d55",
  secondary_color: "#27b8b2",
  accent_color: "#ef7900",
  preferred_cover_style: "modern_professional",
  footer_text: "",
  default_filename_template: "",
};

function combinedValidation(project: ProjectDetail): StepValidation {
  const issues = [
    ...project.student_setup_validation.issues,
    ...project.goals_validation.issues,
    ...project.at_a_glance_validation.issues,
    ...project.data_sheets_validation.issues,
  ];
  return { is_complete: issues.length === 0, issues };
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} bytes`;
  if (value < 1024 * 1024) return `${Math.round(value / 102.4) / 10} KB`;
  return `${Math.round(value / 1024 / 102.4) / 10} MB`;
}

function projectBrandKit(value: BrandKit | BrandKitLibraryItem): BrandKit {
  return {
    id: value.id,
    name: value.name,
    district_name: value.district_name,
    school_name: value.school_name,
    district_logo_label: value.district_logo_label,
    school_logo_label: value.school_logo_label,
    logo_relative_path: value.logo_relative_path,
    logo_filename: value.logo_filename,
    watermark_logo_relative_path: value.watermark_logo_relative_path,
    watermark_logo_filename: value.watermark_logo_filename,
    watermark_enabled: value.watermark_enabled,
    default_fonts: value.default_fonts,
    primary_color: value.primary_color,
    secondary_color: value.secondary_color,
    accent_color: value.accent_color,
    preferred_cover_style: value.preferred_cover_style,
    footer_text: value.footer_text,
    default_filename_template: value.default_filename_template,
  };
}

interface ReviewExportPageProps {
  readonly project: ProjectDetail;
  readonly onProjectUpdate: (project: ProjectDetail) => void;
  readonly onBack: () => void;
  readonly onComplete: () => void;
}

export function ReviewExportPage({
  project,
  onProjectUpdate,
  onBack,
  onComplete,
}: ReviewExportPageProps) {
  const [exportResult, setExportResult] = useState<ExportResult | null>(null);
  const [backupResult, setBackupResult] = useState<BackupResult | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [packetTemplates, setPacketTemplates] = useState<PacketTemplateLibraryItem[]>([]);
  const [brandKits, setBrandKits] = useState<BrandKitLibraryItem[]>([]);
  const [selectedBrandKitId, setSelectedBrandKitId] = useState(project.brand_kit.id !== "personal" ? project.brand_kit.id : "");
  const [selectedThemeId, setSelectedThemeId] = useState(project.theme_id || "teacher_friendly");
  const [selectedTemplateId, setSelectedTemplateId] = useState(project.packet_template_id || "modern_professional");
  const [exportSettings, setExportSettings] = useState<ExportSettings>(project.export_settings);
  const [selectedPacketVersionId, setSelectedPacketVersionId] = useState(
    project.packet_versions[0]?.id ?? "",
  );
  const [exporting, setExporting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState("");
  const validation = combinedValidation(project);

  useEffect(() => {
    void listTemplateLibrary()
      .then(setPacketTemplates)
      .catch(() => setPacketTemplates([]));
    void listBrandKits()
      .then((kits) => setBrandKits(kits.filter((kit) => kit.id !== "personal")))
      .catch(() => setBrandKits([]));
  }, []);

  function brandKitForSelection(brandKitId: string): BrandKit {
    const selected = brandKits.find((kit) => kit.id === brandKitId);
    return selected ? projectBrandKit(selected) : emptyBrandKit;
  }

  async function handleExport() {
    setExporting(true);
    setError("");
    try {
      const result = await generatePdfExport(project.id, {
        packetVersionId: selectedPacketVersionId || null,
        themeId: selectedThemeId,
        packetTemplateId: selectedTemplateId,
        filenameTemplate: exportSettings.filename_template,
        exportMode: exportSettings.export_mode,
      });
      setExportResult(result);
      onComplete();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The packet could not be exported.");
    } finally {
      setExporting(false);
    }
  }

  async function handlePreview() {
    setPreviewing(true);
    setError("");
    try {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      const blob = await previewPdfExport(project.id, {
        packetVersionId: selectedPacketVersionId || null,
        themeId: selectedThemeId,
        packetTemplateId: selectedTemplateId,
        filenameTemplate: exportSettings.filename_template,
        exportMode: "single_pdf",
      });
      setPreviewUrl(URL.createObjectURL(blob));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The PDF preview could not be created.");
    } finally {
      setPreviewing(false);
    }
  }

  async function saveThemeSettings(next: {
    themeId?: string;
    templateId?: string;
    brandKitId?: string;
  }) {
    const selectedTemplate = packetTemplates.find((template) => template.id === (next.templateId ?? selectedTemplateId));
    const themeId = next.themeId ?? selectedTemplate?.theme_id ?? selectedThemeId;
    const templateId = next.templateId ?? selectedTemplateId;
    const brandKitId = next.brandKitId ?? selectedBrandKitId;
    setSelectedThemeId(themeId);
    setSelectedTemplateId(templateId);
    setSelectedBrandKitId(brandKitId);
    setError("");
    try {
      const saved = await saveProjectTheme(project.id, {
        theme_id: themeId,
        packet_template_id: templateId,
        theme_customization: selectedTemplate?.customization ?? project.theme_customization,
        brand_kit: brandKitForSelection(brandKitId),
      });
      onProjectUpdate(saved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The theme settings could not be saved.");
    }
  }

  async function saveExportOptions(next: ExportSettings) {
    setExportSettings(next);
    setError("");
    try {
      const saved = await saveExportSettings(project.id, next);
      onProjectUpdate(saved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The export settings could not be saved.");
    }
  }

  async function handleBackup() {
    setBackingUp(true);
    setError("");
    try {
      setBackupResult(await createProjectBackup(project.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The backup could not be created.");
    } finally {
      setBackingUp(false);
    }
  }

  async function handleOpenExport() {
    if (!exportResult) return;
    setOpening(true);
    setError("");
    try {
      await invoke("open_path", { path: exportResult.absolute_path });
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The PDF was generated, but the desktop app could not open it automatically. Use the download link or open the saved path manually.",
      );
    } finally {
      setOpening(false);
    }
  }

  async function handleSelectFolder() {
    setError("");
    try {
      const folder = await invoke<string | null>("select_folder");
      if (folder) {
        await saveExportOptions({ ...exportSettings, last_export_location: folder });
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The save folder could not be selected.");
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 7 of 7"
        title={`Review & Export${project.student?.name ? ` - ${project.student.name}` : ""}`}
        description="Confirm the packet is complete, then generate a deterministic PDF from the backend packet builder."
      />

      {error && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          {error}
        </div>
      )}

      <div className="grid items-start gap-5 xl:grid-cols-[1fr_24rem]">
        <div className="space-y-5">
          <ValidationSummary
            validation={validation}
            completeMessage="All required packet sections are ready for export."
          />

          <Card title="Packet version" description="Choose the staff audience to export.">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="text-sm font-semibold text-[var(--theme-text)]">
                Packet version
                <select
                  className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm outline-none focus:border-[var(--theme-primary)] focus:ring-2 focus:ring-[var(--theme-primary-soft)]"
                  value={selectedPacketVersionId}
                  onChange={(event) => setSelectedPacketVersionId(event.target.value)}
                >
                  <option value="">Base Packet</option>
                  {project.packet_versions.map((version) => (
                    <option key={version.id} value={version.id}>
                      {version.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </Card>

          <Card title="Template gallery" description="Templates change packet layout, not student data.">
            <div className="grid gap-3 md:grid-cols-2">
              {(packetTemplates.length ? packetTemplates : []).map((template) => (
                <button
                  key={template.id}
                  className={`rounded-xl border p-4 text-left transition ${selectedTemplateId === template.id ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)]" : "border-[var(--theme-border)] bg-white hover:bg-[var(--theme-surface-muted)]"}`}
                  onClick={() => void saveThemeSettings({ templateId: template.id })}
                >
                  <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--theme-accent)]">{template.category}</span>
                  <span className="mt-1 block font-semibold text-[var(--theme-text)]">{template.name}</span>
                  <span className="mt-2 block text-xs leading-5 text-[var(--theme-text-muted)]">{template.description}</span>
                  <span className="mt-3 block rounded-lg border border-[var(--theme-border)] bg-white p-3 text-xs text-[var(--theme-text-muted)]">
                    Cover: {template.cover_style}<br />
                    Best for: {template.best_for}
                  </span>
                </button>
              ))}
            </div>
          </Card>

          <Card title="Brand Kit" description="Optionally apply district identity, cover logo, and watermark settings.">
            <label className="text-sm font-semibold text-[var(--theme-text)]">
              Brand Kit
              <select
                className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm outline-none focus:border-[var(--theme-primary)] focus:ring-2 focus:ring-[var(--theme-primary-soft)]"
                value={selectedBrandKitId}
                onChange={(event) => void saveThemeSettings({ brandKitId: event.target.value })}
              >
                <option value="">None</option>
                {brandKits.map((kit) => (
                  <option key={kit.id} value={kit.id}>
                    {kit.name}
                  </option>
                ))}
              </select>
            </label>
            {selectedBrandKitId && (
              <p className="mt-3 text-sm leading-6 text-[var(--theme-text-muted)]">
                Selected kit will be applied to previews and exports. Colors still come from the selected template palette.
              </p>
            )}
          </Card>

          {backupResult && (
            <Card title="Latest backup" description="This JSON backup was written locally.">
              <dl className="grid gap-3 text-sm md:grid-cols-2">
                <div>
                  <dt className="font-semibold text-[var(--theme-text-muted)]">File</dt>
                  <dd className="mt-1 break-words text-[var(--theme-text)]">{backupResult.filename}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-[var(--theme-text-muted)]">Size</dt>
                  <dd className="mt-1 text-[var(--theme-text)]">{formatBytes(backupResult.size_bytes)}</dd>
                </div>
                <div className="md:col-span-2">
                  <dt className="font-semibold text-[var(--theme-text-muted)]">Saved path</dt>
                  <dd className="mt-1 break-all text-xs text-[var(--theme-text)]">{backupResult.absolute_path}</dd>
                </div>
              </dl>
            </Card>
          )}
        </div>

        <aside className="xl:sticky xl:top-6">
          <Card title="Export options" description="Choose how and where the packet is saved.">
            <div className="space-y-4">
              <label className="text-sm font-semibold text-[var(--theme-text)]">
                Filename
                <input
                  className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm outline-none focus:border-[var(--theme-primary)] focus:ring-2 focus:ring-[var(--theme-primary-soft)]"
                  placeholder={`${project.student?.name || "Student"} - ${project.school_year || "School Year"}`}
                  value={exportSettings.filename_template}
                  onChange={(event) => void saveExportOptions({ ...exportSettings, filename_template: event.target.value })}
                />
              </label>
              <label className="text-sm font-semibold text-[var(--theme-text)]">
                Export mode
                <select
                  className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm outline-none focus:border-[var(--theme-primary)] focus:ring-2 focus:ring-[var(--theme-primary-soft)]"
                  value={exportSettings.export_mode}
                  onChange={(event) => void saveExportOptions({ ...exportSettings, export_mode: event.target.value as ExportMode })}
                >
                  <option value="single_pdf">Single PDF</option>
                  <option value="zip_archive">ZIP Archive of All</option>
                </select>
              </label>
              <label className="text-sm font-semibold text-[var(--theme-text)]">
                Save to
                <input
                  className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm outline-none focus:border-[var(--theme-primary)] focus:ring-2 focus:ring-[var(--theme-primary-soft)]"
                  readOnly
                  placeholder="Choose a folder..."
                  value={exportSettings.last_export_location}
                />
              </label>
              <Button className="w-full justify-center" variant="outline" onClick={() => void handleSelectFolder()}>
                Save to...
              </Button>
            </div>
          </Card>
          <Card title="Generate PDF" description="Uses WeasyPrint through FastAPI." className="mt-5">
            <p className="text-sm leading-6 text-[var(--theme-text-muted)]">
              Export includes the cover page, At-a-Glance, placeholders for future accommodations and behavior plans, goal summary, service areas, and data collection pages.
            </p>
            <Button
              className="mt-5 w-full justify-center"
              variant="outline"
              disabled={!validation.is_complete || previewing || exporting}
              onClick={() => void handlePreview()}
            >
              {previewing ? "Creating preview..." : "Create Preview"}
            </Button>
            <Button
              className="mt-2 w-full justify-center"
              disabled={!validation.is_complete || previewing || exporting}
              onClick={() => void handleExport()}
            >
              {exporting ? "Exporting..." : exportSettings.export_mode === "zip_archive" ? "Export ZIP" : "Export PDF"}
            </Button>
            {previewUrl && (
              <div className="mt-4 overflow-hidden rounded-xl border border-[var(--theme-border)] bg-white">
                <iframe className="h-96 w-full" src={previewUrl} title="Packet PDF preview" />
              </div>
            )}
            {exportResult && (
              <div className="mt-5 flex flex-wrap gap-2">
                <Button disabled={opening} onClick={() => void handleOpenExport()}>
                  {opening ? "Opening..." : exportSettings.export_mode === "zip_archive" ? "Open ZIP" : "Open PDF"}
                </Button>
                <a
                  className="inline-flex rounded-xl border border-[var(--theme-border)] bg-white px-4 py-2.5 text-sm font-semibold text-[var(--theme-primary)] transition hover:bg-[var(--theme-surface-muted)]"
                  href={exportDownloadUrl(exportResult)}
                  download={exportResult.filename}
                >
                  Download
                </a>
              </div>
            )}
          </Card>
          <Card title="Backup project" description="Create a local JSON backup of the project data." className="mt-5">
            <p className="text-sm leading-6 text-[var(--theme-text-muted)]">
              Backups include project structure and owned data, not generated PDF binary files.
            </p>
            <Button
              className="mt-5 w-full justify-center"
              disabled={backingUp}
              variant="outline"
              onClick={() => void handleBackup()}
            >
              {backingUp ? "Creating backup..." : "Create Backup"}
            </Button>
          </Card>
        </aside>
      </div>

      <footer className="mt-5 flex flex-wrap items-center justify-between gap-3 pb-6">
        <Button variant="outline" onClick={onBack}>Back</Button>
      </footer>
    </div>
  );
}
