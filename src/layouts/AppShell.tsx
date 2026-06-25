import type { PropsWithChildren } from "react";
import { navigationItems } from "../navigation/navigation";
import type { AppScreen } from "../types/navigation";

interface AppShellProps {
  readonly activeScreen: AppScreen;
  readonly hasProject: boolean;
  readonly onNavigate: (screen: AppScreen) => void;
}

export function AppShell({
  children,
  activeScreen,
  hasProject,
  onNavigate,
}: PropsWithChildren<AppShellProps>) {
  return <div className="min-h-screen bg-[var(--theme-background)] lg:grid lg:grid-cols-[17rem_1fr]">
    <aside className="border-b border-[var(--theme-border)] bg-[var(--theme-primary)] px-6 py-6 text-white lg:min-h-screen lg:border-r lg:border-b-0">
      <div className="flex items-center gap-3">
        <div aria-hidden="true" className="grid size-11 place-items-center rounded-2xl bg-white/12 text-xl font-semibold">S</div>
        <div><p className="text-sm font-semibold tracking-wide">SpEd Packet Studio</p><p className="text-xs text-white/60">Publishing, thoughtfully built</p></div>
      </div>
      <nav aria-label="Primary navigation" className="mt-8"><ul className="flex gap-2 overflow-x-auto lg:flex-col">
        {navigationItems.map((item) => {
          const available = item.enabled && (!item.requiresProject || hasProject);
          const current = item.id === activeScreen;
          return <li key={item.id}><button type="button" disabled={!available} aria-current={current ? "page" : undefined}
          onClick={() => available && onNavigate(item.id as AppScreen)}
          className={["w-full rounded-xl px-4 py-3 text-left text-sm transition", current ? "bg-white text-[var(--theme-primary)] shadow-sm" : "text-white/55", available ? "hover:bg-white/10" : "cursor-not-allowed"].join(" ")}>
          <span className="block font-medium">{item.label}</span><span className="mt-0.5 block text-xs opacity-65">{item.description}</span>
        </button></li>;
        })}
      </ul></nav>
      <p className="mt-8 hidden text-xs leading-5 text-white/50 lg:block">Enter educational information once. Publish it everywhere.</p>
    </aside>
    <main className="min-w-0">{children}</main>
  </div>;
}
