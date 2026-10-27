import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PriorityBadge, StatusBadge } from "../../components/complaints/StatusBadge";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import { useAuth } from "../../hooks/useAuth";
import { getErrorMessage } from "../../services/api";
import { listCategories, listComplaints } from "../../services/complaintService";
import type { Category, ComplaintListItem, ComplaintQuery, ComplaintStatus } from "../../types/complaint";
import { STATUS_LABELS, STATUS_ORDER } from "../../utils/complaintLabels";
import { categoryStyleByName } from "../../utils/categoryStyles";
import { formatDateTime } from "../../utils/format";

const PAGE_SIZE = 10;

export default function ComplaintsListPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const isStaff = user?.role === "staff";
  const isManager = isAdmin || isStaff;

  const [categories, setCategories] = useState<Category[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState<ComplaintQuery>({ limit: PAGE_SIZE, offset: 0, sort: "newest", status: "", category_id: "", search: "" });
  const [items, setItems] = useState<ComplaintListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await listComplaints(query);
      setItems(page.items);
      setTotal(page.total);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void load();
  }, [load]);

  // Debounced search by reference number or subject.
  useEffect(() => {
    const id = window.setTimeout(() => {
      setQuery((q) => (q.search === searchInput.trim() ? q : { ...q, search: searchInput.trim(), offset: 0 }));
    }, 300);
    return () => window.clearTimeout(id);
  }, [searchInput]);

  const update = (changes: Partial<ComplaintQuery>) => setQuery((q) => ({ ...q, ...changes, offset: 0 }));
  const page = Math.floor(query.offset / PAGE_SIZE);
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters = Boolean(query.status || query.category_id || query.search);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {isAdmin ? "All complaints" : isStaff ? "Department complaints" : "My complaints"}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {isAdmin
              ? "Every complaint filed in the system."
              : isStaff
                ? `Complaints routed to ${user?.department?.name ?? "your department"}.`
                : "Complaints you have filed and their current status."}
          </p>
        </div>
        {!isManager && (
          <Link to="/app/complaints/new" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
            File a complaint
          </Link>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="sm:col-span-2">
          <span className="sr-only">Search by reference or subject</span>
          <input
            type="search"
            placeholder="Search by reference (CMP-…) or subject"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </label>
        <label>
          <span className="sr-only">Filter by status</span>
          <select
            value={query.status}
            onChange={(e) => update({ status: e.target.value as ComplaintStatus | "" })}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm"
          >
            <option value="">All statuses</option>
            {STATUS_ORDER.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter by category</span>
          <select
            value={query.category_id}
            onChange={(e) => update({ category_id: e.target.value ? Number(e.target.value) : "" })}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm"
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex items-center justify-between text-sm">
        <label className="flex items-center gap-2 text-slate-600">
          Sort
          <select
            value={query.sort}
            onChange={(e) => update({ sort: e.target.value as ComplaintQuery["sort"] })}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="updated">Recently updated</option>
          </select>
        </label>
        {hasFilters && (
          <button
            type="button"
            className="font-medium text-brand-600 hover:underline"
            onClick={() => {
              setSearchInput("");
              setQuery({ limit: PAGE_SIZE, offset: 0, sort: query.sort, status: "", category_id: "", search: "" });
            }}
          >
            Clear filters
          </button>
        )}
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <div className="p-8 text-center">
            <Spinner label="Loading complaints" />
          </div>
        ) : items.length === 0 ? (
          <div className="p-10 text-center">
            <p className="font-medium text-slate-900">{hasFilters ? "No complaints match your filters" : "No complaints yet"}</p>
            <p className="mt-1 text-sm text-slate-500">
              {hasFilters ? "Try a different search or clear the filters." : isManager ? "New complaints will appear here." : "When you file a complaint, it will appear here."}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((c, index) => {
              const style = categoryStyleByName(c.category.name);
              return (
              <li key={c.id} className="animate-fade-up" style={{ animationDelay: `${index * 30}ms` }}>
                <Link
                  to={`/app/complaints/${c.id}`}
                  className="group flex gap-3 px-4 py-4 transition hover:bg-brand-50/40 focus:bg-brand-50/40 sm:px-5"
                >
                  <span aria-hidden className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg ring-1 transition group-hover:scale-110 ${style.chip}`}>
                    {style.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-mono text-xs text-slate-500">{c.reference_number}</p>
                      <p className="mt-0.5 truncate font-semibold text-slate-900 group-hover:text-brand-700">{c.subject}</p>
                    </div>
                    <StatusBadge status={c.status} />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                    <span className="font-medium text-slate-700">{c.category.name}</span>
                    {c.department && <span>{c.department.name}</span>}
                    <span>
                      Priority: <PriorityBadge priority={c.priority} />
                    </span>
                    {isManager && <span>By {c.user.full_name}</span>}
                    {isManager && <span>{c.assigned_to ? `Assigned to ${c.assigned_to.full_name}` : "Unassigned"}</span>}
                    <span>Filed {formatDateTime(c.created_at)}</span>
                  </div>
                  </div>
                </Link>
              </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>
          {total} complaint{total === 1 ? "" : "s"} · page {page + 1} of {pageCount}
        </span>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={page === 0 || loading} onClick={() => setQuery((q) => ({ ...q, offset: q.offset - PAGE_SIZE }))}>
            Previous
          </Button>
          <Button variant="secondary" disabled={page + 1 >= pageCount || loading} onClick={() => setQuery((q) => ({ ...q, offset: q.offset + PAGE_SIZE }))}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
