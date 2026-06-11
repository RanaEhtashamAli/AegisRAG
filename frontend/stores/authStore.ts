import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";

interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setAuth: (token, user) => {
        if (typeof window !== "undefined") {
          localStorage.setItem("aegis_token", token);
          document.cookie = `aegis_token=${token}; path=/; max-age=3600`;
        }
        set({ token, user });
      },
      clearAuth: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("aegis_token");
          document.cookie = "aegis_token=; path=/; max-age=0";
        }
        set({ token: null, user: null });
      },
    }),
    { name: "aegis-auth" }
  )
);
