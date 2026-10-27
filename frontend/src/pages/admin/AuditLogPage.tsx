import { useEffect, useState } from "react";

import Alert from "../../components/ui/Alert";
import Spinner from "../../components/ui/Spinner";
import { listAuditLogs } from "../../services/adminService";
import { getErrorMessage } from "../../services/api";
import type { AuditLogEntry } from "../../types/auth";
import { formatDateTime } from "../../utils/format";

const ACTION_LABELS: Record<string, string> = {
  "admin.user_updated": "User updated by admin",
  "admin.department_created": "Department created",
  "admin.department_updated": "Department updated",
  "admin.category_created": "Category created",
  "admin.category_updated": "Category updated",
  "complaint.assigned": "Complaint assigned / re-routed",
  "auth.password_changed": "Password changed",
  "auth.password_reset": "Password reset",
  "auth.password_reset_requested": "Password reset requested",
};

function describeDetails(entry: AuditLogEntry): string {
  const details = entry.details as { before?: Record<string, unknown>; after?: Record<string, unknown> } | null;
  if (!details?.before || !details.after) return "";
  return Object.keys(details.after)
    .filter((key) => details.before![key] !== details.after![key])
    .map((key) => `${key}: ${String(details.before![key])} → ${String(details.after![key])}`)
    .join(", ");
}

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAuditLogs()
      .then((data) => setEntries(data.items))
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Audit log</h1>
        <p className="mt-1 text-sm text-slate-500">The 50 most recent security-relevant actions.</p>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      {loading ? (
        <Spinner label="Loading audit log" />
      ) : entries.length === 0 && !error ? (
        <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">No audit entries yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm">
          {entries.map((entry) => (
            <li key={entry.id} className="flex flex-col gap-1 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-medium text-slate-900">{ACTION_LABELS[entry.action] ?? entry.action}</p>
                <p className="text-slate-500">
                  {entry.target_type} #{entry.target_id}
                  {entry.actor_id !== null && ` · by user #${entry.actor_id}`}
                  {describeDetails(entry) && ` · ${describeDetails(entry)}`}
                </p>
              </div>
              <time dateTime={entry.created_at} className="shrink-0 text-xs text-slate-500">
                {formatDateTime(entry.created_at)}
              </time>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
