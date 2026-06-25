import type { PropsWithChildren, ReactNode } from "react";

interface CardProps {
  readonly title?: string;
  readonly description?: string;
  readonly actions?: ReactNode;
  readonly className?: string;
}

export function Card({
  title,
  description,
  actions,
  children,
  className = "",
}: PropsWithChildren<CardProps>) {
  return (
    <section
      className={`rounded-[var(--theme-radius)] border border-[var(--theme-border)] bg-[var(--theme-surface)] p-5 shadow-[var(--theme-shadow)] ${className}`}
    >
      {(title || description || actions) && (
        <header className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            {title && (
              <h2 className="text-lg font-semibold text-[var(--theme-text)]">{title}</h2>
            )}
            {description && (
              <p className="mt-1 text-sm leading-6 text-[var(--theme-text-muted)]">
                {description}
              </p>
            )}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
