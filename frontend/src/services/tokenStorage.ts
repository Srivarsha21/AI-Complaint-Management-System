import type { TokenPair } from "../types/auth";

/**
 * Persists tokens in localStorage so a page refresh keeps the user signed in.
 * Trade-off: localStorage is readable by injected scripts, so access tokens are
 * short-lived (30 min), refresh tokens rotate, and logout revokes both server-side.
 */
const ACCESS_KEY = "resolveai.access_token";
const REFRESH_KEY = "resolveai.refresh_token";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export const tokenStorage = {
  getAccessToken: () => read(ACCESS_KEY),
  getRefreshToken: () => read(REFRESH_KEY),
  save(tokens: Pick<TokenPair, "access_token" | "refresh_token">) {
    try {
      localStorage.setItem(ACCESS_KEY, tokens.access_token);
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    } catch {
      // Storage unavailable (private mode): the session lasts until reload.
    }
  },
  clear() {
    try {
      localStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
    } catch {
      // ignore
    }
  },
};
