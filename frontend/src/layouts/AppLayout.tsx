import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import NotificationBell from "../components/notifications/NotificationBell";
import { useAuth } from "../hooks/useAuth";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  end?: boolean;
  adminOnly?: boolean;
  userOnly?: boolean;
  staffOnly?: boolean;
  /** Shown under the "Administration" heading. */
  admin?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/app", label: "Dashboard", icon: "🏠", end: true },
  { to: "/app/complaints/new", label: "File a complaint", icon: "✍️", userOnly: true },
  { to: "/app/assistant", label: "Complaint assistant", icon: "🤖" },
  { to: "/app/complaints", label: "My complaints", icon: "📋", end: true, userOnly: true },
  { to: "/app/complaints", label: "All complaints", icon: "📋", end: true, adminOnly: true },
  { to: "/app/complaints", label: "Department complaints", icon: "📋", end: true, staffOnly: true },
  { to: "/app/notifications", label: "Notifications", icon: "🔔" },
  { to: "/app/reports", label: "Reports", icon: "📄" },
  { to: "/app/profile", label: "Profile", icon: "👤" },
  { to: "/app/admin/analytics", label: "Analytics", icon: "📊", adminOnly: true, admin: true },
  { to: "/app/admin/ai-review", label: "AI review", icon: "🧠", adminOnly: true, admin: true },
  { to: "/app/admin/users", label: "User management", icon: "🧑‍🤝‍🧑", adminOnly: true, admin: true },
  { to: "/app/admin/departments", label: "Departments & categories", icon: "🏛️", adminOnly: true, admin: true },
  { to: "/app/admin/audit-log", label: "Audit log", icon: "🛡️", adminOnly: true, admin: true },
  { to: "/app/status", label: "System status", icon: "🩺", adminOnly: true, admin: true },
];

function navClass({ isActive }: { isActive: boolean }) {
  return `group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-all duration-150 ${
    isActive
      ? "bg-white text-brand-700 shadow-[0_8px_20px_-8px_rgb(0_0_0/0.45)]"
      : "text-indigo-100/85 hover:bg-white/10 hover:text-white hover:translate-x-0.5"
  }`;
}

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  const isAdmin = user?.role === "admin";
  const isStaff = user?.role === "staff";
  const items = NAV_ITEMS.filter((item) =>
    item.adminOnly ? isAdmin : item.userOnly ? !isAdmin && !isStaff : item.staffOnly ? isStaff : true,
  );
  const mainItems = items.filter((item) => !item.admin);
  const adminItems = items.filter((item) => item.admin);
  const roleLabel = isAdmin ? "Administrator" : isStaff ? `Staff · ${user?.department?.name ?? "No department"}` : "Citizen";

  async function handleLogout() {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  }

  const renderItems = (list: NavItem[]) => (
    <ul className="space-y-1">
      {list.map((item) => (
        <li key={item.label}>
          <NavLink to={item.to} end={item.end} className={navClass} onClick={() => setMenuOpen(false)}>
            <span aria-hidden className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/10 text-base group-[.bg-white]:bg-brand-50">
              {item.icon}
            </span>
            <span className="truncate">{item.label}</span>
          </NavLink>
        </li>
      ))}
    </ul>
  );

  return (
    <div className="min-h-screen md:flex">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center gap-1 bg-gradient-to-r from-indigo-950 via-brand-800 to-violet-800 px-4 py-3 text-white shadow-md md:hidden">
        <Brand />
        <div className="ml-auto">
          <NotificationBell className="text-white hover:bg-white/15" />
        </div>
        <button
          type="button"
          aria-label="Toggle navigation"
          aria-expanded={menuOpen}
          aria-controls="sidebar"
          onClick={() => setMenuOpen((open) => !open)}
          className="rounded-xl p-2 text-white hover:bg-white/15"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d={menuOpen ? "M6 6l12 12M18 6L6 18" : "M4 6h16M4 12h16M4 18h16"} strokeLinecap="round" />
          </svg>
        </button>
      </header>

      <aside
        id="sidebar"
        className={`${menuOpen ? "flex animate-fade-in" : "hidden"} relative flex-col overflow-hidden bg-gradient-to-b from-indigo-950 via-brand-900 to-violet-900 px-3 py-4 text-white md:sticky md:top-0 md:flex md:h-screen md:w-68 md:shrink-0`}
      >
        <div aria-hidden className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-fuchsia-500/25 blur-3xl" />
        <div aria-hidden className="pointer-events-none absolute -bottom-24 -left-16 h-64 w-64 rounded-full bg-sky-400/20 blur-3xl" />

        <div className="relative hidden items-center justify-between px-2 pb-6 md:flex">
          <Brand />
          <NotificationBell className="text-indigo-100 hover:bg-white/15 hover:text-white" />
        </div>

        <nav aria-label="Main" className="relative flex-1 space-y-6 overflow-y-auto pr-1">
          {renderItems(mainItems)}
          {adminItems.length > 0 && (
            <div>
              <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-indigo-200/70">Administration</p>
              {renderItems(adminItems)}
            </div>
          )}
        </nav>

        {user && (
          <div className="relative mt-4 rounded-2xl bg-white/10 p-3 backdrop-blur">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-amber-300 to-pink-400 text-sm font-bold text-indigo-950 shadow">
                {initials(user.full_name)}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{user.full_name}</p>
                <p className="truncate text-xs text-indigo-200">{roleLabel}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void handleLogout()}
              disabled={signingOut}
              className="mt-3 w-full rounded-xl bg-white/15 px-3 py-2 text-sm font-semibold text-white transition hover:bg-white/25 disabled:opacity-60"
            >
              {signingOut ? "Signing out…" : "Sign out"}
            </button>
          </div>
        )}
      </aside>

      {/* min-w-0 lets wide content (tables, charts) shrink instead of stretching the page. */}
      <main id="main" className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
        <div key={location.pathname} className="mx-auto max-w-7xl animate-fade-up">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

/** The logo doubles as the way back to the public home page. */
function Brand() {
  return (
    <Link
      to="/"
      title="Go to the home page"
      className="flex items-center gap-2 rounded-xl text-lg font-extrabold tracking-tight transition hover:opacity-90"
    >
      <img src="/favicon.svg" alt="" className="h-8 w-8 rounded-lg ring-2 ring-white/30" />
      <span>
        Resolve<span className="bg-gradient-to-r from-amber-200 to-pink-300 bg-clip-text text-transparent">AI</span>
        <span className="sr-only"> home page</span>
      </span>
    </Link>
  );
}
