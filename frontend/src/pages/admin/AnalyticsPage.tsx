import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PriorityBadge, StatusBadge } from "../../components/complaints/StatusBadge";
import ChartCard from "../../components/dashboard/ChartCard";
import ComplaintFilterBar, { EMPTY_FILTERS, validateFilters } from "../../components/dashboard/ComplaintFilterBar";
import { StatCard } from "../../components/dashboard/UserStats";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import { getErrorMessage } from "../../services/api";
import { listCategories } from "../../services/complaintService";
import { getAnalytics } from "../../services/dashboardService";
import type { Analytics, NamedCount, PriorityKey, ReportFilters } from "../../types/analytics";
import type { Category } from "../../types/complaint";
import { PRIORITY_LABELS, STATUS_LABELS } from "../../utils/complaintLabels";
import { formatDateTime, formatHours, formatShortDate } from "../../utils/format";

const PRIORITY_KEY_LABELS: Record<PriorityKey, string> = { ...PRIORITY_LABELS, not_assessed: "Not assessed" };
const PRIORITY_COLORS: Record<PriorityKey, string> = {
  low: "#64748b",
  medium: "#d97706",
  high: "#ea580c",
  critical: "#dc2626",
  not_assessed: "#cbd5e1",
};
const STATUS_COLORS = ["#64748b", "#0284c7", "#d97706", "#059669", "#1e293b"];
const BRAND = "#4f46e5";
const RESOLVED = "#059669";

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function rankingSummary(items: NamedCount[], total: number, noun: string, nounPlural: string): string {
  if (items.length === 0) return `No ${noun} data.`;
  const top = items[0];
  return `${top.name} has the most complaints (${top.count} of ${total}). ${items.length} ${items.length === 1 ? noun : nounPlural} in these results.`;
}

/** Axis labels must fit on one line; full names stay in the tooltip and the data table. */
function shortLabel(name: string): string {
  const trimmed = name.replace(/ Department$/, "").replace(/ & Illegal Construction$/, "");
  return trimmed.length > 22 ? `${trimmed.slice(0, 21)}…` : trimmed;
}

/** Recharts wraps category ticks by default; this renders each label as a single line. */
function SingleLineTick({ x = 0, y = 0, payload }: { x?: number; y?: number; payload?: { value: string } }) {
  return (
    <text x={x} y={y} dy={4} textAnchor="end" fontSize={11} fill="#475569">
      <title>{payload?.value}</title>
      {shortLabel(payload?.value ?? "")}
    </text>
  );
}

function HorizontalBars({ data, color }: { data: NamedCount[]; color: string }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 32, bottom: 4, left: 4 }}>
        <CartesianGrid horizontal={false} stroke="#e2e8f0" />
        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
        <YAxis type="category" dataKey="name" width={150} tick={<SingleLineTick />} interval={0} />
        <Tooltip />
        <Bar dataKey="count" name="Complaints" fill={color} radius={[0, 4, 4, 0]}>
          <LabelList dataKey="count" position="right" className="fill-slate-700 text-xs" />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ColumnBars({ data }: { data: { label: string; count: number; color: string }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 20, right: 8, bottom: 4, left: -16 }}>
        <CartesianGrid vertical={false} stroke="#e2e8f0" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} />
        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
        <Tooltip />
        <Bar dataKey="count" name="Complaints" radius={[4, 4, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.label} fill={d.color} stroke="#334155" strokeWidth={0.5} />
          ))}
          <LabelList dataKey="count" position="top" className="fill-slate-700 text-xs" />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function AnalyticsPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [draft, setDraft] = useState<ReportFilters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<ReportFilters>(EMPTY_FILTERS);
  const [filterError, setFilterError] = useState<string | null>(null);
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getAnalytics(applied));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [applied]);

  useEffect(() => {
    void load();
  }, [load]);

  function apply() {
    const problem = validateFilters(draft);
    setFilterError(problem);
    if (!problem) setApplied({ ...draft });
  }

  function reset() {
    setFilterError(null);
    setDraft(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <p className="mt-1 text-sm text-slate-500">
          Live figures computed from the complaint records. Days and weeks follow India Standard Time.
        </p>
      </div>

      <ComplaintFilterBar value={draft} onChange={setDraft} onSubmit={apply} categories={categories} error={filterError}>
        <Button type="submit" disabled={loading}>Apply filters</Button>
        <Button variant="secondary" onClick={reset} disabled={loading}>Reset</Button>
      </ComplaintFilterBar>

      {error ? (
        <Alert tone="error">
          Could not load analytics: {error}{" "}
          <button type="button" onClick={() => void load()} className="font-medium underline">Try again</button>
        </Alert>
      ) : loading && !data ? (
        <Spinner label="Loading analytics" />
      ) : data ? (
        <AnalyticsContent data={data} refreshing={loading} />
      ) : null}
    </div>
  );
}

function AnalyticsContent({ data, refreshing }: { data: Analytics; refreshing: boolean }) {
  const { totals, resolution, trend } = data;

  const kpis = (
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <StatCard label="Total complaints" value={totals.total} tone="brand" icon="📋" />
      <StatCard label="Open" value={totals.open} hint={`${totals.pending} pending · ${totals.in_progress} in progress`} tone="amber" icon="🛠️" />
      <StatCard label="Resolved" value={totals.resolved} tone="emerald" icon="✅" />
      <StatCard label="Closed" value={totals.closed} tone="slate" icon="🔒" />
      <StatCard
        tone="sky"
        icon="⏱️"
        label="Avg. resolution time"
        value={formatHours(resolution.average_hours)}
        hint={
          resolution.sample_size === 0
            ? "No resolved complaints yet"
            : `Median ${formatHours(resolution.median_hours)} · based on ${plural(resolution.sample_size, "resolved complaint")}`
        }
      />
    </dl>
  );

  if (totals.total === 0) {
    return (
      <div className="space-y-6" aria-busy={refreshing}>
        {kpis}
        <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
          No complaints match these filters. Try a wider date range or clear the filters.
        </p>
      </div>
    );
  }

  const priorityData = data.by_priority.map((p) => ({
    label: PRIORITY_KEY_LABELS[p.priority], count: p.count, color: PRIORITY_COLORS[p.priority],
  }));
  const statusData = data.by_status.map((s, i) => ({ label: STATUS_LABELS[s.status], count: s.count, color: STATUS_COLORS[i] }));
  const trendData = trend.points.map((p) => ({ ...p, label: formatShortDate(p.period_start) }));
  const created = trend.points.reduce((sum, p) => sum + p.created, 0);
  const resolved = trend.points.reduce((sum, p) => sum + p.resolved, 0);
  const busiest = trend.points.reduce((best, p) => (p.created > best.created ? p : best), trend.points[0] ?? { period_start: "", created: 0, resolved: 0 });
  const unit = trend.granularity === "week" ? "week" : "day";
  const trendSummary = trend.points.length
    ? `${trend.granularity === "week" ? "Weekly" : "Daily"} totals from ${formatShortDate(trend.points[0].period_start)} to ` +
      `${formatShortDate(trend.points[trend.points.length - 1].period_start)}: ${created} created, ${resolved} resolved. ` +
      (busiest.created > 0 ? `Busiest ${unit}: ${unit === "week" ? "week of " : ""}${formatShortDate(busiest.period_start)} (${busiest.created} created).` : "")
    : "No trend data.";

  return (
    <div className="space-y-6" aria-busy={refreshing}>
      {refreshing && <Spinner label="Updating" />}
      {kpis}

      <div className="grid gap-4 md:grid-cols-2">
        <ChartCard
          title="Complaints by category"
          summary={rankingSummary(data.by_category, totals.total, "category", "categories")}
          table={{ columns: ["Category", "Complaints"], rows: data.by_category.map((c) => [c.name, c.count]) }}
        >
          <HorizontalBars data={data.by_category} color={BRAND} />
        </ChartCard>
        <ChartCard
          title="Complaints by department"
          summary={rankingSummary(data.by_department, totals.total, "department", "departments")}
          table={{ columns: ["Department", "Complaints"], rows: data.by_department.map((d) => [d.name, d.count]) }}
        >
          <HorizontalBars data={data.by_department} color="#0284c7" />
        </ChartCard>
        <ChartCard
          title="Complaints by priority"
          summary={priorityData.map((p) => `${p.label}: ${p.count}`).join(", ") + "."}
          table={{ columns: ["Priority", "Complaints"], rows: priorityData.map((p) => [p.label, p.count]) }}
        >
          <ColumnBars data={priorityData} />
        </ChartCard>
        <ChartCard
          title="Complaints by status"
          summary={statusData.map((s) => `${s.label}: ${s.count}`).join(", ") + "."}
          table={{ columns: ["Status", "Complaints"], rows: statusData.map((s) => [s.label, s.count]) }}
        >
          <ColumnBars data={statusData} />
        </ChartCard>
        <ChartCard
          className="md:col-span-2"
          title={`Created vs resolved per ${unit}`}
          summary={trendSummary}
          table={{
            columns: [unit === "week" ? "Week starting" : "Date", "Created", "Resolved"],
            rows: trend.points.map((p) => [formatShortDate(p.period_start), p.created, p.resolved]),
          }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData} margin={{ top: 8, right: 16, bottom: 4, left: -16 }}>
              <CartesianGrid stroke="#e2e8f0" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={16} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="created" name="Created (solid line)" stroke={BRAND} strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="resolved" name="Resolved (dashed line)" stroke={RESOLVED} strokeWidth={2}
                strokeDasharray="6 4" dot={{ r: 3, strokeDasharray: "" }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5" aria-labelledby="oldest-open-heading">
        <h2 id="oldest-open-heading" className="text-base font-semibold text-slate-900">Oldest open complaints</h2>
        <p className="mt-1 text-sm text-slate-500">Submitted, assigned or in progress, oldest first.</p>
        {data.oldest_open.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No open complaints match these filters.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th scope="col" className="py-2 pr-4 font-medium">Reference</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Subject</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Category</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Department</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Status</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Priority</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Filed</th>
                  <th scope="col" className="py-2 font-medium">Age</th>
                </tr>
              </thead>
              <tbody>
                {data.oldest_open.map((c) => (
                  <tr key={c.id} className="border-b border-slate-100 last:border-0 align-top">
                    <td className="py-2 pr-4 font-mono text-xs">
                      <Link to={`/app/complaints/${c.id}`} className="text-brand-600 hover:underline">{c.reference_number}</Link>
                    </td>
                    <td className="max-w-xs py-2 pr-4">{c.subject}</td>
                    <td className="py-2 pr-4">{c.category}</td>
                    <td className="py-2 pr-4">{c.department ?? "Unassigned"}</td>
                    <td className="py-2 pr-4"><StatusBadge status={c.status} /></td>
                    <td className="py-2 pr-4"><PriorityBadge priority={c.priority} /></td>
                    <td className="whitespace-nowrap py-2 pr-4">{formatDateTime(c.created_at)}</td>
                    <td className="whitespace-nowrap py-2">{plural(c.age_days, "day")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="text-xs text-slate-400">
        Generated {formatDateTime(data.generated_at)} IST. Resolution time is measured from filing to the resolved
        timestamp and only counts complaints that have one.
      </p>
    </div>
  );
}
