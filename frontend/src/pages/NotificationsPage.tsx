import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";
import Spinner from "../components/ui/Spinner";
import { getErrorMessage } from "../services/api";
import {
  NOTIFICATIONS_CHANGED_EVENT,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../services/notificationService";
import type { AppNotification } from "../types/notification";
import { formatDateTime } from "../utils/format";

const PAGE_SIZE = 20;

export default function NotificationsPage() {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [total, setTotal] = useState(0);
  const [unread, setUnread] = useState(0);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listNotifications({ unreadOnly, limit: PAGE_SIZE, offset: page * PAGE_SIZE });
      setItems(data.items);
      setTotal(data.total);
      setUnread(data.unread);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [unreadOnly, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const changed = () => window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT));

  async function markRead(item: AppNotification) {
    if (item.is_read) return;
    try {
      const updated = await markNotificationRead(item.id);
      setItems((list) => list.map((n) => (n.id === updated.id ? updated : n)));
      setUnread((count) => Math.max(0, count - 1));
      changed();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function markAll() {
    setBusy(true);
    setError(null);
    try {
      await markAllNotificationsRead();
      changed();
      await load();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Notifications</h1>
          <p className="mt-1 text-sm text-slate-500">
            {unread === 0 ? "You are all caught up." : `${unread} unread notification${unread === 1 ? "" : "s"}.`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(e) => {
                setPage(0);
                setUnreadOnly(e.target.checked);
              }}
              className="h-4 w-4 rounded border-slate-300"
            />
            Unread only
          </label>
          <Button variant="secondary" disabled={busy || unread === 0} onClick={() => void markAll()}>
            Mark all as read
          </Button>
        </div>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <div className="p-8 text-center">
            <Spinner label="Loading notifications" />
          </div>
        ) : items.length === 0 ? (
          <p className="p-10 text-center text-sm text-slate-500">{unreadOnly ? "No unread notifications." : "No notifications yet."}</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((n) => (
              <li key={n.id} className={`flex flex-wrap items-start justify-between gap-3 px-4 py-4 sm:px-5 ${n.is_read ? "" : "bg-brand-50/50"}`}>
                <div className="min-w-0">
                  <p className={`text-sm ${n.is_read ? "text-slate-600" : "font-medium text-slate-900"}`}>
                    {!n.is_read && <span className="sr-only">Unread: </span>}
                    {n.message}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">{formatDateTime(n.created_at)}</p>
                </div>
                <div className="flex shrink-0 gap-2">
                  {n.complaint_id && (
                    <Link
                      to={`/app/complaints/${n.complaint_id}`}
                      onClick={() => void markRead(n)}
                      className="rounded-lg px-3 py-1.5 text-sm font-medium text-brand-600 hover:bg-brand-50"
                    >
                      View complaint
                    </Link>
                  )}
                  {!n.is_read && (
                    <Button variant="ghost" onClick={() => void markRead(n)} aria-label={`Mark as read: ${n.message}`}>
                      Mark read
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>
            page {page + 1} of {pageCount}
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
      )}
    </div>
  );
}
