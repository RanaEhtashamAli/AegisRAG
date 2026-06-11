"use client";

import { useState, useCallback, useRef } from "react";
import { ragService } from "@/services/rag";
import type { SourceReference } from "@/types";

interface StreamState {
  answer: string;
  sources: SourceReference[];
  isStreaming: boolean;
  error: string | null;
}

export function useStream() {
  const [state, setState] = useState<StreamState>({
    answer: "",
    sources: [],
    isStreaming: false,
    error: null,
  });
  const abortRef = useRef<(() => void) | null>(null);

  const stream = useCallback((question: string, top_k = 5) => {
    setState({ answer: "", sources: [], isStreaming: true, error: null });

    const abort = ragService.streamQuery(
      question,
      top_k,
      (token) => setState((s) => ({ ...s, answer: s.answer + token })),
      (sources) => setState((s) => ({ ...s, sources: sources as SourceReference[] })),
      () => setState((s) => ({ ...s, isStreaming: false })),
      (msg) => setState((s) => ({ ...s, isStreaming: false, error: msg }))
    );

    abortRef.current = abort;
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.();
    setState((s) => ({ ...s, isStreaming: false }));
  }, []);

  return { ...state, stream, abort };
}
