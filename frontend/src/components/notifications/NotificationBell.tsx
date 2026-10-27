import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { NOTIFICATIONS_CHANGED_EVENT as CHANGED_EVENT, getUnreadCount } from "../../services/notificationService";

const POLL_MS = 60_000;

/** Bell with unread badge. Polls every 60 s while the tab is visible and refreshes on navigation. */
export default function NotificationBell({
  className = "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
}: {
  /** Colour classes, so the bell can sit on light or dark backgrounds. */
  className?: string;
}) {
  const [unread, setUnread] = useState(0);
  const location = useLocation();

  const refresh = useCallback(() => {
    getUnreadCount()
      .then(setUnread)
      .catch(() => undefined); // keep the last known count; the bell is non-critical
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, location.pathname]);

  useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") refresh();
    };
    const id = window.setInterval(tick, POLL_MS);
    document.addEventListener("visibilitychange", tick);
    window.addEventListener(CHANGED_EVENT, refresh);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
      window.removeEventListener(CHANGED_EVENT, refresh);
    };
  }, [refresh]);

  const label = unread > 0 ? `Notifications, ${unread} unread` : "Notifications";
  return (
    <Link to="/app/notifications" aria-label={label} title={label} className={`relative rounded-xl p-2 transition ${className}`}>
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M13.7 21a2 2 0 0 1-3.4 0" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {unread > 0 && (
        <span aria-hidden className="absolute -right-0.5 -top-0.5 min-w-[1.1rem] rounded-full bg-rose-500 px-1 text-center text-[10px] font-bold leading-[1.1rem] text-white shadow ring-2 ring-white animate-pop">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}
