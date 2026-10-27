import type { ComplaintPriority, ComplaintStatus } from "../types/complaint";

export const STATUS_ORDER: ComplaintStatus[] = ["submitted", "assigned", "in_progress", "resolved", "closed"];

export const STATUS_LABELS: Record<ComplaintStatus, string> = {
  submitted: "Submitted",
  assigned: "Assigned",
  in_progress: "In progress",
  resolved: "Resolved",
  closed: "Closed",
};

export const STATUS_STYLES: Record<ComplaintStatus, string> = {
  submitted: "bg-violet-50 text-violet-700 ring-violet-600/20",
  assigned: "bg-sky-50 text-sky-700 ring-sky-600/20",
  in_progress: "bg-amber-50 text-amber-800 ring-amber-600/25",
  resolved: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  closed: "bg-slate-700 text-white ring-slate-700",
};

/** Solid colour per status, for dots, progress bars and charts. */
export const STATUS_COLORS: Record<ComplaintStatus, string> = {
  submitted: "#8b5cf6",
  assigned: "#0ea5e9",
  in_progress: "#f59e0b",
  resolved: "#10b981",
  closed: "#475569",
};

export const PRIORITY_LABELS: Record<ComplaintPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

/** Button text for a status change, worded from the viewer's point of view. */
export function transitionLabel(from: ComplaintStatus, to: ComplaintStatus, isOwner: boolean): string {
  if (from === "resolved" && to === "closed") return isOwner ? "Confirm resolved & close" : "Close complaint";
  if (from === "resolved" && to === "in_progress") return "Reopen";
  if (to === "closed") return "Close early";
  if (to === "assigned") return "Mark assigned";
  if (to === "in_progress") return "Start work";
  if (to === "resolved") return "Mark resolved";
  return STATUS_LABELS[to];
}

/** Mirrors the backend rule for which changes need an explanation. */
export function noteRequired(from: ComplaintStatus, to: ComplaintStatus): boolean {
  if (to === "resolved") return true;
  if (from === "resolved" && to === "in_progress") return true;
  return to === "closed" && from !== "resolved";
}
