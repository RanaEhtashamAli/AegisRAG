import { api, streamUrl } from "@/lib/api";
import type { RAGQueryResponse } from "@/types";

export const ragService = {
  async query(question: string, top_k = 5): Promise<RAGQueryResponse> {
    const { data } = await api.post("/rag/query", { question, top_k });
    return data;
  },

  streamQuery(
    question: string,
    top_k = 5,
    onToken: (token: string) => void,
    onSources: (sources: unknown[]) => void,
    onDone: () => void,
    onError: (msg: string) => void,
    session_id?: string,
  ): () => void {
    const token = typeof window !== "undefined" ? localStorage.getItem("aegis_token") : null;
    const url = streamUrl("/rag/query-stream");

    const controller = new AbortController();

    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ question, top_k, session_id: session_id ?? null }),
      signal: controller.signal,
    }).then(async (res) => {
      if (!res.ok) {
        if (res.status === 401 && typeof window !== "undefined") {
          localStorage.removeItem("aegis_token");
          window.location.href = "/login";
          return;
        }
        onError(`HTTP ${res.status}`);
        return;
      }
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "token") onToken(event.content);
            else if (event.type === "sources") onSources(event.sources ?? []);
            else if (event.type === "done") onDone();
            else if (event.type === "error") onError(event.content ?? "Unknown error");
          } catch {
            // ignore malformed lines
          }
        }
      }
    }).catch((err) => {
      if (err.name !== "AbortError") onError(String(err));
    });

    return () => controller.abort();
  },
};
