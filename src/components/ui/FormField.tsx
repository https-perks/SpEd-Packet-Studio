import type { InputHTMLAttributes, PropsWithChildren, TextareaHTMLAttributes } from "react";

interface FieldFrameProps {
  readonly label: string;
  readonly htmlFor: string;
  readonly hint?: string;
  readonly error?: string;
  readonly required?: boolean;
}

export function FieldFrame({
  label,
  htmlFor,
  hint,
  error,
  required,
  children,
}: PropsWithChildren<FieldFrameProps>) {
  return (
    <div>
      <label className="text-sm font-semibold text-[var(--theme-text)]" htmlFor={htmlFor}>
        {label}
        {required && <span className="ml-1 text-[var(--theme-error)]">*</span>}
      </label>
      {hint && <p className="mt-1 text-xs text-[var(--theme-text-muted)]">{hint}</p>}
      <div className="mt-2">{children}</div>
      {error && <p className="mt-1.5 text-xs font-medium text-[var(--theme-error)]">{error}</p>}
    </div>
  );
}

const controlClass =
  "w-full rounded-xl border border-[var(--theme-border)] bg-white px-3.5 py-2.5 text-sm text-[var(--theme-text)] shadow-sm outline-none transition placeholder:text-slate-400 focus:border-[var(--theme-primary)] focus:ring-2 focus:ring-[var(--theme-primary-soft)]";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const { className = "", ...rest } = props;
  return <input {...rest} className={`${controlClass} ${className}`} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { className = "", ...rest } = props;
  return (
    <textarea
      {...rest}
      className={`${controlClass} min-h-28 resize-y ${className}`}
    />
  );
}

export const selectClass = controlClass;
