import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { SESSION_EXPIRED_EVENT } from "../services/api";
import * as authService from "../services/authService";
import { tokenStorage } from "../services/tokenStorage";
import type { User } from "../types/auth";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  loginWithGoogle: (credential: string) => Promise<User>;
  register: (fullName: string, email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const setUser = useCallback((next: User | null) => {
    setUserState(next);
    setStatus(next ? "authenticated" : "anonymous");
  }, []);

  // Restore the session on page load.
  useEffect(() => {
    let cancelled = false;
    if (!tokenStorage.getAccessToken()) {
      setUser(null);
      return;
    }
    authService
      .fetchCurrentUser()
      .then((me) => !cancelled && setUser(me))
      .catch(() => {
        if (cancelled) return;
        tokenStorage.clear();
        setUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, [setUser]);

  // The API client signals when tokens can no longer be refreshed.
  useEffect(() => {
    const onExpired = () => setUser(null);
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [setUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const me = await authService.login(email, password);
      setUser(me);
      return me;
    },
    [setUser],
  );

  const loginWithGoogle = useCallback(
    async (credential: string) => {
      const me = await authService.loginWithGoogle(credential);
      setUser(me);
      return me;
    },
    [setUser],
  );

  const register = useCallback(
    async (fullName: string, email: string, password: string) => {
      await authService.register(fullName, email, password);
      return login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      setUser(null);
    }
  }, [setUser]);

  const value = useMemo(
    () => ({ status, user, login, loginWithGoogle, register, logout, setUser: (u: User) => setUser(u) }),
    [status, user, login, loginWithGoogle, register, logout, setUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
