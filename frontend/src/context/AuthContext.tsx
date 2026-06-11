import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setToken, setOnUnauthorized } from '@/lib/api';
import type { User } from '@/lib/types';

interface AuthContextValue {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<{ force_password_change: boolean }>;
  logout: () => void;
  isAuthenticated: boolean;
  sessionWarning: boolean;           // §6.6 — true when < warning threshold to expiry
  extendSession: () => Promise<void>; // §6.6 — call /auth/refresh to get new token
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Decode the `exp` claim (UTC seconds) from a JWT without verifying it. */
function getTokenExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return typeof payload.exp === 'number' ? payload.exp : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [sessionWarning, setSessionWarning] = useState(false);
  const navigate = useNavigate();

  // Refs for timers so they survive re-renders without stale closures
  const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const expiryTimerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimers = () => {
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (expiryTimerRef.current)  clearTimeout(expiryTimerRef.current);
  };

  const logout = useCallback(() => {
    clearTimers();
    setUser(null);
    setTokenState(null);
    setToken(null);
    setSessionWarning(false);
    void api.logout().catch(() => {});
    navigate('/login', { replace: true });
  }, [navigate]);

  /** Schedule the §6.6 warning and auto-logout based on the token's exp claim. */
  const scheduleSessionTimers = useCallback(
    (rawToken: string) => {
      clearTimers();
      setSessionWarning(false);

      const exp = getTokenExpiry(rawToken);
      if (!exp) return;

      const nowMs      = Date.now();
      const expiryMs   = exp * 1000;
      const msLeft     = expiryMs - nowMs;
      if (msLeft <= 0) { logout(); return; }

      // Read the admin-configurable warning threshold (default 2 minutes)
      const WARNING_MS = 2 * 60 * 1000; // fallback 2 min

      if (msLeft > WARNING_MS) {
        warningTimerRef.current = setTimeout(() => {
          setSessionWarning(true);
        }, msLeft - WARNING_MS);
      } else {
        // Already in the warning window
        setSessionWarning(true);
      }

      expiryTimerRef.current = setTimeout(() => {
        logout();
      }, msLeft);
    },
    [logout]
  );

  /** §6.6 — refresh the token so the user can continue without re-logging in. */
  const extendSession = useCallback(async () => {
    try {
      const resp = await api.refreshToken();
      setTokenState(resp.token);
      setToken(resp.token);
      if (resp.user) setUser(resp.user);
      setSessionWarning(false);
      scheduleSessionTimers(resp.token);
    } catch {
      logout();
    }
  }, [logout, scheduleSessionTimers]);

  useEffect(() => {
    setOnUnauthorized(() => {
      clearTimers();
      setUser(null);
      setTokenState(null);
      setToken(null);
      setSessionWarning(false);
      navigate('/login', { replace: true });
    });
  }, [navigate]);

  const login = useCallback(
    async (username: string, password: string) => {
      const response = await api.login(username, password);
      setTokenState(response.token);
      setToken(response.token);
      setUser(response.user);
      scheduleSessionTimers(response.token);
      return { force_password_change: response.user?.force_password_change ?? false };
    },
    [scheduleSessionTimers]
  );

  // Cleanup on unmount
  useEffect(() => () => clearTimers(), []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        logout,
        isAuthenticated: !!token && !!user,
        sessionWarning,
        extendSession,
      }}
    >
      {children}
      {/* §6.6 — Session expiry warning dialog */}
      {sessionWarning && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" />
          <div className="relative bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
                <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-900">Session expiring soon</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Your session is about to expire. Click <strong>Stay Logged In</strong> to continue, or you will be logged out automatically.
                </p>
              </div>
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={logout}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Log out
              </button>
              <button
                onClick={extendSession}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg"
              >
                Stay Logged In
              </button>
            </div>
          </div>
        </div>
      )}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
