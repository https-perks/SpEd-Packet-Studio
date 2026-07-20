import { createContext, useContext, useMemo, type PropsWithChildren } from "react";
import type { TerminologyPreference } from "../types/projects";

export const terminologyOptions = {
  sped: { acronym: "SpEd", fullTitle: "Special Education" },
  ese: { acronym: "ESE", fullTitle: "Exceptional Student Education" },
  ess: { acronym: "ESS", fullTitle: "Exceptional Student Services" },
} as const;

interface TerminologyValue {
  readonly preference: TerminologyPreference;
  readonly acronym: string;
  readonly fullTitle: string;
  readonly productName: string;
  replace: (value: string) => string;
}

const TerminologyContext = createContext<TerminologyValue | null>(null);

export function TerminologyProvider({
  children,
  preference,
}: PropsWithChildren<{ readonly preference: TerminologyPreference }>) {
  const value = useMemo<TerminologyValue>(() => {
    const terms = terminologyOptions[preference];
    return {
      preference,
      ...terms,
      productName: `${terms.acronym} Packet Studio`,
      replace: (text) => text
        .replaceAll("SPECIAL EDUCATION", terms.fullTitle.toUpperCase())
        .replaceAll("Special Education", terms.fullTitle)
        .replaceAll("SpEd", terms.acronym),
    };
  }, [preference]);
  return <TerminologyContext.Provider value={value}>{children}</TerminologyContext.Provider>;
}

export function useTerminology() {
  const value = useContext(TerminologyContext);
  if (!value) throw new Error("useTerminology must be used inside TerminologyProvider");
  return value;
}
