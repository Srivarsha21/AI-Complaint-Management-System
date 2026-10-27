import { useId, type InputHTMLAttributes } from "react";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string | null;
  hint?: string;
}

export default function TextField({ label, error, hint, className = "", ...inputProps }: TextFieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;

  return (
    <div className={className}>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={`mt-1 block w-full rounded-xl border bg-white px-3 py-2.5 text-sm shadow-sm transition placeholder:text-slate-400 hover:border-slate-400 focus:outline-none focus:ring-4 disabled:bg-slate-50 disabled:text-slate-500 ${
          error ? "border-rose-400 focus:ring-rose-100" : "border-slate-300 focus:border-brand-500 focus:ring-brand-100"
        }`}
        {...inputProps}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-xs font-medium text-rose-600 animate-fade-in">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">
            {hint}
          </p>
        )
      )}
    </div>
  );
}
