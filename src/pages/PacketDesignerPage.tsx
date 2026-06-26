import type { ReactNode } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { WorkflowHeader } from "../components/workflow/WorkflowHeader";
import type { DataSheetDraft, GoalDraft, ProjectDetail, ServiceAreaDraft } from "../types/projects";

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
  readonly onBack: () => void;
  readonly onComplete: () => void;
}

export function PacketDesignerPage({
  project,
  onBack,
  onComplete,
}: PacketDesignerPageProps) {
  const studentName = project.student?.name || "Student";
  const serviceNames = uniqueServiceNames(project.service_areas);
  const goalsByServiceArea = project.service_areas.map((area) => ({
    area,
    goals: project.goals.filter((goal) => goal.service_area_id === area.id),
  }));
  const unassignedGoals = project.goals.filter((goal) => !goal.service_area_id);
  const dataCollectionPages = project.data_sheets.flatMap((sheet) =>
    goalsForSheet(sheet, project.goals).flatMap((goal) =>
      Array.from({ length: sheet.blank_instance_count }).map((_, index) => ({
        sheet,
        goal,
        instance: index + 1,
      })),
    ),
  );
  const outlinePages = [
    { title: "Cover Page", description: "Student and packet overview" },
    { title: "At-a-Glance", description: "Instructional summary" },
    { title: "Accommodations/Modifications", description: "Placeholder for future editor" },
    { title: "Behavior Plans", description: "Placeholder for future editor" },
    { title: "Goal Summary", description: "Full goals grouped by service area" },
    { title: "Service Areas", description: "Services, minutes, and delivery models" },
    ...dataCollectionPages.map(({ sheet, goal, instance }) => ({
      title: `Data Collection - ${goal.title}`,
      description: `${sheet.title}, blank table ${instance} of ${sheet.blank_instance_count}`,
    })),
  ];

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 sm:px-10 lg:px-12">
      <WorkflowHeader
        eyebrow="Step 5 of 6"
        title="Packet Designer"
        description="Review the base packet structure generated from the data already entered. Sprint 4 will handle PDF review and export."
      />

      <div className="grid items-start gap-5 xl:grid-cols-[23rem_1fr]">
        <Card title="Packet outline" description="Pages are generated deterministically from owned project objects.">
          <ol className="space-y-3 text-sm">
            {outlinePages.map((page, index) => (
              <li
                key={`${page.title}-${index}`}
                className="rounded-xl border border-[var(--theme-border)] bg-white p-3"
              >
                <span className="block font-semibold text-[var(--theme-text)]">
                  {index + 1}. {page.title}
                </span>
                <span className="text-xs text-[var(--theme-text-muted)]">
                  {page.description}
                </span>
              </li>
            ))}
          </ol>
        </Card>

        <div className="space-y-5">
          <PacketPage title="Cover Page" description="Uses Student Setup data.">
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
          </PacketPage>

          <PacketPage title="At-a-Glance" description="Instructional summary preview.">
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
          </PacketPage>

          <PacketPage title="Accommodations/Modifications" description="Reserved for future functionality.">
            <p className="text-sm leading-6 text-[var(--theme-text-muted)]">
              This page is part of the base packet structure. Content will be powered by the future accommodations/modifications editor.
            </p>
          </PacketPage>

          <PacketPage title="Behavior Plans" description="Reserved for future functionality.">
            <p className="text-sm leading-6 text-[var(--theme-text-muted)]">
              This page is part of the base packet structure. Behavior plan content will be added alongside the future accommodations/modifications workflow.
            </p>
          </PacketPage>

          <PacketPage title="Goal Summary" description="Full goals grouped under each service area.">
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
          </PacketPage>

          <PacketPage title="Service Areas" description="Includes duplicate service names when delivery differs.">
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
          </PacketPage>

          {dataCollectionPages.map(({ sheet, goal, instance }) => (
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
        <Button onClick={onComplete}>Finish Sprint 3</Button>
      </footer>
    </div>
  );
}
