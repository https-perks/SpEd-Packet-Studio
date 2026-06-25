import type { ServiceStatus } from "../../types/system";
const styles: Record<ServiceStatus, string> = { checking: "bg-[var(--theme-surface-muted)] text-[var(--theme-text-muted)]", ready: "bg-emerald-50 text-emerald-800", unavailable: "bg-red-50 text-red-800" };
const labels: Record<ServiceStatus, string> = { checking: "Checking", ready: "Ready", unavailable: "Unavailable" };
export function StatusBadge({ status }: { readonly status: ServiceStatus }) { return <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${styles[status]}`}><span className="size-1.5 rounded-full bg-current" aria-hidden="true" />{labels[status]}</span>; }
