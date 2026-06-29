import { useCallback, useEffect, useState } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { TextInput } from "../components/ui/FormField";
import {
  applyBulkProjectAction,
  archiveProject,
  createProject,
  createBrandKit,
  createTemplateLibraryItem,
  deleteProject,
  deleteBrandKit,
  deleteTemplateLibraryItem,
  duplicateBrandKit,
  duplicateProject,
  duplicateTemplateLibraryItem,
  listBrandKits,
  listPacketTemplates,
  listProjects,
  listTemplateLibrary,
  listThemes,
  restoreProject,
  setDefaultBrandKit,
  setDefaultTemplateLibraryItem,
  updateBrandKit,
  updateTemplateLibraryItem,
  uploadBrandKitLogo,
} from "../services/api/projects";
import type {
  BrandKitLibraryDraft,
  BrandKitLibraryItem,
  DuplicateOptions,
  PacketTemplateLibraryDraft,
  PacketTemplateLibraryItem,
  PacketTemplateOption,
  ProjectDetail,
  ProjectSummary,
  ThemeCustomization,
  ThemeOption,
} from "../types/projects";

const stepLabels = {
  student_setup: "Student Setup",
  at_a_glance: "At-a-Glance",
  goals: "Goal Builder",
  data_sheets: "Data Sheets",
  observation_sheets: "Observation Sheets",
  packet_designer: "Packet Designer",
  review: "Review & Export",
  complete: "Packet complete",
} as const;

const defaultDuplicateOptions: DuplicateOptions = {
  student_information: true,
  service_areas: true,
  goals: true,
  at_a_glance: false,
  observation_notes: false,
  data_sheets: false,
  theme: true,
  template: true,
  packet_layout: true,
};

const duplicateOptionLabels: Record<keyof DuplicateOptions, string> = {
  student_information: "Student Information",
  service_areas: "Service Areas",
  goals: "Goals",
  at_a_glance: "At-a-Glance",
  observation_notes: "Observation Notes",
  data_sheets: "Data Sheets",
  theme: "Theme",
  template: "Template",
  packet_layout: "Packet Layout",
};

const defaultCustomization: ThemeCustomization = {
  primary_color: "#0f2d55",
  secondary_color: "#27b8b2",
  accent_color: "#ef7900",
  background_color: "#f3f7fc",
  card_color: "#ffffff",
  text_color: "#12213a",
  service_area_colors: {},
};

function templateDraftFromItem(item?: PacketTemplateLibraryItem): PacketTemplateLibraryDraft {
  const themeId = item?.theme_id === "minimal" ? "minimal" : "teacher_friendly";
  return {
    name: item?.name ?? "Custom Template",
    description: item?.description ?? "",
    category: item?.category ?? "Custom",
    base_template_id: item?.base_template_id ?? "modern_professional",
    theme_id: themeId,
    customization: item?.customization ?? defaultCustomization,
  };
}

function brandKitDraftFromItem(item?: BrandKitLibraryItem): BrandKitLibraryDraft {
  return {
    name: item?.name ?? "Brand Kit",
    district_name: item?.district_name ?? "",
    school_name: item?.school_name ?? "",
    district_logo_label: item?.district_logo_label ?? "",
    school_logo_label: item?.school_logo_label ?? "",
    logo_relative_path: item?.logo_relative_path ?? "",
    logo_filename: item?.logo_filename ?? "",
    watermark_enabled: item?.watermark_enabled ?? false,
    default_fonts: item?.default_fonts ?? "",
    primary_color: item?.primary_color ?? "#0f2d55",
    secondary_color: item?.secondary_color ?? "#27b8b2",
    accent_color: item?.accent_color ?? "#ef7900",
    preferred_cover_style: item?.preferred_cover_style ?? "modern_professional",
    footer_text: item?.footer_text ?? "",
    default_filename_template: item?.default_filename_template ?? "",
  };
}

function fileToBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("The logo file could not be read."));
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.readAsDataURL(file);
  });
}

const basePreviewTone: Record<string, { panel: string; accent: string; mode: "light" | "dark"; label: string }> = {
  modern_professional: { panel: "linear-gradient(145deg, #0f2d55, #1f6fb8)", accent: "#27b8b2", mode: "dark", label: "Geometric" },
  district_branding: { panel: "linear-gradient(180deg, #ffffff, #eef6fb)", accent: "#0f2d55", mode: "light", label: "Logo-ready" },
  mountain_illustrated: { panel: "linear-gradient(180deg, #f7ffff 0%, #d7f3f0 55%, #0b6b78 100%)", accent: "#0f766e", mode: "light", label: "Landscape" },
  elementary_pop: { panel: "radial-gradient(circle at 12% 18%, #f08a24 0 12%, transparent 13%), radial-gradient(circle at 84% 14%, #35b7a9 0 10%, transparent 11%), #fff7e8", accent: "#ef7900", mode: "light", label: "Playful" },
  alpine_photo: { panel: "linear-gradient(115deg, #071827 0 58%, #1f6fb8 58% 100%)", accent: "#149fe3", mode: "dark", label: "Bold" },
  botanical_frame: { panel: "radial-gradient(circle at 9% 10%, #dcebd8 0 18%, transparent 19%), #fbfbf5", accent: "#557a46", mode: "light", label: "Botanical" },
  chalkboard: { panel: "linear-gradient(135deg, #1f2933, #111827)", accent: "#38bdf8", mode: "dark", label: "Chalkboard" },
  soft_organic: { panel: "radial-gradient(circle at 84% 14%, #ead8bd 0 18%, transparent 19%), #fbf6ed", accent: "#9b7f5f", mode: "light", label: "Organic" },
  purple_dot: { panel: "radial-gradient(circle, rgba(126,87,194,.38) 0 2px, transparent 2px) right center / 15px 15px, linear-gradient(90deg, #ffffff 0 64%, #f3e8ff 64%)", accent: "#6d3fc0", mode: "light", label: "Editorial" },
};

function TemplateLivePreview({
  draft,
  baseTemplate,
}: {
  readonly draft: PacketTemplateLibraryDraft;
  readonly baseTemplate?: PacketTemplateOption;
}) {
  const baseId = baseTemplate?.id ?? draft.base_template_id;
  const tone = basePreviewTone[baseId] ?? basePreviewTone.modern_professional;
  const colors = draft.customization;
  const isDark = tone.mode === "dark";
  const textColor = isDark ? "#ffffff" : colors.text_color;
  const coverTitleStyle = baseId === "botanical_frame" || baseId === "soft_organic"
    ? { fontFamily: "Georgia, serif", letterSpacing: "0.04em" }
    : baseId === "elementary_pop"
      ? { letterSpacing: "0.06em", textShadow: "2px 2px 0 rgba(244,169,55,.22)" }
      : {};
  const pageAccentStyle = baseId === "alpine_photo" || baseId === "chalkboard"
    ? { backgroundColor: baseId === "alpine_photo" ? "#0d1f35" : "#1f2933", color: "#ffffff", borderColor: "transparent" }
    : baseId === "botanical_frame"
      ? { backgroundColor: "#fbfaf5", borderColor: "#9fb695", color: "#3f544c" }
      : baseId === "elementary_pop"
        ? { backgroundColor: "#fff7e8", borderColor: "#f3c27a", color: "#275769" }
        : { backgroundColor: colors.card_color, borderColor: "#dbe5f1", color: colors.text_color };
  const cardRadius = baseId === "botanical_frame" ? "rounded-sm" : baseId === "elementary_pop" || baseId === "soft_organic" ? "rounded-2xl" : "rounded-lg";

  return (
    <div className="rounded-2xl border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--theme-accent)]">Live Preview</p>
          <h3 className="text-lg font-semibold text-[var(--theme-primary)]">{baseTemplate?.name ?? "Modern Professional"}</h3>
        </div>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-[var(--theme-text-muted)]">{tone.label}</span>
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(18rem,24rem)_1fr]">
        <div className="mx-auto aspect-[8.5/11] w-full max-w-[24rem] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="relative flex h-full flex-col justify-between overflow-hidden p-7" style={{ background: tone.panel, color: textColor }}>
            <div className="absolute -bottom-10 left-4 h-28 w-40 rotate-45 opacity-25" style={{ backgroundColor: tone.accent }} />
            <div className="absolute -right-10 bottom-8 h-32 w-44 rotate-45 opacity-20" style={{ backgroundColor: colors.secondary_color }} />
            {baseId === "mountain_illustrated" && <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-teal-950/70 to-transparent" />}
            {baseId === "purple_dot" && <div className="absolute right-0 top-0 h-full w-28 opacity-70" style={{ backgroundImage: "radial-gradient(circle, rgba(126,87,194,.42) 0 2px, transparent 2px)", backgroundSize: "14px 14px" }} />}
            <div className="relative text-center">
              <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full text-lg font-black shadow-lg" style={{ backgroundColor: tone.accent, color: "#ffffff" }}>SP</div>
              <p className="text-[0.62rem] font-bold uppercase tracking-[0.28em]" style={{ color: tone.accent }}>Special Education</p>
              <h4 className="mt-3 text-4xl font-black uppercase leading-none tracking-normal" style={{ color: textColor, ...coverTitleStyle }}>Service<br />Packet</h4>
              <div className="mx-auto mt-5 max-w-[14rem] px-5 py-2 text-center text-sm font-bold text-white" style={{ backgroundColor: colors.secondary_color }}>2026-2027</div>
              <p className="mt-5 text-lg font-black uppercase" style={{ color: tone.accent }}>Sample Student</p>
            </div>
            <div className="relative">
              <div className="mb-5 flex justify-center gap-4">
                {["R", "W", "S"].map((label, index) => (
                  <div key={label} className="w-16 text-center text-[0.52rem] font-black uppercase leading-tight" style={{ color: textColor }}>
                    <div className="mx-auto mb-2 grid h-11 w-11 place-items-center rounded-full text-sm font-black text-white" style={{ backgroundColor: index === 0 ? colors.primary_color : index === 1 ? colors.secondary_color : colors.accent_color }}>{label}</div>
                    {index === 0 ? "Reading" : index === 1 ? "Written" : "Speech"}
                  </div>
                ))}
              </div>
              <div className={`grid grid-cols-2 gap-2 ${baseId === "district_branding" || baseId === "botanical_frame" ? "border border-slate-300 bg-white/70" : ""} p-2 text-[0.55rem]`}>
                {["Grade 4", "IEP 2026-2027", "Case Manager", "School"].map((label) => (
                  <div key={label} className="rounded-md border border-white/20 bg-white/10 p-2 font-bold" style={{ color: textColor }}>{label}</div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {["At-a-Glance", "Goal Summary", "Data Collection", "Observations"].map((label, index) => (
            <div key={label} className="aspect-[8.5/11] overflow-hidden rounded-lg border bg-white p-3 shadow-sm" style={pageAccentStyle}>
              <div className="mb-3 flex items-center gap-2 border-b pb-2" style={{ borderColor: index === 0 ? colors.primary_color : index === 1 ? colors.secondary_color : colors.accent_color }}>
                <div className="grid h-6 w-6 place-items-center rounded-full text-[0.55rem] font-black text-white" style={{ backgroundColor: index === 0 ? colors.primary_color : index === 1 ? colors.secondary_color : colors.accent_color }}>{label[0]}</div>
                <p className="text-[0.55rem] font-black uppercase tracking-wide">{label}</p>
              </div>
              <div className="space-y-2">
                <div className={`${cardRadius} border bg-white/85 p-2`} style={{ borderColor: index === 1 ? colors.secondary_color : "#dbe5f1" }}>
                  <div className="mb-2 h-1.5 w-20 rounded-full" style={{ backgroundColor: index === 0 ? colors.primary_color : index === 1 ? colors.secondary_color : colors.accent_color }} />
                  <div className="space-y-1">
                    <div className="h-1.5 rounded-full bg-slate-200" />
                    <div className="h-1.5 w-4/5 rounded-full bg-slate-200" />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-1">
                  {Array.from({ length: 12 }).map((_, cellIndex) => (
                    <div key={cellIndex} className="h-4 border border-slate-200 bg-white/80" />
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface DashboardPageProps {
  readonly notice?: string;
  readonly onOpen: (project: ProjectSummary | ProjectDetail) => void;
}

export function DashboardPage({ notice, onOpen }: DashboardPageProps) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [search, setSearch] = useState("");
  const [grade, setGrade] = useState("");
  const [schoolYear, setSchoolYear] = useState("");
  const [caseManager, setCaseManager] = useState("");
  const [serviceArea, setServiceArea] = useState("");
  const [missingDataSheets, setMissingDataSheets] = useState(false);
  const [packetTemplates, setPacketTemplates] = useState<PacketTemplateOption[]>([]);
  const [templateLibrary, setTemplateLibrary] = useState<PacketTemplateLibraryItem[]>([]);
  const [themes, setThemes] = useState<ThemeOption[]>([]);
  const [brandKits, setBrandKits] = useState<BrandKitLibraryItem[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<PacketTemplateLibraryItem | null>(null);
  const [templateDraft, setTemplateDraft] = useState<PacketTemplateLibraryDraft>(templateDraftFromItem());
  const [editingTemplate, setEditingTemplate] = useState(false);
  const [hoveredBaseTemplateId, setHoveredBaseTemplateId] = useState<string | null>(null);
  const [selectedBrandKit, setSelectedBrandKit] = useState<BrandKitLibraryItem | null>(null);
  const [brandKitDraft, setBrandKitDraft] = useState<BrandKitLibraryDraft>(brandKitDraftFromItem());
  const [editingBrandKit, setEditingBrandKit] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [renameValue, setRenameValue] = useState("");
  const [duplicateTarget, setDuplicateTarget] = useState<ProjectSummary | null>(null);
  const [duplicateOptions, setDuplicateOptions] = useState<DuplicateOptions>(defaultDuplicateOptions);
  const [archived, setArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const baseTemplates = packetTemplates.filter((template) => !template.id.startsWith("custom_"));
  const previewBaseTemplate = baseTemplates.find((template) => template.id === (hoveredBaseTemplateId ?? templateDraft.base_template_id))
    ?? baseTemplates.find((template) => template.id === "modern_professional");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setProjects(await listProjects({
        archived,
        search,
        grade,
        schoolYear,
        caseManager,
        serviceArea,
        missingDataSheets,
      }));
      setSelectedIds([]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Projects could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [archived, caseManager, grade, missingDataSheets, schoolYear, search, serviceArea]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 220);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    void listPacketTemplates().then(setPacketTemplates).catch(() => setPacketTemplates([]));
    void listTemplateLibrary().then(setTemplateLibrary).catch(() => setTemplateLibrary([]));
    void listThemes().then(setThemes).catch(() => setThemes([]));
    void listBrandKits().then(setBrandKits).catch(() => setBrandKits([]));
  }, []);

  async function handleCreate() {
    setError("");
    try {
      onOpen(await createProject());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Project could not be created.");
    }
  }

  async function handleDuplicate(projectId: string, options: DuplicateOptions = defaultDuplicateOptions) {
    setError("");
    try {
      onOpen(await duplicateProject(projectId, options));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Project could not be duplicated.");
    }
  }

  async function handleBulk(action: "archive" | "restore" | "duplicate" | "export" | "delete" | "rename") {
    if (!selectedIds.length) return;
    if (action === "delete" && !window.confirm(`${archived ? "Permanently delete" : "Archive"} ${selectedIds.length} selected project(s)?`)) return;
    if (action === "rename" && selectedIds.length !== 1) {
      setError("Select one project to rename.");
      return;
    }
    setError("");
    try {
      if (action === "delete" && !archived) {
        await applyBulkProjectAction(selectedIds, "archive", { duplicateOptions });
        await load();
        return;
      }
      const result = await applyBulkProjectAction(selectedIds, action, {
        projectName: action === "rename" ? renameValue : null,
        duplicateOptions,
      });
      if (action === "duplicate" && result.duplicated_projects[0]) {
        onOpen(result.duplicated_projects[0]);
        return;
      }
      if (action === "export" && result.exports.length > 0) {
        setError("");
      }
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Bulk action could not be completed.");
    }
  }

  async function handleArchive(projectId: string) {
    setError("");
    try {
      if (archived) {
        await restoreProject(projectId);
      } else {
        await archiveProject(projectId);
      }
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Project could not be updated.");
    }
  }

  async function handlePermanentDelete(project: ProjectSummary) {
    if (!window.confirm(`Permanently delete "${project.name}"? This cannot be undone.`)) return;
    setError("");
    try {
      await deleteProject(project.id);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Project could not be permanently deleted.");
    }
  }

  function toggleSelected(projectId: string) {
    setSelectedIds((current) =>
      current.includes(projectId)
        ? current.filter((id) => id !== projectId)
        : [...current, projectId],
    );
  }

  function startRename(project: ProjectSummary) {
    setSelectedIds([project.id]);
    setRenameValue(project.name);
  }

  function openDuplicateWizard(project: ProjectSummary) {
    setDuplicateTarget(project);
    setDuplicateOptions(defaultDuplicateOptions);
  }

  async function refreshTemplateLibrary() {
    setTemplateLibrary(await listTemplateLibrary());
    setPacketTemplates(await listPacketTemplates());
  }

  async function refreshBrandKits() {
    setBrandKits(await listBrandKits());
  }

  function openTemplateEditor(template?: PacketTemplateLibraryItem) {
    setSelectedTemplate(template ?? null);
    const draft = templateDraftFromItem(template);
    if (baseTemplates.length && !baseTemplates.some((base) => base.id === draft.base_template_id)) {
      draft.base_template_id = "modern_professional";
    }
    setTemplateDraft(draft);
    setHoveredBaseTemplateId(null);
    setEditingTemplate(true);
  }

  async function saveTemplateEditor() {
    setError("");
    try {
      const saved = selectedTemplate && !selectedTemplate.is_builtin
        ? await updateTemplateLibraryItem(selectedTemplate.id, templateDraft)
        : await createTemplateLibraryItem(templateDraft);
      setSelectedTemplate(saved);
      setEditingTemplate(false);
      await refreshTemplateLibrary();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Template could not be saved.");
    }
  }

  async function duplicateSelectedTemplate() {
    if (!selectedTemplate) return;
    setError("");
    try {
      const duplicate = await duplicateTemplateLibraryItem(selectedTemplate.id);
      setSelectedTemplate(duplicate);
      await refreshTemplateLibrary();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Template could not be duplicated.");
    }
  }

  async function deleteSelectedTemplate() {
    if (!selectedTemplate) return;
    if (!window.confirm(`Delete "${selectedTemplate.name}"?`)) return;
    setError("");
    try {
      await deleteTemplateLibraryItem(selectedTemplate.id);
      setSelectedTemplate(null);
      await refreshTemplateLibrary();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Template could not be deleted.");
    }
  }

  async function setSelectedTemplateDefault() {
    if (!selectedTemplate) return;
    setError("");
    try {
      setTemplateLibrary(await setDefaultTemplateLibraryItem(selectedTemplate.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Default template could not be updated.");
    }
  }

  function openBrandKitEditor(brandKit?: BrandKitLibraryItem) {
    setSelectedBrandKit(brandKit ?? null);
    setBrandKitDraft(brandKitDraftFromItem(brandKit));
    setEditingBrandKit(true);
  }

  async function saveBrandKitEditor() {
    setError("");
    try {
      const saved = selectedBrandKit && selectedBrandKit.id !== "personal"
        ? await updateBrandKit(selectedBrandKit.id, brandKitDraft)
        : await createBrandKit(brandKitDraft);
      setSelectedBrandKit(saved);
      setBrandKitDraft(brandKitDraftFromItem(saved));
      await refreshBrandKits();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Brand Kit could not be saved.");
    }
  }

  async function duplicateSelectedBrandKit() {
    if (!selectedBrandKit) return;
    setError("");
    try {
      const duplicate = await duplicateBrandKit(selectedBrandKit.id);
      setSelectedBrandKit(duplicate);
      setBrandKitDraft(brandKitDraftFromItem(duplicate));
      await refreshBrandKits();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Brand Kit could not be duplicated.");
    }
  }

  async function deleteSelectedBrandKit() {
    if (!selectedBrandKit) return;
    if (!window.confirm(`Delete "${selectedBrandKit.name}"?`)) return;
    setError("");
    try {
      await deleteBrandKit(selectedBrandKit.id);
      setSelectedBrandKit(null);
      setEditingBrandKit(false);
      await refreshBrandKits();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Brand Kit could not be deleted.");
    }
  }

  async function setSelectedBrandKitDefault() {
    if (!selectedBrandKit) return;
    setError("");
    try {
      setBrandKits(await setDefaultBrandKit(selectedBrandKit.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Default Brand Kit could not be updated.");
    }
  }

  async function uploadSelectedBrandKitLogo(file: File | null) {
    if (!file || !selectedBrandKit) return;
    setError("");
    try {
      const saved = await uploadBrandKitLogo({
        brandKitId: selectedBrandKit.id,
        filename: file.name,
        contentType: file.type || "application/octet-stream",
        dataBase64: await fileToBase64(file),
      });
      setSelectedBrandKit(saved);
      setBrandKitDraft(brandKitDraftFromItem(saved));
      await refreshBrandKits();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Logo could not be uploaded.");
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12 lg:py-12">
      <header className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--theme-accent)]">
            Project dashboard
          </p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--theme-primary)]">
            Welcome back.
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-[var(--theme-text-muted)]">
            Create, continue, duplicate, and archive student packet projects from one place.
          </p>
        </div>
        <Button onClick={handleCreate}>New project</Button>
      </header>

      {notice && (
        <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-900">
          {notice}
        </div>
      )}
      {error && (
        <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          {error}
        </div>
      )}

      <div className="mt-8 grid gap-4 lg:grid-cols-[1fr_auto]">
        <TextInput
          aria-label="Search projects"
          placeholder="Search by project, student, or school year"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <div className="flex rounded-xl border border-[var(--theme-border)] bg-[var(--theme-surface)] p-1">
          <button
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${!archived ? "bg-[var(--theme-primary)] text-white" : "text-[var(--theme-text-muted)]"}`}
            onClick={() => setArchived(false)}
          >
            Active
          </button>
          <button
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${archived ? "bg-[var(--theme-primary)] text-white" : "text-[var(--theme-text-muted)]"}`}
            onClick={() => setArchived(true)}
          >
            Archived
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 rounded-xl border border-[var(--theme-border)] bg-white p-4 md:grid-cols-2 xl:grid-cols-5">
        <TextInput aria-label="Filter by grade" placeholder="Grade" value={grade} onChange={(event) => setGrade(event.target.value)} />
        <TextInput aria-label="Filter by school year" placeholder="School year" value={schoolYear} onChange={(event) => setSchoolYear(event.target.value)} />
        <TextInput aria-label="Filter by case manager" placeholder="Case manager" value={caseManager} onChange={(event) => setCaseManager(event.target.value)} />
        <TextInput aria-label="Filter by service area" placeholder="Service area" value={serviceArea} onChange={(event) => setServiceArea(event.target.value)} />
        <label className="flex items-center gap-2 rounded-xl border border-[var(--theme-border)] px-3.5 py-2.5 text-sm font-semibold text-[var(--theme-text-muted)]">
          <input type="checkbox" checked={missingDataSheets} onChange={(event) => setMissingDataSheets(event.target.checked)} />
          Missing data sheets
        </label>
      </div>

      {selectedIds.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-[var(--theme-border)] bg-[var(--theme-primary-soft)] p-4 text-sm">
          <span className="font-semibold text-[var(--theme-primary)]">{selectedIds.length} selected</span>
          <Button variant="outline" onClick={() => void handleBulk(archived ? "restore" : "archive")}>{archived ? "Restore Selected" : "Archive Selected"}</Button>
          <Button variant="outline" onClick={() => void handleBulk("duplicate")}>Duplicate Selected</Button>
          <Button variant="outline" onClick={() => void handleBulk("export")}>Export Selected</Button>
          <input
            aria-label="Project rename"
            className="rounded-xl border border-[var(--theme-border)] bg-white px-3 py-2 text-sm"
            disabled={selectedIds.length !== 1}
            placeholder="Rename selected project"
            value={renameValue}
            onChange={(event) => setRenameValue(event.target.value)}
          />
          <Button variant="outline" disabled={selectedIds.length !== 1 || !renameValue.trim()} onClick={() => void handleBulk("rename")}>Rename</Button>
          <Button variant="text" onClick={() => void handleBulk("delete")}>{archived ? "Delete Selected" : "Delete Selected"}</Button>
        </div>
      )}

      {duplicateTarget && (
        <Card title="Duplicate wizard" description={`Choose what carries forward from ${duplicateTarget.name}.`} className="mt-4">
          <div className="grid gap-3 text-sm md:grid-cols-3">
            {Object.entries(duplicateOptions).map(([key, value]) => (
              <label key={key} className="flex items-center gap-2 rounded-xl border border-[var(--theme-border)] bg-white px-3 py-2 font-medium text-[var(--theme-text)]">
                <input
                  type="checkbox"
                  checked={value}
                  onChange={(event) => setDuplicateOptions((current) => ({ ...current, [key]: event.target.checked }))}
                />
                {duplicateOptionLabels[key as keyof DuplicateOptions]}
              </label>
            ))}
          </div>
          <div className="mt-4 flex gap-2">
            <Button onClick={() => void handleDuplicate(duplicateTarget.id, duplicateOptions)}>Create Copy</Button>
            <Button variant="text" onClick={() => setDuplicateTarget(null)}>Cancel</Button>
          </div>
        </Card>
      )}

      <section aria-label="Projects" className="mt-6">
        {loading ? (
          <p className="py-12 text-center text-sm text-[var(--theme-text-muted)]">
            Loading projects...
          </p>
        ) : projects.length === 0 ? (
          <Card className="py-12 text-center">
            <p className="text-lg font-semibold text-[var(--theme-text)]">
              {search ? "No matching projects" : archived ? "No archived projects" : "Your studio is ready"}
            </p>
            <p className="mt-2 text-sm text-[var(--theme-text-muted)]">
              {search
                ? "Try a different search."
                : archived
                  ? "Archived projects will appear here."
                  : "Create a project to begin Student Setup."}
            </p>
            {!search && !archived && (
              <Button className="mt-5" onClick={handleCreate}>
                Create first project
              </Button>
            )}
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {projects.map((project) => (
              <Card key={project.id} className="flex min-h-64 flex-col">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex gap-3">
                    <input
                      aria-label={`Select ${project.name}`}
                      className="mt-1"
                      type="checkbox"
                      checked={selectedIds.includes(project.id)}
                      onChange={() => toggleSelected(project.id)}
                    />
                    <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--theme-accent)]">
                      {stepLabels[project.current_step]}
                    </p>
                    <h2 className="mt-2 text-xl font-semibold text-[var(--theme-text)]">
                      {project.name}
                    </h2>
                    </div>
                  </div>
                  {project.grade && (
                    <span className="rounded-full bg-[var(--theme-primary-soft)] px-3 py-1 text-xs font-semibold text-[var(--theme-primary)]">
                      Grade {project.grade}
                    </span>
                  )}
                </div>
                <dl className="mt-5 space-y-2 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--theme-text-muted)]">Student</dt>
                    <dd className="font-medium text-[var(--theme-text)]">
                      {project.student_name || "Not entered"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--theme-text-muted)]">School year</dt>
                    <dd className="font-medium text-[var(--theme-text)]">
                      {project.school_year || "Not entered"}
                    </dd>
                  </div>
                </dl>
                <div className="mt-4 flex flex-wrap gap-2 text-xs">
                  {project.case_manager && <span className="rounded-full bg-[var(--theme-surface-muted)] px-2.5 py-1 text-[var(--theme-text-muted)]">{project.case_manager}</span>}
                  {project.service_areas.slice(0, 3).map((area) => <span key={area} className="rounded-full bg-[var(--theme-primary-soft)] px-2.5 py-1 text-[var(--theme-primary)]">{area}</span>)}
                  {project.missing_data_sheets && <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-800">Needs data sheets</span>}
                </div>
                <div className="mt-auto flex flex-wrap gap-2 pt-6">
                  <Button onClick={() => onOpen(project)}>
                    {project.current_step === "student_setup" ? "Start setup" : "Continue"}
                  </Button>
                  {!archived && (
                    <Button variant="outline" onClick={() => openDuplicateWizard(project)}>
                      Duplicate
                    </Button>
                  )}
                  <Button variant="outline" onClick={() => startRename(project)}>
                    Rename
                  </Button>
                  <Button variant="text" onClick={() => void handleArchive(project.id)}>
                    {archived ? "Restore" : "Archive"}
                  </Button>
                  {archived && (
                    <Button variant="text" onClick={() => void handlePermanentDelete(project)}>
                      Delete
                    </Button>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <Card
          title="Template Library"
          description="Create and manage reusable packet templates without student data."
          actions={<Button variant="outline" onClick={() => openTemplateEditor()}>Create Template</Button>}
        >
          {selectedTemplate && (
            <div className="mb-3 flex flex-wrap gap-2 rounded-xl border border-[var(--theme-border)] bg-[var(--theme-primary-soft)] p-3">
              <Button variant="outline" onClick={() => openTemplateEditor(selectedTemplate)}>Edit Template</Button>
              <Button variant="outline" onClick={() => void duplicateSelectedTemplate()}>Duplicate Template</Button>
              <Button variant="outline" onClick={() => void setSelectedTemplateDefault()}>Set Default Template</Button>
              {!selectedTemplate.is_builtin && <Button variant="text" onClick={() => void deleteSelectedTemplate()}>Delete Template</Button>}
            </div>
          )}
          <div className="space-y-2 text-sm text-[var(--theme-text-muted)]">
            {(templateLibrary.length ? templateLibrary : packetTemplates.map((template) => ({
              ...template,
              base_template_id: template.id,
              theme_id: "teacher_friendly",
              customization: defaultCustomization,
              is_builtin: true,
              is_default: false,
            }))).slice(0, 8).map((template) => (
              <button
                key={template.id}
                className={`w-full rounded-lg border px-3 py-2 text-left transition ${selectedTemplate?.id === template.id ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)]" : "border-[var(--theme-border)] bg-white hover:bg-[var(--theme-surface-muted)]"}`}
                onClick={() => setSelectedTemplate(template)}
              >
                <span className="font-semibold text-[var(--theme-text)]">{template.name}</span>
                {template.is_default && <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-[var(--theme-primary)]">Default</span>}
                <span className="ml-2 text-xs uppercase tracking-[0.12em]">{template.category}</span>
                <span className="mt-1 block text-xs">{template.description}</span>
              </button>
            ))}
          </div>
        </Card>
        <Card
          title="Application settings"
          description="Manage local defaults used across packet projects."
          actions={<Button variant="outline" onClick={() => openBrandKitEditor()}>Create Brand Kit</Button>}
        >
          <div className="space-y-2 text-sm text-[var(--theme-text-muted)]">
            {brandKits.map((kit) => (
              <button
                key={kit.id}
                className={`w-full rounded-lg border px-3 py-2 text-left transition ${selectedBrandKit?.id === kit.id ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)]" : "border-[var(--theme-border)] bg-white hover:bg-[var(--theme-surface-muted)]"}`}
                onClick={() => {
                  setSelectedBrandKit(kit);
                  setBrandKitDraft(brandKitDraftFromItem(kit));
                }}
              >
                <span className="font-semibold text-[var(--theme-text)]">{kit.name}</span>
                {kit.is_default && <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-[var(--theme-primary)]">Default</span>}
                <span className="mt-1 block text-xs">{kit.district_name || kit.school_name || "No district or school label yet."}</span>
              </button>
            ))}
          </div>
          {selectedBrandKit && (
            <div className="mt-3 flex flex-wrap gap-2 rounded-xl border border-[var(--theme-border)] bg-[var(--theme-primary-soft)] p-3">
              <Button variant="outline" onClick={() => openBrandKitEditor(selectedBrandKit)}>Edit Brand Kit</Button>
              <Button variant="outline" onClick={() => void duplicateSelectedBrandKit()}>Duplicate Brand Kit</Button>
              <Button variant="outline" onClick={() => void setSelectedBrandKitDefault()}>Set Default Brand Kit</Button>
              {selectedBrandKit.id !== "personal" && <Button variant="text" onClick={() => void deleteSelectedBrandKit()}>Delete Brand Kit</Button>}
            </div>
          )}
        </Card>
      </div>
      {editingTemplate && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-6">
          <div className="max-h-[92vh] w-full max-w-6xl overflow-auto rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold text-[var(--theme-primary)]">{selectedTemplate && !selectedTemplate.is_builtin ? "Edit Template" : "Create Template"}</h2>
                <p className="mt-1 text-sm text-[var(--theme-text-muted)]">Templates store layout and colors only, never student information. Hover a base layout to preview it.</p>
              </div>
              <Button variant="text" onClick={() => setEditingTemplate(false)}>Close</Button>
            </div>
            <div className="mt-5 grid gap-6 lg:grid-cols-[21rem_1fr]">
              <div className="space-y-4">
                <label className="block text-sm font-semibold text-[var(--theme-text)]">
                  Template Name
                  <TextInput className="mt-2" value={templateDraft.name} onChange={(event) => setTemplateDraft({ ...templateDraft, name: event.target.value })} />
                </label>
                <label className="block text-sm font-semibold text-[var(--theme-text)]">
                  Category
                  <TextInput className="mt-2" value={templateDraft.category} onChange={(event) => setTemplateDraft({ ...templateDraft, category: event.target.value })} />
                </label>
                <label className="block text-sm font-semibold text-[var(--theme-text)]">
                  Description
                  <TextInput className="mt-2" value={templateDraft.description} onChange={(event) => setTemplateDraft({ ...templateDraft, description: event.target.value })} />
                </label>

                <div>
                  <p className="text-sm font-semibold text-[var(--theme-text)]">Base Layout</p>
                  <div className="mt-2 max-h-72 space-y-2 overflow-auto pr-1">
                    {baseTemplates.map((template) => {
                      const active = templateDraft.base_template_id === template.id;
                      const hover = hoveredBaseTemplateId === template.id;
                      return (
                        <button
                          key={template.id}
                          className={`w-full rounded-xl border px-3 py-2.5 text-left text-sm transition ${active ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)]" : hover ? "border-[var(--theme-accent)] bg-amber-50" : "border-[var(--theme-border)] bg-white hover:border-[var(--theme-accent)] hover:bg-amber-50"}`}
                          onClick={() => setTemplateDraft({ ...templateDraft, base_template_id: template.id })}
                          onMouseEnter={() => setHoveredBaseTemplateId(template.id)}
                          onMouseLeave={() => setHoveredBaseTemplateId(null)}
                          type="button"
                        >
                          <span className="block font-semibold text-[var(--theme-text)]">{template.name}</span>
                          <span className="mt-1 block text-xs text-[var(--theme-text-muted)]">{template.cover_style}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <label className="block text-sm font-semibold text-[var(--theme-text)]">
                  Color Palette
                  <select
                    className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm"
                    value={templateDraft.theme_id}
                    onChange={(event) => {
                      const theme = themes.find((candidate) => candidate.id === event.target.value);
                      setTemplateDraft({
                        ...templateDraft,
                        theme_id: event.target.value,
                        customization: { ...templateDraft.customization, ...(theme?.default_customization ?? {}) },
                      });
                    }}
                  >
                    {themes.map((theme) => <option key={theme.id} value={theme.id}>{theme.name}</option>)}
                  </select>
                </label>

                <div className="grid grid-cols-2 gap-3">
                  {([
                    ["primary_color", "Primary"],
                    ["secondary_color", "Secondary"],
                    ["accent_color", "Accent"],
                    ["background_color", "Background"],
                    ["card_color", "Cards"],
                    ["text_color", "Text"],
                  ] as const).map(([key, label]) => (
                    <label key={key} className="text-xs font-semibold text-[var(--theme-text-muted)]">
                      {label}
                      <input className="mt-2 h-10 w-full rounded-lg border border-[var(--theme-border)] bg-white p-1" type="color" value={templateDraft.customization[key]} onChange={(event) => setTemplateDraft({ ...templateDraft, customization: { ...templateDraft.customization, [key]: event.target.value } })} />
                    </label>
                  ))}
                </div>
              </div>

              <TemplateLivePreview draft={templateDraft} baseTemplate={previewBaseTemplate} />
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setEditingTemplate(false)}>Cancel</Button>
              <Button onClick={() => void saveTemplateEditor()}>Save Template</Button>
            </div>
          </div>
        </div>
      )}
      {editingBrandKit && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-6">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold text-[var(--theme-primary)]">{selectedBrandKit && selectedBrandKit.id !== "personal" ? "Edit Brand Kit" : "Create Brand Kit"}</h2>
                <p className="mt-1 text-sm text-[var(--theme-text-muted)]">Brand Kits store district defaults and reusable cover identity.</p>
              </div>
              <Button variant="text" onClick={() => setEditingBrandKit(false)}>Close</Button>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <label className="text-sm font-semibold text-[var(--theme-text)]">Brand Kit Name<TextInput className="mt-2" value={brandKitDraft.name} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, name: event.target.value })} /></label>
              <label className="text-sm font-semibold text-[var(--theme-text)]">Default Fonts<TextInput className="mt-2" value={brandKitDraft.default_fonts} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, default_fonts: event.target.value })} /></label>
              <label className="text-sm font-semibold text-[var(--theme-text)]">District<TextInput className="mt-2" value={brandKitDraft.district_name} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, district_name: event.target.value })} /></label>
              <label className="text-sm font-semibold text-[var(--theme-text)]">School<TextInput className="mt-2" value={brandKitDraft.school_name} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, school_name: event.target.value })} /></label>
              <label className="text-sm font-semibold text-[var(--theme-text)] md:col-span-2">Footer Text<TextInput className="mt-2" value={brandKitDraft.footer_text} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, footer_text: event.target.value })} /></label>
              <label className="flex items-center gap-2 rounded-xl border border-[var(--theme-border)] px-3.5 py-2.5 text-sm font-semibold text-[var(--theme-text)]">
                <input type="checkbox" checked={brandKitDraft.watermark_enabled} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, watermark_enabled: event.target.checked })} />
                Use district logo as page watermark
              </label>
              <label className="text-sm font-semibold text-[var(--theme-text)]">
                School logo
                <input accept="image/png,image/jpeg,image/svg+xml" className="mt-2 block w-full text-sm text-[var(--theme-text-muted)] file:mr-3 file:rounded-lg file:border-0 file:bg-[var(--theme-primary)] file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white" disabled={!selectedBrandKit || selectedBrandKit.id === "personal"} type="file" onChange={(event) => void uploadSelectedBrandKitLogo(event.target.files?.[0] ?? null)} />
                {brandKitDraft.logo_filename && <span className="mt-2 block text-xs text-[var(--theme-primary)]">Current logo: {brandKitDraft.logo_filename}</span>}
              </label>
              {([
                ["primary_color", "Primary Color"],
                ["secondary_color", "Secondary Color"],
                ["accent_color", "Accent Color"],
              ] as const).map(([key, label]) => (
                <label key={key} className="text-xs font-semibold text-[var(--theme-text-muted)]">
                  {label}
                  <input className="mt-2 h-10 w-full rounded-lg border border-[var(--theme-border)] bg-white p-1" type="color" value={brandKitDraft[key]} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, [key]: event.target.value })} />
                </label>
              ))}
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setEditingBrandKit(false)}>Cancel</Button>
              <Button onClick={() => void saveBrandKitEditor()}>Save Brand Kit</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
