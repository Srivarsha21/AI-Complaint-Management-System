import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { StatusBadge } from "../components/complaints/StatusBadge";
import UserStats from "../components/dashboard/UserStats";
import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import Spinner from "../components/ui/Spinner";
import { useAuth } from "../hooks/useAuth";
import { getErrorMessage } from "../services/api";
import { getComplaintByReference, listComplaints } from "../services/complaintService";
import type { ComplaintListItem } from "../types/complaint";
import { formatDateTime } from "../utils/format";

export default function DashboardPage() {
  const { user } = useAuth();
  const [recent, setRecent] = useState<ComplaintListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listComplaints({ limit: 5, offset: 0, sort: "updated" })
      .then((page) => setRecent(page.items))
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (!user) return null;
  const isAdmin = user.role === "admin";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Welcome, {user.full_name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {isAdmin ? "Recently updated complaints across the system." : "Track your complaints or file a new one."}
          </p>
        </div>
        {!isAdmin && (
          <Link to="/app/complaints/new" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
            File a complaint
          </Link>
        )}
      </div>

      {isAdmin ? (
        <p className="text-sm">
          <Link to="/app/admin/analytics" className="font-medium text-brand-600 hover:underline">
            Open analytics →
          </Link>
        </p>
      ) : (
        <UserStats />
      )}

      <TrackByReference />

      <Card title="Recently updated">
        {loading ? (
          <Spinner label="Loading complaints" />
        ) : error ? (
          <Alert tone="error">{error}</Alert>
        ) : recent.length === 0 ? (
          <p className="text-sm text-slate-500">
            {isAdmin ? "No complaints have been filed yet." : "You have not filed any complaints yet."}
          </p>
        ) : (
          <ul className="-mx-2 divide-y divide-slate-100">
            {recent.map((c) => (
              <li key={c.id}>
                <Link to={`/app/complaints/${c.id}`} className="flex items-center justify-between gap-3 rounded-lg px-2 py-3 hover:bg-slate-50">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">{c.subject}</p>
                    <p className="text-xs text-slate-500">
                      <span className="font-mono">{c.reference_number}</span> · updated {formatDateTime(c.updated_at)}
                    </p>
                  </div>
                  <StatusBadge status={c.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
        <Link to="/app/complaints" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
          View all complaints →
        </Link>
      </Card>
    </div>
  );
}

function TrackByReference() {
  const navigate = useNavigate();
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = reference.trim();
    if (!value) return;
    setSearching(true);
    setError(null);
    try {
      const complaint = await getComplaintByReference(value);
      navigate(`/app/complaints/${complaint.id}`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSearching(false);
    }
  }

  return (
    <Card title="Track a complaint" description="Enter a reference number such as CMP-2026-000001.">
      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="reference" className="sr-only">
          Reference number
        </label>
        <input
          id="reference"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          placeholder="CMP-2026-000001"
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm uppercase shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
        />
        <Button type="submit" disabled={searching || !reference.trim()}>
          {searching ? "Searching…" : "Track"}
        </Button>
      </form>
      {error && (
        <div className="mt-3">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
    </Card>
  );
}
