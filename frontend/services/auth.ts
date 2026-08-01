import { api } from "@/lib/api";
import type { User } from "@/types";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

export const authService = {
  async login(email: string, password: string): Promise<TokenPair> {
    const { data } = await api.post("/auth/login", { email, password });
    return data;
  },

  async register(email: string, password: string, full_name: string) {
    const { data } = await api.post("/auth/register", { email, password, full_name });
    return data;
  },

  async me(): Promise<User> {
    const { data } = await api.get("/auth/me");
    return data;
  },

  async refresh(refreshToken: string): Promise<TokenPair> {
    // Deliberately a plain axios call, not `api` — refresh must never itself
    // go through the 401-triggers-refresh interceptor (that would recurse).
    const { data } = await api.post(
      "/auth/refresh",
      { refresh_token: refreshToken },
      { headers: { "X-Skip-Auth-Refresh": "1" } }
    );
    return data;
  },

  async logout(refreshToken: string): Promise<void> {
    await api.post(
      "/auth/logout",
      { refresh_token: refreshToken },
      { headers: { "X-Skip-Auth-Refresh": "1" } }
    );
  },
};
