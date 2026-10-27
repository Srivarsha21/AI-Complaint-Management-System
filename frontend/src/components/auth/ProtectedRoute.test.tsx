import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import { AuthProvider } from "../../hooks/useAuth";
import * as authService from "../../services/authService";
import { tokenStorage } from "../../services/tokenStorage";
import ProtectedRoute from "./ProtectedRoute";

vi.mock("../../services/authService");

function renderAt(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>Login page</p>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/app" element={<p>Private dashboard</p>} />
            <Route element={<ProtectedRoute role="admin" />}>
              <Route path="/app/admin" element={<p>Admin area</p>} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

const baseUser = {
  id: 1, full_name: "Test User", email: "t@example.com", is_active: true,
  created_at: "2026-10-10T10:00:00Z", last_login_at: null,
};

beforeEach(() => localStorage.clear());
afterEach(() => vi.resetAllMocks());

test("redirects anonymous visitors to the login page", async () => {
  renderAt("/app");
  expect(await screen.findByText("Login page")).toBeInTheDocument();
});

test("shows the page to a signed-in user restored from storage", async () => {
  tokenStorage.save({ access_token: "a", refresh_token: "r" });
  vi.mocked(authService.fetchCurrentUser).mockResolvedValue({ ...baseUser, role: "user" });
  renderAt("/app");
  expect(await screen.findByText("Private dashboard")).toBeInTheDocument();
});

test("blocks regular users from admin pages", async () => {
  tokenStorage.save({ access_token: "a", refresh_token: "r" });
  vi.mocked(authService.fetchCurrentUser).mockResolvedValue({ ...baseUser, role: "user" });
  renderAt("/app/admin");
  expect(await screen.findByText("Access denied")).toBeInTheDocument();
  expect(screen.queryByText("Admin area")).not.toBeInTheDocument();
});

test("allows admins into admin pages", async () => {
  tokenStorage.save({ access_token: "a", refresh_token: "r" });
  vi.mocked(authService.fetchCurrentUser).mockResolvedValue({ ...baseUser, role: "admin" });
  renderAt("/app/admin");
  expect(await screen.findByText("Admin area")).toBeInTheDocument();
});

test("clears a stored session the server rejects", async () => {
  tokenStorage.save({ access_token: "expired", refresh_token: "expired" });
  vi.mocked(authService.fetchCurrentUser).mockRejectedValue(new Error("401"));
  renderAt("/app");
  expect(await screen.findByText("Login page")).toBeInTheDocument();
  expect(tokenStorage.getAccessToken()).toBeNull();
});
