import type { AutosaveStatus } from "../../hooks/useAutosave";

const labels: Record<AutosaveStatus, string> = {
  idle: "Draft ready",
  pending: "Changes pending",
  saving: "Saving...",
  saved: "All changes saved",
  error: "Save failed",
};

export function SaveStatus({ status }: { readonly status: AutosaveStatus }) {
  const color =
    status === "error"
      ? "text-[var(--theme-error)]"
      : status === "saved"
        ? "text-[var(--theme-success)]"
        : "text-[var(--theme-text-muted)]";
  return (
    <span className={`inline-flex items-center gap-2 text-xs font-semibold ${color}`}>
      <span className="size-2 rounded-full bg-current" />
      {labels[status]}
    </span>
  );
}
