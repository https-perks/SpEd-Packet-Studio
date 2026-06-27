import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ValidationSummary } from "../components/workflow/ValidationSummary";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import {
  createProjectBackup,
  exportDownloadUrl,
  generateAllPdfExports,
  generatePdfExport,
  listThemes,
  saveProjectTheme,
} from "../services/api/projects";
import type {
  BackupResult,
  ExportResult,
  ProjectDetail,
  StepValidation,
  ThemeOption,
} from "../types/projects";

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
  const [allExportResults, setAllExportResults] = useState<readonly ExportResult[]>([]);
  const [backupResult, setBackupResult] = useState<BackupResult | null>(null);
  const [themes, setThemes] = useState<ThemeOption[]>([]);
  const [selectedThemeId, setSelectedThemeId] = useState(project.theme_id || "teacher_friendly");
  const [selectedPacketVersionId, setSelectedPacketVersionId] = useState(
    project.packet_versions[0]?.id ?? "",
  );
  const [exporting, setExporting] = useState(false);
  const [exportingAll, setExportingAll] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState("");
  const validation = combinedValidation(project);

  useEffect(() => {
    void listThemes()
      .then(setThemes)
      .catch(() => setThemes([]));
  }, []);

  async function handleExport() {
    setExporting(true);
    setError("");
    try {
      const result = await generatePdfExport(project.id, {
        packetVersionId: selectedPacketVersionId || null,
        themeId: selectedThemeId,
      });
      setExportResult(result);
      onComplete();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The packet could not be exported.");
    } finally {
      setExporting(false);
    }
  }

  async function handleExportAll() {
    setExportingAll(true);
    setError("");
    try {
      const result = await generateAllPdfExports(project.id, {
        themeId: selectedThemeId,
      });
      setAllExportResults(result.exports);
      setExportResult(result.exports[0] ?? null);
      onComplete();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The packet versions could not be exported.");
    } finally {
      setExportingAll(false);
    }
  }

  async function handleThemeChange(themeId: string) {
    setSelectedThemeId(themeId);
    setError("");
    try {
      const saved = await saveProjectTheme(project.id, themeId);
      onProjectUpdate(saved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The theme could not be saved.");
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

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 7 of 7"
        title="Review & Export"
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

          <Card title="Export checklist" description="The PDF is generated from the same owned objects used by Packet Designer.">
            <dl className="grid gap-4 text-sm md:grid-cols-2">
              <div className="rounded-xl border border-[var(--theme-border)] bg-white p-4">
                <dt className="font-semibold text-[var(--theme-text-muted)]">Student</dt>
                <dd className="mt-1 text-[var(--theme-text)]">{project.student?.name || "Not entered"}</dd>
              </div>
              <div className="rounded-xl border border-[var(--theme-border)] bg-white p-4">
                <dt className="font-semibold text-[var(--theme-text-muted)]">Filename</dt>
                <dd className="mt-1 break-words text-[var(--theme-text)]">{project.default_export_filename}</dd>
              </div>
              <div className="rounded-xl border border-[var(--theme-border)] bg-white p-4">
                <dt className="font-semibold text-[var(--theme-text-muted)]">Goals</dt>
                <dd className="mt-1 text-[var(--theme-text)]">{project.goals.length}</dd>
              </div>
              <div className="rounded-xl border border-[var(--theme-border)] bg-white p-4">
                <dt className="font-semibold text-[var(--theme-text-muted)]">Data sheet definitions</dt>
                <dd className="mt-1 text-[var(--theme-text)]">{project.data_sheets.length}</dd>
              </div>
            </dl>
          </Card>

          <Card title="Version 1.0 export options" description="Packet versions and themes never duplicate student data.">
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
              <label className="text-sm font-semibold text-[var(--theme-text)]">
                Packet theme
                <select
                  className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm outline-none focus:border-[var(--theme-primary)] focus:ring-2 focus:ring-[var(--theme-primary-soft)]"
                  value={selectedThemeId}
                  onChange={(event) => void handleThemeChange(event.target.value)}
                >
                  {(themes.length ? themes : [{ id: "teacher_friendly", name: "Teacher Friendly", description: "" }]).map((theme) => (
                    <option key={theme.id} value={theme.id}>
                      {theme.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {themes.find((theme) => theme.id === selectedThemeId)?.description && (
              <p className="mt-3 text-sm text-[var(--theme-text-muted)]">
                {themes.find((theme) => theme.id === selectedThemeId)?.description}
              </p>
            )}
          </Card>

          {exportResult && (
            <Card title="Latest export" description="This file was written to the local exports folder.">
              <dl className="grid gap-3 text-sm md:grid-cols-2">
                <div>
                  <dt className="font-semibold text-[var(--theme-text-muted)]">File</dt>
                  <dd className="mt-1 break-words text-[var(--theme-text)]">{exportResult.filename}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-[var(--theme-text-muted)]">Size</dt>
                  <dd className="mt-1 text-[var(--theme-text)]">{formatBytes(exportResult.size_bytes)}</dd>
                </div>
                <div className="md:col-span-2">
                  <dt className="font-semibold text-[var(--theme-text-muted)]">Content hash</dt>
                  <dd className="mt-1 break-all font-mono text-xs text-[var(--theme-text)]">{exportResult.content_hash}</dd>
                </div>
                <div className="md:col-span-2">
                  <dt className="font-semibold text-[var(--theme-text-muted)]">Saved path</dt>
                  <dd className="mt-1 break-all text-xs text-[var(--theme-text)]">{exportResult.absolute_path}</dd>
                </div>
              </dl>
              <div className="mt-5 flex flex-wrap gap-2">
                <Button disabled={opening} onClick={() => void handleOpenExport()}>
                  {opening ? "Opening..." : "Open PDF"}
                </Button>
                <a
                  className="inline-flex rounded-xl border border-[var(--theme-border)] bg-white px-4 py-2.5 text-sm font-semibold text-[var(--theme-primary)] transition hover:bg-[var(--theme-surface-muted)]"
                  href={exportDownloadUrl(exportResult)}
                  download={exportResult.filename}
                >
                  Download PDF
                </a>
              </div>
            </Card>
          )}

          {allExportResults.length > 1 && (
            <Card title="All packet exports" description="Each selected packet version was exported separately.">
              <div className="space-y-3">
                {allExportResults.map((result) => (
                  <div key={result.id} className="rounded-xl border border-[var(--theme-border)] bg-white p-3 text-sm">
                    <p className="font-semibold text-[var(--theme-text)]">{result.filename}</p>
                    <p className="mt-1 break-all text-xs text-[var(--theme-text-muted)]">{result.absolute_path}</p>
                    <a
                      className="mt-2 inline-flex text-sm font-semibold text-[var(--theme-primary)]"
                      href={exportDownloadUrl(result)}
                      download={result.filename}
                    >
                      Download
                    </a>
                  </div>
                ))}
              </div>
            </Card>
          )}

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
          <Card title="Generate PDF" description="Uses WeasyPrint through FastAPI.">
            <p className="text-sm leading-6 text-[var(--theme-text-muted)]">
              Export includes the cover page, At-a-Glance, placeholders for future accommodations and behavior plans, goal summary, service areas, and data collection pages.
            </p>
            <Button
              className="mt-5 w-full justify-center"
              disabled={!validation.is_complete || exporting || exportingAll}
              onClick={() => void handleExport()}
            >
              {exporting ? "Generating..." : "Generate PDF"}
            </Button>
            <Button
              className="mt-2 w-full justify-center"
              variant="outline"
              disabled={!validation.is_complete || exporting || exportingAll}
              onClick={() => void handleExportAll()}
            >
              {exportingAll ? "Generating all..." : "Export All Versions"}
            </Button>
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
