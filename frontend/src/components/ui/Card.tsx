import type { ReactNode } from "react";

export type Accent = "brand" | "violet" | "sky" | "teal" | "amber" | "rose" | "emerald" | "slate";

/** Coloured icon tile + top stripe per accent. */
export const ACCENTS: Record<Accent, { tile: string; stripe: string }> = {
  brand: { tile: "bg-brand-100 text-brand-700", stripe: "from-brand-500 to-accent-violet" },
  violet: { tile: "bg-violet-100 text-violet-700", stripe: "from-violet-500 to-fuchsia-500" },
  sky: { tile: "bg-sky-100 text-sky-700", stripe: "from-sky-500 to-cyan-400" },
  teal: { tile: "bg-teal-100 text-teal-700", stripe: "from-teal-500 to-emerald-400" },
  amber: { tile: "bg-amber-100 text-amber-700", stripe: "from-amber-500 to-orange-400" },
  rose: { tile: "bg-rose-100 text-rose-700", stripe: "from-rose-500 to-pink-500" },
  emerald: { tile: "bg-emerald-100 text-emerald-700", stripe: "from-emerald-500 to-teal-400" },
  slate: { tile: "bg-slate-100 text-slate-700", stripe: "from-slate-400 to-slate-300" },
};

interface CardProps {
  title?: string;
  description?: string;
  children?: ReactNode;
  className?: string;
  /** Optional emoji or icon element shown in a coloured tile next to the title. */
  icon?: ReactNode;
  accent?: Accent;
  /** Lifts on hover; use for clickable cards. */
  interactive?: boolean;
}

export default function Card({ title, description, children, className = "", icon, accent, interactive = false }: CardProps) {
  const colors = accent ? ACCENTS[accent] : null;
  return (
    <section
      className={`relative overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[var(--shadow-soft)] transition-all duration-200 animate-fade-up ${
        interactive ? "hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-[var(--shadow-lift)]" : ""
      } ${className}`}
    >
      {colors && <div aria-hidden className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${colors.stripe}`} />}
      {(title || description || icon) && (
        <div className="flex items-start gap-3">
          {icon && (
            <span aria-hidden className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg ${colors?.tile ?? ACCENTS.brand.tile}`}>
              {icon}
            </span>
          )}
          <div className="min-w-0">
            {title && <h2 className="text-base font-bold text-slate-900">{title}</h2>}
            {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
          </div>
        </div>
      )}
      {children && <div className={title || description || icon ? "mt-4" : ""}>{children}</div>}
    </section>
  );
}
