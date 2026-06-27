import { useEffect, useState, type ReactNode } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FieldFrame, selectClass } from "../components/ui/FormField";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import { useAutosave } from "../hooks/useAutosave";
import { savePacketBuilder } from "../services/api/projects";
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

function deliveryLabel(value: string | null) {
  if (!value) return "Not selected";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
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
  const [draggedPageIndex, setDraggedPageIndex] = useState<number | null>(null);
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

  useEffect(() => {
    if (draggedPageIndex === null) return;
    const stopDragging = () => setDraggedPageIndex(null);
    window.addEventListener("pointerup", stopDragging);
    window.addEventListener("pointercancel", stopDragging);
    return () => {
      window.removeEventListener("pointerup", stopDragging);
      window.removeEventListener("pointercancel", stopDragging);
    };
  }, [draggedPageIndex]);

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

  function moveDraggedPage(targetIndex: number) {
    if (draggedPageIndex === null || draggedPageIndex === targetIndex) return;
    movePage(draggedPageIndex, targetIndex);
    setDraggedPageIndex(targetIndex);
  }

  const studentName = project.student?.name || "Student";
  const serviceNames = uniqueServiceNames(project.service_areas);
  const goalsByServiceArea = project.service_areas.map((area) => ({
    area,
    goals: project.goals.filter((goal) => goal.service_area_id === area.id),
  }));
  const unassignedGoals = project.goals.filter((goal) => !goal.service_area_id);
  const dataCollectionPages = project.data_sheets.flatMap((sheet) =>
    sheet.is_observation_form ? [] :
    goalsForSheet(sheet, project.goals).flatMap((goal) =>
      Array.from({ length: sheet.blank_instance_count }).map((_, index) => ({
        sheet,
        goal,
        instance: index + 1,
      })),
    ),
  );
  const enabledPageIds = new Set(selectedConfig?.pages.filter((page) => page.enabled).map((page) => page.id) ?? []);
  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 6 of 7"
        title="Packet Designer"
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
            {selectedConfig?.pages.map((page, index) => (
              <div
                key={page.id}
                onPointerEnter={() => moveDraggedPage(index)}
                onDragOver={(event) => {
                  event.preventDefault();
                  event.dataTransfer.dropEffect = "move";
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  const source = Number(event.dataTransfer.getData("text/plain"));
                  const from = Number.isNaN(source) ? draggedPageIndex : source;
                  if (from !== null) movePage(from, index);
                  setDraggedPageIndex(null);
                }}
                className={`rounded-xl border bg-white p-3 ${draggedPageIndex === index ? "border-[var(--theme-primary)] opacity-70" : "border-[var(--theme-border)]"}`}
              >
                <div className="flex items-start gap-3">
                  <button
                    type="button"
                    aria-label={`Drag ${page.title}`}
                    title="Hold and drag to reorder"
                    onPointerDown={(event) => {
                      event.preventDefault();
                      setDraggedPageIndex(index);
                    }}
                    onPointerUp={() => setDraggedPageIndex(null)}
                    className="mt-0.5 cursor-grab select-none rounded-lg border border-[var(--theme-border)] px-2 py-1 text-xs font-semibold text-[var(--theme-text-muted)] active:cursor-grabbing"
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
                      {index + 1}. {page.title}
                    </span>
                    <span className="text-xs text-[var(--theme-text-muted)]">
                      Hold Drag and move over another row, or use Up/Down
                    </span>
                  </span>
                </div>
                <div className="mt-2 flex gap-1">
                  <Button variant="text" disabled={index === 0} onClick={() => movePage(index, index - 1)}>Up</Button>
                  <Button variant="text" disabled={index === selectedConfig.pages.length - 1} onClick={() => movePage(index, index + 1)}>Down</Button>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <div className="space-y-5">
          {enabledPageIds.has("cover") && <PacketPage title="Cover Page" description="Uses Student Setup data.">
            <div className="border-b border-[var(--theme-border)] pb-6">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--theme-accent)]">
                Special Education Service Packet
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
          </PacketPage>}

          {enabledPageIds.has("at_a_glance") && <PacketPage title="At-a-Glance" description="Instructional summary preview.">
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
          </PacketPage>}

          {enabledPageIds.has("accommodations") && <PacketPage title="Accommodations/Modifications" description="Reserved for future functionality.">
            <p className="text-sm leading-6 text-[var(--theme-text-muted)]">
              This page is part of the base packet structure. Content will be powered by the future accommodations/modifications editor.
            </p>
          </PacketPage>}

          {enabledPageIds.has("behavior") && <PacketPage title="Behavior Plans" description="Reserved for future functionality.">
            <p className="text-sm leading-6 text-[var(--theme-text-muted)]">
              This page is part of the base packet structure. Behavior plan content will be added alongside the future accommodations/modifications workflow.
            </p>
          </PacketPage>}

          {enabledPageIds.has("goal_summary") && <PacketPage title="Goal Summary" description="Full goals grouped under each service area.">
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
          </PacketPage>}

          {enabledPageIds.has("services") && <PacketPage title="Service Areas" description="Includes duplicate service names when delivery differs.">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr>
                    <th className="border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] px-3 py-2 text-left font-semibold">Service</th>
                    <th className="border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] px-3 py-2 text-left font-semibold">Minutes per week</th>
                    <th className="border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] px-3 py-2 text-left font-semibold">Delivery</th>
                    <th className="border border-[var(--theme-border)] bg-[var(--theme-surface-muted)] px-3 py-2 text-left font-semibold">Setting</th>
                  </tr>
                </thead>
                <tbody>
                  {project.service_areas.map((area) => (
                    <tr key={area.id}>
                      <td className="border border-[var(--theme-border)] px-3 py-2">{area.name}</td>
                      <td className="border border-[var(--theme-border)] px-3 py-2">{area.minutes_per_week ?? "Not entered"}</td>
                      <td className="border border-[var(--theme-border)] px-3 py-2">{deliveryLabel(area.delivery_model)}</td>
                      <td className="border border-[var(--theme-border)] px-3 py-2">{area.setting || "Not entered"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </PacketPage>}

          {enabledPageIds.has("data_collection") && dataCollectionPages.map(({ sheet, goal, instance }) => (
            <PacketPage
              key={`${sheet.id ?? sheet.title}-${goal.id}-${instance}`}
              title={`Data Collection - ${goal.title}`}
              description={`${sheet.title}, blank table ${instance} of ${sheet.blank_instance_count}`}
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
          ))}
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
