import { useMemo, useState } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FieldFrame, selectClass, TextArea, TextInput } from "../components/ui/FormField";
import { ValidationSummary } from "../components/workflow/ValidationSummary";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import { useAutosave } from "../hooks/useAutosave";
import { validateDataSheets } from "../lib/validation";
import { saveDataSheets } from "../services/api/projects";
import type {
  DataSheetColumnDraft,
  DataSheetColumnType,
  DataSheetDraft,
  DataSheetType,
  ProjectDetail,
} from "../types/projects";

const sheetTypes: readonly { value: DataSheetType; label: string }[] = [
  { value: "trial_count", label: "Trial count" },
  { value: "frequency", label: "Frequency" },
  { value: "duration", label: "Duration" },
  { value: "rubric", label: "Rubric" },
  { value: "notes", label: "Notes" },
];

const columnTypes: readonly { value: DataSheetColumnType; label: string }[] = [
  { value: "text", label: "Text" },
  { value: "number", label: "Number" },
  { value: "date", label: "Date" },
  { value: "checkbox", label: "Checkbox" },
  { value: "notes", label: "Notes" },
];

const defaultColumns: readonly DataSheetColumnDraft[] = [
  { id: "date", title: "Date", column_type: "date", position: 0 },
  { id: "trial", title: "Trial", column_type: "text", position: 1 },
  { id: "result", title: "Result", column_type: "text", position: 2 },
  { id: "notes", title: "Notes", column_type: "notes", position: 3 },
];

function newColumn(position: number): DataSheetColumnDraft {
  return {
    id: `column-${crypto.randomUUID()}`,
    title: "",
    column_type: "text",
    position,
  };
}

function blankDataSheet(project: ProjectDetail, position: number): DataSheetDraft {
  const firstTemplate = project.data_sheets.find((sheet) => sheet.is_template && !sheet.is_observation_form);
  return {
    title: "",
    sheet_type: firstTemplate?.sheet_type ?? "trial_count",
    goal_ids: project.goals[0]?.id ? [project.goals[0].id] : [],
    collection_schedule: firstTemplate?.collection_schedule ?? "",
    blank_instance_count: 1,
    columns: firstTemplate?.columns.map((column) => ({ ...column })) ?? defaultColumns.map((column) => ({ ...column })),
    notes: firstTemplate?.notes ?? "",
    template_name: "",
    is_template: false,
    is_observation_form: false,
    position,
  };
}

interface DataSheetBuilderPageProps {
  readonly project: ProjectDetail;
  readonly onProjectUpdate: (project: ProjectDetail) => void;
  readonly onBack: () => void;
  readonly onComplete: () => void;
}

export function DataSheetBuilderPage({
  project,
  onProjectUpdate,
  onBack,
  onComplete,
}: DataSheetBuilderPageProps) {
  const [dataSheets, setDataSheets] = useState<DataSheetDraft[]>(() =>
    project.data_sheets.filter((sheet) => !sheet.is_observation_form).map((sheet) => ({
      ...sheet,
      goal_ids: [...sheet.goal_ids],
      columns: sheet.columns.map((column) => ({ ...column })),
      template_name: sheet.template_name ?? "",
      is_template: sheet.is_template ?? false,
      is_observation_form: sheet.is_observation_form ?? false,
    })),
  );
  const observationSheets = useMemo(
    () => project.data_sheets.filter((sheet) => sheet.is_observation_form).map((sheet) => ({
      ...sheet,
      goal_ids: [],
      columns: sheet.columns.map((column) => ({ ...column })),
    })),
    [project.data_sheets],
  );
  const [selectedIndex, setSelectedIndex] = useState(project.data_sheets.length ? 0 : -1);
  const [saveError, setSaveError] = useState("");
  const validation = useMemo(() => validateDataSheets(dataSheets), [dataSheets]);
  const selectedSheet = selectedIndex >= 0 ? dataSheets[selectedIndex] : undefined;
  const templates = project.data_sheets.filter((sheet) => sheet.is_template && !sheet.is_observation_form);
  const goalsById = useMemo(
    () => new Map(project.goals.map((goal) => [goal.id, goal])),
    [project.goals],
  );
  const selectedGoals = selectedSheet
    ? selectedSheet.goal_ids.map((id) => goalsById.get(id)).filter(Boolean)
    : [];

  const autosave = useAutosave({
    value: dataSheets,
    delayMs: 850,
    save: async (value, signal) => {
      try {
        const saved = await saveDataSheets(project.id, [...value, ...observationSheets], signal);
        setSaveError("");
        onProjectUpdate(saved);
        setDataSheets((current) => {
          const idsChanged = current.some(
            (sheet, index) => (saved.data_sheets[index]?.id ?? sheet.id) !== sheet.id,
          );
          if (!idsChanged) return current;
          return current.map((sheet, index) => ({
            ...sheet,
            id: saved.data_sheets[index]?.id ?? sheet.id,
          }));
        });
      } catch (reason) {
        if (signal.aborted) return;
        setSaveError(reason instanceof Error ? reason.message : "Data sheets could not be saved.");
        throw reason;
      }
    },
  });

  function addDataSheet() {
    const next = blankDataSheet(project, dataSheets.length);
    setDataSheets((current) => [...current, next]);
    setSelectedIndex(dataSheets.length);
  }

  function updateSelected(patch: Partial<DataSheetDraft>) {
    if (selectedIndex < 0) return;
    setDataSheets((current) =>
      current.map((sheet, index) =>
        index === selectedIndex ? { ...sheet, ...patch } : sheet,
      ),
    );
  }

  function applyTemplate(templateId: string) {
    const template = templates.find((sheet) => sheet.id === templateId);
    if (!template || !selectedSheet) return;
    updateSelected({
      sheet_type: template.sheet_type,
      collection_schedule: template.collection_schedule,
      blank_instance_count: template.blank_instance_count,
      columns: template.columns.map((column) => ({ ...column, id: `column-${crypto.randomUUID()}` })),
      notes: template.notes,
    });
  }

  function toggleGoal(goalId: string) {
    if (!selectedSheet) return;
    const goalIds = selectedSheet.goal_ids.includes(goalId)
      ? selectedSheet.goal_ids.filter((id) => id !== goalId)
      : [...selectedSheet.goal_ids, goalId];
    updateSelected({ goal_ids: goalIds });
  }

  function addColumn() {
    if (!selectedSheet) return;
    updateSelected({ columns: [...selectedSheet.columns, newColumn(selectedSheet.columns.length)] });
  }

  function updateColumn(columnIndex: number, patch: Partial<DataSheetColumnDraft>) {
    if (!selectedSheet) return;
    updateSelected({
      columns: selectedSheet.columns.map((column, index) =>
        index === columnIndex ? { ...column, ...patch } : column,
      ),
    });
  }

  function deleteColumn(columnIndex: number) {
    if (!selectedSheet) return;
    updateSelected({
      columns: selectedSheet.columns
        .filter((_, index) => index !== columnIndex)
        .map((column, position) => ({ ...column, position })),
    });
  }

  function moveColumn(columnIndex: number, direction: -1 | 1) {
    if (!selectedSheet) return;
    const target = columnIndex + direction;
    if (target < 0 || target >= selectedSheet.columns.length) return;
    const reordered = [...selectedSheet.columns];
    [reordered[columnIndex], reordered[target]] = [reordered[target], reordered[columnIndex]];
    updateSelected({
      columns: reordered.map((column, position) => ({ ...column, position })),
    });
  }

  function duplicateSelected() {
    if (!selectedSheet) return;
    const copy: DataSheetDraft = {
      ...selectedSheet,
      id: null,
      title: selectedSheet.title ? `${selectedSheet.title} (Copy)` : "",
      goal_ids: [...selectedSheet.goal_ids],
      columns: selectedSheet.columns.map((column) => ({ ...column })),
      template_name: selectedSheet.template_name,
      is_template: selectedSheet.is_template,
      is_observation_form: selectedSheet.is_observation_form,
      position: dataSheets.length,
    };
    setDataSheets((current) => [...current, copy]);
    setSelectedIndex(dataSheets.length);
  }

  function deleteSelected() {
    if (selectedIndex < 0) return;
    setDataSheets((current) =>
      current
        .filter((_, index) => index !== selectedIndex)
        .map((sheet, position) => ({ ...sheet, position })),
    );
    setSelectedIndex((current) => Math.min(current, dataSheets.length - 2));
  }

  function moveSelected(direction: -1 | 1) {
    if (selectedIndex < 0) return;
    const target = selectedIndex + direction;
    if (target < 0 || target >= dataSheets.length) return;
    setDataSheets((current) => {
      const reordered = [...current];
      [reordered[selectedIndex], reordered[target]] = [
        reordered[target],
        reordered[selectedIndex],
      ];
      return reordered.map((sheet, position) => ({ ...sheet, position }));
    });
    setSelectedIndex(target);
  }

  async function finish() {
    await autosave.saveImmediately();
    if (validation.is_complete) onComplete();
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 4 of 7"
        title="Data Sheet Builder"
        description="Create progress-monitoring sheet definitions from existing goals. Goal text stays owned by the Goal Builder."
        status={autosave.status}
        actions={<Button onClick={addDataSheet}>Add Data Sheet</Button>}
      />

      {saveError && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          {saveError}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[22rem_1fr]">
        <Card title="Data sheet list" description="Each sheet references one or more existing goals.">
          {dataSheets.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--theme-border)] p-6 text-center">
              <p className="text-sm text-[var(--theme-text-muted)]">No data sheets created.</p>
              <Button className="mt-4" onClick={addDataSheet}>Add the first data sheet</Button>
            </div>
          ) : (
            <div className="space-y-2">
              {dataSheets.map((sheet, index) => (
                <button
                  key={sheet.id ?? `draft-${index}`}
                  className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                    index === selectedIndex
                      ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)]"
                      : "border-[var(--theme-border)] bg-white hover:bg-[var(--theme-surface-muted)]"
                  }`}
                  onClick={() => setSelectedIndex(index)}
                >
                  <span className="block text-xs font-semibold text-[var(--theme-accent)]">
                    Sheet {index + 1}
                  </span>
                  <span className="mt-1 block text-sm font-medium text-[var(--theme-text)]">
                    {sheet.title || "Untitled data sheet"}
                  </span>
                  <span className="mt-1 block text-xs text-[var(--theme-text-muted)]">
                    {sheet.goal_ids.length} goal{sheet.goal_ids.length === 1 ? "" : "s"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </Card>

        <Card
          title={selectedSheet ? `Data Sheet ${selectedIndex + 1}` : "Data sheet editor"}
          description={
            selectedSheet
              ? "Configure the sheet without copying goal language into a second owner."
              : "Select a sheet or add a new one to begin."
          }
          actions={
            selectedSheet && (
              <div className="flex flex-wrap gap-1">
                <Button variant="text" disabled={selectedIndex === 0} onClick={() => moveSelected(-1)}>Up</Button>
                <Button variant="text" disabled={selectedIndex === dataSheets.length - 1} onClick={() => moveSelected(1)}>Down</Button>
                <Button variant="outline" onClick={duplicateSelected}>Duplicate</Button>
                <Button variant="danger" onClick={deleteSelected}>Delete</Button>
              </div>
            )
          }
        >
          {selectedSheet ? (
            <div className="grid gap-5 lg:grid-cols-[1fr_22rem]">
              <div className="grid gap-5 md:grid-cols-2">
                <FieldFrame label="Data sheet title" htmlFor="sheet-title" required>
                  <TextInput
                    id="sheet-title"
                    value={selectedSheet.title}
                    onChange={(event) => updateSelected({ title: event.target.value })}
                    placeholder="Reading fluency weekly probe"
                  />
                </FieldFrame>
                <FieldFrame label="Collection type" htmlFor="sheet-type" required>
                  <select
                    id="sheet-type"
                    className={selectClass}
                    value={selectedSheet.sheet_type ?? ""}
                    onChange={(event) =>
                      updateSelected({ sheet_type: event.target.value as DataSheetType })
                    }
                  >
                    {sheetTypes.map((type) => (
                      <option key={type.value} value={type.value}>{type.label}</option>
                    ))}
                  </select>
                </FieldFrame>
                <FieldFrame label="Reusable template name" htmlFor="template-name" hint="Optional label for reusing this table structure later.">
                  <TextInput
                    id="template-name"
                    value={selectedSheet.template_name}
                    onChange={(event) =>
                      updateSelected({
                        template_name: event.target.value,
                        is_template: Boolean(event.target.value.trim()),
                      })
                    }
                    placeholder="Weekly fluency table"
                  />
                </FieldFrame>
                <FieldFrame label="Apply template" htmlFor="apply-template" hint="Copies reusable table settings into this sheet.">
                  <select id="apply-template" className={selectClass} defaultValue="" onChange={(event) => applyTemplate(event.target.value)}>
                    <option value="">Choose template</option>
                    {templates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.template_name || template.title}
                      </option>
                    ))}
                  </select>
                </FieldFrame>
                <div className="md:col-span-2">
                  <FieldFrame
                    label="Collection schedule"
                    htmlFor="collection-schedule"
                    required
                    hint="Examples: weekly, every other Friday, 3 trials per session."
                  >
                    <TextInput
                      id="collection-schedule"
                      value={selectedSheet.collection_schedule}
                      onChange={(event) =>
                        updateSelected({ collection_schedule: event.target.value })
                      }
                    />
                  </FieldFrame>
                </div>
                <FieldFrame
                  label="Blank table instances in packet"
                  htmlFor="blank-instance-count"
                  required
                  hint="This repeats the blank table in the final packet without duplicating the data sheet object."
                >
                  <TextInput
                    id="blank-instance-count"
                    type="number"
                    min={1}
                    max={100}
                    value={selectedSheet.blank_instance_count}
                    onChange={(event) =>
                      updateSelected({
                        blank_instance_count: Math.max(1, Number(event.target.value) || 1),
                      })
                    }
                  />
                </FieldFrame>
                <div className="md:col-span-2">
                  <Card
                    title="Table columns"
                    description="Add, edit, and reorder the blank collection table columns."
                    actions={<Button variant="outline" onClick={addColumn}>Add Column</Button>}
                  >
                    <div className="space-y-3">
                      {selectedSheet.columns.map((column, columnIndex) => (
                        <div
                          key={column.id}
                          className="rounded-xl border border-[var(--theme-border)] bg-white p-3"
                        >
                          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_9rem]">
                            <FieldFrame
                              label={`Column ${columnIndex + 1} title`}
                              htmlFor={`column-${column.id}-title`}
                              required
                            >
                              <TextInput
                                id={`column-${column.id}-title`}
                                value={column.title}
                                onChange={(event) =>
                                  updateColumn(columnIndex, { title: event.target.value })
                                }
                                placeholder="Column title"
                              />
                            </FieldFrame>
                            <FieldFrame
                              label="Type"
                              htmlFor={`column-${column.id}-type`}
                            >
                              <select
                                id={`column-${column.id}-type`}
                                className={selectClass}
                                value={column.column_type}
                                onChange={(event) =>
                                  updateColumn(columnIndex, {
                                    column_type: event.target.value as DataSheetColumnType,
                                  })
                                }
                              >
                                {columnTypes.map((type) => (
                                  <option key={type.value} value={type.value}>{type.label}</option>
                                ))}
                              </select>
                            </FieldFrame>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <Button variant="text" disabled={columnIndex === 0} onClick={() => moveColumn(columnIndex, -1)}>Move left</Button>
                            <Button variant="text" disabled={columnIndex === selectedSheet.columns.length - 1} onClick={() => moveColumn(columnIndex, 1)}>Move right</Button>
                            <Button variant="danger" onClick={() => deleteColumn(columnIndex)}>Delete</Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
                <div className="md:col-span-2">
                  <FieldFrame label="Notes for staff" htmlFor="sheet-notes">
                    <TextArea
                      id="sheet-notes"
                      value={selectedSheet.notes}
                      onChange={(event) => updateSelected({ notes: event.target.value })}
                      placeholder="Optional directions for collecting consistent data."
                    />
                  </FieldFrame>
                </div>
              </div>

              <aside className="space-y-4">
                <Card title="Attach goals" description="Summaries are pulled from Goal Builder.">
                  <div className="space-y-3">
                    {project.goals.map((goal) => (
                      <label
                        key={goal.id}
                        className="flex gap-3 rounded-xl border border-[var(--theme-border)] bg-white p-3 text-sm"
                      >
                        <input
                          type="checkbox"
                          checked={selectedSheet.goal_ids.includes(goal.id)}
                          onChange={() => toggleGoal(goal.id)}
                        />
                        <span>
                          <span className="block font-semibold text-[var(--theme-text)]">
                            {goal.title}
                          </span>
                          <span className="mt-1 block text-xs leading-5 text-[var(--theme-text-muted)]">
                            {goal.data_sheet_summary || "No data-sheet summary entered."}
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                </Card>
                <Card title="Packet table preview" description="Goal summaries appear above each blank table instance.">
                  {selectedGoals.length ? (
                    <div className="space-y-5">
                      {Array.from({ length: selectedSheet.blank_instance_count }).map((_, instanceIndex) => (
                        <section
                          key={`instance-${instanceIndex}`}
                          className="rounded-xl border border-[var(--theme-border)] bg-white p-3"
                        >
                          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--theme-accent)]">
                            Blank table {instanceIndex + 1} of {selectedSheet.blank_instance_count}
                          </p>
                          <div className="mt-3 space-y-2">
                            {selectedGoals.map((goal) => goal && (
                              <p key={goal.id} className="text-sm leading-6 text-[var(--theme-text)]">
                                <span className="font-semibold text-[var(--theme-primary)]">{goal.title}: </span>
                                {goal.data_sheet_summary}
                              </p>
                            ))}
                          </div>
                          <div className="mt-3 overflow-x-auto">
                            <table className="w-full border-collapse text-xs">
                              <thead>
                                <tr>
                                  {selectedSheet.columns.map((column) => (
                                    <th
                                      key={column.id}
                                      className="border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] px-2 py-2 text-left font-semibold text-[var(--theme-text)]"
                                    >
                                      {column.title || "Untitled"}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {Array.from({ length: 4 }).map((__, rowIndex) => (
                                  <tr key={rowIndex}>
                                    {selectedSheet.columns.map((column) => (
                                      <td key={column.id} className="h-9 border border-[var(--theme-border)] px-2 py-2">
                                        {column.column_type === "checkbox" ? (
                                          <input type="checkbox" disabled aria-label="Blank checkbox cell" />
                                        ) : ""}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </section>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--theme-text-muted)]">
                      Attach at least one goal to preview sheet targets.
                    </p>
                  )}
                </Card>
              </aside>
            </div>
          ) : (
            <div className="grid min-h-80 place-items-center rounded-xl border border-dashed border-[var(--theme-border)]">
              <Button onClick={addDataSheet}>Add Data Sheet</Button>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-5">
        <ValidationSummary
          validation={validation}
          completeMessage="Data sheet definitions are ready."
        />
      </div>
      <footer className="mt-5 flex flex-wrap items-center justify-between gap-3 pb-6">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void autosave.saveImmediately()}>Save Draft</Button>
          <Button disabled={!validation.is_complete} onClick={() => void finish()}>Save & Continue</Button>
        </div>
      </footer>
    </div>
  );
}
