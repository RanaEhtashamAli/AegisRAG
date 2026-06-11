"use client";

import { useAuthStore } from "@/stores/authStore";
import { authService } from "@/services/auth";
import { useRouter } from "next/navigation";

export function useAuth() {
  const { token, user, setAuth, clearAuth } = useAuthStore();
  const router = useRouter();

  async function login(email: string, password: string) {
    const { access_token } = await authService.login(email, password);
    if (typeof window !== "undefined") {
      localStorage.setItem("aegis_token", access_token);
    }
    const me = await authService.me();
    setAuth(access_token, me);
    router.push("/dashboard");
  }

  function logout() {
    clearAuth();
    router.push("/login");
  }

  return { token, user, login, logout, isAuthenticated: !!token };
}
