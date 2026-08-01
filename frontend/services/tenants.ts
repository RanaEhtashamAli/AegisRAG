import { api } from "@/lib/api";
import type { Tenant } from "@/types";

export const tenantsService = {
  async create(name: string, slug: string): Promise<Tenant> {
    const { data } = await api.post("/tenants", { name, slug });
    return data;
  },
};
