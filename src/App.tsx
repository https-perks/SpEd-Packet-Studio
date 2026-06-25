import { useCallback, useState } from "react";
import { AppShell } from "./layouts/AppShell";
import { AtAGlancePage } from "./pages/AtAGlancePage";
import { DashboardPage } from "./pages/DashboardPage";
import { GoalBuilderPage } from "./pages/GoalBuilderPage";
import { StudentSetupPage } from "./pages/StudentSetupPage";
import { getProject } from "./services/api/projects";
import type { AppScreen } from "./types/navigation";
import type { ProjectDetail, ProjectSummary } from "./types/projects";

function stepToScreen(step: ProjectSummary["current_step"]): AppScreen {
  if (step === "complete") return "at_a_glance";
  return step;
}

export function App() {
  const [screen, setScreen] = useState<AppScreen>("dashboard");
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const openProject = useCallback(async (value: ProjectSummary | ProjectDetail) => {
    setLoading(true);
    setError("");
    try {
      const detail = "student" in value ? value : await getProject(value.id);
      setProject(detail);
      setScreen("current_step" in value ? stepToScreen(value.current_step) : "student_setup");
      setNotice("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Project could not be opened.");
    } finally {
      setLoading(false);
    }
  }, []);

  const navigate = useCallback(
    (target: AppScreen) => {
      if (target === "dashboard") {
        setScreen(target);
        return;
      }
      if (!project) return;
      if (target === "goals" && !project.student_setup_validation.is_complete) {
        setScreen("student_setup");
        return;
      }
      if (target === "at_a_glance") {
        if (!project.student_setup_validation.is_complete) {
          setScreen("student_setup");
          return;
        }
        if (!project.goals_validation.is_complete) {
          setScreen("goals");
          return;
        }
      }
      setScreen(target);
    },
    [project],
  );

  function finishSprintOne() {
    setNotice(
      "Sprint 1 is complete for this project. Data Sheet Builder will become available in Sprint 2.",
    );
    setScreen("dashboard");
  }

  let content;
  if (loading) {
    content = (
      <div className="grid min-h-screen place-items-center text-sm text-[var(--theme-text-muted)]">
        Opening project...
      </div>
    );
  } else if (screen === "dashboard" || !project) {
    content = (
      <>
        {error && (
          <div className="mx-auto mt-6 max-w-7xl rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
            {error}
          </div>
        )}
        <DashboardPage notice={notice} onOpen={(value) => void openProject(value)} />
      </>
    );
  } else if (screen === "student_setup") {
    content = (
      <StudentSetupPage
        key={`${project.id}-student`}
        project={project}
        onProjectUpdate={setProject}
        onBack={() => setScreen("dashboard")}
        onContinue={() => setScreen("goals")}
      />
    );
  } else if (screen === "goals") {
    content = (
      <GoalBuilderPage
        key={`${project.id}-goals`}
        project={project}
        onProjectUpdate={setProject}
        onBack={() => setScreen("student_setup")}
        onContinue={() => setScreen("at_a_glance")}
      />
    );
  } else {
    content = (
      <AtAGlancePage
        key={`${project.id}-glance`}
        project={project}
        onProjectUpdate={setProject}
        onBack={() => setScreen("goals")}
        onComplete={finishSprintOne}
      />
    );
  }

  return (
    <AppShell activeScreen={screen} hasProject={project !== null} onNavigate={navigate}>
      {content}
    </AppShell>
  );
}
