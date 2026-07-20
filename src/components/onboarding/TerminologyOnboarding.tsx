import { useState } from "react";
import { Button } from "../ui/Button";
import { terminologyOptions } from "../../terminology/TerminologyProvider";
import type { TerminologyPreference } from "../../types/projects";

interface TerminologyOnboardingProps {
  readonly saving: boolean;
  readonly error: string;
  readonly onContinue: (preference: TerminologyPreference) => void;
}

export function TerminologyOnboarding({ saving, error, onContinue }: TerminologyOnboardingProps) {
  const [selected, setSelected] = useState<TerminologyPreference | null>(null);
  return (
    <div className="fixed inset-0 z-[100] grid place-items-center bg-slate-950/70 p-6">
      <section aria-labelledby="terminology-title" className="w-full max-w-2xl rounded-3xl bg-white p-8 shadow-2xl">
        <p className="text-xs font-bold uppercase tracking-[0.24em] text-[var(--theme-accent)]">Welcome to Packet Studio</p>
        <h1 id="terminology-title" className="mt-3 text-3xl font-semibold text-[var(--theme-primary)]">Which abbreviation does the district use?</h1>
        <p className="mt-3 text-sm leading-6 text-[var(--theme-text-muted)]">Your choice changes the product name and terminology shown throughout the app and generated packets. You can change it later in Application Settings.</p>
        <fieldset className="mt-6 grid gap-3">
          <legend className="sr-only">District terminology</legend>
          {(Object.entries(terminologyOptions) as [TerminologyPreference, (typeof terminologyOptions)[TerminologyPreference]][]).map(([key, option]) => (
            <label key={key} className={`flex cursor-pointer items-center gap-4 rounded-2xl border p-4 transition ${selected === key ? "border-[var(--theme-primary)] bg-[var(--theme-primary-soft)]" : "border-[var(--theme-border)] hover:bg-[var(--theme-surface-muted)]"}`}>
              <input type="radio" name="terminology" value={key} checked={selected === key} onChange={() => setSelected(key)} />
              <span><strong className="text-[var(--theme-primary)]">{option.acronym}</strong><span className="mx-2 text-[var(--theme-text-muted)]">-</span><span className="text-[var(--theme-text)]">{option.fullTitle}</span></span>
            </label>
          ))}
        </fieldset>
        {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</p>}
        <div className="mt-7 flex justify-end"><Button disabled={!selected || saving} onClick={() => selected && onContinue(selected)}>{saving ? "Saving..." : "Continue"}</Button></div>
      </section>
    </div>
  );
}
