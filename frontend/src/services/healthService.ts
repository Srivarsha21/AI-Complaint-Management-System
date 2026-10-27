import type { DatabaseHealthResponse, HealthResponse } from "../types/health";
import { api } from "./api";

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
}

export async function fetchDatabaseHealth(): Promise<DatabaseHealthResponse> {
  // A 503 still carries a useful body, so don't treat it as an exception.
  const { data } = await api.get<DatabaseHealthResponse>("/health/db", {
    validateStatus: (status) => status === 200 || status === 503,
  });
  return data;
}
