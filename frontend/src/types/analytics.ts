import type { ComplaintPriority, ComplaintStatus } from "./complaint";

export type StatusBreakdown = Record<ComplaintStatus, number>;

export interface RecentUpdate {
  complaint_id: number;
  reference_number: string | null;
  subject: string;
  from_status: ComplaintStatus | null;
  to_status: ComplaintStatus;
  note: string | null;
  at: string;
}

export interface DashboardSummary {
  total: number;
  pending: number;
  by_status: StatusBreakdown;
  recent_updates: RecentUpdate[];
}

/** Filters shared by analytics and reports. Dates are YYYY-MM-DD in IST. */
export interface AnalyticsFilters {
  date_from?: string;
  date_to?: string;
  category_id?: number | "";
  department_id?: number | "";
  status?: ComplaintStatus | "";
}

export interface ReportFilters extends AnalyticsFilters {
  search?: string;
}

export type PriorityKey = ComplaintPriority | "not_assessed";

export interface NamedCount {
  id: number | null;
  name: string;
  count: number;
}

export interface TrendPoint {
  period_start: string;
  created: number;
  resolved: number;
}

export interface OldestOpenComplaint {
  id: number;
  reference_number: string | null;
  subject: string;
  status: ComplaintStatus;
  priority: ComplaintPriority | null;
  category: string;
  department: string | null;
  created_at: string;
  age_days: number;
}

export interface Analytics {
  generated_at: string;
  filters: {
    date_from: string | null;
    date_to: string | null;
    category_id: number | null;
    department_id: number | null;
    status: ComplaintStatus | null;
    timezone: string;
  };
  totals: { total: number; open: number; pending: number; in_progress: number; resolved: number; closed: number };
  by_status: { status: ComplaintStatus; count: number }[];
  by_priority: { priority: PriorityKey; count: number }[];
  by_category: NamedCount[];
  by_department: NamedCount[];
  trend: { granularity: "day" | "week"; points: TrendPoint[] };
  resolution: { average_hours: number | null; median_hours: number | null; sample_size: number };
  oldest_open: OldestOpenComplaint[];
}

export type ReportFormat = "pdf" | "xlsx";
