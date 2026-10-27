import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AuthProvider } from "../hooks/useAuth";

/** Renders `element` at `path` inside AuthProvider with a router; extra routes show their names. */
export function renderWithAuth(element: ReactElement, { path = "/", route = "/" }: { path?: string; route?: string } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <Routes>
          <Route path={path} element={element} />
          <Route path="/app" element={<p>Dashboard page</p>} />
          <Route path="/login" element={<p>Login page</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}
