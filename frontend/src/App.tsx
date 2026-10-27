import { Route, Routes } from "react-router-dom";

import ProtectedRoute, { PublicOnlyRoute } from "./components/auth/ProtectedRoute";
import AppLayout from "./layouts/AppLayout";
import AuthLayout from "./layouts/AuthLayout";
import AIReviewPage from "./pages/admin/AIReviewPage";
import AnalyticsPage from "./pages/admin/AnalyticsPage";
import AuditLogPage from "./pages/admin/AuditLogPage";
import DepartmentsPage from "./pages/admin/DepartmentsPage";
import UsersPage from "./pages/admin/UsersPage";
import AssistantPage from "./pages/assistant/AssistantPage";
import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import ResetPasswordPage from "./pages/auth/ResetPasswordPage";
import ComplaintDetailPage from "./pages/complaints/ComplaintDetailPage";
import ComplaintsListPage from "./pages/complaints/ComplaintsListPage";
import NewComplaintPage from "./pages/complaints/NewComplaintPage";
import DashboardPage from "./pages/DashboardPage";
import LandingPage from "./pages/LandingPage";
import NotFoundPage from "./pages/NotFoundPage";
import NotificationsPage from "./pages/NotificationsPage";
import ProfilePage from "./pages/ProfilePage";
import ReportsPage from "./pages/ReportsPage";
import SystemStatusPage from "./pages/SystemStatusPage";

export default function App() {
  return (
    <Routes>
      <Route index element={<LandingPage />} />

      <Route element={<AuthLayout />}>
        <Route element={<PublicOnlyRoute />}>
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
          <Route path="forgot-password" element={<ForgotPasswordPage />} />
        </Route>
        <Route path="reset-password" element={<ResetPasswordPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route path="app" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="complaints" element={<ComplaintsListPage />} />
          <Route path="complaints/new" element={<NewComplaintPage />} />
          <Route path="complaints/:id" element={<ComplaintDetailPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route element={<ProtectedRoute role="admin" />}>
            <Route path="admin/users" element={<UsersPage />} />
            <Route path="admin/departments" element={<DepartmentsPage />} />
            <Route path="admin/audit-log" element={<AuditLogPage />} />
            <Route path="admin/analytics" element={<AnalyticsPage />} />
            <Route path="admin/ai-review" element={<AIReviewPage />} />
            <Route path="status" element={<SystemStatusPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
