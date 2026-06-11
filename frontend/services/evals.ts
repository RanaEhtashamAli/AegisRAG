import { api } from "@/lib/api";
import type { EvalRun } from "@/types";

export const evalsService = {
  async list(): Promise<EvalRun[]> {
    const { data } = await api.get("/evals/runs");
    return data;
  },

  async get(id: string): Promise<EvalRun> {
    const { data } = await api.get(`/evals/runs/${id}`);
    return data;
  },
};
