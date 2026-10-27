import type { ReactNode } from "react";

type Tone = "error" | "success" | "info" | "warning";

const TONES: Record<Tone, { box: string; icon: string; symbol: string }> = {
  error: { box: "border-rose-200 bg-rose-50 text-rose-800", icon: "bg-rose-500", symbol: "!" },
  success: { box: "border-emerald-200 bg-emerald-50 text-emerald-800", icon: "bg-emerald-500", symbol: "✓" },
  info: { box: "border-brand-200 bg-brand-50 text-brand-900", icon: "bg-brand-500", symbol: "i" },
  warning: { box: "border-amber-200 bg-amber-50 text-amber-900", icon: "bg-amber-500", symbol: "!" },
};

export default function Alert({ tone, children }: { tone: Tone; children: ReactNode }) {
  const style = TONES[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`flex gap-3 rounded-xl border p-3 text-sm animate-fade-in ${style.box}`}>
      <span aria-hidden className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${style.icon}`}>
        {style.symbol}
      </span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
