import { useEffect, useState, type ReactNode } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FieldFrame, selectClass } from "../components/ui/FormField";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import { useAutosave } from "../hooks/useAutosave";
import { savePacketBuilder } from "../services/api/projects";
import { useTerminology } from "../terminology/TerminologyProvider";
import type { DataSheetDraft, GoalDraft, PacketVersionConfig, ProjectDetail, ServiceAreaDraft } from "../types/projects";

type GoalWithId = GoalDraft & { readonly id: string };
type ServiceAreaWithId = ServiceAreaDraft & { readonly id: string };

function goalsForSheet(
  sheet: DataSheetDraft,
  goals: readonly GoalWithId[],
) {
  const byId = new Map(goals.map((goal) => [goal.id, goal]));
  return sheet.goal_ids.map((id) => byId.get(id)).filter(Boolean) as GoalWithId[];
}

function serviceAreaName(
  serviceAreaId: string | null,
  serviceAreas: readonly ServiceAreaWithId[],
) {
  return serviceAreas.find((area) => area.id === serviceAreaId)?.name || "Unassigned";
}

function accommodationLabel(item: ProjectDetail["accommodations"][number]) {
  if (item.content_area === "Other") return item.custom_content_area.trim() || "Other";
  return item.content_area || "Instructional";
}

function visibleBehaviorSections(project: ProjectDetail) {
  return project.behavior_plan_sections.filter((item) => item.text.trim());
}

function hasAccommodationContent(project: ProjectDetail) {
  return project.accommodations.some((item) => item.text.trim());
}

function hasBehaviorContent(project: ProjectDetail) {
  return visibleBehaviorSections(project).length > 0 || project.behavior_plan.trim().length > 0;
}

function isPageAvailable(pageId: string, project: ProjectDetail) {
  if (pageId === "accommodations") return hasAccommodationContent(project);
  if (pageId === "accommodations_signature") return hasAccommodationContent(project);
  if (pageId === "behavior") return hasBehaviorContent(project);
  return true;
}

function uniqueServiceNames(serviceAreas: readonly ServiceAreaWithId[]) {
  return [...new Set(serviceAreas.map((area) => area.name).filter(Boolean))];
}

function PacketPage({
  title,
  description,
  children,
}: {
  readonly title: string;
  readonly description?: string;
  readonly children: ReactNode;
}) {
  return (
    <Card title={title} description={description}>
      <div className="rounded-2xl border border-[var(--theme-border)] bg-white p-6 shadow-sm">
        {children}
      </div>
    </Card>
  );
}

interface PacketDesignerPageProps {
  readonly project: ProjectDetail;
  readonly onProjectUpdate: (project: ProjectDetail) => void;
  readonly onBack: () => void;
  readonly onComplete: () => void;
}

export function PacketDesignerPage({
  project,
  onProjectUpdate,
  onBack,
  onComplete,
}: PacketDesignerPageProps) {
  const { fullTitle } = useTerminology();
  const [configs, setConfigs] = useState<PacketVersionConfig[]>(() =>
    project.packet_builder.map((config) => ({
      packet_version_id: config.packet_version_id,
      pages: config.pages.map((page) => ({ ...page })),
      asset_placements: config.asset_placements.map((asset) => ({ ...asset })),
    })),
  );
  const [selectedVersionId, setSelectedVersionId] = useState(
    project.packet_versions[0]?.id ?? configs[0]?.packet_version_id ?? "",
  );
  const [draggedPageId, setDraggedPageId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState("");
  const selectedConfig = configs.find((config) => config.packet_version_id === selectedVersionId) ?? configs[0];
  const autosave = useAutosave({
    value: configs,
    delayMs: 850,
    save: async (value, signal) => {
      try {
        const saved = await savePacketBuilder(project.id, value, signal);
        setSaveError("");
        onProjectUpdate(saved);
      } catch (reason) {
        if (signal.aborted) return;
        setSaveError(reason instanceof Error ? reason.message : "Packet builder could not be saved.");
        throw reason;
      }
    },
  });

  function updateSelectedConfig(patch: Partial<PacketVersionConfig>) {
    if (!selectedConfig) return;
    setConfigs((current) =>
      current.map((config) =>
        config.packet_version_id === selectedConfig.packet_version_id
          ? { ...config, ...patch }
          : config,
      ),
    );
  }

  function updatePage(pageIndex: number, enabled: boolean) {
    if (!selectedConfig) return;
    updateSelectedConfig({
      pages: selectedConfig.pages.map((page, index) =>
        index === pageIndex ? { ...page, enabled } : page,
      ),
    });
  }

  function movePage(from: number, to: number) {
    if (!selectedConfig || from === to || to < 0 || to >= selectedConfig.pages.length) return;
    const pages = [...selectedConfig.pages];
    const [page] = pages.splice(from, 1);
    pages.splice(to, 0, page);
    updateSelectedConfig({ pages: pages.map((item, position) => ({ ...item, position })) });
  }

  useEffect(() => {
    if (!draggedPageId) return;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.userSelect = "none";

    function moveDraggedPage(targetIndex: number) {
      setConfigs((current) =>
        current.map((config) => {
          if (config.packet_version_id !== selectedVersionId) return config;
          const fromIndex = config.pages.findIndex((page) => page.id === draggedPageId);
          if (fromIndex === -1 || fromIndex === targetIndex) return config;
          const pages = [...config.pages];
          const [page] = pages.splice(fromIndex, 1);
          pages.splice(targetIndex, 0, page);
          return {
            ...config,
            pages: pages.map((item, position) => ({ ...item, position })),
          };
        }),
      );
    }

    function handlePointerMove(event: PointerEvent) {
      const element = document.elementFromPoint(event.clientX, event.clientY);
      const row = element?.closest("[data-packet-page-index]") as HTMLElement | null;
      if (!row) return;
      const targetIndex = Number(row.dataset.packetPageIndex);
      if (Number.isNaN(targetIndex)) return;
      moveDraggedPage(targetIndex);
    }

    function stopDragging() {
      setDraggedPageId(null);
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopDragging);
    window.addEventListener("pointercancel", stopDragging);
    return () => {
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopDragging);
      window.removeEventListener("pointercancel", stopDragging);
    };
  }, [draggedPageId, selectedVersionId]);

  const studentName = project.student?.name || "Student";
  const serviceNames = uniqueServiceNames(project.service_areas);
  const goalsByServiceArea = project.service_areas.map((area) => ({
    area,
    goals: project.goals.filter((goal) => goal.service_area_id === area.id),
  }));
  const unassignedGoals = project.goals.filter((goal) => !goal.service_area_id);
  const dataCollectionPages = project.data_sheets.flatMap((sheet) =>
    sheet.is_observation_form ? [] :
    goalsForSheet(sheet, project.goals).map((goal) => ({
      sheet,
      goal,
    })),
  );
  const observationForms = project.data_sheets.filter((sheet) => sheet.is_observation_form);
  const customPages = selectedConfig?.pages.filter((page) => page.page_type === "custom_text" && page.enabled) ?? [];
  const visiblePageEntries = selectedConfig?.pages
    .map((page, index) => ({ page, index }))
    .filter(({ page }) => isPageAvailable(page.id, project)) ?? [];
  const availableEnabledPageIds = new Set(
    selectedConfig?.pages
      .filter((page) => page.enabled && isPageAvailable(page.id, project))
      .map((page) => page.id) ?? [],
  );
  const orderedEnabledPageIds = selectedConfig?.pages
    .filter((page) => page.enabled && isPageAvailable(page.id, project))
    .map((page) => page.id) ?? [];
  function previewOrder(pageId: string) {
    const index = orderedEnabledPageIds.indexOf(pageId);
    return index === -1 ? 999 : index;
  }
  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 6 of 7"
        title={`Packet Designer${project.student?.name ? ` - ${project.student.name}` : ""}`}
        description="Choose which pages belong in each packet version, order them, and reserve asset placement slots."
        status={autosave.status}
      />

      {saveError && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          {saveError}
        </div>
      )}

      <div className="grid items-start gap-5 xl:grid-cols-[23rem_1fr]">
        <Card title="Packet controls" description="Visibility and order autosave per packet version.">
          <FieldFrame label="Packet version" htmlFor="packet-version">
            <select
              id="packet-version"
              className={selectClass}
              value={selectedVersionId}
              onChange={(event) => setSelectedVersionId(event.target.value)}
            >
              {project.packet_versions.map((version) => (
                <option key={version.id} value={version.id}>{version.name}</option>
              ))}
            </select>
          </FieldFrame>
          <div className="mt-5 space-y-3 text-sm">
            {visiblePageEntries.map(({ page, index }, visibleIndex) => (
              <div
                key={page.id}
                data-packet-page-index={index}
                className={`rounded-xl border bg-white p-3 ${draggedPageId === page.id ? "border-[var(--theme-primary)] opacity-70" : "border-[var(--theme-border)]"}`}
              >
                <div className="flex items-start gap-3">
                  <button
                    type="button"
                    aria-label={`Drag ${page.title}`}
                    title="Hold and drag to reorder"
                    onPointerDown={(event) => {
                      event.preventDefault();
                      setDraggedPageId(page.id);
                    }}
                    className="mt-0.5 cursor-grab touch-none select-none rounded-lg border border-[var(--theme-border)] px-2 py-1 text-xs font-semibold text-[var(--theme-text-muted)] active:cursor-grabbing"
                  >
                    Drag
                  </button>
                  <input
                    className="mt-1"
                    type="checkbox"
                    checked={page.enabled}
                    onChange={(event) => updatePage(index, event.target.checked)}
                  />
                  <span className="min-w-0">
                    <span className="block font-semibold text-[var(--theme-text)]">
                      {visibleIndex + 1}. {page.title || "Custom Page"}
                    </span>
                    <span className="text-xs text-[var(--theme-text-muted)]">
                      {page.page_type === "custom_text"
                        ? "Edit custom pages from Staff Notes and Custom Pages."
                        : "Hold Drag and move over another row, or use Up/Down"}
                    </span>
                  </span>
                </div>
                <div className="mt-2 flex gap-1">
                  <Button variant="text" disabled={visibleIndex === 0} onClick={() => movePage(index, visiblePageEntries[visibleIndex - 1]?.index ?? index)}>Up</Button>
                  <Button variant="text" disabled={visibleIndex === visiblePageEntries.length - 1} onClick={() => movePage(index, visiblePageEntries[visibleIndex + 1]?.index ?? index)}>Down</Button>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <div className="flex flex-col gap-5">
          {availableEnabledPageIds.has("cover") && <div style={{ order: previewOrder("cover") }}><PacketPage title="Cover Page" description="Uses Student Setup data.">
            <div className="border-b border-[var(--theme-border)] pb-6">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--theme-accent)]">
                {fullTitle} Service Packet
              </p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight text-[var(--theme-primary)]">
                {project.name}
              </h2>
              <p className="mt-2 text-xl text-[var(--theme-text)]">{studentName}</p>
            </div>
            <dl className="mt-6 grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="font-semibold text-[var(--theme-text-muted)]">Grade</dt>
                <dd className="mt-1 text-[var(--theme-text)]">{project.student?.grade || "Not entered"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-[var(--theme-text-muted)]">IEP end date</dt>
                <dd className="mt-1 text-[var(--theme-text)]">{project.student?.iep_end_date || "Not entered"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-[var(--theme-text-muted)]">School year</dt>
                <dd className="mt-1 text-[var(--theme-text)]">{project.school_year || "Not entered"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-[var(--theme-text-muted)]">Service areas</dt>
                <dd className="mt-1 text-[var(--theme-text)]">
                  {serviceNames.length ? serviceNames.join(", ") : "Not entered"}
                </dd>
              </div>
            </dl>
          </PacketPage></div>}

          {availableEnabledPageIds.has("at_a_glance") && <div style={{ order: previewOrder("at_a_glance") }}><PacketPage title="At-a-Glance" description="Instructional summary preview.">
            <div className="overflow-hidden rounded-xl border border-[var(--theme-border)]">
              <div className="bg-[var(--theme-primary)] px-5 py-5 text-white">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/65">
                  At a Glance
                </p>
                <h2 className="mt-2 text-2xl font-semibold">{studentName}</h2>
                {project.school_year && <p className="mt-1 text-sm text-white/70">{project.school_year}</p>}
              </div>
              <div className="space-y-5 p-5">
                {project.at_a_glance.sections
                  .filter((section) => section.enabled && section.content.trim())
                  .map((section) => (
                    <section key={section.id}>
                      <h3 className="text-sm font-semibold text-[var(--theme-primary)]">
                        {section.title}
                      </h3>
                      <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[var(--theme-text)]">
                        {section.content}
                      </p>
                    </section>
                  ))}
              </div>
            </div>
          </PacketPage></div>}

          {availableEnabledPageIds.has("accommodations") && <div style={{ order: previewOrder("accommodations") }}><PacketPage title="Accommodations/Modifications" description="Student Setup accommodations and modifications.">
            {project.accommodations.filter((item) => item.text.trim()).length ? (
              <div className="space-y-4">
                {project.accommodations
                  .filter((item) => item.text.trim())
                  .map((item, index) => (
                    <section key={item.id ?? `${item.content_area}-${index}`} className="rounded-xl border border-[var(--theme-border)] p-4">
                      <h3 className="text-sm font-semibold text-[var(--theme-primary)]">{accommodationLabel(item)}</h3>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--theme-text-muted)]">{item.text}</p>
                    </section>
                  ))}
              </div>
            ) : (
              <p className="text-sm leading-6 text-[var(--theme-text-muted)]">No accommodations or modifications entered yet.</p>
            )}
          </PacketPage></div>}

          {availableEnabledPageIds.has("accommodations_signature") && <div style={{ order: previewOrder("accommodations_signature") }}><PacketPage title="Accommodations Signature Page" description="Staff receipt signature sheet.">
            <div className="rounded-2xl border border-[var(--theme-border)] bg-[var(--theme-surface)] p-5">
              <div className="border-b-2 border-[var(--theme-border)] pb-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--theme-accent)]">
                  Accommodations receipt
                </p>
                <h3 className="mt-2 text-2xl font-semibold text-[var(--theme-primary)]">
                  Staff Signature Page
                </h3>
                <div className="mt-3 flex flex-wrap gap-4 text-sm text-[var(--theme-text)]">
                  <span><strong>Student:</strong> {studentName}</span>
                  <span><strong>IEP End:</strong> {project.student?.iep_end_date || "Not entered"}</span>
                </div>
              </div>
              <p className="mt-4 text-sm leading-6 text-[var(--theme-text-muted)]">
                The final PDF uses the title, note, and line style from Dashboard accommodations settings.
              </p>
              <div className="mt-5 overflow-hidden rounded-xl border border-[var(--theme-border)] bg-white">
                <div className="grid grid-cols-[1fr_10rem] bg-[var(--theme-primary)] text-xs font-semibold uppercase tracking-[0.12em] text-white">
                  <div className="border-r border-white/25 px-4 py-3">Staff Member</div>
                  <div className="px-4 py-3">Date</div>
                </div>
                {Array.from({ length: 7 }).map((_, index) => (
                  <div key={index} className="grid grid-cols-[1fr_10rem]">
                    <div className="h-16 border-r border-t border-[var(--theme-border)]" />
                    <div className="h-16 border-t border-[var(--theme-border)]" />
                  </div>
                ))}
              </div>
            </div>
          </PacketPage></div>}

          {availableEnabledPageIds.has("behavior") && <div style={{ order: previewOrder("behavior") }}><PacketPage title="Behavior Plans" description="Student Setup behavior support content.">
            {visibleBehaviorSections(project).length ? (
              <div className="space-y-4">
                {visibleBehaviorSections(project).map((item, index) => (
                  <section key={item.id ?? `${item.title}-${index}`} className="rounded-xl border border-[var(--theme-border)] p-4">
                    <h3 className="text-sm font-semibold text-[var(--theme-primary)]">
                      {item.title.trim() || `Behavior plan section ${index + 1}`}
                    </h3>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--theme-text-muted)]">{item.text}</p>
                  </section>
                ))}
              </div>
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-6 text-[var(--theme-text-muted)]">
                {project.behavior_plan.trim() || "No behavior plan entered yet."}
              </p>
            )}
          </PacketPage></div>}

          {availableEnabledPageIds.has("goal_summary") && <div style={{ order: previewOrder("goal_summary") }}><PacketPage title="Goal Summary" description="Full goals grouped under each service area.">
            <div className="space-y-6">
              {[...goalsByServiceArea, ...(unassignedGoals.length ? [{ area: null, goals: unassignedGoals }] : [])]
                .filter((group) => group.goals.length)
                .map((group) => (
                  <section key={group.area?.id ?? "unassigned"}>
                    <h3 className="text-base font-semibold text-[var(--theme-primary)]">
                      {group.area?.name || "Unassigned"}
                    </h3>
                    <div className="mt-3 space-y-4">
                      {group.goals.map((goal) => (
                        <article key={goal.id} className="rounded-xl border border-[var(--theme-border)] p-4">
                          <h4 className="font-semibold text-[var(--theme-text)]">{goal.title}</h4>
                          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--theme-text)]">
                            {goal.statement}
                          </p>
                        </article>
                      ))}
                    </div>
                  </section>
                ))}
            </div>
          </PacketPage></div>}

          {availableEnabledPageIds.has("services") && <div style={{ order: previewOrder("services") }}><PacketPage title="Service Areas" description="Lists service minutes and instructional setting.">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr>
                    <th className="border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] px-3 py-2 text-left font-semibold">Service</th>
                    <th className="border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] px-3 py-2 text-left font-semibold">Minutes per week</th>
                    <th className="border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] px-3 py-2 text-left font-semibold">Setting</th>
                  </tr>
                </thead>
                <tbody>
                  {project.service_areas.map((area) => (
                    <tr key={area.id}>
                      <td className="border border-[var(--theme-border)] px-3 py-2">{area.name}</td>
                      <td className="border border-[var(--theme-border)] px-3 py-2">{area.minutes_per_week ?? "Not entered"}</td>
                      <td className="border border-[var(--theme-border)] px-3 py-2">{area.setting || "Not entered"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </PacketPage></div>}

          {availableEnabledPageIds.has("data_collection") && <div style={{ order: previewOrder("data_collection") }} className="space-y-5">{dataCollectionPages.map(({ sheet, goal }) => (
            <PacketPage
              key={`${sheet.id ?? sheet.title}-${goal.id}`}
              title={`Data Collection - ${goal.title}`}
              description={`${sheet.title}. Final PDF includes ${sheet.blank_instance_count} blank ${sheet.blank_instance_count === 1 ? "table" : "tables"}.`}
            >
              <div>
                <p className="text-sm leading-6 text-[var(--theme-text)]">
                  <span className="font-semibold text-[var(--theme-primary)]">{goal.title}: </span>
                  {goal.data_sheet_summary}
                </p>
                <p className="mt-2 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--theme-accent)]">
                  {serviceAreaName(goal.service_area_id, project.service_areas)}
                </p>
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr>
                      {sheet.columns.map((column) => (
                        <th
                          key={column.id}
                          className="border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] px-3 py-2 text-left font-semibold"
                        >
                          {column.title}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from({ length: 10 }).map((_, rowIndex) => (
                      <tr key={rowIndex}>
                        {sheet.columns.map((column) => (
                          <td key={column.id} className="h-10 border border-[var(--theme-border)] px-3 py-2">
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
            </PacketPage>
          ))}</div>}

          {customPages.map((page) => (
            <div key={page.id} style={{ order: previewOrder(page.id) }}>
              <PacketPage title={page.title || "Custom Page"} description="Blank/custom packet page.">
                <div>
                  {page.body_text?.trim() ? (
                    <p className="whitespace-pre-wrap text-sm leading-6 text-[var(--theme-text)]">
                      {page.body_text}
                    </p>
                  ) : (
                    <div className="space-y-4">
                      <p className="text-sm text-[var(--theme-text-muted)]">
                        Blank lined page. Edit title/text from Staff Notes and Custom Pages.
                      </p>
                      {Array.from({ length: 8 }).map((_, index) => (
                        <div key={index} className="h-8 border-b border-[var(--theme-border)]" />
                      ))}
                    </div>
                  )}
                </div>
              </PacketPage>
            </div>
          ))}

          {availableEnabledPageIds.has("observations") && <div style={{ order: previewOrder("observations") }}><PacketPage title="Observations & Notes" description="Standalone observation forms and staff-to-case-manager checklist.">
            <div className="space-y-5">
              {(observationForms.length ? observationForms : [{
                id: "default-observations",
                title: "Observations & Notes",
                collection_schedule: "General observation form",
                columns: [
                  { id: "date", title: "Date", column_type: "date", position: 0 },
                  { id: "setting", title: "Setting / Context", column_type: "text", position: 1 },
                  { id: "observation", title: "Observation", column_type: "notes", position: 2 },
                  { id: "follow_up", title: "Follow-up / Action", column_type: "notes", position: 3 },
                ],
                notes: "",
              }]).map((sheet, sheetIndex) => (
                <section key={sheet.id ?? `${sheet.title}-${sheetIndex}`} className="rounded-xl border border-[var(--theme-border)] p-4">
                  <div>
                    <h3 className="text-base font-semibold text-[var(--theme-primary)]">{sheet.title || "Observation Sheet"}</h3>
                    <p className="mt-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--theme-accent)]">
                      {sheet.collection_schedule || "General observation form"}
                    </p>
                    {sheet.notes && <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--theme-text-muted)]">{sheet.notes}</p>}
                  </div>
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr>
                          {sheet.columns.map((column) => (
                            <th key={column.id} className="border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] px-3 py-2 text-left font-semibold">
                              {column.title}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {Array.from({ length: 8 }).map((_, rowIndex) => (
                          <tr key={rowIndex}>
                            {sheet.columns.map((column) => (
                              <td key={column.id} className="h-10 border border-[var(--theme-border)] px-3 py-2" />
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ))}
              <section className="rounded-xl border border-orange-200 bg-orange-50 p-4">
                <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-orange-700">
                  Things Staff Need To Tell {project.student?.case_manager_first_name || "The Case Manager"}
                </h3>
                <div className="mt-3 grid gap-2 text-sm text-orange-950 sm:grid-cols-2">
                  {(project.observation_checklist.length ? project.observation_checklist : ["Other observations"]).map((item, index) => (
                    <label key={`${item}-${index}`} className="flex gap-2">
                      <input type="checkbox" disabled />
                      <span>{item}</span>
                    </label>
                  ))}
                </div>
              </section>
            </div>
          </PacketPage></div>}
        </div>
      </div>

      <footer className="mt-5 flex flex-wrap items-center justify-between gap-3 pb-6">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void autosave.saveImmediately()}>Save Draft</Button>
          <Button onClick={() => void autosave.saveImmediately().then(onComplete)}>Continue to Review</Button>
        </div>
      </footer>
    </div>
  );
}
