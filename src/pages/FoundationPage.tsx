import { StatusBadge } from "../components/system/StatusBadge";
import { SystemCard } from "../components/system/SystemCard";
import { useSystemHealth } from "../hooks/useSystemHealth";
export function FoundationPage() { const health = useSystemHealth(); return <div className="mx-auto max-w-6xl px-6 py-10 sm:px-10 lg:px-12 lg:py-14">
  <header className="max-w-3xl"><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--theme-accent)]">Sprint 0</p><h1 className="mt-3 text-4xl font-semibold tracking-tight text-[var(--theme-primary)] sm:text-5xl">The studio foundation is in place.</h1><p className="mt-5 text-base leading-7 text-[var(--theme-text-muted)] sm:text-lg">The desktop shell, presentation layer, local API, database, and PDF engine are separated into clear, reusable layers and ready for future feature development.</p></header>
  <section aria-labelledby="system-status" className="mt-10"><div className="flex items-center justify-between gap-4"><h2 id="system-status" className="text-xl font-semibold text-[var(--theme-text)]">System status</h2><StatusBadge status={health.status} /></div>
    <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <SystemCard eyebrow="Desktop" title="Tauri shell" detail="Native application window and secure boundary for local services." />
      <SystemCard eyebrow="Presentation" title="React + TypeScript" detail="Reusable, theme-aware components with no business or persistence logic." />
      <SystemCard eyebrow="Business layer" title="FastAPI" detail={health.data ? `${health.data.service} API ${health.data.api_version} is responding locally.` : "The local API owns application rules and coordinates persistence."} status={<StatusBadge status={health.status} />} />
      <SystemCard eyebrow="Persistence" title="SQLAlchemy + SQLite" detail={health.data ? `Schema ${health.data.database.schema_version} is ready.` : "A normalized object model provides one authoritative owner for every record."} />
      <SystemCard eyebrow="Publishing" title="WeasyPrint" detail="The deterministic export boundary is reserved without implementing packet generation." />
      <SystemCard eyebrow="Scope" title="Features intentionally paused" detail="Student Setup and all application workflows begin after the Sprint 0 foundation." />
    </div>
  </section>
</div>; }
