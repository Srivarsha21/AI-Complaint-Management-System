import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import { AuthProvider } from "../../hooks/useAuth";
import * as authService from "../../services/authService";
import GoogleSignInButton from "./GoogleSignInButton";

vi.mock("../../services/authService");

function renderButton() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<GoogleSignInButton />} />
          <Route path="/app" element={<p>Dashboard page</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  vi.resetAllMocks();
  delete window.google;
});

test("renders nothing when Google sign-in is not configured", async () => {
  vi.mocked(authService.getAuthConfig).mockResolvedValue({ google_client_id: null });
  const { container } = renderButton();
  await act(async () => undefined);
  expect(container.textContent).toBe("");
});

test("signs in with the Google credential and opens the dashboard", async () => {
  vi.mocked(authService.getAuthConfig).mockResolvedValue({ google_client_id: "client.apps.googleusercontent.com" });
  vi.mocked(authService.loginWithGoogle).mockResolvedValue({
    id: 1, full_name: "Priya Nair", email: "priya@gmail.com", role: "user", is_active: true,
    created_at: "2026-10-11T00:00:00Z", last_login_at: null,
  });
  let googleCallback: ((r: { credential?: string }) => void) | undefined;
  const renderButtonSpy = vi.fn();
  window.google = {
    accounts: {
      id: {
        initialize: (options) => {
          googleCallback = options.callback;
        },
        renderButton: renderButtonSpy,
      },
    },
  };
  // The Google script is "already loaded": make the injected <script> resolve immediately.
  const append = vi.spyOn(document.head, "appendChild").mockImplementation((node) => {
    queueMicrotask(() => (node as HTMLScriptElement).onload?.(new Event("load")));
    return node;
  });

  renderButton();
  expect(await screen.findByText("or")).toBeInTheDocument();
  await vi.waitFor(() => expect(renderButtonSpy).toHaveBeenCalled());

  await act(async () => googleCallback?.({ credential: "google-id-token" }));
  expect(await screen.findByText("Dashboard page")).toBeInTheDocument();
  expect(authService.loginWithGoogle).toHaveBeenCalledWith("google-id-token");
  append.mockRestore();
});
