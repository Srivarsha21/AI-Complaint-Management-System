import { AxiosError } from "axios";

import type { ReportFilters, ReportFormat } from "../types/analytics";
import { todayInIst } from "../utils/format";
import { api } from "./api";
import { filterParams } from "./dashboardService";

export interface DownloadedReport {
  blob: Blob;
  filename: string;
}

function filenameFrom(disposition: unknown, format: ReportFormat): string {
  const match = typeof disposition === "string" ? /filename="?([^";]+)"?/i.exec(disposition) : null;
  return match?.[1] ?? `complaints-${todayInIst()}.${format}`;
}

/** Fetches a report with the auth header (so it cannot be a plain link). */
export async function fetchReport(format: ReportFormat, filters: ReportFilters): Promise<DownloadedReport> {
  try {
    const response = await api.get<Blob>(`/reports/complaints.${format}`, {
      params: filterParams(filters),
      responseType: "blob",
      timeout: 120000, // large exports take a while to build
    });
    return { blob: response.data, filename: filenameFrom(response.headers["content-disposition"], format) };
  } catch (error) {
    // Error bodies arrive as Blobs too; turn them back into JSON so getErrorMessage can read `detail`.
    if (error instanceof AxiosError && error.response?.data instanceof Blob) {
      try {
        error.response.data = JSON.parse(await error.response.data.text());
      } catch {
        error.response.data = {};
      }
    }
    throw error;
  }
}

/** Saves a blob through a temporary link. */
export function saveBlob({ blob, filename }: DownloadedReport): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
