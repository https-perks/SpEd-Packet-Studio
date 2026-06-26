import { useMemo, useState } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FieldFrame, selectClass, TextArea, TextInput } from "../components/ui/FormField";
import { ValidationSummary } from "../components/workflow/ValidationSummary";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import { useAutosave } from "../hooks/useAutosave";
import { validateStudentSetup } from "../lib/validation";
import { saveStudentSetup } from "../services/api/projects";
import type {
  Audience,
  DeliveryModel,
  ProjectDetail,
  ServiceAreaDraft,
  StudentSetupDraft,
} from "../types/projects";

const audienceOptions: readonly { value: Audience; label: string }[] = [
  { value: "case_manager", label: "Case Manager" },
  { value: "general_education", label: "General Education" },
  { value: "paraeducator", label: "Paraeducator" },
  { value: "related_services", label: "Related Services" },
  { value: "substitute", label: "Substitute" },
];

const settingOptions = ["Regular Education", "Special Education"] as const;
const customSettingValue = "__custom_setting__";

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
    delivery_model: null,
    notes: "",
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
        iep_end_date: project.student.iep_end_date,
      }
    : {
        name: "",
        initials: "",
        grade: "",
        school: "",
        case_manager: "",
        iep_end_date: null,
      };

  return {
    project_name: project.name === "Untitled Student Project" ? "" : project.name,
    school_year: project.school_year,
    student,
    service_areas: project.service_areas.map((area) => ({ ...area })),
    audiences: [...project.audiences],
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
  const [draft, setDraft] = useState<StudentSetupDraft>(() => initialDraft(project));
  const [saveError, setSaveError] = useState("");
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

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 1 of 6"
        title="Student Setup"
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
            <FieldFrame label="Initials" htmlFor="initials" hint="Generated automatically; you may override it.">
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
            <FieldFrame label="Case manager" htmlFor="case-manager">
              <TextInput id="case-manager" value={draft.student.case_manager} onChange={(event) => updateStudent("case_manager", event.target.value)} />
            </FieldFrame>
            <FieldFrame label="IEP end date" htmlFor="iep-end" required error={fieldError("student.iep_end_date")}>
              <TextInput id="iep-end" type="date" value={draft.student.iep_end_date ?? ""} onChange={(event) => updateStudent("iep_end_date", event.target.value)} />
            </FieldFrame>
            <FieldFrame label="School year" htmlFor="school-year" hint="Suggested from the IEP end date.">
              <TextInput id="school-year" value={draft.school_year} onChange={(event) => setDraft((current) => ({ ...current, school_year: event.target.value }))} placeholder="2026-2027" />
            </FieldFrame>
            <FieldFrame label="Project name" htmlFor="project-name" hint="Generated from the student and school year.">
              <TextInput id="project-name" value={draft.project_name} onChange={(event) => setDraft((current) => ({ ...current, project_name: event.target.value }))} />
            </FieldFrame>
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
                      <TextInput id={`area-${index}-name`} value={area.name} onChange={(event) => updateArea(index, { name: event.target.value })} placeholder="Reading, mathematics..." />
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
                        <option value="Special Education">Special Education</option>
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
                    <FieldFrame label="Delivery" htmlFor={`area-${index}-delivery`}>
                      <select className={selectClass} id={`area-${index}-delivery`} value={area.delivery_model ?? ""} onChange={(event) => updateArea(index, { delivery_model: (event.target.value || null) as DeliveryModel | null })}>
                        <option value="">Select</option><option value="push_in">Push-in</option><option value="pull_out">Pull-out</option><option value="combined">Combined</option><option value="other">Other</option>
                      </select>
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

        <Card title="Packet audiences" description="These selections create initial Packet Version objects. Page visibility will be configured later.">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {audienceOptions.map((option) => (
              <label key={option.value} className={`flex cursor-pointer items-center gap-3 rounded-xl border p-4 text-sm font-semibold transition ${draft.audiences.includes(option.value) ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)] text-[var(--theme-primary)]" : "border-[var(--theme-border)] bg-white text-[var(--theme-text)]"}`}>
                <input type="checkbox" checked={draft.audiences.includes(option.value)} onChange={() => toggleAudience(option.value)} />
                {option.label}
              </label>
            ))}
          </div>
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
    </div>
  );
}
