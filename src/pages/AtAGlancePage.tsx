import { useMemo, useState } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { TextArea } from "../components/ui/FormField";
import { ValidationSummary } from "../components/workflow/ValidationSummary";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import { useAutosave } from "../hooks/useAutosave";
import { validateAtAGlance } from "../lib/validation";
import { saveAtAGlance } from "../services/api/projects";
import type { AtAGlanceSection, ProjectDetail } from "../types/projects";

const defaultSections: readonly Omit<AtAGlanceSection, "position">[] = [
  { id: "strengths", title: "Student Strengths", content: "", enabled: true },
  { id: "interests", title: "Interests & Motivators", content: "", enabled: true },
  { id: "needs", title: "Areas of Need", content: "", enabled: true },
  { id: "strategies", title: "Effective Strategies", content: "", enabled: true },
  { id: "communication", title: "Communication Tips", content: "", enabled: true },
  { id: "behavior", title: "Behavioral Supports", content: "", enabled: true },
  { id: "safety", title: "Medical or Safety Considerations", content: "", enabled: true },
  { id: "reminders", title: "Staff Reminders", content: "", enabled: true },
];

function initialSections(project: ProjectDetail): AtAGlanceSection[] {
  if (project.at_a_glance.sections.length) {
    return project.at_a_glance.sections
      .filter((section) => section.id !== "supports")
      .map((section, position) => ({ ...section, position }));
  }
  return defaultSections.map((section, position) => ({ ...section, position }));
}

interface AtAGlancePageProps {
  readonly project: ProjectDetail;
  readonly onProjectUpdate: (project: ProjectDetail) => void;
  readonly onBack: () => void;
  readonly onComplete: () => void;
}

export function AtAGlancePage({
  project,
  onProjectUpdate,
  onBack,
  onComplete,
}: AtAGlancePageProps) {
  const [sections, setSections] = useState<AtAGlanceSection[]>(() =>
    initialSections(project),
  );
  const [saveError, setSaveError] = useState("");
  const validation = useMemo(() => validateAtAGlance(sections), [sections]);

  const autosave = useAutosave({
    value: sections,
    delayMs: 850,
    save: async (value, signal) => {
      try {
        const saved = await saveAtAGlance(project.id, value, signal);
        setSaveError("");
        onProjectUpdate(saved);
      } catch (reason) {
        if (signal.aborted) return;
        setSaveError(reason instanceof Error ? reason.message : "Summary could not be saved.");
        throw reason;
      }
    },
  });

  function updateSection(index: number, patch: Partial<AtAGlanceSection>) {
    setSections((current) =>
      current.map((section, sectionIndex) =>
        sectionIndex === index ? { ...section, ...patch } : section,
      ),
    );
  }

  function moveSection(index: number, direction: -1 | 1) {
    setSections((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const reordered = [...current];
      [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
      return reordered.map((section, position) => ({ ...section, position }));
    });
  }

  async function finish() {
    await autosave.saveImmediately();
    onComplete();
  }

  const visibleSections = sections.filter(
    (section) => section.enabled && section.content.trim(),
  );
  const studentName = project.student?.name || "Student";

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 2 of 7"
        title={`At-a-Glance${project.student?.name ? ` - ${project.student.name}` : ""}`}
        description="Create a concise, practical summary that educators can read in under one minute."
        status={autosave.status}
      />

      {saveError && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          {saveError}
        </div>
      )}

      <div className="grid items-start gap-5 xl:grid-cols-[1fr_24rem]">
        <div className="space-y-4">
          {sections.map((section, index) => (
            <Card
              key={section.id}
              title={section.title}
              actions={
                <div className="flex flex-wrap items-center gap-1">
                  <label className="mr-2 flex items-center gap-2 text-xs font-semibold text-[var(--theme-text-muted)]">
                    <input
                      type="checkbox"
                      checked={section.enabled}
                      onChange={(event) => updateSection(index, { enabled: event.target.checked })}
                    />
                    Include
                  </label>
                  <Button variant="text" disabled={index === 0} onClick={() => moveSection(index, -1)}>Up</Button>
                  <Button variant="text" disabled={index === sections.length - 1} onClick={() => moveSection(index, 1)}>Down</Button>
                  <Button variant="text" onClick={() => updateSection(index, { content: "" })}>Reset Section</Button>
                </div>
              }
            >
              <TextArea
                aria-label={section.title}
                disabled={!section.enabled}
                value={section.content}
                onChange={(event) => updateSection(index, { content: event.target.value })}
                placeholder={`Add concise ${section.title.toLowerCase()}...`}
              />
            </Card>
          ))}
        </div>

        <aside className="xl:sticky xl:top-6">
          <Card title="Live preview" description="Empty or disabled sections are hidden automatically.">
            <div className="overflow-hidden rounded-xl border border-[var(--theme-border)] bg-white">
              <div className="bg-[var(--theme-primary)] px-5 py-5 text-white">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/65">At a Glance</p>
                <h2 className="mt-2 text-2xl font-semibold">{studentName}</h2>
                {project.school_year && <p className="mt-1 text-sm text-white/70">{project.school_year}</p>}
              </div>
              <div className="space-y-5 p-5">
                {visibleSections.length ? (
                  visibleSections.map((section) => (
                    <section key={section.id}>
                      <h3 className="text-sm font-semibold text-[var(--theme-primary)]">{section.title}</h3>
                      <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[var(--theme-text)]">{section.content}</p>
                    </section>
                  ))
                ) : (
                  <p className="py-8 text-center text-sm text-[var(--theme-text-muted)]">Your instructional summary preview will appear here.</p>
                )}
              </div>
            </div>
          </Card>
        </aside>
      </div>

      <div className="mt-5">
        <ValidationSummary
          validation={validation}
          completeMessage="The instructional summary is ready."
        />
      </div>
      <footer className="mt-5 flex flex-wrap items-center justify-between gap-3 pb-6">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void autosave.saveImmediately()}>Save Draft</Button>
          <Button onClick={() => void finish()}>Save & Continue</Button>
        </div>
      </footer>
    </div>
  );
}
