import { useMemo, useState } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FieldFrame, selectClass, TextArea, TextInput } from "../components/ui/FormField";
import { ValidationSummary } from "../components/workflow/ValidationSummary";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import { useAutosave } from "../hooks/useAutosave";
import { validateGoals } from "../lib/validation";
import { saveGoals } from "../services/api/projects";
import type { GoalDraft, ProjectDetail } from "../types/projects";

function blankGoal(serviceAreaId: string | null, position: number): GoalDraft {
  return {
    title: "",
    statement: "",
    service_area_id: serviceAreaId,
    mastery_criteria: "",
    progress_monitoring_method: "",
    instructional_notes: "",
    position,
  };
}

interface GoalBuilderPageProps {
  readonly project: ProjectDetail;
  readonly onProjectUpdate: (project: ProjectDetail) => void;
  readonly onBack: () => void;
  readonly onContinue: () => void;
}

export function GoalBuilderPage({
  project,
  onProjectUpdate,
  onBack,
  onContinue,
}: GoalBuilderPageProps) {
  const [goals, setGoals] = useState<GoalDraft[]>(() =>
    project.goals.map((goal) => ({ ...goal })),
  );
  const [selectedIndex, setSelectedIndex] = useState(project.goals.length ? 0 : -1);
  const [saveError, setSaveError] = useState("");
  const validation = useMemo(() => validateGoals(goals), [goals]);
  const selectedGoal = selectedIndex >= 0 ? goals[selectedIndex] : undefined;
  const monitoringMethods = useMemo(
    () =>
      [...new Set(goals.map((goal) => goal.progress_monitoring_method.trim()).filter(Boolean))],
    [goals],
  );

  const autosave = useAutosave({
    value: goals,
    delayMs: 850,
    save: async (value, signal) => {
      try {
        const saved = await saveGoals(project.id, value, signal);
        setSaveError("");
        onProjectUpdate(saved);
        setGoals((current) => {
          const idsChanged = current.some(
            (goal, index) => (saved.goals[index]?.id ?? goal.id) !== goal.id,
          );
          if (!idsChanged) return current;
          return current.map((goal, index) => ({
            ...goal,
            id: saved.goals[index]?.id ?? goal.id,
          }));
        });
      } catch (reason) {
        if (signal.aborted) return;
        setSaveError(reason instanceof Error ? reason.message : "Goals could not be saved.");
        throw reason;
      }
    },
  });

  function addGoal() {
    const next = blankGoal(project.service_areas[0]?.id ?? null, goals.length);
    setGoals((current) => [...current, next]);
    setSelectedIndex(goals.length);
  }

  function updateSelected(patch: Partial<GoalDraft>) {
    if (selectedIndex < 0) return;
    setGoals((current) =>
      current.map((goal, index) => (index === selectedIndex ? { ...goal, ...patch } : goal)),
    );
  }

  function duplicateSelected() {
    if (!selectedGoal) return;
    const copy: GoalDraft = {
      ...selectedGoal,
      id: null,
      title: selectedGoal.title ? `${selectedGoal.title} (Copy)` : "",
      position: goals.length,
    };
    setGoals((current) => [...current, copy]);
    setSelectedIndex(goals.length);
  }

  function deleteSelected() {
    if (selectedIndex < 0) return;
    setGoals((current) =>
      current
        .filter((_, index) => index !== selectedIndex)
        .map((goal, position) => ({ ...goal, position })),
    );
    setSelectedIndex((current) => Math.min(current, goals.length - 2));
  }

  function moveSelected(direction: -1 | 1) {
    if (selectedIndex < 0) return;
    const target = selectedIndex + direction;
    if (target < 0 || target >= goals.length) return;
    setGoals((current) => {
      const reordered = [...current];
      [reordered[selectedIndex], reordered[target]] = [
        reordered[target],
        reordered[selectedIndex],
      ];
      return reordered.map((goal, position) => ({ ...goal, position }));
    });
    setSelectedIndex(target);
  }

  async function saveAndContinue() {
    await autosave.saveImmediately();
    if (validation.is_complete) onContinue();
  }

  const groupedGoals = project.service_areas.map((area) => ({
    area,
    goals: goals
      .map((goal, index) => ({ goal, index }))
      .filter(({ goal }) => goal.service_area_id === area.id),
  }));
  const unassigned = goals
    .map((goal, index) => ({ goal, index }))
    .filter(({ goal }) => !goal.service_area_id);

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 2 of 3"
        title="Goal Builder"
        description="Enter each annual goal once, assign it to one service area, and preserve the exact educational language."
        status={autosave.status}
        actions={<Button onClick={addGoal}>Add Goal</Button>}
      />

      {saveError && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          {saveError}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[22rem_1fr]">
        <Card title="Goal list" description="Goals are grouped by their service area.">
          {goals.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--theme-border)] p-6 text-center">
              <p className="text-sm text-[var(--theme-text-muted)]">No goals entered.</p>
              <Button className="mt-4" onClick={addGoal}>Add the first goal</Button>
            </div>
          ) : (
            <div className="space-y-5">
              {[...groupedGoals, ...(unassigned.length ? [{ area: { id: "", name: "Unassigned" }, goals: unassigned }] : [])].map(
                (group) =>
                  group.goals.length > 0 && (
                    <section key={group.area.id || "unassigned"}>
                      <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--theme-text-muted)]">
                        {group.area.name}
                      </h3>
                      <div className="mt-2 space-y-2">
                        {group.goals.map(({ goal, index }) => (
                          <button
                            key={goal.id ?? `draft-${index}`}
                            className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                              index === selectedIndex
                                ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)]"
                                : "border-[var(--theme-border)] bg-white hover:bg-[var(--theme-surface-muted)]"
                            }`}
                            onClick={() => setSelectedIndex(index)}
                          >
                            <span className="block text-xs font-semibold text-[var(--theme-accent)]">
                              Goal {index + 1}
                            </span>
                            <span className="mt-1 block text-sm font-medium text-[var(--theme-text)]">
                              {goal.title || "Untitled goal"}
                            </span>
                          </button>
                        ))}
                      </div>
                    </section>
                  ),
              )}
            </div>
          )}
        </Card>

        <Card
          title={selectedGoal ? `Goal ${selectedIndex + 1}` : "Goal editor"}
          description={
            selectedGoal
              ? "Required fields may remain incomplete in a saved draft."
              : "Select a goal or add a new one to begin."
          }
          actions={
            selectedGoal && (
              <div className="flex flex-wrap gap-1">
                <Button variant="text" disabled={selectedIndex === 0} onClick={() => moveSelected(-1)}>Up</Button>
                <Button variant="text" disabled={selectedIndex === goals.length - 1} onClick={() => moveSelected(1)}>Down</Button>
                <Button variant="outline" onClick={duplicateSelected}>Duplicate</Button>
                <Button variant="danger" onClick={deleteSelected}>Delete</Button>
              </div>
            )
          }
        >
          {selectedGoal ? (
            <div className="grid gap-5 md:grid-cols-2">
              <FieldFrame label="Goal title" htmlFor="goal-title" required>
                <TextInput id="goal-title" value={selectedGoal.title} onChange={(event) => updateSelected({ title: event.target.value })} />
              </FieldFrame>
              <FieldFrame label="Service area" htmlFor="goal-area" required>
                <select className={selectClass} id="goal-area" value={selectedGoal.service_area_id ?? ""} onChange={(event) => updateSelected({ service_area_id: event.target.value || null })}>
                  <option value="">Select a service area</option>
                  {project.service_areas.map((area) => <option key={area.id} value={area.id}>{area.name || "Untitled service area"}</option>)}
                </select>
              </FieldFrame>
              <div className="md:col-span-2">
                <FieldFrame label="Goal statement" htmlFor="goal-statement" required hint="Enter the goal exactly as it appears in the IEP.">
                  <TextArea id="goal-statement" className="min-h-40" value={selectedGoal.statement} onChange={(event) => updateSelected({ statement: event.target.value })} />
                </FieldFrame>
              </div>
              <FieldFrame label="Mastery criteria" htmlFor="mastery" required>
                <TextArea id="mastery" value={selectedGoal.mastery_criteria} onChange={(event) => updateSelected({ mastery_criteria: event.target.value })} />
              </FieldFrame>
              <FieldFrame label="Progress-monitoring method" htmlFor="monitoring" required>
                <TextInput id="monitoring" list="monitoring-methods" value={selectedGoal.progress_monitoring_method} onChange={(event) => updateSelected({ progress_monitoring_method: event.target.value })} />
                <datalist id="monitoring-methods">
                  {monitoringMethods.map((method) => <option key={method} value={method} />)}
                </datalist>
              </FieldFrame>
              <div className="md:col-span-2">
                <FieldFrame label="Instructional notes" htmlFor="goal-notes">
                  <TextArea id="goal-notes" value={selectedGoal.instructional_notes} onChange={(event) => updateSelected({ instructional_notes: event.target.value })} />
                </FieldFrame>
              </div>
            </div>
          ) : (
            <div className="grid min-h-80 place-items-center rounded-xl border border-dashed border-[var(--theme-border)]">
              <Button onClick={addGoal}>Add Goal</Button>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-5">
        <ValidationSummary validation={validation} />
      </div>
      <footer className="mt-5 flex flex-wrap items-center justify-between gap-3 pb-6">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void autosave.saveImmediately()}>Save Draft</Button>
          <Button disabled={!validation.is_complete} onClick={() => void saveAndContinue()}>Save & Continue</Button>
        </div>
      </footer>
    </div>
  );
}
