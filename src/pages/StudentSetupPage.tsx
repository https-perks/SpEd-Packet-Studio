import { useEffect, useMemo, useState } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FieldFrame, selectClass, TextArea, TextInput } from "../components/ui/FormField";
import { ValidationSummary } from "../components/workflow/ValidationSummary";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import { useAutosave } from "../hooks/useAutosave";
import { validateStudentSetup } from "../lib/validation";
import { useTerminology } from "../terminology/TerminologyProvider";
import { getAppSettings, saveAppSettings, saveStudentSetup } from "../services/api/projects";
import type {
  AccommodationDraft,
  AppSettings,
  Audience,
  BehaviorPlanSectionDraft,
  ProjectDetail,
  RelatedServiceProviderDraft,
  ServiceAreaDraft,
  StudentSetupDraft,
} from "../types/projects";

const settingOptions = ["Regular Education", "Special Education"] as const;
const customSettingValue = "__custom_setting__";
type StudentSetupModal = "accommodations" | "behavior_plan" | "related_services" | null;
const accommodationAreaOptions = ["Instructional", "Classroom Assessment", "Personnel", "Parent", "Other"] as const;
const relatedServiceProviderOptions = ["Speech/Language Pathologist", "Occupational Therapist", "Physical Therapist"] as const;
const defaultBehaviorPlanSections = [
  "Defined Problem Behavior",
  "Context and Function (FBA Results)",
  "Prevention Strategies",
  "Replacement Behaviors",
  "Response Strategies",
  "Safety Net/Crisis Plan",
  "Monitoring and Adjustment",
] as const;

const fallbackServiceAreaPresets = [
  "Reading",
  "Math",
  "Written Expression",
  "Social/Emotional/Behavioral",
  "Self-Help/Independence",
];

function deriveInitials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase())
    .join("")
    .slice(0, 4);
}

function suggestSchoolYear(dateValue: string) {
  if (!dateValue) return "";
  const date = new Date(`${dateValue}T00:00:00`);
  const start = date.getMonth() >= 6 ? date.getFullYear() : date.getFullYear() - 1;
  return `${start}-${start + 1}`;
}

function blankServiceArea(position: number): ServiceAreaDraft {
  return {
    name: "",
    setting: "",
    minutes_per_week: null,
    notes: "",
    position,
  };
}

function blankAccommodation(position: number): AccommodationDraft {
  return {
    id: null,
    content_area: "Instructional",
    custom_content_area: "",
    text: "",
    position,
  };
}

function accommodationLabel(item: AccommodationDraft) {
  if (item.content_area === "Other") return item.custom_content_area.trim() || "Other";
  return item.content_area || "Instructional";
}

function blankBehaviorPlanSection(position: number, existingSections: readonly BehaviorPlanSectionDraft[] = []): BehaviorPlanSectionDraft {
  const usedTitles = new Set(existingSections.map((section) => section.title.trim()).filter(Boolean));
  const nextTitle = defaultBehaviorPlanSections.find((title) => !usedTitles.has(title)) ?? "New Behavior Plan Section";
  return {
    id: null,
    title: nextTitle,
    text: "",
    position,
  };
}

function blankRelatedServiceProvider(position: number): RelatedServiceProviderDraft {
  return {
    id: null,
    name: "",
    email: "",
    phone: "",
    service_area: "Speech/Language Pathologist",
    position,
  };
}

function settingSelectValue(setting: string) {
  if (!setting) return "";
  return settingOptions.includes(setting as (typeof settingOptions)[number])
    ? setting
    : customSettingValue;
}

function serviceAreaKey(_area: ServiceAreaDraft, index: number) {
  return `service-area-${index}`;
}

function initialDraft(project: ProjectDetail): StudentSetupDraft {
  const student = project.student
    ? {
        name: project.student.name,
        initials: project.student.initials,
        grade: project.student.grade,
        school: project.student.school,
        case_manager: project.student.case_manager,
        case_manager_first_name: project.student.case_manager_first_name,
        case_manager_last_name: project.student.case_manager_last_name,
        case_manager_phone: project.student.case_manager_phone,
        case_manager_email: project.student.case_manager_email,
        case_manager_notes: project.student.case_manager_notes,
        iep_end_date: project.student.iep_end_date,
      }
    : {
        name: "",
        initials: "",
        grade: "",
        school: "",
        case_manager: "",
        case_manager_first_name: "",
        case_manager_last_name: "",
        case_manager_phone: "",
        case_manager_email: "",
        case_manager_notes: "",
        iep_end_date: null,
      };

  return {
    project_name: project.name === "Untitled Student Project" ? "" : project.name,
    school_year: project.school_year,
    student,
    service_areas: project.service_areas.map((area) => ({ ...area })),
    audiences: [...project.audiences],
    accommodations: (project.accommodations ?? []).map((item) => ({ ...item })),
    accommodations_parent_strengths_enabled: project.accommodations_parent_strengths_enabled ?? false,
    accommodations_parent_strengths: project.accommodations_parent_strengths ?? "",
    behavior_plan: project.behavior_plan ?? "",
    behavior_plan_sections: (project.behavior_plan_sections ?? []).map((item) => ({ ...item })),
    related_service_providers: (project.related_service_providers ?? []).map((item) => ({ ...item })),
  };
}

interface StudentSetupPageProps {
  readonly project: ProjectDetail;
  readonly onProjectUpdate: (project: ProjectDetail) => void;
  readonly onBack: () => void;
  readonly onContinue: () => void;
}

export function StudentSetupPage({
  project,
  onProjectUpdate,
  onBack,
  onContinue,
}: StudentSetupPageProps) {
  const { fullTitle } = useTerminology();
  const [draft, setDraft] = useState<StudentSetupDraft>(() => initialDraft(project));
  const [saveError, setSaveError] = useState("");
  const [appSettings, setAppSettings] = useState<AppSettings | null>(null);
  const [openServiceAreaMenu, setOpenServiceAreaMenu] = useState<number | null>(null);
  const [addingServiceAreaForIndex, setAddingServiceAreaForIndex] = useState<number | null>(null);
  const [newServiceAreaName, setNewServiceAreaName] = useState("");
  const [contentModal, setContentModal] = useState<StudentSetupModal>(null);
  const [customSettingRows, setCustomSettingRows] = useState<ReadonlySet<string>>(
    () =>
      new Set(
        project.service_areas
          .map((area, index) => ({ key: serviceAreaKey(area, index), setting: area.setting }))
          .filter(({ setting }) => settingSelectValue(setting) === customSettingValue)
          .map(({ key }) => key),
      ),
  );
  const validation = useMemo(() => validateStudentSetup(draft), [draft]);
  const serviceAreaOptions = useMemo(() => {
    const saved = appSettings?.service_area_presets
      .map((area) => area.name.trim())
      .filter(Boolean) ?? [];
    return saved.length ? saved : fallbackServiceAreaPresets;
  }, [appSettings]);
  const packetAudienceOptions = useMemo(() => {
    const configured = appSettings?.packet_versions
      .map((version) => ({
        value: version.audience,
        label: version.name,
      }))
      .filter((version) => version.value && version.label.trim()) ?? [];
    const projectOnly = draft.audiences
      .filter((audience) => !configured.some((option) => option.value === audience))
      .map((audience) => {
        const version = project.packet_versions.find((item) => item.audience === audience);
        return {
          value: audience,
          label: version?.name || audience.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()),
        };
      });
    return [...configured, ...projectOnly];
  }, [appSettings, draft.audiences, project.packet_versions]);

  useEffect(() => {
    void getAppSettings()
      .then(setAppSettings)
      .catch(() => setAppSettings(null));
  }, []);

  const autosave = useAutosave({
    value: draft,
    delayMs: 850,
    save: async (value, signal) => {
      try {
        const saved = await saveStudentSetup(project.id, value, signal);
        setSaveError("");
        onProjectUpdate(saved);
        setDraft((current) => {
          const idsChanged = current.service_areas.some(
            (area, index) =>
              (saved.service_areas[index]?.id ?? area.id) !== area.id,
          );
          if (!idsChanged) return current;
          return {
            ...current,
            service_areas: current.service_areas.map((area, index) => ({
              ...area,
              id: saved.service_areas[index]?.id ?? area.id,
            })),
          };
        });
      } catch (reason) {
        if (signal.aborted) return;
        setSaveError(reason instanceof Error ? reason.message : "Draft could not be saved.");
        throw reason;
      }
    },
  });

  function updateStudent(field: keyof StudentSetupDraft["student"], value: string) {
    setDraft((current) => {
      const student = { ...current.student, [field]: value };
      if (field === "case_manager_first_name" || field === "case_manager_last_name") {
        student.case_manager = [student.case_manager_first_name, student.case_manager_last_name]
          .map((part) => part.trim())
          .filter(Boolean)
          .join(" ");
      }
      const next = { ...current, student };
      if (field === "name") {
        if (!current.student.initials || current.student.initials === deriveInitials(current.student.name)) {
          student.initials = deriveInitials(value);
        }
        const previousDefault = [current.student.name, current.school_year].filter(Boolean).join(" - ");
        if (!current.project_name || current.project_name === previousDefault) {
          next.project_name = [value.trim(), current.school_year].filter(Boolean).join(" - ");
        }
      }
      if (field === "iep_end_date") {
        const suggested = suggestSchoolYear(value);
        const previousSuggested = suggestSchoolYear(current.student.iep_end_date ?? "");
        if (!current.school_year || current.school_year === previousSuggested) {
          next.school_year = suggested;
          const previousDefault = [current.student.name, current.school_year].filter(Boolean).join(" - ");
          if (!current.project_name || current.project_name === previousDefault) {
            next.project_name = [current.student.name.trim(), suggested].filter(Boolean).join(" - ");
          }
        }
      }
      return next;
    });
  }

  function updateArea(index: number, patch: Partial<ServiceAreaDraft>) {
    setDraft((current) => ({
      ...current,
      service_areas: current.service_areas.map((area, areaIndex) =>
        areaIndex === index ? { ...area, ...patch } : area,
      ),
    }));
  }

  async function updateServiceAreaPresets(names: string[]) {
    if (!appSettings) return;
    const uniqueNames = Array.from(new Set(names.map((name) => name.trim()).filter(Boolean)));
    const nextSettings = {
      ...appSettings,
      service_area_presets: uniqueNames.map((name, position) => ({
        id: null,
        name,
        setting: "",
        minutes_per_week: null,
        notes: "",
        position,
      })),
    };
    setAppSettings(nextSettings);
    try {
      setAppSettings(await saveAppSettings(nextSettings));
      setSaveError("");
    } catch (reason) {
      setSaveError(reason instanceof Error ? reason.message : "Service area list could not be saved.");
    }
  }

  function openAddServiceAreaPreset(index: number) {
    setAddingServiceAreaForIndex(index);
    setNewServiceAreaName("");
    setOpenServiceAreaMenu(null);
  }

  async function saveNewServiceAreaPreset() {
    const trimmed = newServiceAreaName.trim();
    if (addingServiceAreaForIndex === null) return;
    if (!trimmed) return;
    await updateServiceAreaPresets([...serviceAreaOptions, trimmed]);
    updateArea(addingServiceAreaForIndex, { name: trimmed });
    setAddingServiceAreaForIndex(null);
    setNewServiceAreaName("");
    setOpenServiceAreaMenu(null);
  }

  function closeAddServiceAreaPreset() {
    setAddingServiceAreaForIndex(null);
    setNewServiceAreaName("");
  }

  async function deleteServiceAreaPreset(name: string) {
    await updateServiceAreaPresets(serviceAreaOptions.filter((option) => option !== name));
  }

  function moveArea(index: number, direction: -1 | 1) {
    setDraft((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.service_areas.length) return current;
      const serviceAreas = [...current.service_areas];
      [serviceAreas[index], serviceAreas[target]] = [serviceAreas[target], serviceAreas[index]];
      return {
        ...current,
        service_areas: serviceAreas.map((area, position) => ({ ...area, position })),
      };
    });
  }

  function toggleAudience(audience: Audience) {
    setDraft((current) => ({
      ...current,
      audiences: current.audiences.includes(audience)
        ? current.audiences.filter((value) => value !== audience)
        : [...current.audiences, audience],
    }));
  }

  async function saveAndContinue() {
    await autosave.saveImmediately();
    if (validation.is_complete) onContinue();
  }

  const fieldError = (field: string) =>
    validation.issues.find((issue) => issue.field === field)?.message;
  const hasAccommodations = draft.accommodations.some((item) => item.text.trim());
  const hasBehaviorPlan = draft.behavior_plan_sections.some((item) => item.text.trim()) || draft.behavior_plan.trim().length > 0;

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 1 of 7"
        title={`Student Setup${project.student?.name ? ` - ${project.student.name}` : ""}`}
        description="Create the student profile, service areas, and initial packet audiences that every later step will reference."
        status={autosave.status}
      />

      {saveError && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          {saveError}
        </div>
      )}

      <div className="grid gap-5">
        <Card
          title="Student information"
          description="Only information used by staff-facing service packets belongs here."
        >
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            <FieldFrame label="Student name" htmlFor="student-name" required error={fieldError("student.name")}>
              <TextInput
                id="student-name"
                value={draft.student.name}
                onChange={(event) => updateStudent("name", event.target.value)}
                placeholder="First and last name"
              />
            </FieldFrame>
            <FieldFrame label="Initials" htmlFor="initials">
              <TextInput
                id="initials"
                value={draft.student.initials}
                onChange={(event) => updateStudent("initials", event.target.value.toUpperCase())}
                maxLength={12}
              />
            </FieldFrame>
            <FieldFrame label="Grade" htmlFor="grade" required error={fieldError("student.grade")}>
              <TextInput
                id="grade"
                value={draft.student.grade}
                onChange={(event) => updateStudent("grade", event.target.value)}
                placeholder="Example: 7"
              />
            </FieldFrame>
            <FieldFrame label="School" htmlFor="school">
              <TextInput id="school" value={draft.student.school} onChange={(event) => updateStudent("school", event.target.value)} />
            </FieldFrame>
            <FieldFrame label="IEP end date" htmlFor="iep-end" required error={fieldError("student.iep_end_date")}>
              <TextInput id="iep-end" type="date" value={draft.student.iep_end_date ?? ""} onChange={(event) => updateStudent("iep_end_date", event.target.value)} />
            </FieldFrame>
            <FieldFrame label="School year" htmlFor="school-year">
              <TextInput id="school-year" value={draft.school_year} onChange={(event) => setDraft((current) => ({ ...current, school_year: event.target.value }))} placeholder="2026-2027" />
            </FieldFrame>
            <FieldFrame label="Project name" htmlFor="project-name">
              <TextInput id="project-name" value={draft.project_name} onChange={(event) => setDraft((current) => ({ ...current, project_name: event.target.value }))} />
            </FieldFrame>
          </div>
        </Card>

        <Card
          title="Case manager"
          description="This contact information appears in the Team Contacts box on the Service Information page."
          actions={(
            <Button variant="outline" onClick={() => setContentModal("related_services")}>
              Related Services
            </Button>
          )}
        >
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            <FieldFrame label="First name" htmlFor="case-manager-first">
              <TextInput
                id="case-manager-first"
                value={draft.student.case_manager_first_name}
                onChange={(event) => updateStudent("case_manager_first_name", event.target.value)}
              />
            </FieldFrame>
            <FieldFrame label="Last name" htmlFor="case-manager-last">
              <TextInput
                id="case-manager-last"
                value={draft.student.case_manager_last_name}
                onChange={(event) => updateStudent("case_manager_last_name", event.target.value)}
              />
            </FieldFrame>
            <FieldFrame label="Phone number" htmlFor="case-manager-phone">
              <TextInput
                id="case-manager-phone"
                type="tel"
                value={draft.student.case_manager_phone}
                onChange={(event) => updateStudent("case_manager_phone", event.target.value)}
              />
            </FieldFrame>
            <FieldFrame label="Email" htmlFor="case-manager-email">
              <TextInput
                id="case-manager-email"
                type="email"
                value={draft.student.case_manager_email}
                onChange={(event) => updateStudent("case_manager_email", event.target.value)}
              />
            </FieldFrame>
            <div className="md:col-span-2 xl:col-span-4">
              <FieldFrame label="Notes" htmlFor="case-manager-notes">
                <TextArea
                  id="case-manager-notes"
                  value={draft.student.case_manager_notes}
                  onChange={(event) => updateStudent("case_manager_notes", event.target.value)}
                  placeholder="Preferred contact times, role notes, or internal reminders"
                />
              </FieldFrame>
            </div>
          </div>
          <div className="mt-5 rounded-xl border border-[var(--theme-border)] bg-white p-4">
            <p className="text-sm font-semibold text-[var(--theme-text)]">Related service providers</p>
            <p className="mt-2 text-sm leading-6 text-[var(--theme-text-muted)]">
              {draft.related_service_providers.filter((provider) => provider.name.trim()).length
                ? `${draft.related_service_providers.filter((provider) => provider.name.trim()).length} provider(s) entered.`
                : "No related service providers entered yet."}
            </p>
          </div>
        </Card>

        <Card
          title="Packet support pages"
          description="Add staff-facing accommodations and behavior support content for the packet."
          actions={(
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => setContentModal("accommodations")}>
                {hasAccommodations ? "Edit Accommodations" : "Add Accommodations"}
              </Button>
              <Button variant="outline" onClick={() => setContentModal("behavior_plan")}>
                {hasBehaviorPlan ? "Edit Behavior Plan" : "Add Behavior Plan"}
              </Button>
            </div>
          )}
        >
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-[var(--theme-border)] bg-white p-4">
              <p className="text-sm font-semibold text-[var(--theme-text)]">Accommodations/Modifications</p>
              <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-sm leading-6 text-[var(--theme-text-muted)]">
                {draft.accommodations.filter((item) => item.text.trim()).length
                  ? `${draft.accommodations.filter((item) => item.text.trim()).length} content area(s) entered.`
                  : "No accommodations entered yet."}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--theme-border)] bg-white p-4">
              <p className="text-sm font-semibold text-[var(--theme-text)]">Behavior Plan</p>
              <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-sm leading-6 text-[var(--theme-text-muted)]">
                {draft.behavior_plan_sections.filter((item) => item.text.trim()).length
                  ? `${draft.behavior_plan_sections.filter((item) => item.text.trim()).length} section(s) entered.`
                  : draft.behavior_plan.trim() || "No behavior plan entered yet."}
              </p>
            </div>
          </div>
        </Card>

        <Card
          title="Service areas"
          description="Each service area is a reusable object that goals will reference."
          actions={<Button variant="outline" onClick={() => setDraft((current) => ({ ...current, service_areas: [...current.service_areas, blankServiceArea(current.service_areas.length)] }))}>Add service area</Button>}
        >
          {draft.service_areas.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--theme-border)] p-8 text-center">
              <p className="text-sm font-medium text-[var(--theme-text)]">No service areas yet.</p>
              <Button className="mt-4" onClick={() => setDraft((current) => ({ ...current, service_areas: [blankServiceArea(0)] }))}>Add the first service area</Button>
            </div>
          ) : (
            <div className="space-y-4">
              {draft.service_areas.map((area, index) => (
                <div key={area.id ?? `new-${index}`} className="rounded-xl border border-[var(--theme-border)] bg-[var(--theme-surface-muted)]/45 p-4">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-[var(--theme-text)]">Service area {index + 1}</p>
                    <div className="flex gap-1">
                      <Button variant="text" disabled={index === 0} onClick={() => moveArea(index, -1)} aria-label={`Move service area ${index + 1} up`}>Up</Button>
                      <Button variant="text" disabled={index === draft.service_areas.length - 1} onClick={() => moveArea(index, 1)} aria-label={`Move service area ${index + 1} down`}>Down</Button>
                      <Button variant="danger" onClick={() => setDraft((current) => ({ ...current, service_areas: current.service_areas.filter((_, areaIndex) => areaIndex !== index).map((value, position) => ({ ...value, position })) }))}>Remove</Button>
                    </div>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <FieldFrame label="Service area" htmlFor={`area-${index}-name`} required>
                      <div className="relative">
                        <button
                          className={`${selectClass} text-left`}
                          id={`area-${index}-name`}
                          type="button"
                          onClick={() => setOpenServiceAreaMenu((current) => current === index ? null : index)}
                        >
                          {area.name || "Select service area"}
                        </button>
                        {openServiceAreaMenu === index && (
                          <div className="absolute z-30 mt-2 max-h-72 w-full overflow-auto rounded-xl border border-[var(--theme-border)] bg-white p-1 shadow-xl">
                            {serviceAreaOptions.map((option) => (
                              <button
                                key={option}
                                className="group flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm text-[var(--theme-text)] transition hover:bg-[var(--theme-primary-soft)]"
                                type="button"
                                onClick={() => {
                                  updateArea(index, { name: option });
                                  setOpenServiceAreaMenu(null);
                                }}
                              >
                                <span>{option}</span>
                                <span
                                  aria-label={`Delete ${option}`}
                                  className="rounded-md px-2 py-0.5 text-xs font-bold text-[var(--theme-text-muted)] opacity-0 transition hover:bg-white hover:text-[var(--theme-error)] group-hover:opacity-100"
                                  role="button"
                                  tabIndex={0}
                                  onClick={(event) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    void deleteServiceAreaPreset(option);
                                  }}
                                  onKeyDown={(event) => {
                                    if (event.key === "Enter" || event.key === " ") {
                                      event.preventDefault();
                                      event.stopPropagation();
                                      void deleteServiceAreaPreset(option);
                                    }
                                  }}
                                >
                                  X
                                </span>
                              </button>
                            ))}
                            <button
                              className="mt-1 w-full rounded-lg border border-dashed border-[var(--theme-border)] px-3 py-2 text-left text-sm font-semibold text-[var(--theme-primary)] transition hover:bg-[var(--theme-surface-muted)]"
                              type="button"
                              onClick={() => openAddServiceAreaPreset(index)}
                            >
                              Add new service area
                            </button>
                          </div>
                        )}
                      </div>
                    </FieldFrame>
                    <FieldFrame label="Setting" htmlFor={`area-${index}-setting`}>
                      <select
                        className={selectClass}
                        id={`area-${index}-setting`}
                        value={customSettingRows.has(serviceAreaKey(area, index)) ? customSettingValue : settingSelectValue(area.setting)}
                        onChange={(event) => {
                          const value = event.target.value;
                          const rowKey = serviceAreaKey(area, index);
                          setCustomSettingRows((current) => {
                            const next = new Set(current);
                            if (value === customSettingValue) {
                              next.add(rowKey);
                            } else {
                              next.delete(rowKey);
                            }
                            return next;
                          });
                          updateArea(index, { setting: value === customSettingValue ? "" : value });
                        }}
                      >
                        <option value="">Select setting</option>
                        <option value="Regular Education">Regular Education</option>
                        <option value="Special Education">{fullTitle}</option>
                        <option value={customSettingValue}>Other</option>
                      </select>
                      {(settingSelectValue(area.setting) === customSettingValue || customSettingRows.has(serviceAreaKey(area, index))) && (
                        <TextInput
                          className="mt-2"
                          value={area.setting}
                          onChange={(event) => updateArea(index, { setting: event.target.value })}
                          placeholder="Type custom setting"
                          aria-label={`Custom setting for service area ${index + 1}`}
                        />
                      )}
                    </FieldFrame>
                    <FieldFrame label="Minutes per week" htmlFor={`area-${index}-minutes`}>
                      <TextInput id={`area-${index}-minutes`} type="number" min={0} value={area.minutes_per_week ?? ""} onChange={(event) => updateArea(index, { minutes_per_week: event.target.value ? Number(event.target.value) : null })} />
                    </FieldFrame>
                    <div className="md:col-span-2 xl:col-span-4">
                      <FieldFrame label="Notes" htmlFor={`area-${index}-notes`}>
                        <TextArea id={`area-${index}-notes`} value={area.notes} onChange={(event) => updateArea(index, { notes: event.target.value })} placeholder="Optional instructional or scheduling notes" />
                      </FieldFrame>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Packet audiences" description="Choose which Dashboard-defined packet versions this project should include. Page visibility will be configured later.">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {packetAudienceOptions.map((option) => (
              <label key={option.value} className={`flex cursor-pointer items-center gap-3 rounded-xl border p-4 text-sm font-semibold transition ${draft.audiences.includes(option.value) ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)] text-[var(--theme-primary)]" : "border-[var(--theme-border)] bg-white text-[var(--theme-text)]"}`}>
                <input type="checkbox" checked={draft.audiences.includes(option.value)} onChange={() => toggleAudience(option.value)} />
                {option.label}
              </label>
            ))}
          </div>
          {packetAudienceOptions.length === 0 && (
            <p className="text-sm text-[var(--theme-text-muted)]">
              Add packet audiences from Dashboard settings before selecting versions for this project.
            </p>
          )}
        </Card>

        <ValidationSummary validation={validation} />

        <footer className="flex flex-wrap items-center justify-between gap-3 pb-6">
          <div className="flex gap-2">
            <Button variant="outline" onClick={onBack}>Back to Dashboard</Button>
            <Button variant="text" onClick={onBack}>Cancel</Button>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void autosave.saveImmediately()}>Save Draft</Button>
            <Button disabled={!validation.is_complete} onClick={() => void saveAndContinue()}>Save & Continue</Button>
          </div>
        </footer>
      </div>
      {addingServiceAreaForIndex !== null && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-6">
          <div className="w-full max-w-md rounded-2xl border border-[var(--theme-border)] bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--theme-accent)]">
                  Service Areas
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-[var(--theme-primary)]">
                  Add Service Area
                </h2>
                <p className="mt-1 text-sm text-[var(--theme-text-muted)]">
                  Add a reusable option to the service area dropdown, then use it for this row.
                </p>
              </div>
              <Button variant="text" onClick={closeAddServiceAreaPreset}>
                Close
              </Button>
            </div>

            <label className="mt-5 block text-sm font-semibold text-[var(--theme-text)]">
              Service area name
              <TextInput
                className="mt-2"
                value={newServiceAreaName}
                onChange={(event) => setNewServiceAreaName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void saveNewServiceAreaPreset();
                  }
                }}
                autoFocus
                placeholder="Example: Speech/Language"
              />
            </label>

            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={closeAddServiceAreaPreset}>
                Cancel
              </Button>
              <Button disabled={!newServiceAreaName.trim()} onClick={() => void saveNewServiceAreaPreset()}>
                Add Service Area
              </Button>
            </div>
          </div>
        </div>
      )}
      {contentModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-6">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-2xl border border-[var(--theme-border)] bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--theme-accent)]">
                  Student Setup
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-[var(--theme-primary)]">
                  {contentModal === "accommodations"
                    ? "Accommodations/Modifications"
                    : contentModal === "behavior_plan"
                      ? "Behavior Plan"
                      : "Related Service Providers"}
                </h2>
                <p className="mt-1 text-sm text-[var(--theme-text-muted)]">
                  This content appears on its matching packet page.
                </p>
              </div>
              <Button variant="text" onClick={() => setContentModal(null)}>
                Close
              </Button>
            </div>

            {contentModal === "accommodations" ? (
              <div className="mt-5 space-y-4">
                <Button
                  variant="outline"
                  onClick={() => setDraft((current) => ({
                    ...current,
                    accommodations: [
                      ...current.accommodations,
                      blankAccommodation(current.accommodations.length),
                    ],
                  }))}
                >
                  Add New
                </Button>

                <div className="rounded-xl border border-[var(--theme-border)] bg-white p-4">
                  <label className="flex items-start gap-3 text-sm font-semibold text-[var(--theme-text)]">
                    <input
                      checked={draft.accommodations_parent_strengths_enabled}
                      className="mt-1"
                      type="checkbox"
                      onChange={(event) => setDraft((current) => ({
                        ...current,
                        accommodations_parent_strengths_enabled: event.target.checked,
                      }))}
                    />
                    <span>
                      Add Parent Perception of Student&apos;s Strengths?
                      <span className="mt-1 block text-xs font-medium text-[var(--theme-text-muted)]">
                        This appears at the bottom of the accommodations page and is separate from At-a-Glance.
                      </span>
                    </span>
                  </label>
                  {draft.accommodations_parent_strengths_enabled && (
                    <div className="mt-4">
                      <FieldFrame label="Parent Perception of Student's Strengths" htmlFor="accommodations-parent-strengths">
                        <TextArea
                          id="accommodations-parent-strengths"
                          value={draft.accommodations_parent_strengths}
                          onChange={(event) => setDraft((current) => ({
                            ...current,
                            accommodations_parent_strengths: event.target.value,
                          }))}
                          placeholder="Paste or type parent input about the student's strengths..."
                        />
                      </FieldFrame>
                    </div>
                  )}
                </div>

                {draft.accommodations.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[var(--theme-border)] p-6 text-center text-sm text-[var(--theme-text-muted)]">
                    No accommodation content areas yet.
                  </div>
                ) : (
                  draft.accommodations.map((item, index) => (
                    <div key={item.id ?? `accommodation-${index}`} className="rounded-xl border border-[var(--theme-border)] bg-[var(--theme-surface-muted)]/45 p-4">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-[var(--theme-text)]">
                          {accommodationLabel(item)}
                        </p>
                        <Button
                          variant="text"
                          onClick={() => setDraft((current) => ({
                            ...current,
                            accommodations: current.accommodations
                              .filter((_, accommodationIndex) => accommodationIndex !== index)
                              .map((value, position) => ({ ...value, position })),
                          }))}
                        >
                          Remove
                        </Button>
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        <FieldFrame label="Content Area" htmlFor={`accommodation-${index}-area`}>
                          <select
                            className={selectClass}
                            id={`accommodation-${index}-area`}
                            value={item.content_area}
                            onChange={(event) => {
                              const value = event.target.value;
                              setDraft((current) => ({
                                ...current,
                                accommodations: current.accommodations.map((currentItem, accommodationIndex) =>
                                  accommodationIndex === index
                                    ? {
                                      ...currentItem,
                                      content_area: value,
                                      custom_content_area: value === "Other" ? currentItem.custom_content_area : "",
                                    }
                                    : currentItem,
                                ),
                              }));
                            }}
                          >
                            {accommodationAreaOptions.map((option) => (
                              <option key={option} value={option}>{option}</option>
                            ))}
                          </select>
                        </FieldFrame>
                        {item.content_area === "Other" && (
                          <FieldFrame label="Custom Content Area" htmlFor={`accommodation-${index}-custom-area`}>
                            <TextInput
                              id={`accommodation-${index}-custom-area`}
                              value={item.custom_content_area}
                              onChange={(event) => setDraft((current) => ({
                                ...current,
                                accommodations: current.accommodations.map((currentItem, accommodationIndex) =>
                                  accommodationIndex === index
                                    ? { ...currentItem, custom_content_area: event.target.value }
                                    : currentItem,
                                ),
                              }))}
                              placeholder="Example: Transportation"
                            />
                          </FieldFrame>
                        )}
                        <div className="md:col-span-2">
                          <FieldFrame label="Accommodations" htmlFor={`accommodation-${index}-text`}>
                            <TextArea
                              id={`accommodation-${index}-text`}
                              value={item.text}
                              onChange={(event) => setDraft((current) => ({
                                ...current,
                                accommodations: current.accommodations.map((currentItem, accommodationIndex) =>
                                  accommodationIndex === index
                                    ? { ...currentItem, text: event.target.value, position: index }
                                    : currentItem,
                                ),
                              }))}
                              placeholder="Enter accommodations for this content area..."
                            />
                          </FieldFrame>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            ) : contentModal === "behavior_plan" ? (
              <div className="mt-5 space-y-4">
                <Button
                  variant="outline"
                  onClick={() => setDraft((current) => ({
                    ...current,
                    behavior_plan_sections: [
                      ...current.behavior_plan_sections,
                      blankBehaviorPlanSection(
                        current.behavior_plan_sections.length,
                        current.behavior_plan_sections,
                      ),
                    ],
                  }))}
                >
                  Add New
                </Button>

                {draft.behavior_plan_sections.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[var(--theme-border)] p-6 text-center text-sm text-[var(--theme-text-muted)]">
                    No behavior plan sections yet.
                  </div>
                ) : (
                  draft.behavior_plan_sections.map((item, index) => (
                    <div key={item.id ?? `behavior-section-${index}`} className="rounded-xl border border-[var(--theme-border)] bg-[var(--theme-surface-muted)]/45 p-4">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-[var(--theme-text)]">
                          {item.title.trim() || `Behavior plan section ${index + 1}`}
                        </p>
                        <Button
                          variant="text"
                          onClick={() => setDraft((current) => ({
                            ...current,
                            behavior_plan_sections: current.behavior_plan_sections
                              .filter((_, sectionIndex) => sectionIndex !== index)
                              .map((value, position) => ({ ...value, position })),
                          }))}
                        >
                          Remove
                        </Button>
                      </div>
                      <div className="grid gap-4">
                        <FieldFrame label="Section Name" htmlFor={`behavior-${index}-title`}>
                          <TextInput
                            id={`behavior-${index}-title`}
                            list={`behavior-${index}-title-options`}
                            value={item.title}
                            onChange={(event) => setDraft((current) => ({
                              ...current,
                              behavior_plan_sections: current.behavior_plan_sections.map((currentItem, sectionIndex) =>
                                sectionIndex === index
                                  ? { ...currentItem, title: event.target.value, position: index }
                                  : currentItem,
                              ),
                            }))}
                            placeholder="Example: Prevention Strategies"
                          />
                          <datalist id={`behavior-${index}-title-options`}>
                            {defaultBehaviorPlanSections.map((sectionTitle) => (
                              <option key={sectionTitle} value={sectionTitle} />
                            ))}
                          </datalist>
                        </FieldFrame>
                        <FieldFrame label="Behavior Plan Content" htmlFor={`behavior-${index}-text`}>
                          <TextArea
                            id={`behavior-${index}-text`}
                            className="min-h-40"
                            value={item.text}
                            onChange={(event) => setDraft((current) => ({
                              ...current,
                              behavior_plan_sections: current.behavior_plan_sections.map((currentItem, sectionIndex) =>
                                sectionIndex === index
                                  ? { ...currentItem, text: event.target.value, position: index }
                                  : currentItem,
                              ),
                            }))}
                            placeholder="Enter details for this behavior plan section..."
                          />
                        </FieldFrame>
                      </div>
                    </div>
                  ))
                )}
              </div>
            ) : (
              <div className="mt-5 space-y-4">
                <Button
                  variant="outline"
                  onClick={() => setDraft((current) => ({
                    ...current,
                    related_service_providers: [
                      ...current.related_service_providers,
                      blankRelatedServiceProvider(current.related_service_providers.length),
                    ],
                  }))}
                >
                  Add Provider
                </Button>

                {draft.related_service_providers.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[var(--theme-border)] p-6 text-center text-sm text-[var(--theme-text-muted)]">
                    No related service providers yet.
                  </div>
                ) : (
                  draft.related_service_providers.map((provider, index) => (
                    <div key={provider.id ?? `related-provider-${index}`} className="rounded-xl border border-[var(--theme-border)] bg-[var(--theme-surface-muted)]/45 p-4">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-[var(--theme-text)]">
                          {provider.name.trim() || `Provider ${index + 1}`}
                        </p>
                        <Button
                          variant="text"
                          onClick={() => setDraft((current) => ({
                            ...current,
                            related_service_providers: current.related_service_providers
                              .filter((_, providerIndex) => providerIndex !== index)
                              .map((value, position) => ({ ...value, position })),
                          }))}
                        >
                          Remove
                        </Button>
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        <FieldFrame label="Provider Name" htmlFor={`related-provider-${index}-name`}>
                          <TextInput
                            id={`related-provider-${index}-name`}
                            value={provider.name}
                            onChange={(event) => setDraft((current) => ({
                              ...current,
                              related_service_providers: current.related_service_providers.map((currentProvider, providerIndex) =>
                                providerIndex === index
                                  ? { ...currentProvider, name: event.target.value, position: index }
                                  : currentProvider,
                              ),
                            }))}
                            placeholder="First and last name"
                          />
                        </FieldFrame>
                        <FieldFrame label="Service Area" htmlFor={`related-provider-${index}-service`}>
                          <select
                            className={selectClass}
                            id={`related-provider-${index}-service`}
                            value={provider.service_area}
                            onChange={(event) => setDraft((current) => ({
                              ...current,
                              related_service_providers: current.related_service_providers.map((currentProvider, providerIndex) =>
                                providerIndex === index
                                  ? { ...currentProvider, service_area: event.target.value, position: index }
                                  : currentProvider,
                              ),
                            }))}
                          >
                            {relatedServiceProviderOptions.map((option) => (
                              <option key={option} value={option}>{option}</option>
                            ))}
                          </select>
                        </FieldFrame>
                        <FieldFrame label="Email" htmlFor={`related-provider-${index}-email`}>
                          <TextInput
                            id={`related-provider-${index}-email`}
                            type="email"
                            value={provider.email}
                            onChange={(event) => setDraft((current) => ({
                              ...current,
                              related_service_providers: current.related_service_providers.map((currentProvider, providerIndex) =>
                                providerIndex === index
                                  ? { ...currentProvider, email: event.target.value, position: index }
                                  : currentProvider,
                              ),
                            }))}
                            placeholder="provider@example.org"
                          />
                        </FieldFrame>
                        <FieldFrame label="Phone Number" htmlFor={`related-provider-${index}-phone`}>
                          <TextInput
                            id={`related-provider-${index}-phone`}
                            type="tel"
                            value={provider.phone}
                            onChange={(event) => setDraft((current) => ({
                              ...current,
                              related_service_providers: current.related_service_providers.map((currentProvider, providerIndex) =>
                                providerIndex === index
                                  ? { ...currentProvider, phone: event.target.value, position: index }
                                  : currentProvider,
                              ),
                            }))}
                            placeholder="(555) 010-1234"
                          />
                        </FieldFrame>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setContentModal(null)}>
                Done
              </Button>
              <Button onClick={() => void autosave.saveImmediately().then(() => setContentModal(null))}>
                Save & Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
