import { useEffect, useState } from "react";

import ComplaintFilterBar, { EMPTY_FILTERS, validateFilters } from "../components/dashboard/ComplaintFilterBar";
import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";
import { useAuth } from "../hooks/useAuth";
import { getErrorMessage } from "../services/api";
import { listCategories } from "../services/complaintService";
import { fetchReport, saveBlob } from "../services/reportService";
import type { ReportFilters, ReportFormat } from "../types/analytics";
import type { Category } from "../types/complaint";

const FORMAT_LABELS: Record<ReportFormat, string> = { pdf: "PDF", xlsx: "Excel" };

export default function ReportsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [categories, setCategories] = useState<Category[]>([]);
  const [filters, setFilters] = useState<ReportFilters>(EMPTY_FILTERS);
  const [busy, setBusy] = useState<ReportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    listCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  async function download(format: ReportFormat) {
    const problem = validateFilters(filters);
    setMessage(null);
    setError(problem);
    if (problem) return;

    setBusy(format);
    try {
      const report = await fetchReport(format, filters);
      saveBlob(report);
      setMessage(`Downloaded ${report.filename}.`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Reports</h1>
        <p className="mt-1 text-sm text-slate-500">
          {isAdmin
            ? "Export complaints across the system as PDF or Excel. Exports include complainant names (never contact details) and are recorded in the audit log."
            : "Download a record of the complaints you have filed as PDF or Excel."}
        </p>
      </div>

      <ComplaintFilterBar
        value={filters}
        onChange={setFilters}
        onSubmit={() => void download("pdf")}
        categories={categories}
        showDepartment={isAdmin}
        showSearch
      >
        {(["pdf", "xlsx"] as ReportFormat[]).map((format) => (
          <Button
            key={format}
            variant={format === "pdf" ? "primary" : "secondary"}
            onClick={() => void download(format)}
            disabled={busy !== null}
            aria-busy={busy === format}
          >
            {busy === format ? `Preparing ${FORMAT_LABELS[format]}…` : `Download ${FORMAT_LABELS[format]}`}
          </Button>
        ))}
      </ComplaintFilterBar>

      {error && <Alert tone="error">{error}</Alert>}
      {message && <Alert tone="success">{message}</Alert>}

      <p className="text-xs text-slate-500">
        Reports list up to 5,000 complaints, newest first; the report says so when more match. Times are shown in
        India Standard Time.
      </p>
    </div>
  );
}
