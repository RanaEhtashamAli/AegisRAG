import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";

// Matches the backend's REFRESH_TOKEN_EXPIRE_DAYS (7 days). The cookie only
// gates client-side routing (middleware.ts) — the real auth boundary is the
// backend validating the JWT/refresh token on every request — so it's fine
// for this to be long-lived; a session refreshed at least once a week never
// hits this ceiling.
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

function setAuthCookie(token: string) {
  if (typeof window !== "undefined") {
    document.cookie = `aegis_token=${token}; path=/; max-age=${COOKIE_MAX_AGE_SECONDS}`;
  }
}

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  setAuth: (token: string, refreshToken: string, user: User) => void;
  setTokens: (token: string, refreshToken: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      user: null,
      setAuth: (token, refreshToken, user) => {
        if (typeof window !== "undefined") {
          localStorage.setItem("aegis_token", token);
          setAuthCookie(token);
        }
        set({ token, refreshToken, user });
      },
      setTokens: (token, refreshToken) => {
        if (typeof window !== "undefined") {
          localStorage.setItem("aegis_token", token);
          setAuthCookie(token);
        }
        set({ token, refreshToken });
      },
      clearAuth: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("aegis_token");
          document.cookie = "aegis_token=; path=/; max-age=0";
        }
        set({ token: null, refreshToken: null, user: null });
      },
    }),
    { name: "aegis-auth" }
  )
);
