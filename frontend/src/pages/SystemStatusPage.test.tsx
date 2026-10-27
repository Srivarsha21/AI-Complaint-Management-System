import { render, screen } from "@testing-library/react";
import { AxiosError } from "axios";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { fetchDatabaseHealth, fetchHealth } from "../services/healthService";
import SystemStatusPage from "./SystemStatusPage";

vi.mock("../services/healthService");

const mockedHealth = vi.mocked(fetchHealth);
const mockedDbHealth = vi.mocked(fetchDatabaseHealth);

function renderPage() {
  return render(
    <MemoryRouter>
      <SystemStatusPage />
    </MemoryRouter>,
  );
}

afterEach(() => vi.resetAllMocks());

test("shows online API and reachable database", async () => {
  mockedHealth.mockResolvedValue({ status: "ok", app: "Test App", environment: "test" });
  mockedDbHealth.mockResolvedValue({ status: "ok", database: "reachable" });

  renderPage();

  expect(await screen.findByText("Online")).toBeInTheDocument();
  expect(screen.getByText("Reachable")).toBeInTheDocument();
});

test("shows unreachable database", async () => {
  mockedHealth.mockResolvedValue({ status: "ok", app: "Test App", environment: "test" });
  mockedDbHealth.mockResolvedValue({ status: "unavailable", database: "unreachable" });

  renderPage();

  expect(await screen.findByText("Unreachable")).toBeInTheDocument();
});

test("shows a friendly error when the backend is down", async () => {
  mockedHealth.mockRejectedValue(new AxiosError("Network Error"));
  mockedDbHealth.mockRejectedValue(new AxiosError("Network Error"));

  renderPage();

  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
});
