import { useCallback, useEffect, useState } from "react";

import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import StatusPill from "../../components/ui/StatusPill";
import { useAuth } from "../../hooks/useAuth";
import { listUsers, updateUser, type UserChanges } from "../../services/adminService";
import { getErrorMessage } from "../../services/api";
import { listDepartments } from "../../services/departmentService";
import type { User, UserRole } from "../../types/auth";
import type { Department } from "../../types/department";
import { formatDateTime } from "../../utils/format";

const PAGE_SIZE = 10;

export default function UsersPage() {
  const { user: me } = useAuth();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<UserRole | "">("");
  const [page, setPage] = useState(0);
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  // A user being turned into staff: the change waits until a department is chosen.
  const [pendingStaff, setPendingStaff] = useState<{ userId: number; departmentId: string; error?: string } | null>(null);

  useEffect(() => {
    listDepartments().then(setDepartments).catch(() => setDepartments([]));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listUsers({ search: query, role, limit: PAGE_SIZE, offset: page * PAGE_SIZE });
      setUsers(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [query, role, page]);

  useEffect(() => {
    void load();
  }, [load]);

  // Debounce the search box.
  useEffect(() => {
    const id = window.setTimeout(() => {
      setPage(0);
      setQuery(search.trim());
    }, 300);
    return () => window.clearTimeout(id);
  }, [search]);

  async function applyChange(target: User, changes: UserChanges, description: string) {
    setBusyId(target.id);
    setNotice(null);
    setError(null);
    try {
      const updated = await updateUser(target.id, changes);
      setUsers((list) => list.map((u) => (u.id === updated.id ? updated : u)));
      setNotice(`${updated.full_name}: ${description}.`);
      return true;
    } catch (err) {
      setError(getErrorMessage(err));
      return false;
    } finally {
      setBusyId(null);
    }
  }

  function changeRole(target: User, next: UserRole) {
    if (next === "staff") {
      setPendingStaff({ userId: target.id, departmentId: "" });
      return;
    }
    setPendingStaff(null);
    void applyChange(target, { role: next }, next === "admin" ? "now an administrator" : "now a regular user");
  }

  async function confirmStaff(target: User) {
    if (!pendingStaff) return;
    if (!pendingStaff.departmentId) {
      setPendingStaff({ ...pendingStaff, error: "Choose a department for this staff member." });
      return;
    }
    const department = departments.find((d) => d.id === Number(pendingStaff.departmentId));
    const ok = await applyChange(
      target,
      { role: "staff", department_id: Number(pendingStaff.departmentId) },
      `now staff of ${department?.name ?? "the department"}`,
    );
    if (ok) setPendingStaff(null);
  }

  const activeDepartments = departments.filter((d) => d.is_active);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">User management</h1>
        <p className="mt-1 text-sm text-slate-500">Every change here is recorded in the audit log.</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="flex-1">
          <span className="sr-only">Search users</span>
          <input
            type="search"
            placeholder="Search by name or email"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </label>
        <label>
          <span className="sr-only">Filter by role</span>
          <select
            value={role}
            onChange={(e) => {
              setPage(0);
              setRole(e.target.value as UserRole | "");
            }}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm sm:w-40"
          >
            <option value="">All roles</option>
            <option value="user">Users</option>
            <option value="staff">Staff</option>
            <option value="admin">Administrators</option>
          </select>
        </label>
      </div>

      {notice && <Alert tone="success">{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th scope="col" className="px-4 py-3">Name</th>
              <th scope="col" className="px-4 py-3">Role</th>
              <th scope="col" className="px-4 py-3">Department</th>
              <th scope="col" className="px-4 py-3">Status</th>
              <th scope="col" className="px-4 py-3">Last sign-in</th>
              <th scope="col" className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <Spinner label="Loading users" />
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No users match your filters.
                </td>
              </tr>
            ) : (
              users.map((u) => {
                const isSelf = u.id === me?.id;
                const busy = busyId === u.id;
                const pending = pendingStaff?.userId === u.id ? pendingStaff : null;
                return (
                  <tr key={u.id}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">
                        {u.full_name} {isSelf && <span className="text-xs font-normal text-slate-500">(you)</span>}
                      </div>
                      <div className="text-slate-500">{u.email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <label>
                        <span className="sr-only">Role for {u.full_name}</span>
                        <select
                          value={pending ? "staff" : u.role}
                          disabled={isSelf || busy}
                          onChange={(e) => changeRole(u, e.target.value as UserRole)}
                          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm disabled:bg-slate-50 disabled:text-slate-400"
                        >
                          <option value="user">User</option>
                          <option value="staff">Staff</option>
                          <option value="admin">Administrator</option>
                        </select>
                      </label>
                    </td>
                    <td className="px-4 py-3">
                      {pending ? (
                        <div className="space-y-1">
                          <label>
                            <span className="sr-only">Department for {u.full_name}</span>
                            <select
                              value={pending.departmentId}
                              disabled={busy}
                              aria-invalid={Boolean(pending.error)}
                              onChange={(e) => setPendingStaff({ userId: u.id, departmentId: e.target.value })}
                              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
                            >
                              <option value="">Choose a department</option>
                              {activeDepartments.map((d) => (
                                <option key={d.id} value={d.id}>
                                  {d.name}
                                </option>
                              ))}
                            </select>
                          </label>
                          {pending.error && <p className="text-xs text-red-600">{pending.error}</p>}
                          <div className="flex gap-1">
                            <Button className="px-2 py-1" disabled={busy} onClick={() => void confirmStaff(u)}>
                              Make staff
                            </Button>
                            <Button variant="ghost" className="px-2 py-1" onClick={() => setPendingStaff(null)}>
                              Cancel
                            </Button>
                          </div>
                        </div>
                      ) : u.role === "staff" ? (
                        <label>
                          <span className="sr-only">Department for {u.full_name}</span>
                          <select
                            value={u.department?.id ?? ""}
                            disabled={isSelf || busy}
                            onChange={(e) => {
                              const dept = departments.find((d) => d.id === Number(e.target.value));
                              if (dept) void applyChange(u, { department_id: dept.id }, `moved to ${dept.name}`);
                            }}
                            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm disabled:bg-slate-50 disabled:text-slate-400"
                          >
                            {!u.department && <option value="">No department</option>}
                            {departments
                              .filter((d) => d.is_active || d.id === u.department?.id)
                              .map((d) => (
                                <option key={d.id} value={d.id}>
                                  {d.name}
                                </option>
                              ))}
                          </select>
                        </label>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {u.is_active ? <StatusPill tone="success">Active</StatusPill> : <StatusPill tone="neutral">Disabled</StatusPill>}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{u.last_login_at ? formatDateTime(u.last_login_at) : "Never"}</td>
                    <td className="px-4 py-3 text-right">
                      {!isSelf && (
                        <Button
                          variant="secondary"
                          disabled={busy}
                          onClick={() => void applyChange(u, { is_active: !u.is_active }, u.is_active ? "account disabled" : "account enabled")}
                        >
                          {u.is_active ? "Disable" : "Enable"}
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>
          {total} user{total === 1 ? "" : "s"} · page {page + 1} of {pageCount}
        </span>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={page === 0 || loading} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <Button variant="secondary" disabled={page + 1 >= pageCount || loading} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
