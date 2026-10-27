import { fireEvent, screen } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { vi } from "vitest";

import * as authService from "../../services/authService";
import { renderWithAuth } from "../../test/renderWithAuth";
import type { User } from "../../types/auth";
import LoginPage from "./LoginPage";

vi.mock("../../services/authService");

const USER: User = {
  id: 1,
  full_name: "Priya Sharma",
  email: "priya@example.com",
  role: "user",
  is_active: true,
  created_at: "2026-10-10T10:00:00Z",
  last_login_at: null,
};

function apiError(status: number, detail: string) {
  const headers = new AxiosHeaders();
  return new AxiosError("fail", "ERR", { headers }, null, {
    status,
    statusText: "",
    headers: {},
    config: { headers },
    data: { detail },
  });
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.resetAllMocks());

function fill(email: string, password: string) {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

test("signs in and redirects to the dashboard", async () => {
  vi.mocked(authService.login).mockResolvedValue(USER);
  renderWithAuth(<LoginPage />, { path: "/login-form", route: "/login-form" });

  fill("priya@example.com", "secret123");

  expect(await screen.findByText("Dashboard page")).toBeInTheDocument();
  expect(authService.login).toHaveBeenCalledWith("priya@example.com", "secret123");
});

test("shows the server error for wrong credentials", async () => {
  vi.mocked(authService.login).mockRejectedValue(apiError(401, "Incorrect email or password."));
  renderWithAuth(<LoginPage />, { path: "/login-form", route: "/login-form" });

  fill("priya@example.com", "wrong-pass1");

  expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
});

test("requires both fields before calling the API", async () => {
  renderWithAuth(<LoginPage />, { path: "/login-form", route: "/login-form" });

  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Enter your email and password.");
  expect(authService.login).not.toHaveBeenCalled();
});
