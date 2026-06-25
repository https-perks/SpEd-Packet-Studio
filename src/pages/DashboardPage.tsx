import { useCallback, useEffect, useState } from "react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { TextInput } from "../components/ui/FormField";
import {
  archiveProject,
  createProject,
  duplicateProject,
  listProjects,
  restoreProject,
} from "../services/api/projects";
import type { ProjectDetail, ProjectSummary } from "../types/projects";

const stepLabels = {
  student_setup: "Student Setup",
  goals: "Goal Builder",
  at_a_glance: "At-a-Glance",
  complete: "Sprint 1 complete",
} as const;

interface DashboardPageProps {
  readonly notice?: string;
  readonly onOpen: (project: ProjectSummary | ProjectDetail) => void;
}

export function DashboardPage({ notice, onOpen }: DashboardPageProps) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [search, setSearch] = useState("");
  const [archived, setArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setProjects(await listProjects({ archived, search }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Projects could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [archived, search]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 220);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function handleCreate() {
    setError("");
    try {
      onOpen(await createProject());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Project could not be created.");
    }
  }

  async function handleDuplicate(projectId: string) {
    setError("");
    try {
      onOpen(await duplicateProject(projectId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Project could not be duplicated.");
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
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--theme-accent)]">
                      {stepLabels[project.current_step]}
                    </p>
                    <h2 className="mt-2 text-xl font-semibold text-[var(--theme-text)]">
                      {project.name}
                    </h2>
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
                <div className="mt-auto flex flex-wrap gap-2 pt-6">
                  <Button onClick={() => onOpen(project)}>
                    {project.current_step === "student_setup" ? "Start setup" : "Continue"}
                  </Button>
                  {!archived && (
                    <Button variant="outline" onClick={() => void handleDuplicate(project.id)}>
                      Duplicate
                    </Button>
                  )}
                  <Button variant="text" onClick={() => void handleArchive(project.id)}>
                    {archived ? "Restore" : "Archive"}
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <Card title="Templates" description="Reusable project templates are planned for a later Version 1 sprint.">
          <p className="text-sm text-[var(--theme-text-muted)]">
            Sprint 1 projects begin with a clean, structured student record.
          </p>
        </Card>
        <Card title="Application settings" description="The local-first foundation is active.">
          <p className="text-sm text-[var(--theme-text-muted)]">
            Projects autosave to the local SQLite database and remain on this computer.
          </p>
        </Card>
      </div>
    </div>
  );
}
