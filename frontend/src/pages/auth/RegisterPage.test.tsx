import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import * as authService from "../../services/authService";
import { renderWithAuth } from "../../test/renderWithAuth";
import RegisterPage from "./RegisterPage";

vi.mock("../../services/authService");

beforeEach(() => localStorage.clear());
afterEach(() => vi.resetAllMocks());

function fill(values: { name: string; email: string; password: string; confirm: string }) {
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: values.name } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: values.email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: values.password } });
  fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: values.confirm } });
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));
}

test("shows field errors and does not submit invalid data", async () => {
  renderWithAuth(<RegisterPage />, { path: "/signup", route: "/signup" });

  fill({ name: "A", email: "bad", password: "short", confirm: "other" });

  expect(await screen.findByText("Full name must be at least 2 characters.")).toBeInTheDocument();
  expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
  expect(screen.getByText("Password must be at least 8 characters.")).toBeInTheDocument();
  expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
  expect(authService.register).not.toHaveBeenCalled();
});

test("registers, signs in and redirects", async () => {
  const user = {
    id: 2, full_name: "Ravi Kumar", email: "ravi@example.com", role: "user" as const,
    is_active: true, created_at: "2026-10-10T10:00:00Z", last_login_at: null,
  };
  vi.mocked(authService.register).mockResolvedValue(user);
  vi.mocked(authService.login).mockResolvedValue(user);
  renderWithAuth(<RegisterPage />, { path: "/signup", route: "/signup" });

  fill({ name: "Ravi Kumar", email: "ravi@example.com", password: "secret123", confirm: "secret123" });

  expect(await screen.findByText("Dashboard page")).toBeInTheDocument();
  expect(authService.register).toHaveBeenCalledWith("Ravi Kumar", "ravi@example.com", "secret123");
});
