import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import type { UserRole } from "../../types/auth";
import Spinner from "../ui/Spinner";

/** Renders child routes only for signed-in users (optionally with a given role). */
export default function ProtectedRoute({ role }: { role?: UserRole }) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner label="Loading your session" />
      </div>
    );
  }
  if (status === "anonymous" || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (role && user.role !== role) {
    return (
      <div className="py-16 text-center">
        <h1 className="text-xl font-semibold">Access denied</h1>
        <p className="mt-2 text-slate-500">You do not have permission to view this page.</p>
      </div>
    );
  }
  return <Outlet />;
}

/** Keeps signed-in users away from login/register pages. */
export function PublicOnlyRoute() {
  const { status } = useAuth();
  if (status === "loading") return null;
  if (status === "authenticated") return <Navigate to="/app" replace />;
  return <Outlet />;
}
