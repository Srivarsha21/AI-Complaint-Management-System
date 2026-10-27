import type { ComplaintPriority, ComplaintStatus } from "../../types/complaint";
import { PRIORITY_LABELS, STATUS_COLORS, STATUS_LABELS, STATUS_STYLES } from "../../utils/complaintLabels";

export function StatusBadge({ status }: { status: ComplaintStatus }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${STATUS_STYLES[status]}`}>
      <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: status === "closed" ? "#fff" : STATUS_COLORS[status] }} />
      {STATUS_LABELS[status]}
    </span>
  );
}

const PRIORITY_STYLES: Record<ComplaintPriority, string> = {
  critical: "bg-rose-100 text-rose-700",
  high: "bg-orange-100 text-orange-700",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-slate-100 text-slate-600",
};

export function PriorityBadge({ priority }: { priority: ComplaintPriority | null }) {
  if (!priority) return <span className="text-xs text-slate-400">Not assessed</span>;
  return (
    <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-semibold ${PRIORITY_STYLES[priority]}`}>
      {priority === "critical" && <span aria-hidden className="mr-1">▲</span>}
      {PRIORITY_LABELS[priority]}
    </span>
  );
}
