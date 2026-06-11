import { api } from "@/lib/api";
import type { Document, PiiFinding } from "@/types";

export const documentsService = {
  async list(): Promise<Document[]> {
    const { data } = await api.get("/documents");
    return data;
  },

  async get(id: string): Promise<Document> {
    const { data } = await api.get(`/documents/${id}`);
    return data;
  },

  async upload(file: File, classification: string): Promise<Document> {
    const form = new FormData();
    form.append("file", file);
    form.append("classification", classification);
    const { data } = await api.post("/documents/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  async updateClassification(id: string, classification: string): Promise<Document> {
    const { data } = await api.patch(`/documents/${id}/classification`, { classification });
    return data;
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/documents/${id}`);
  },

  async reindex(id: string): Promise<void> {
    await api.post(`/documents/${id}/reindex`);
  },

  async piiFindings(id: string): Promise<PiiFinding[]> {
    const { data } = await api.get(`/documents/${id}/pii-findings`);
    return data;
  },
};
