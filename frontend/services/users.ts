import { api } from "@/lib/api";
import type { User, InviteResponse } from "@/types";

export const usersService = {
  async list(): Promise<User[]> {
    const { data } = await api.get("/users");
    return data;
  },

  async invite(email: string, role: string, full_name?: string): Promise<InviteResponse> {
    const { data } = await api.post("/users/invite", { email, role, full_name });
    return data;
  },

  async acceptInvite(token: string, password: string, full_name?: string) {
    const { data } = await api.post("/users/accept-invite", { token, password, full_name });
    return data;
  },

  async updateRole(id: string, role: string): Promise<User> {
    const { data } = await api.patch(`/users/${id}/role`, { role });
    return data;
  },

  async deactivate(id: string): Promise<void> {
    await api.delete(`/users/${id}`);
  },
};
