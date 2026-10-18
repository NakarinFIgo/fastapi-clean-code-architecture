import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import * as api from "../api/auth_service";
import { setSessionExpiredHandler } from "../../../shared/api/client";
import { clearTokens, loadTokens, saveTokens } from "../../../shared/api/token_store";
import type { User } from "../dto/types";

interface AuthState {
  user: User | null;
  /** true while a saved session is being checked on first load */
  restoring: boolean;
  /** set when the session ended because the tokens stopped working */
  expired: boolean;
  login(email: string, password: string): Promise<void>;
  logout(): Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [restoring, setRestoring] = useState(() => loadTokens() !== null);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      setExpired(true);
    });
  }, []);

  // Restore a saved session (page reload) by asking the API who we are.
  useEffect(() => {
    if (!restoring) return;
    let cancelled = false;
    api
      .profile()
      .then((u) => !cancelled && setUser(u))
      .catch(() => clearTokens())
      .finally(() => !cancelled && setRestoring(false));
    return () => {
      cancelled = true;
    };
  }, [restoring]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    saveTokens(res.token);
    setExpired(false);
    setUser(res.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* the local session ends either way */
    }
    clearTokens();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, restoring, expired, login, logout }),
    [user, restoring, expired, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
