import { useMemo, useState } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FieldFrame, selectClass, TextArea, TextInput } from "../components/ui/FormField";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import { useAutosave } from "../hooks/useAutosave";
import { saveDataSheets, saveObservationChecklist, savePacketBuilder } from "../services/api/projects";
import type { DataSheetColumnDraft, DataSheetColumnType, DataSheetDraft, PacketPageDraft, PacketVersionConfig, ProjectDetail } from "../types/projects";

const columnTypes: readonly { value: DataSheetColumnType; label: string }[] = [
  { value: "text", label: "Text" },
  { value: "number", label: "Number" },
  { value: "date", label: "Date" },
  { value: "checkbox", label: "Checkbox" },
  { value: "notes", label: "Notes" },
];

const defaultObservationColumns: readonly DataSheetColumnDraft[] = [
  { id: "date", title: "Date", column_type: "date", position: 0 },
  { id: "context", title: "Setting / Context", column_type: "text", position: 1 },
  { id: "observation", title: "Observation", column_type: "notes", position: 2 },
  { id: "follow_up", title: "Follow-up / Action", column_type: "notes", position: 3 },
];

function newColumn(position: number): DataSheetColumnDraft {
  return {
    id: `column-${crypto.randomUUID()}`,
    title: "",
    column_type: "text",
    position,
  };
}

function blankObservation(position: number): DataSheetDraft {
  return {
    title: "Observation Sheet",
    sheet_type: "notes",
    goal_ids: [],
    collection_schedule: "General observation notes",
    blank_instance_count: 1,
    columns: defaultObservationColumns.map((column) => ({ ...column })),
    notes: "",
    template_name: "",
    is_template: false,
    is_observation_form: true,
    position,
  };
}

interface ObservationSheetsPageProps {
  readonly project: ProjectDetail;
  readonly onProjectUpdate: (project: ProjectDetail) => void;
  readonly onBack: () => void;
  readonly onComplete: () => void;
}

export function ObservationSheetsPage({
  project,
  onProjectUpdate,
  onBack,
  onComplete,
}: ObservationSheetsPageProps) {
  const regularSheets = useMemo(
    () => project.data_sheets.filter((sheet) => !sheet.is_observation_form).map((sheet) => ({
      ...sheet,
      goal_ids: [...sheet.goal_ids],
      columns: sheet.columns.map((column) => ({ ...column })),
    })),
    [project.data_sheets],
  );
  const [observations, setObservations] = useState<DataSheetDraft[]>(() =>
    project.data_sheets
      .filter((sheet) => sheet.is_observation_form)
      .map((sheet) => ({
        ...sheet,
        goal_ids: [],
        columns: sheet.columns.map((column) => ({ ...column })),
      })),
  );
  const [packetConfigs, setPacketConfigs] = useState<PacketVersionConfig[]>(() =>
    project.packet_builder.map((config) => ({
      packet_version_id: config.packet_version_id,
      pages: config.pages.map((page) => ({ ...page })),
      asset_placements: config.asset_placements.map((asset) => ({ ...asset })),
    })),
  );
  const [checklist, setChecklist] = useState<string[]>(() => [...project.observation_checklist]);
  const [selectedIndex, setSelectedIndex] = useState(observations.length ? 0 : -1);
  const [selectedCustomPageId, setSelectedCustomPageId] = useState("");
  const [saveError, setSaveError] = useState("");
  const selected = selectedIndex >= 0 ? observations[selectedIndex] : undefined;
  const customPages = packetConfigs[0]?.pages.filter((page) => page.page_type === "custom_text") ?? [];
  const selectedCustomPage = customPages.find((page) => page.id === selectedCustomPageId) ?? customPages[0];

  const autosave = useAutosave({
    value: { observations, checklist, packetConfigs },
    delayMs: 850,
    save: async (value, signal) => {
      try {
        const savedSheets = await saveDataSheets(project.id, [...regularSheets, ...value.observations], signal);
        const savedChecklist = await saveObservationChecklist(project.id, value.checklist, signal);
        const savedPackets = await savePacketBuilder(project.id, value.packetConfigs, signal);
        setSaveError("");
        onProjectUpdate({ ...savedPackets, data_sheets: savedSheets.data_sheets, observation_checklist: savedChecklist.observation_checklist });
      } catch (reason) {
        if (signal.aborted) return;
        setSaveError(reason instanceof Error ? reason.message : "Observation sheets could not be saved.");
        throw reason;
      }
    },
  });

  function addObservation() {
    const next = blankObservation(observations.length);
    setObservations((current) => [...current, next]);
    setSelectedIndex(observations.length);
  }

  function updateSelected(patch: Partial<DataSheetDraft>) {
    if (selectedIndex < 0) return;
    setObservations((current) =>
      current.map((sheet, index) => index === selectedIndex ? { ...sheet, ...patch } : sheet),
    );
  }

  function updateColumn(columnIndex: number, patch: Partial<DataSheetColumnDraft>) {
    if (!selected) return;
    updateSelected({
      columns: selected.columns.map((column, index) =>
        index === columnIndex ? { ...column, ...patch } : column,
      ),
    });
  }

  function deleteSelected() {
    if (selectedIndex < 0) return;
    setObservations((current) =>
      current.filter((_, index) => index !== selectedIndex).map((sheet, position) => ({ ...sheet, position })),
    );
    setSelectedIndex((current) => Math.min(current, observations.length - 2));
  }

  function addCustomPage() {
    const id = `custom_${crypto.randomUUID()}`;
    setSelectedCustomPageId(id);
    setPacketConfigs((current) =>
      current.map((config) => ({
        ...config,
        pages: [
          ...config.pages,
          {
            id,
            title: "Custom Page",
            page_type: "custom_text",
            enabled: true,
            position: config.pages.length,
            body_text: "",
          },
        ],
      })),
    );
  }

  function updateCustomPage(pageId: string, patch: Partial<Pick<PacketPageDraft, "title" | "body_text">>) {
    setPacketConfigs((current) =>
      current.map((config) => ({
        ...config,
        pages: config.pages.map((page) =>
          page.id === pageId ? { ...page, ...patch } : page,
        ),
      })),
    );
  }

  function deleteCustomPage(pageId: string) {
    setSelectedCustomPageId((current) => current === pageId ? "" : current);
    setPacketConfigs((current) =>
      current.map((config) => ({
        ...config,
        pages: config.pages
          .filter((page) => page.id !== pageId)
          .map((page, position) => ({ ...page, position })),
      })),
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 5 of 7"
        title={`Observation Sheets${project.student?.name ? ` - ${project.student.name}` : ""}`}
        description="Staff notes and custom pages."
        status={autosave.status}
        actions={<Button onClick={addObservation}>Add Observation Sheet</Button>}
      />

      {saveError && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          {saveError}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[21rem_1fr]">
        <div className="space-y-5 self-start">
          <Card title="Observation sheets" description="Separate from goal data collection.">
            <div className="space-y-2">
              {observations.map((sheet, index) => (
                <button
                  key={sheet.id ?? `observation-${index}`}
                  className={`w-full rounded-xl border px-3 py-3 text-left text-sm ${index === selectedIndex ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)]" : "border-[var(--theme-border)] bg-white"}`}
                  onClick={() => setSelectedIndex(index)}
                >
                  <span className="block font-semibold">{sheet.title || "Untitled observation sheet"}</span>
                  <span className="text-xs text-[var(--theme-text-muted)]">{sheet.columns.length} columns</span>
                </button>
              ))}
              {!observations.length && <Button onClick={addObservation}>Add the first observation sheet</Button>}
            </div>
          </Card>

          <Card
            title="Custom pages"
            description="Blank pages or staff notes."
            actions={<Button variant="outline" onClick={addCustomPage} disabled={!packetConfigs.length}>Add</Button>}
          >
            {customPages.length ? (
              <div className="space-y-2">
                {customPages.map((page) => (
                  <button
                    key={page.id}
                    className={`w-full rounded-xl border px-3 py-3 text-left text-sm ${page.id === selectedCustomPage?.id ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)]" : "border-[var(--theme-border)] bg-white"}`}
                    onClick={() => setSelectedCustomPageId(page.id)}
                  >
                    <span className="block font-semibold">{page.title || "Custom Page"}</span>
                    <span className="text-xs text-[var(--theme-text-muted)]">
                      {page.body_text?.trim() ? "Text page" : "Blank lined page"}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-[var(--theme-border)] p-4 text-center">
                <p className="text-sm text-[var(--theme-text-muted)]">No custom pages yet.</p>
                <Button className="mt-3" onClick={addCustomPage} disabled={!packetConfigs.length}>Add Custom Page</Button>
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-5">
          <Card
            title={selected ? "Observation form editor" : "Observation form editor"}
            description="Configure a general-purpose staff observation table."
            actions={selected && <Button variant="danger" onClick={deleteSelected}>Delete</Button>}
          >
            {selected ? (
              <div className="grid gap-4 md:grid-cols-2">
                <FieldFrame label="Title" htmlFor="observation-title">
                  <TextInput id="observation-title" value={selected.title} onChange={(event) => updateSelected({ title: event.target.value })} />
                </FieldFrame>
                <FieldFrame label="Use / schedule" htmlFor="observation-schedule">
                  <TextInput id="observation-schedule" value={selected.collection_schedule} onChange={(event) => updateSelected({ collection_schedule: event.target.value })} />
                </FieldFrame>
                <div className="md:col-span-2">
                  <FieldFrame label="Staff directions" htmlFor="observation-notes">
                    <TextArea id="observation-notes" value={selected.notes} onChange={(event) => updateSelected({ notes: event.target.value })} />
                  </FieldFrame>
                </div>
                <div className="md:col-span-2">
                  <Card title="Columns" actions={<Button variant="outline" onClick={() => updateSelected({ columns: [...selected.columns, newColumn(selected.columns.length)] })}>Add Column</Button>}>
                    <div className="space-y-3">
                      {selected.columns.map((column, index) => (
                        <div key={column.id} className="grid gap-3 rounded-xl border border-[var(--theme-border)] bg-white p-3 md:grid-cols-[1fr_10rem_auto]">
                          <TextInput value={column.title} onChange={(event) => updateColumn(index, { title: event.target.value })} />
                          <select className={selectClass} value={column.column_type} onChange={(event) => updateColumn(index, { column_type: event.target.value as DataSheetColumnType })}>
                            {columnTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
                          </select>
                          <Button variant="danger" onClick={() => updateSelected({ columns: selected.columns.filter((_, columnIndex) => columnIndex !== index).map((item, position) => ({ ...item, position })) })}>Delete</Button>
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              </div>
            ) : (
              <Button onClick={addObservation}>Add Observation Sheet</Button>
            )}
          </Card>

          <Card title="Things Staff Should Tell the Case Manager" description="These bullets appear in the checklist box on the observation section.">
            <div className="space-y-3">
              {checklist.map((item, index) => (
                <div key={index} className="flex gap-2">
                  <TextInput value={item} onChange={(event) => setChecklist((current) => current.map((value, itemIndex) => itemIndex === index ? event.target.value : value))} />
                  <Button variant="danger" onClick={() => setChecklist((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Remove</Button>
                </div>
              ))}
            </div>
            <Button className="mt-3" variant="outline" onClick={() => setChecklist((current) => [...current, ""])}>Add Bullet</Button>
          </Card>

          {customPages.length > 0 && (
            <Card
              title="Custom page editor"
              description="Add text, or leave a page body blank for a lined page."
            >
              <div className="space-y-5">
                {customPages.map((page, index) => (
                  <section key={page.id} className="rounded-xl border border-[var(--theme-border)] bg-white p-4">
                    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-[var(--theme-text)]">
                        Custom page {index + 1}
                      </p>
                      <Button variant="danger" onClick={() => deleteCustomPage(page.id)}>Delete</Button>
                    </div>
                    <div className="grid gap-4">
                      <FieldFrame label="Page title" htmlFor={`${page.id}-title`}>
                        <TextInput
                          id={`${page.id}-title`}
                          value={page.title}
                          onChange={(event) => updateCustomPage(page.id, { title: event.target.value })}
                        />
                      </FieldFrame>
                      <FieldFrame label="Page text" htmlFor={`${page.id}-body`}>
                        <TextArea
                          id={`${page.id}-body`}
                          value={page.body_text ?? ""}
                          onChange={(event) => updateCustomPage(page.id, { body_text: event.target.value })}
                          placeholder="Leave blank for a lined blank page, or add notes/instructions to print on the page."
                        />
                      </FieldFrame>
                    </div>
                  </section>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>

      <footer className="mt-5 flex flex-wrap items-center justify-between gap-3 pb-6">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void autosave.saveImmediately()}>Save Draft</Button>
          <Button onClick={() => void autosave.saveImmediately().then(onComplete)}>Continue</Button>
        </div>
      </footer>
    </div>
  );
}
