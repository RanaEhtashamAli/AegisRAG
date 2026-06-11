import { api } from "@/lib/api";
import type { AuditEvent } from "@/types";

export const auditService = {
  async list(params?: {
    event_type?: string;
    entity_type?: string;
    user_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<AuditEvent[]> {
    const { data } = await api.get("/audit/events", { params });
    return data;
  },
};
