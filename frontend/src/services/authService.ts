import type { AuthResponse, TokenPair, User } from "../types/auth";
import { api } from "./api";
import { tokenStorage } from "./tokenStorage";

export async function login(email: string, password: string): Promise<User> {
  const { data } = await api.post<AuthResponse>("/auth/login", { email, password });
  tokenStorage.save(data);
  return data.user;
}

/** Public sign-in options; `google_client_id` is null when Google sign-in is not configured. */
export async function getAuthConfig(): Promise<{ google_client_id: string | null }> {
  const { data } = await api.get<{ google_client_id: string | null }>("/auth/config");
  return data;
}

/** Exchanges a Google ID token (verified by the backend) for our own session tokens. */
export async function loginWithGoogle(credential: string): Promise<User> {
  const { data } = await api.post<AuthResponse>("/auth/google", { credential });
  tokenStorage.save(data);
  return data.user;
}

export async function register(fullName: string, email: string, password: string): Promise<User> {
  const { data } = await api.post<User>("/auth/register", { full_name: fullName, email, password });
  return data;
}

export async function logout(): Promise<void> {
  const refreshToken = tokenStorage.getRefreshToken();
  try {
    if (tokenStorage.getAccessToken()) {
      await api.post("/auth/logout", { refresh_token: refreshToken });
    }
  } finally {
    // Sign out locally even if the server call fails.
    tokenStorage.clear();
  }
}

export async function requestPasswordReset(email: string): Promise<string> {
  const { data } = await api.post<{ message: string }>("/auth/forgot-password", { email });
  return data.message;
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await api.post("/auth/reset-password", { token, new_password: newPassword });
}

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await api.get<User>("/users/me");
  return data;
}

export async function updateProfile(fullName: string): Promise<User> {
  const { data } = await api.patch<User>("/users/me", { full_name: fullName });
  return data;
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const { data } = await api.post<TokenPair>("/users/me/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
  // Old tokens are now invalid server-side; keep this session alive with the new ones.
  tokenStorage.save(data);
}
