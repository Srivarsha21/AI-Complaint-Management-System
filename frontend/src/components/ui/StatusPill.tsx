type Tone = "success" | "danger" | "neutral" | "warning" | "info";

const TONES: Record<Tone, string> = {
  success: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  danger: "bg-rose-50 text-rose-700 ring-rose-600/20",
  neutral: "bg-slate-100 text-slate-600 ring-slate-500/20",
  warning: "bg-amber-50 text-amber-800 ring-amber-600/20",
  info: "bg-sky-50 text-sky-700 ring-sky-600/20",
};

const DOTS: Record<Tone, string> = {
  success: "bg-emerald-500",
  danger: "bg-rose-500",
  neutral: "bg-slate-400",
  warning: "bg-amber-500",
  info: "bg-sky-500",
};

export default function StatusPill({ tone, children }: { tone: Tone; children: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${TONES[tone]}`}>
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${DOTS[tone]} ${tone === "success" ? "animate-pulse" : ""}`} />
      {children}
    </span>
  );
}
