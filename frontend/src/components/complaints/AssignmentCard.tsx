import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "../../hooks/useAuth";
import { getErrorMessage } from "../../services/api";
import { assignComplaint } from "../../services/complaintService";
import { listDepartmentStaff, listDepartments } from "../../services/departmentService";
import type { ComplaintDetail, UserBrief } from "../../types/complaint";
import type { Department } from "../../types/department";
import { formatDateTime } from "../../utils/format";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
import Card from "../ui/Card";

const SELECT = "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100";

/**
 * Routing and assignment for people who manage the complaint. Admins may
 * re-route to another department; staff assign within their own department.
 * The backend enforces the same rules.
 */
export default function AssignmentCard({ complaint, onUpdated }: { complaint: ComplaintDetail; onUpdated: (c: ComplaintDetail) => void }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const currentDeptId = complaint.department?.id ?? null;

  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentId, setDepartmentId] = useState<number | null>(currentDeptId);
  const [staff, setStaff] = useState<UserBrief[]>([]);
  const [assigneeId, setAssigneeId] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => setDepartmentId(currentDeptId), [currentDeptId]);

  useEffect(() => {
    if (!isAdmin || !complaint.can_manage) return;
    listDepartments()
      .then((list) => setDepartments(list.filter((d) => d.is_active || d.id === currentDeptId)))
      .catch(() => setDepartments([]));
  }, [isAdmin, complaint.can_manage, currentDeptId]);

  useEffect(() => {
    setAssigneeId("");
    if (!departmentId || !complaint.can_manage) {
      setStaff([]);
      return;
    }
    let cancelled = false;
    listDepartmentStaff(departmentId)
      .then((list) => !cancelled && setStaff(list))
      .catch(() => !cancelled && setStaff([]));
    return () => {
      cancelled = true;
    };
  }, [departmentId, complaint.can_manage]);

  if (!complaint.can_manage) return null;
  const closed = complaint.status === "closed";
  const rerouting = departmentId !== null && departmentId !== currentDeptId;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!rerouting && !assigneeId) {
      setError(isAdmin ? "Choose a staff member or a different department." : "Choose a staff member.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await assignComplaint(complaint.id, {
        department_id: rerouting ? departmentId ?? undefined : undefined,
        assignee_id: assigneeId ? Number(assigneeId) : undefined,
        note: note.trim(),
      });
      setNote("");
      setAssigneeId("");
      onUpdated(updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Assignment">
      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Department</dt>
          <dd className="mt-0.5 text-slate-900">{complaint.department?.name ?? "Not routed yet"}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Assigned to</dt>
          <dd className="mt-0.5 text-slate-900">{complaint.assigned_to?.full_name ?? "Unassigned"}</dd>
        </div>
      </dl>

      {closed ? (
        <p className="mt-4 text-sm text-slate-500">Closed complaints cannot be re-assigned.</p>
      ) : (
        <form onSubmit={submit} className="mt-4 space-y-3" aria-label="Assign complaint">
          {error && <Alert tone="error">{error}</Alert>}
          {isAdmin && (
            <div>
              <label htmlFor="assign-department" className="block text-sm font-medium text-slate-700">
                Route to department
              </label>
              <select
                id="assign-department"
                value={departmentId ?? ""}
                onChange={(e) => setDepartmentId(e.target.value ? Number(e.target.value) : null)}
                className={SELECT}
              >
                {currentDeptId === null && <option value="">Choose a department</option>}
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                    {d.id === currentDeptId ? " (current)" : ""}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div>
            <label htmlFor="assign-staff" className="block text-sm font-medium text-slate-700">
              Assign to staff member{rerouting ? " (optional)" : ""}
            </label>
            <select id="assign-staff" value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)} className={SELECT}>
              <option value="">{staff.length ? "Choose a staff member" : "No active staff in this department"}</option>
              {staff.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name}
                  {s.id === complaint.assigned_to?.id ? " (current)" : ""}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="assign-note" className="block text-sm font-medium text-slate-700">
              Note (optional)
            </label>
            <textarea
              id="assign-note"
              rows={2}
              maxLength={1000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className={SELECT}
            />
          </div>
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : rerouting ? "Re-route complaint" : "Assign"}
          </Button>
        </form>
      )}

      {complaint.assignments.length > 0 && (
        <div className="mt-5">
          <h3 className="text-sm font-medium text-slate-900">Assignment history</h3>
          <ol className="mt-2 space-y-3">
            {[...complaint.assignments].reverse().map((a) => (
              <li key={a.id} className="text-sm">
                <p className="text-slate-900">
                  {a.from_department?.id !== a.to_department?.id
                    ? `Re-routed ${a.from_department?.name ?? "—"} → ${a.to_department?.name ?? "—"}`
                    : a.assigned_to
                      ? `Assigned to ${a.assigned_to.full_name}`
                      : "Assignment cleared"}
                  {a.from_department?.id !== a.to_department?.id && a.assigned_to && `, assigned to ${a.assigned_to.full_name}`}
                </p>
                <p className="text-xs text-slate-500">
                  {formatDateTime(a.created_at)}
                  {a.assigned_by && ` · by ${a.assigned_by.full_name}`}
                </p>
                {a.note && <p className="mt-0.5 whitespace-pre-line text-slate-600">{a.note}</p>}
              </li>
            ))}
          </ol>
        </div>
      )}
    </Card>
  );
}
