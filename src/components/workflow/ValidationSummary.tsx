import type { StepValidation } from "../../types/projects";

export function ValidationSummary({
  validation,
  completeMessage = "This step is complete.",
}: {
  readonly validation: StepValidation;
  readonly completeMessage?: string;
}) {
  if (validation.is_complete) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
        {completeMessage}
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
      <p className="text-sm font-semibold text-amber-950">Before continuing</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-900">
        {validation.issues.map((issue) => (
          <li key={`${issue.field}-${issue.message}`}>{issue.message}</li>
        ))}
      </ul>
    </div>
  );
}
