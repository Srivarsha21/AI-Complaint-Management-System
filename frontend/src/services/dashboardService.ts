import type { Analytics, AnalyticsFilters, DashboardSummary, ReportFilters } from "../types/analytics";
import { api } from "./api";

/** Drops empty values so they are not sent as query parameters. */
export function filterParams(filters: ReportFilters): Record<string, string | number> {
  const params: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === "") continue;
    params[key] = typeof value === "string" ? value.trim() : value;
    if (params[key] === "") delete params[key];
  }
  return params;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await api.get<DashboardSummary>("/dashboard/summary");
  return data;
}

export async function getAnalytics(filters: AnalyticsFilters): Promise<Analytics> {
  const { data } = await api.get<Analytics>("/dashboard/analytics", { params: filterParams(filters) });
  return data;
}
