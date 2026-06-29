import { useCallback, useState } from "react";
import { AppShell } from "./layouts/AppShell";
import { AtAGlancePage } from "./pages/AtAGlancePage";
import { DashboardPage } from "./pages/DashboardPage";
import { DataSheetBuilderPage } from "./pages/DataSheetBuilderPage";
import { GoalBuilderPage } from "./pages/GoalBuilderPage";
import { ObservationSheetsPage } from "./pages/ObservationSheetsPage";
import { PacketDesignerPage } from "./pages/PacketDesignerPage";
import { ReviewExportPage } from "./pages/ReviewExportPage";
import { StudentSetupPage } from "./pages/StudentSetupPage";
import { getProject } from "./services/api/projects";
import type { AppScreen } from "./types/navigation";
import type { ProjectDetail, ProjectSummary } from "./types/projects";

function stepToScreen(step: ProjectSummary["current_step"]): AppScreen {
  if (step === "complete") return "review";
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
      if (target === "at_a_glance") {
        if (!project.student_setup_validation.is_complete) {
          setScreen("student_setup");
          return;
        }
      }
      if (target === "goals") {
        if (!project.student_setup_validation.is_complete) {
          setScreen("student_setup");
          return;
        }
        if (!project.at_a_glance_validation.is_complete) {
          setScreen("at_a_glance");
          return;
        }
      }
      if (target === "data_sheets") {
        if (!project.student_setup_validation.is_complete) {
          setScreen("student_setup");
          return;
        }
        if (!project.at_a_glance_validation.is_complete) {
          setScreen("at_a_glance");
          return;
        }
        if (!project.goals_validation.is_complete) {
          setScreen("goals");
          return;
        }
      }
      if (target === "observation_sheets" || target === "packet_designer") {
        if (!project.student_setup_validation.is_complete) {
          setScreen("student_setup");
          return;
        }
        if (!project.at_a_glance_validation.is_complete) {
          setScreen("at_a_glance");
          return;
        }
        if (!project.goals_validation.is_complete) {
          setScreen("goals");
          return;
        }
        if (!project.data_sheets_validation.is_complete) {
          setScreen("data_sheets");
          return;
        }
      }
      if (target === "review") {
        if (!project.student_setup_validation.is_complete) {
          setScreen("student_setup");
          return;
        }
        if (!project.at_a_glance_validation.is_complete) {
          setScreen("at_a_glance");
          return;
        }
        if (!project.goals_validation.is_complete) {
          setScreen("goals");
          return;
        }
        if (!project.data_sheets_validation.is_complete) {
          setScreen("data_sheets");
          return;
        }
      }
      setScreen(target);
    },
    [project],
  );

  function markExported() {
    setNotice(
      "Packet export generated successfully.",
    );
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
        onContinue={() => setScreen("at_a_glance")}
      />
    );
  } else if (screen === "at_a_glance") {
    content = (
      <AtAGlancePage
        key={`${project.id}-glance`}
        project={project}
        onProjectUpdate={setProject}
        onBack={() => setScreen("student_setup")}
        onComplete={() => setScreen("goals")}
      />
    );
  } else if (screen === "goals") {
    content = (
      <GoalBuilderPage
        key={`${project.id}-goals`}
        project={project}
        onProjectUpdate={setProject}
        onBack={() => setScreen("at_a_glance")}
        onContinue={() => setScreen("data_sheets")}
      />
    );
  } else if (screen === "data_sheets") {
    content = (
      <DataSheetBuilderPage
        key={`${project.id}-data-sheets`}
        project={project}
        onProjectUpdate={setProject}
        onBack={() => setScreen("at_a_glance")}
        onComplete={() => setScreen("observation_sheets")}
      />
    );
  } else if (screen === "observation_sheets") {
    content = (
      <ObservationSheetsPage
        key={`${project.id}-observation-sheets`}
        project={project}
        onProjectUpdate={setProject}
        onBack={() => setScreen("data_sheets")}
        onComplete={() => setScreen("packet_designer")}
      />
    );
  } else if (screen === "packet_designer") {
    content = (
      <PacketDesignerPage
        key={`${project.id}-packet-designer`}
        project={project}
        onProjectUpdate={setProject}
        onBack={() => setScreen("observation_sheets")}
        onComplete={() => setScreen("review")}
      />
    );
  } else {
    content = (
      <ReviewExportPage
        key={`${project.id}-review-export`}
        project={project}
        onProjectUpdate={setProject}
        onBack={() => setScreen("packet_designer")}
        onComplete={markExported}
      />
    );
  }

  return (
    <AppShell activeScreen={screen} hasProject={project !== null} onNavigate={navigate}>
      {content}
    </AppShell>
  );
}
