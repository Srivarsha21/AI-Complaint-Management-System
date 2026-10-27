import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "../../services/api";
import { getDashboardSummary } from "../../services/dashboardService";
import type { DashboardSummary, RecentUpdate } from "../../types/analytics";
import { STATUS_LABELS } from "../../utils/complaintLabels";
import { formatDateTime } from "../../utils/format";
import { StatusBadge } from "../complaints/StatusBadge";
import Alert from "../ui/Alert";
import Card from "../ui/Card";
import Spinner from "../ui/Spinner";

type StatTone = "brand" | "violet" | "sky" | "amber" | "emerald" | "slate" | "rose";

const STAT_TONES: Record<StatTone, { card: string; tile: string; value: string }> = {
  brand: { card: "from-brand-50 to-white border-brand-100", tile: "bg-brand-gradient text-white", value: "text-brand-800" },
  violet: { card: "from-violet-50 to-white border-violet-100", tile: "bg-violet-500 text-white", value: "text-violet-800" },
  sky: { card: "from-sky-50 to-white border-sky-100", tile: "bg-sky-500 text-white", value: "text-sky-800" },
  amber: { card: "from-amber-50 to-white border-amber-100", tile: "bg-amber-500 text-white", value: "text-amber-800" },
  emerald: { card: "from-emerald-50 to-white border-emerald-100", tile: "bg-emerald-500 text-white", value: "text-emerald-800" },
  slate: { card: "from-slate-100 to-white border-slate-200", tile: "bg-slate-600 text-white", value: "text-slate-800" },
  rose: { card: "from-rose-50 to-white border-rose-100", tile: "bg-rose-500 text-white", value: "text-rose-800" },
};

export function StatCard({
  label,
  value,
  hint,
  tone = "brand",
  icon,
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: StatTone;
  icon?: string;
}) {
  const style = STAT_TONES[tone];
  return (
    <div
      data-stat={label}
      className={`relative overflow-hidden rounded-2xl border bg-gradient-to-br p-4 shadow-[var(--shadow-soft)] transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)] animate-fade-up ${style.card}`}
    >
      <div className="flex items-start justify-between gap-2">
        <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
        {icon && (
          <span aria-hidden className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm shadow-sm ${style.tile}`}>
            {icon}
          </span>
        )}
      </div>
      <dd className={`mt-1 text-3xl font-extrabold tracking-tight ${style.value}`}>{value}</dd>
      {hint && <dd className="mt-0.5 text-xs text-slate-500">{hint}</dd>}
    </div>
  );
}

function describeUpdate(update: RecentUpdate): string {
  if (update.from_status === null) return "Complaint submitted";
  return `${STATUS_LABELS[update.from_status]} → ${STATUS_LABELS[update.to_status]}`;
}

/** The signed-in user's own complaint counts and latest status changes. */
export default function UserStats() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboardSummary()
      .then(setSummary)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  if (error) return <Alert tone="error">Could not load your statistics: {error}</Alert>;
  if (!summary) return <Spinner label="Loading your statistics" />;

  const { by_status: s } = summary;
  return (
    <div className="space-y-6">
      <section aria-labelledby="my-stats-heading">
        <h2 id="my-stats-heading" className="sr-only">
          Your complaint statistics
        </h2>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Total filed" value={summary.total} tone="brand" icon="📋" />
          <StatCard label="Pending" value={summary.pending} hint={`${s.submitted} submitted · ${s.assigned} assigned`} tone="violet" icon="⏳" />
          <StatCard label="In progress" value={s.in_progress} tone="amber" icon="🛠️" />
          <StatCard label="Resolved" value={s.resolved} tone="emerald" icon="✅" />
          <StatCard label="Closed" value={s.closed} tone="slate" icon="🔒" />
        </dl>
      </section>

      <Card title="Recent updates" description="The latest status changes on your complaints.">
        {summary.recent_updates.length === 0 ? (
          <p className="text-sm text-slate-500">No updates yet. Changes to your complaints will appear here.</p>
        ) : (
          <ul className="-mx-2 divide-y divide-slate-100">
            {summary.recent_updates.map((u, index) => (
              <li key={`${u.complaint_id}-${u.at}-${index}`}>
                <Link
                  to={`/app/complaints/${u.complaint_id}`}
                  className="flex flex-col gap-1 rounded-lg px-2 py-3 hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between sm:gap-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">{u.subject}</p>
                    <p className="text-xs text-slate-500">
                      <span className="font-mono">{u.reference_number}</span> · {describeUpdate(u)} · {formatDateTime(u.at)}
                    </p>
                    {u.note && <p className="mt-1 line-clamp-2 text-xs text-slate-600">“{u.note}”</p>}
                  </div>
                  <StatusBadge status={u.to_status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
