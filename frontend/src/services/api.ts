import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import type { TokenPair } from "../types/auth";
import { tokenStorage } from "./tokenStorage";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

/** Shared HTTP client: attaches the access token and refreshes it once on 401. */
export const api = axios.create({ baseURL, timeout: 15000 });

/** Fired when the session can no longer be renewed; AuthProvider listens for it. */
export const SESSION_EXPIRED_EVENT = "resolveai:session-expired";

// Requests where a 401 means "bad credentials", not "expired session".
const NO_REFRESH_PATHS = ["/auth/login", "/auth/google", "/auth/register", "/auth/refresh", "/auth/forgot-password", "/auth/reset-password"];

api.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) return null;
  try {
    // Plain axios: must not go through the interceptors above.
    const { data } = await axios.post<TokenPair>(`${baseURL}/auth/refresh`, { refresh_token: refreshToken });
    tokenStorage.save(data);
    return data.access_token;
  } catch {
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const isAuthCall = NO_REFRESH_PATHS.some((path) => original?.url?.startsWith(path));

    if (error.response?.status !== 401 || !original || original._retried || isAuthCall) {
      throw error;
    }

    original._retried = true;
    // Concurrent 401s share one refresh (refresh tokens are single-use).
    refreshInFlight ??= refreshAccessToken().finally(() => {
      refreshInFlight = null;
    });
    const newToken = await refreshInFlight;

    if (!newToken) {
      tokenStorage.clear();
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
      throw error;
    }
    original.headers.Authorization = `Bearer ${newToken}`;
    return api(original);
  },
);

/** Turns any API/network failure into a message safe to show users. */
export function getErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    if (!error.response) return "Cannot reach the server. Check that the backend is running.";
    const detail = (error.response.data as { detail?: unknown })?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      // FastAPI validation errors: show the first readable message.
      const msg = String((detail[0] as { msg?: string }).msg ?? "");
      return msg.replace(/^Value error, /, "") || "Please check the form and try again.";
    }
    if (error.response.status === 429) return "Too many attempts. Please wait a minute and try again.";
    return `Request failed (${error.response.status}).`;
  }
  return "Something went wrong. Please try again.";
}
