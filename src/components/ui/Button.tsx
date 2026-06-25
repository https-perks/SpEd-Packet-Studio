import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

type Variant = "primary" | "secondary" | "outline" | "text" | "danger";

const variants: Record<Variant, string> = {
  primary:
    "bg-[var(--theme-primary)] text-white hover:opacity-90",
  secondary:
    "bg-[var(--theme-accent)] text-white hover:opacity-90",
  outline:
    "border border-[var(--theme-border)] bg-[var(--theme-surface)] text-[var(--theme-text)] hover:bg-[var(--theme-surface-muted)]",
  text: "text-[var(--theme-primary)] hover:bg-[var(--theme-primary-soft)]",
  danger: "bg-red-50 text-red-800 hover:bg-red-100",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: Variant;
}

export function Button({
  children,
  className = "",
  variant = "primary",
  type = "button",
  ...props
}: PropsWithChildren<ButtonProps>) {
  return (
    <button
      type={type}
      className={`inline-flex min-h-10 items-center justify-center rounded-xl px-4 py-2 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-[var(--theme-accent)] disabled:cursor-not-allowed disabled:opacity-45 ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
