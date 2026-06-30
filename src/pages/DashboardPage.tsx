import { useCallback, useEffect, useState } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { TextInput } from "../components/ui/FormField";
import {
  applyBulkProjectAction,
  archiveProject,
  createProject,
  createBrandKit,
  createThemePalette,
  createTemplateLibraryItem,
  deleteProject,
  deleteBrandKit,
  deleteThemePalette,
  deleteTemplateLibraryItem,
  getAppSettings,
  duplicateBrandKit,
  duplicateProject,
  duplicateTemplateLibraryItem,
  listBrandKits,
  listPacketTemplates,
  listProjects,
  listTemplateLibrary,
  listThemes,
  restoreProject,
  saveAppSettings,
  setDefaultBrandKit,
  setDefaultTemplateLibraryItem,
  updateBrandKit,
  updateThemePalette,
  updateTemplateLibraryItem,
  uploadBrandKitLogo,
} from "../services/api/projects";
import type {
  AppSettings,
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
  ThemePaletteDraft,
} from "../types/projects";

type SettingsModal =
  | "school_year"
  | "export"
  | "packet_pages"
  | "observation_checklist"
  | "data_columns"
  | "service_presets"
  | "case_manager"
  | null;

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

const defaultAppSettings: AppSettings = {
  default_school_year: "",
  default_theme_id: "teacher_friendly",
  default_packet_template_id: "modern_professional",
  default_export_settings: {
    filename_template: "",
    last_export_location: "",
    export_mode: "single_pdf",
  },
  default_packet_pages: [
    { id: "cover", title: "Cover Page", page_type: "cover", enabled: true, position: 0 },
    { id: "at_a_glance", title: "At-a-Glance", page_type: "at_a_glance", enabled: true, position: 1 },
    { id: "accommodations", title: "Accommodations/Modifications", page_type: "placeholder", enabled: true, position: 2 },
    { id: "behavior", title: "Behavior Plans", page_type: "placeholder", enabled: true, position: 3 },
    { id: "goal_summary", title: "Goal Summary", page_type: "goal_summary", enabled: true, position: 4 },
    { id: "services", title: "Service Areas", page_type: "services", enabled: true, position: 5 },
    { id: "data_collection", title: "Data Collection", page_type: "data_collection", enabled: true, position: 6 },
    { id: "observations", title: "Observations & Notes", page_type: "observations", enabled: true, position: 7 },
  ],
  default_observation_checklist: [
    "Consistently struggling despite accommodations",
    "Social concerns",
    "Accommodations are not sufficient",
    "Student requests additional help",
    "New behavior concerns",
    "Student refusing accommodations",
    "Significant academic improvement",
    "Medical / health concerns",
    "Concerns from parents",
    "Other observations",
  ],
  default_data_sheet_columns: [
    { id: "date", title: "Date", column_type: "date", position: 0 },
    { id: "trial", title: "Trial", column_type: "text", position: 1 },
    { id: "result", title: "Result", column_type: "text", position: 2 },
    { id: "notes", title: "Notes", column_type: "notes", position: 3 },
  ],
  service_area_presets: [],
  case_manager_profile: {
    first_name: "",
    last_name: "",
    phone: "",
    email: "",
    school: "",
    notes: "",
  },
};

const districtBrandingCustomization: ThemeCustomization = {
  primary_color: "#0d2848",
  secondary_color: "#154f85",
  accent_color: "#d89a2b",
  background_color: "#ffffff",
  card_color: "#ffffff",
  text_color: "#14233c",
  service_area_colors: {},
};

function themeIdForItem(item?: PacketTemplateLibraryItem) {
  if (item?.theme_id) {
    return item.theme_id;
  }
  return item?.base_template_id === "district_branding" ? "district_colors" : "teacher_friendly";
}

function customizationForPalette(themeId: string, current?: Partial<ThemeCustomization>) {
  const base = themeId === "district_colors"
    ? districtBrandingCustomization
    : { ...defaultCustomization, ...(current ?? {}) };
  return { ...base, ...(current ?? {}), service_area_colors: current?.service_area_colors ?? base.service_area_colors ?? {} };
}

function paletteDraftFromTheme(theme?: ThemeOption, customization: ThemeCustomization = defaultCustomization): ThemePaletteDraft {
  return {
    name: theme?.name ?? "Custom Palette",
    description: theme?.description ?? "",
    category: theme?.category ?? "Custom",
    customization,
  };
}

function templateDraftFromItem(item?: PacketTemplateLibraryItem): PacketTemplateLibraryDraft {
  const themeId = themeIdForItem(item);
  const baseTemplateId = item?.base_template_id ?? "modern_professional";
  const customization = customizationForPalette(themeId, item?.customization);
  return {
    name: item?.name ?? "Custom Template",
    description: item?.description ?? "",
    category: item?.category ?? "Custom",
    base_template_id: baseTemplateId,
    theme_id: themeId,
    customization,
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
    watermark_logo_relative_path: item?.watermark_logo_relative_path ?? "",
    watermark_logo_filename: item?.watermark_logo_filename ?? "",
    watermark_enabled: item?.watermark_enabled ?? false,
    default_fonts: item?.default_fonts ?? "Open Sans",
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
  modern_professional: { panel: "linear-gradient(132deg, #ffffff 0%, #ffffff 58%, rgba(67,192,189,0.14) 58%, rgba(67,192,189,0.14) 100%)", accent: "#0f8b8d", mode: "light", label: "Geometric" },
  district_branding: { panel: "linear-gradient(180deg, #ffffff, #ffffff)", accent: "#d89a2b", mode: "light", label: "Logo-ready" },
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
  const isModern = baseId === "modern_professional";
  const isDistrict = baseId === "district_branding";
  const districtPrimary = colors.primary_color;
  const districtSecondary = colors.secondary_color;
  const districtAccent = colors.accent_color;
  const coverTextColor = isModern ? "#0d2848" : isDistrict ? districtPrimary : textColor;
  const bottomTextColor = isModern || isDistrict ? "#ffffff" : textColor;
  const coverTitleStyle = baseId === "botanical_frame" || baseId === "soft_organic"
    ? { fontFamily: "Georgia, serif", letterSpacing: "0.04em" }
    : baseId === "elementary_pop"
      ? { letterSpacing: "0.06em", textShadow: "2px 2px 0 rgba(244,169,55,.22)" }
      : {};
  const pageAccentStyle = baseId === "alpine_photo" || baseId === "chalkboard"
    ? { backgroundColor: baseId === "alpine_photo" ? "#0d1f35" : "#1f2933", color: "#ffffff", borderColor: "transparent" }
    : baseId === "district_branding"
      ? { backgroundColor: colors.card_color, borderColor: districtPrimary, color: colors.text_color, borderTop: `8px solid ${districtPrimary}`, borderBottom: `8px solid ${districtAccent}` }
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
            {isDistrict && (
              <>
                <div className="absolute inset-x-0 top-0 h-3" style={{ backgroundColor: districtPrimary }} />
                <div className="absolute inset-x-0 bottom-0 h-[34%]" style={{ background: `linear-gradient(90deg, ${districtPrimary}, ${districtSecondary})` }} />
                <div className="absolute inset-x-0 bottom-0 h-3" style={{ backgroundColor: districtAccent }} />
                <div className="absolute left-2 top-20 -rotate-90 text-[0.5rem] font-black uppercase tracking-[0.22em] text-slate-300">District Branding</div>
              </>
            )}
            {isModern && (
              <>
                <div className="absolute bottom-0 right-0 h-[35%] w-full bg-[#0d2848]" style={{ clipPath: "polygon(36% 0, 100% 0, 100% 100%, 0 100%)" }} />
                <div className="absolute bottom-0 right-0 h-[14%] w-full bg-[#0f8b8d]" style={{ clipPath: "polygon(70% 0, 100% 0, 100% 100%, 42% 100%)" }} />
              </>
            )}
            <div className="absolute -bottom-10 left-4 h-28 w-40 rotate-45 opacity-25" style={{ backgroundColor: tone.accent }} />
            <div className="absolute -right-10 bottom-8 h-32 w-44 rotate-45 opacity-20" style={{ backgroundColor: colors.secondary_color }} />
            {baseId === "mountain_illustrated" && <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-teal-950/70 to-transparent" />}
            {baseId === "purple_dot" && <div className="absolute right-0 top-0 h-full w-28 opacity-70" style={{ backgroundImage: "radial-gradient(circle, rgba(126,87,194,.42) 0 2px, transparent 2px)", backgroundSize: "14px 14px" }} />}
            <div className="relative text-center">
              <div className={`mx-auto mb-4 grid h-14 w-14 place-items-center text-lg font-black shadow-lg ${isModern ? "rounded-2xl" : "rounded-full"}`} style={{ backgroundColor: isDistrict ? districtPrimary : tone.accent, color: "#ffffff" }}>SP</div>
              <p className="text-[0.62rem] font-bold uppercase tracking-[0.28em]" style={{ color: isDistrict ? districtAccent : tone.accent }}>Special Education</p>
              <h4 className="mt-3 text-4xl font-black uppercase leading-none tracking-normal" style={{ color: coverTextColor, ...coverTitleStyle }}>Service<br />Packet</h4>
              <div className="mx-auto mt-5 max-w-[14rem] px-5 py-2 text-center text-sm font-bold text-white" style={{ backgroundColor: isDistrict ? districtAccent : colors.secondary_color }}>2026-2027</div>
              <p className="mt-5 text-lg font-black uppercase" style={{ color: isDistrict ? districtPrimary : tone.accent }}>Sample Student</p>
            </div>
            <div className={`relative ${isModern ? "ml-auto w-[78%] rounded-tl-xl bg-[#0d2848] p-3" : ""} ${isDistrict ? "rounded-lg p-3" : ""}`}>
              <div className="mb-5 flex justify-center gap-4">
                {["R", "W", "S"].map((label, index) => (
                  <div key={label} className="w-16 text-center text-[0.52rem] font-black uppercase leading-tight" style={{ color: bottomTextColor }}>
                    <div className="mx-auto mb-2 grid h-11 w-11 place-items-center rounded-full text-sm font-black text-white" style={{ backgroundColor: isDistrict ? (index === 0 ? districtPrimary : index === 1 ? districtSecondary : districtAccent) : index === 0 ? colors.primary_color : index === 1 ? colors.secondary_color : colors.accent_color }}>{label}</div>
                    {index === 0 ? "Reading" : index === 1 ? "Written" : "Speech"}
                  </div>
                ))}
              </div>
              <div className={`grid grid-cols-2 gap-2 ${baseId === "district_branding" || baseId === "botanical_frame" ? "border border-slate-300 bg-white/70" : ""} p-2 text-[0.55rem]`}>
                {["Grade 4", "IEP 2026-2027", "Case Manager", "School"].map((label) => (
                  <div key={label} className="rounded-md border border-white/20 bg-white/10 p-2 font-bold" style={{ color: bottomTextColor }}>{label}</div>
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
  const [appSettings, setAppSettings] = useState<AppSettings>(defaultAppSettings);
  const [settingsModal, setSettingsModal] = useState<SettingsModal>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<PacketTemplateLibraryItem | null>(null);
  const [templateDraft, setTemplateDraft] = useState<PacketTemplateLibraryDraft>(templateDraftFromItem());
  const [paletteDraft, setPaletteDraft] = useState<ThemePaletteDraft>(paletteDraftFromTheme(undefined, templateDraftFromItem().customization));
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
    void getAppSettings().then(setAppSettings).catch(() => setAppSettings(defaultAppSettings));
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

  async function refreshThemes() {
    const nextThemes = await listThemes();
    setThemes(nextThemes);
    return nextThemes;
  }

  async function saveSettings(next: AppSettings) {
    setError("");
    try {
      setAppSettings(await saveAppSettings(next));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Settings could not be saved.");
    }
  }

  function openTemplateEditor(template?: PacketTemplateLibraryItem) {
    setSelectedTemplate(template ?? null);
    const draft = templateDraftFromItem(template);
    if (baseTemplates.length && !baseTemplates.some((base) => base.id === draft.base_template_id)) {
      draft.base_template_id = "modern_professional";
    }
    if (themes.length && !themes.some((theme) => theme.id === draft.theme_id)) {
      const preferredFallback = draft.base_template_id === "district_branding" ? "district_colors" : "teacher_friendly";
      draft.theme_id = themes.some((theme) => theme.id === preferredFallback)
        ? preferredFallback
        : themes[0].id;
      draft.customization = customizationForPalette(
        draft.theme_id,
        themes.find((theme) => theme.id === draft.theme_id)?.default_customization ?? draft.customization,
      );
    }
    setTemplateDraft(draft);
    const theme = themes.find((candidate) => candidate.id === draft.theme_id);
    setPaletteDraft(paletteDraftFromTheme(theme, draft.customization));
    setHoveredBaseTemplateId(null);
    setEditingTemplate(true);
  }

  async function savePaletteEditor() {
    setError("");
    try {
      const selectedTheme = themes.find((theme) => theme.id === templateDraft.theme_id);
      const draft = { ...paletteDraft, customization: templateDraft.customization };
      const saved = selectedTheme
        ? await updateThemePalette(selectedTheme.id, draft)
        : await createThemePalette(draft);
      await refreshThemes();
      const customization = customizationForPalette(saved.id, saved.default_customization);
      setPaletteDraft(paletteDraftFromTheme(saved, customization));
      setTemplateDraft({
        ...templateDraft,
        theme_id: saved.id,
        customization,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Palette could not be saved.");
    }
  }

  async function addNewPalette() {
    const name = window.prompt("Palette name");
    if (name === null) return;
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Enter a palette name.");
      return;
    }
    setError("");
    try {
      const saved = await createThemePalette({
        ...paletteDraft,
        name: trimmedName,
        description: paletteDraft.description,
        category: paletteDraft.category || "Custom",
        customization: templateDraft.customization,
      });
      await refreshThemes();
      const customization = customizationForPalette(saved.id, saved.default_customization);
      setPaletteDraft(paletteDraftFromTheme(saved, customization));
      setTemplateDraft({
        ...templateDraft,
        theme_id: saved.id,
        customization,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Palette could not be saved.");
    }
  }

  async function deleteSelectedPalette() {
    const selectedTheme = themes.find((theme) => theme.id === templateDraft.theme_id);
    if (!selectedTheme || selectedTheme.id === "minimal") return;
    if (!window.confirm(`Delete "${selectedTheme.name}"? Templates keep their saved colors, but this palette will be removed from the palette list.`)) return;
    setError("");
    try {
      await deleteThemePalette(selectedTheme.id);
      const nextThemes = await refreshThemes();
      const preferredFallback = templateDraft.base_template_id === "district_branding" ? "district_colors" : "teacher_friendly";
      const fallback = nextThemes.some((theme) => theme.id === preferredFallback) ? preferredFallback : "minimal";
      const fallbackTheme = nextThemes.find((theme) => theme.id === fallback);
      const customization = customizationForPalette(fallback, fallbackTheme?.default_customization ?? templateDraft.customization);
      setTemplateDraft({
        ...templateDraft,
        theme_id: fallback,
        customization,
      });
      setPaletteDraft(paletteDraftFromTheme(fallbackTheme, customization));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Palette could not be deleted.");
    }
  }

  async function saveTemplateEditor() {
    setError("");
    try {
      const saved = selectedTemplate && !selectedTemplate.is_builtin
        ? await updateTemplateLibraryItem(selectedTemplate.id, templateDraft)
        : selectedTemplate
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
      const saved = selectedBrandKit
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

  async function uploadSelectedBrandKitLogo(file: File | null, logoKind: "cover" | "watermark" = "cover") {
    if (!file || !selectedBrandKit) return;
    setError("");
    try {
      const saved = await uploadBrandKitLogo({
        brandKitId: selectedBrandKit.id,
        filename: file.name,
        contentType: file.type || "application/octet-stream",
        dataBase64: await fileToBase64(file),
        logoKind,
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
          actions={<Button variant="outline" onClick={() => {
            setSelectedBrandKit(brandKits[0] ?? null);
            setBrandKitDraft(brandKitDraftFromItem(brandKits[0]));
            setEditingBrandKit(true);
          }}>Manage Brand Kits</Button>}
        >
          <div className="grid gap-2 sm:grid-cols-2">
            {([
              ["school_year", "Default School Year"],
              ["export", "Export Defaults"],
              ["packet_pages", "Default Packet Pages"],
              ["observation_checklist", "Observation Checklist"],
              ["data_columns", "Data Table Columns"],
              ["service_presets", "Service Area Presets"],
              ["case_manager", "Case Manager Profile"],
            ] as const).map(([key, label]) => (
              <Button key={key} variant="outline" onClick={() => setSettingsModal(key)}>
                {label}
              </Button>
            ))}
          </div>
        </Card>
      </div>
      {editingTemplate && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-6">
          <div className="max-h-[92vh] w-full max-w-6xl overflow-auto rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold text-[var(--theme-primary)]">{selectedTemplate ? "Edit Template" : "Create Template"}</h2>
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
                          onClick={() => {
                            const preferredThemeId = template.id === "district_branding" ? "district_colors" : templateDraft.theme_id;
                            const themeId = themes.some((candidate) => candidate.id === preferredThemeId)
                              ? preferredThemeId
                              : themes[0]?.id ?? templateDraft.theme_id;
                            const theme = themes.find((candidate) => candidate.id === themeId);
                            const customization = template.id === "district_branding" && themeId === "district_colors"
                              ? customizationForPalette("district_colors", templateDraft.theme_id === "district_colors" ? templateDraft.customization : undefined)
                              : templateDraft.customization;
                            setTemplateDraft({
                              ...templateDraft,
                              base_template_id: template.id,
                              theme_id: themeId,
                              customization,
                            });
                            setPaletteDraft(paletteDraftFromTheme(theme, customization));
                          }}
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
                      const customization = customizationForPalette(event.target.value, theme?.default_customization ?? templateDraft.customization);
                      setTemplateDraft({
                        ...templateDraft,
                        theme_id: event.target.value,
                        customization,
                      });
                      setPaletteDraft(paletteDraftFromTheme(theme, customization));
                    }}
                  >
                    {themes.map((theme) => <option key={theme.id} value={theme.id}>{theme.name}</option>)}
                  </select>
                </label>

                <div className="rounded-xl border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-[var(--theme-text)]">Palette Details</p>
                      <p className="mt-1 text-xs text-[var(--theme-text-muted)]">
                        Rename, recolor, or save reusable palettes for packet templates.
                      </p>
                    </div>
                    {templateDraft.theme_id !== "minimal" && (
                      <Button variant="text" onClick={() => void deleteSelectedPalette()}>Delete</Button>
                    )}
                  </div>
                  <label className="mt-3 block text-xs font-semibold text-[var(--theme-text-muted)]">
                    Palette Name
                    <TextInput className="mt-2" value={paletteDraft.name} onChange={(event) => setPaletteDraft({ ...paletteDraft, name: event.target.value })} />
                  </label>
                  <label className="mt-3 block text-xs font-semibold text-[var(--theme-text-muted)]">
                    Palette Category
                    <TextInput className="mt-2" value={paletteDraft.category} onChange={(event) => setPaletteDraft({ ...paletteDraft, category: event.target.value })} />
                  </label>
                  <label className="mt-3 block text-xs font-semibold text-[var(--theme-text-muted)]">
                    Palette Description
                    <TextInput className="mt-2" value={paletteDraft.description} onChange={(event) => setPaletteDraft({ ...paletteDraft, description: event.target.value })} />
                  </label>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button variant="outline" onClick={() => void savePaletteEditor()}>
                      Update Palette
                    </Button>
                    <Button variant="text" onClick={() => void addNewPalette()}>
                      Add New Palette
                    </Button>
                  </div>
                </div>

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
                      <input
                        className="mt-2 h-10 w-full rounded-lg border border-[var(--theme-border)] bg-white p-1"
                        type="color"
                        value={templateDraft.customization[key]}
                        onChange={(event) => {
                          const customization = { ...templateDraft.customization, [key]: event.target.value };
                          setTemplateDraft({ ...templateDraft, customization });
                          setPaletteDraft({ ...paletteDraft, customization });
                        }}
                      />
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
      {settingsModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-6">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold text-[var(--theme-primary)]">
                  {{
                    school_year: "Default School Year",
                    export: "Export Defaults",
                    packet_pages: "Default Packet Pages",
                    observation_checklist: "Default Observation Checklist",
                    data_columns: "Default Data Table Columns",
                    service_presets: "Service Area Presets",
                    case_manager: "Case Manager Profile",
                  }[settingsModal]}
                </h2>
                <p className="mt-1 text-sm text-[var(--theme-text-muted)]">
                  These defaults are applied to new projects and packet generation.
                </p>
              </div>
              <Button variant="text" onClick={() => setSettingsModal(null)}>Close</Button>
            </div>

            <div className="mt-5 space-y-4">
              {settingsModal === "school_year" && (
                <label className="block text-sm font-semibold text-[var(--theme-text)]">
                  School year
                  <TextInput
                    className="mt-2"
                    placeholder="2026-2027"
                    value={appSettings.default_school_year}
                    onChange={(event) => setAppSettings({ ...appSettings, default_school_year: event.target.value })}
                  />
                </label>
              )}

              {settingsModal === "export" && (
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="text-sm font-semibold text-[var(--theme-text)]">
                    Default packet template
                    <select
                      className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm"
                      value={appSettings.default_packet_template_id}
                      onChange={(event) => setAppSettings({ ...appSettings, default_packet_template_id: event.target.value })}
                    >
                      {templateLibrary.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
                    </select>
                  </label>
                  <label className="text-sm font-semibold text-[var(--theme-text)]">
                    Default palette
                    <select
                      className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm"
                      value={appSettings.default_theme_id}
                      onChange={(event) => setAppSettings({ ...appSettings, default_theme_id: event.target.value })}
                    >
                      {themes.map((theme) => <option key={theme.id} value={theme.id}>{theme.name}</option>)}
                    </select>
                  </label>
                  <label className="text-sm font-semibold text-[var(--theme-text)] md:col-span-2">
                    Filename format
                    <TextInput
                      className="mt-2"
                      placeholder="<Student Name> - <Packet Type> - <School Year>"
                      value={appSettings.default_export_settings.filename_template}
                      onChange={(event) => setAppSettings({
                        ...appSettings,
                        default_export_settings: { ...appSettings.default_export_settings, filename_template: event.target.value },
                      })}
                    />
                  </label>
                  <label className="text-sm font-semibold text-[var(--theme-text)] md:col-span-2">
                    Default export folder
                    <TextInput
                      className="mt-2"
                      placeholder="C:\\Users\\Ryan\\Documents\\Packets"
                      value={appSettings.default_export_settings.last_export_location}
                      onChange={(event) => setAppSettings({
                        ...appSettings,
                        default_export_settings: { ...appSettings.default_export_settings, last_export_location: event.target.value },
                      })}
                    />
                  </label>
                  <label className="text-sm font-semibold text-[var(--theme-text)]">
                    Export mode
                    <select
                      className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm"
                      value={appSettings.default_export_settings.export_mode}
                      onChange={(event) => setAppSettings({
                        ...appSettings,
                        default_export_settings: { ...appSettings.default_export_settings, export_mode: event.target.value as "single_pdf" | "zip_archive" },
                      })}
                    >
                      <option value="single_pdf">Single PDF</option>
                      <option value="zip_archive">ZIP Archive of All</option>
                    </select>
                  </label>
                </div>
              )}

              {settingsModal === "packet_pages" && (
                <div className="space-y-2">
                  {appSettings.default_packet_pages.map((page, index) => (
                    <div key={page.id} className="flex items-center gap-2 rounded-xl border border-[var(--theme-border)] bg-white p-3">
                      <input
                        type="checkbox"
                        checked={page.enabled}
                        onChange={(event) => {
                          const pages = [...appSettings.default_packet_pages];
                          pages[index] = { ...page, enabled: event.target.checked };
                          setAppSettings({ ...appSettings, default_packet_pages: pages });
                        }}
                      />
                      <span className="flex-1 text-sm font-semibold text-[var(--theme-text)]">{page.title}</span>
                      <Button
                        variant="text"
                        disabled={index === 0}
                        onClick={() => {
                          const pages = [...appSettings.default_packet_pages];
                          [pages[index - 1], pages[index]] = [pages[index], pages[index - 1]];
                          setAppSettings({ ...appSettings, default_packet_pages: pages.map((item, position) => ({ ...item, position })) });
                        }}
                      >
                        Up
                      </Button>
                      <Button
                        variant="text"
                        disabled={index === appSettings.default_packet_pages.length - 1}
                        onClick={() => {
                          const pages = [...appSettings.default_packet_pages];
                          [pages[index], pages[index + 1]] = [pages[index + 1], pages[index]];
                          setAppSettings({ ...appSettings, default_packet_pages: pages.map((item, position) => ({ ...item, position })) });
                        }}
                      >
                        Down
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {settingsModal === "observation_checklist" && (
                <div className="space-y-2">
                  {appSettings.default_observation_checklist.map((item, index) => (
                    <div key={`${item}-${index}`} className="flex gap-2">
                      <TextInput
                        value={item}
                        onChange={(event) => {
                          const items = [...appSettings.default_observation_checklist];
                          items[index] = event.target.value;
                          setAppSettings({ ...appSettings, default_observation_checklist: items });
                        }}
                      />
                      <Button
                        variant="text"
                        onClick={() => setAppSettings({
                          ...appSettings,
                          default_observation_checklist: appSettings.default_observation_checklist.filter((_, itemIndex) => itemIndex !== index),
                        })}
                      >
                        Delete
                      </Button>
                    </div>
                  ))}
                  <Button variant="outline" onClick={() => setAppSettings({ ...appSettings, default_observation_checklist: [...appSettings.default_observation_checklist, ""] })}>Add Item</Button>
                </div>
              )}

              {settingsModal === "data_columns" && (
                <div className="space-y-2">
                  {appSettings.default_data_sheet_columns.map((column, index) => (
                    <div key={column.id} className="grid gap-2 rounded-xl border border-[var(--theme-border)] bg-white p-3 md:grid-cols-[1fr_10rem_auto]">
                      <TextInput
                        aria-label="Column title"
                        value={column.title}
                        onChange={(event) => {
                          const columns = [...appSettings.default_data_sheet_columns];
                          columns[index] = { ...column, title: event.target.value };
                          setAppSettings({ ...appSettings, default_data_sheet_columns: columns });
                        }}
                      />
                      <select
                        className="rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm"
                        value={column.column_type}
                        onChange={(event) => {
                          const columns = [...appSettings.default_data_sheet_columns];
                          columns[index] = { ...column, column_type: event.target.value as typeof column.column_type };
                          setAppSettings({ ...appSettings, default_data_sheet_columns: columns });
                        }}
                      >
                        <option value="text">Text</option>
                        <option value="number">Number</option>
                        <option value="date">Date</option>
                        <option value="checkbox">Checkbox</option>
                        <option value="notes">Notes</option>
                      </select>
                      <Button
                        variant="text"
                        onClick={() => setAppSettings({
                          ...appSettings,
                          default_data_sheet_columns: appSettings.default_data_sheet_columns.filter((_, columnIndex) => columnIndex !== index).map((item, position) => ({ ...item, position })),
                        })}
                      >
                        Delete
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    onClick={() => {
                      const position = appSettings.default_data_sheet_columns.length;
                      setAppSettings({
                        ...appSettings,
                        default_data_sheet_columns: [
                          ...appSettings.default_data_sheet_columns,
                          { id: `column_${Date.now()}`, title: "New Column", column_type: "text", position },
                        ],
                      });
                    }}
                  >
                    Add Column
                  </Button>
                </div>
              )}

              {settingsModal === "service_presets" && (
                <div className="space-y-3">
                  {appSettings.service_area_presets.map((area, index) => (
                    <div key={area.id ?? index} className="grid gap-2 rounded-xl border border-[var(--theme-border)] bg-white p-3 md:grid-cols-2">
                      <TextInput placeholder="Service area" value={area.name} onChange={(event) => {
                        const serviceAreas = [...appSettings.service_area_presets];
                        serviceAreas[index] = { ...area, name: event.target.value };
                        setAppSettings({ ...appSettings, service_area_presets: serviceAreas });
                      }} />
                      <TextInput placeholder="Setting" value={area.setting} onChange={(event) => {
                        const serviceAreas = [...appSettings.service_area_presets];
                        serviceAreas[index] = { ...area, setting: event.target.value };
                        setAppSettings({ ...appSettings, service_area_presets: serviceAreas });
                      }} />
                      <TextInput placeholder="Minutes per week" value={area.minutes_per_week?.toString() ?? ""} onChange={(event) => {
                        const serviceAreas = [...appSettings.service_area_presets];
                        serviceAreas[index] = { ...area, minutes_per_week: event.target.value ? Number(event.target.value) : null };
                        setAppSettings({ ...appSettings, service_area_presets: serviceAreas });
                      }} />
                      <select
                        className="rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm"
                        value={area.delivery_model ?? ""}
                        onChange={(event) => {
                          const serviceAreas = [...appSettings.service_area_presets];
                          serviceAreas[index] = { ...area, delivery_model: event.target.value ? event.target.value as typeof area.delivery_model : null };
                          setAppSettings({ ...appSettings, service_area_presets: serviceAreas });
                        }}
                      >
                        <option value="">Delivery model</option>
                        <option value="push_in">Push in</option>
                        <option value="pull_out">Pull out</option>
                        <option value="combined">Combined</option>
                        <option value="other">Other</option>
                      </select>
                      <Button
                        variant="text"
                        onClick={() => setAppSettings({
                          ...appSettings,
                          service_area_presets: appSettings.service_area_presets.filter((_, areaIndex) => areaIndex !== index).map((item, position) => ({ ...item, position })),
                        })}
                      >
                        Delete Service Preset
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    onClick={() => {
                      const position = appSettings.service_area_presets.length;
                      setAppSettings({
                        ...appSettings,
                        service_area_presets: [
                          ...appSettings.service_area_presets,
                          { id: null, name: "", setting: "Special Education", minutes_per_week: null, delivery_model: null, notes: "", position },
                        ],
                      });
                    }}
                  >
                    Add Service Area Preset
                  </Button>
                </div>
              )}

              {settingsModal === "case_manager" && (
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="text-sm font-semibold text-[var(--theme-text)]">First name<TextInput className="mt-2" value={appSettings.case_manager_profile.first_name} onChange={(event) => setAppSettings({ ...appSettings, case_manager_profile: { ...appSettings.case_manager_profile, first_name: event.target.value } })} /></label>
                  <label className="text-sm font-semibold text-[var(--theme-text)]">Last name<TextInput className="mt-2" value={appSettings.case_manager_profile.last_name} onChange={(event) => setAppSettings({ ...appSettings, case_manager_profile: { ...appSettings.case_manager_profile, last_name: event.target.value } })} /></label>
                  <label className="text-sm font-semibold text-[var(--theme-text)]">Phone<TextInput className="mt-2" value={appSettings.case_manager_profile.phone} onChange={(event) => setAppSettings({ ...appSettings, case_manager_profile: { ...appSettings.case_manager_profile, phone: event.target.value } })} /></label>
                  <label className="text-sm font-semibold text-[var(--theme-text)]">Email<TextInput className="mt-2" value={appSettings.case_manager_profile.email} onChange={(event) => setAppSettings({ ...appSettings, case_manager_profile: { ...appSettings.case_manager_profile, email: event.target.value } })} /></label>
                  <label className="text-sm font-semibold text-[var(--theme-text)] md:col-span-2">School<TextInput className="mt-2" value={appSettings.case_manager_profile.school} onChange={(event) => setAppSettings({ ...appSettings, case_manager_profile: { ...appSettings.case_manager_profile, school: event.target.value } })} /></label>
                  <label className="text-sm font-semibold text-[var(--theme-text)] md:col-span-2">Notes<TextInput className="mt-2" value={appSettings.case_manager_profile.notes} onChange={(event) => setAppSettings({ ...appSettings, case_manager_profile: { ...appSettings.case_manager_profile, notes: event.target.value } })} /></label>
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setSettingsModal(null)}>Cancel</Button>
              <Button onClick={() => {
                void saveSettings(appSettings);
                setSettingsModal(null);
              }}>Save Settings</Button>
            </div>
          </div>
        </div>
      )}
      {editingBrandKit && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-6">
          <div className="max-h-[90vh] w-full max-w-5xl overflow-auto rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold text-[var(--theme-primary)]">Brand Kits</h2>
                <p className="mt-1 text-sm text-[var(--theme-text-muted)]">Choose, create, edit, and remove reusable district identity kits. Colors are managed through palettes.</p>
              </div>
              <Button variant="text" onClick={() => setEditingBrandKit(false)}>Close</Button>
            </div>
            <div className="mt-5 grid gap-5 lg:grid-cols-[17rem_1fr]">
              <div className="space-y-2">
                <Button className="w-full justify-center" variant="outline" onClick={() => openBrandKitEditor()}>
                  Add Brand Kit
                </Button>
                {brandKits.map((kit) => (
                  <button
                    key={kit.id}
                    className={`w-full rounded-xl border px-3 py-2.5 text-left text-sm transition ${selectedBrandKit?.id === kit.id ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)]" : "border-[var(--theme-border)] bg-white hover:bg-[var(--theme-surface-muted)]"}`}
                    onClick={() => {
                      setSelectedBrandKit(kit);
                      setBrandKitDraft(brandKitDraftFromItem(kit));
                    }}
                  >
                    <span className="font-semibold text-[var(--theme-text)]">{kit.name}</span>
                    {kit.is_default && <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-[var(--theme-primary)]">Default</span>}
                    <span className="mt-1 block text-xs text-[var(--theme-text-muted)]">{kit.district_name || kit.school_name || "No district or school label yet."}</span>
                  </button>
                ))}
                {!brandKits.length && (
                  <p className="rounded-xl border border-dashed border-[var(--theme-border)] p-3 text-sm text-[var(--theme-text-muted)]">
                    No saved Brand Kits yet.
                  </p>
                )}
              </div>

              <div className="rounded-2xl border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] p-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="text-sm font-semibold text-[var(--theme-text)]">Brand Kit Name<TextInput className="mt-2" value={brandKitDraft.name} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, name: event.target.value })} /></label>
                  <label className="text-sm font-semibold text-[var(--theme-text)]">
                    Font
                    <select
                      className="mt-2 w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm"
                      value={brandKitDraft.default_fonts}
                      onChange={(event) => setBrandKitDraft({ ...brandKitDraft, default_fonts: event.target.value })}
                    >
                      <option value="Open Sans">Open Sans</option>
                      <option value="Poppins">Poppins</option>
                      <option value="Segoe UI">Segoe UI</option>
                      <option value="Arial">Arial</option>
                      <option value="Georgia">Georgia</option>
                      <option value="Times New Roman">Times New Roman</option>
                    </select>
                  </label>
                  <label className="text-sm font-semibold text-[var(--theme-text)]">District<TextInput className="mt-2" value={brandKitDraft.district_name} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, district_name: event.target.value })} /></label>
                  <label className="text-sm font-semibold text-[var(--theme-text)]">School<TextInput className="mt-2" value={brandKitDraft.school_name} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, school_name: event.target.value })} /></label>
                  <label className="text-sm font-semibold text-[var(--theme-text)] md:col-span-2">Footer Text<TextInput className="mt-2" value={brandKitDraft.footer_text} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, footer_text: event.target.value })} /></label>
                  <label className="text-sm font-semibold text-[var(--theme-text)]">
                    Cover logo
                    <input accept="image/png,image/jpeg,image/svg+xml" className="mt-2 block w-full text-sm text-[var(--theme-text-muted)] file:mr-3 file:rounded-lg file:border-0 file:bg-[var(--theme-primary)] file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white" disabled={!selectedBrandKit} type="file" onChange={(event) => void uploadSelectedBrandKitLogo(event.target.files?.[0] ?? null, "cover")} />
                    {brandKitDraft.logo_filename && <span className="mt-2 block text-xs text-[var(--theme-primary)]">Current cover logo: {brandKitDraft.logo_filename}</span>}
                    {!selectedBrandKit && <span className="mt-2 block text-xs text-[var(--theme-text-muted)]">Save the Brand Kit before uploading a logo.</span>}
                  </label>
                  <label className="text-sm font-semibold text-[var(--theme-text)]">
                    Watermark logo
                    <input accept="image/png,image/jpeg,image/svg+xml" className="mt-2 block w-full text-sm text-[var(--theme-text-muted)] file:mr-3 file:rounded-lg file:border-0 file:bg-[var(--theme-primary)] file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white" disabled={!selectedBrandKit} type="file" onChange={(event) => void uploadSelectedBrandKitLogo(event.target.files?.[0] ?? null, "watermark")} />
                    {brandKitDraft.watermark_logo_filename && <span className="mt-2 block text-xs text-[var(--theme-primary)]">Current watermark logo: {brandKitDraft.watermark_logo_filename}</span>}
                  </label>
                  <label className="flex items-center gap-2 rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm font-semibold text-[var(--theme-text)] md:col-span-2">
                    <input type="checkbox" checked={brandKitDraft.watermark_enabled} onChange={(event) => setBrandKitDraft({ ...brandKitDraft, watermark_enabled: event.target.checked })} />
                    Use uploaded watermark logo on interior pages
                  </label>
                </div>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              {selectedBrandKit && (
                <>
                  <Button variant="outline" onClick={() => void duplicateSelectedBrandKit()}>Duplicate</Button>
                  <Button variant="outline" onClick={() => void setSelectedBrandKitDefault()}>Set Default</Button>
                  <Button variant="text" onClick={() => void deleteSelectedBrandKit()}>Delete</Button>
                </>
              )}
              <Button variant="outline" onClick={() => setEditingBrandKit(false)}>Cancel</Button>
              <Button onClick={() => void saveBrandKitEditor()}>Save Brand Kit</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
