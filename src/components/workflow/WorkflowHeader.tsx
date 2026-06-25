import type { ReactNode } from "react";
import { SaveStatus } from "./SaveStatus";
import type { AutosaveStatus } from "../../hooks/useAutosave";

export function WorkflowHeader({
  eyebrow,
  title,
  description,
  status,
  actions,
}: {
  readonly eyebrow: string;
  readonly title: string;
  readonly description: string;
  readonly status?: AutosaveStatus;
  readonly actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-5">
      <div className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--theme-accent)]">
          {eyebrow}
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--theme-primary)] sm:text-4xl">
          {title}
        </h1>
        <p className="mt-3 text-sm leading-6 text-[var(--theme-text-muted)] sm:text-base">
          {description}
        </p>
      </div>
      <div className="flex items-center gap-4">
        {status && <SaveStatus status={status} />}
        {actions}
      </div>
    </header>
  );
}
