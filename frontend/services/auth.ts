import { api } from "@/lib/api";
import type { User } from "@/types";

export const authService = {
  async login(email: string, password: string): Promise<{ access_token: string }> {
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
};
