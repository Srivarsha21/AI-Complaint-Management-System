import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-brand-gradient text-white shadow-[var(--shadow-soft)] hover:shadow-[var(--shadow-lift)] hover:brightness-110 disabled:opacity-60 disabled:shadow-none",
  secondary: "border border-slate-200 bg-white text-slate-700 shadow-sm hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  danger: "bg-rose-600 text-white shadow-sm hover:bg-rose-700 disabled:opacity-60",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export default function Button({ variant = "primary", className = "", type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all duration-200 active:scale-[0.97] disabled:cursor-not-allowed disabled:active:scale-100 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
