"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ragService } from "@/services/rag";
import type { ChatSession, ChatMessage, SourceReference } from "@/types";
import { cn } from "@/lib/utils";
import { Plus, Send, X, ChevronRight } from "lucide-react";

export default function ChatPage() {
  const qc = useQueryClient();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [streamAnswer, setStreamAnswer] = useState("");
  const [streamSources, setStreamSources] = useState<SourceReference[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<(() => void) | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: sessions = [] } = useQuery<ChatSession[]>({
    queryKey: ["chat-sessions"],
    queryFn: async () => {
      const { data } = await api.get("/chat/sessions");
      return data;
    },
  });

  const { data: messages = [], refetch: refetchMessages } = useQuery<ChatMessage[]>({
    queryKey: ["chat-messages", activeSessionId],
    queryFn: async () => {
      const { data } = await api.get(`/chat/sessions/${activeSessionId}/messages`);
      return data;
    },
    enabled: !!activeSessionId,
  });

  const createSession = useMutation({
    mutationFn: async () => {
      const { data } = await api.post("/chat/sessions", { title: "New Chat" });
      return data as ChatSession;
    },
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["chat-sessions"] });
      setActiveSessionId(s.id);
    },
  });

  const deleteSession = useMutation({
    mutationFn: (id: string) => api.delete(`/chat/sessions/${id}`),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["chat-sessions"] });
      if (activeSessionId === id) setActiveSessionId(null);
    },
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamAnswer]);

  // Cleanup stream on unmount
  useEffect(() => () => abortRef.current?.(), []);

  function handleSend() {
    if (!question.trim() || isStreaming || !activeSessionId) return;
    const q = question.trim();
    setQuestion("");
    setStreamAnswer("");
    setStreamSources([]);
    setIsStreaming(true);

    const abort = ragService.streamQuery(
      q,
      5,
      (token) => setStreamAnswer((prev) => prev + token),
      (sources) => setStreamSources(sources as SourceReference[]),
      () => {
        setIsStreaming(false);
        // Reload messages from DB so the persisted history is shown
        refetchMessages();
        setStreamAnswer("");
        setStreamSources([]);
      },
      (err) => {
        setIsStreaming(false);
        setStreamAnswer(`Error: ${err}`);
      },
      activeSessionId,
    );

    abortRef.current = abort;
  }

  return (
    <div className="flex flex-col h-full">
      <Header title="Chat" />
      <div className="flex flex-1 overflow-hidden">
        {/* Session list */}
        <aside className="w-56 border-r border-slate-200 bg-white flex flex-col shrink-0">
          <div className="p-3 border-b border-slate-200">
            <Button
              size="sm"
              className="w-full"
              onClick={() => createSession.mutate()}
              disabled={createSession.isPending}
            >
              <Plus className="mr-1 h-4 w-4" />
              New Chat
            </Button>
          </div>
          <ul className="flex-1 overflow-y-auto p-2 space-y-1">
            {sessions.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => {
                    setActiveSessionId(s.id);
                    setStreamAnswer("");
                    setStreamSources([]);
                  }}
                  className={cn(
                    "group flex w-full items-center justify-between rounded-md px-3 py-2 text-sm text-left transition-colors",
                    activeSessionId === s.id
                      ? "bg-slate-100 text-slate-900"
                      : "text-slate-600 hover:bg-slate-50"
                  )}
                >
                  <span className="truncate">{s.title}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("Delete session?")) deleteSession.mutate(s.id);
                    }}
                    className="hidden group-hover:block shrink-0"
                  >
                    <X className="h-3 w-3 text-slate-400" />
                  </button>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* Chat area */}
        <div className="flex flex-1 flex-col min-w-0">
          {!activeSessionId ? (
            <div className="flex flex-1 items-center justify-center text-slate-400">
              <div className="text-center space-y-2">
                <p className="text-lg font-medium">Select or create a chat session</p>
                <Button onClick={() => createSession.mutate()}>
                  <Plus className="mr-2 h-4 w-4" />
                  New Chat
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Persisted messages from DB */}
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={cn(
                      "flex",
                      m.role === "user" ? "justify-end" : "justify-start"
                    )}
                  >
                    <div
                      className={cn(
                        "max-w-2xl rounded-lg px-4 py-2 text-sm whitespace-pre-wrap",
                        m.role === "user"
                          ? "bg-slate-900 text-white"
                          : "bg-white border border-slate-200 text-slate-900"
                      )}
                    >
                      {m.content}
                    </div>
                  </div>
                ))}

                {/* Live streaming output */}
                {isStreaming && (
                  <div className="flex justify-start">
                    <div className="max-w-2xl rounded-lg px-4 py-2 text-sm bg-white border border-slate-200 text-slate-900 whitespace-pre-wrap">
                      {streamAnswer || <span className="animate-pulse text-slate-400">Thinking…</span>}
                    </div>
                  </div>
                )}

                {/* Sources shown after stream ends */}
                {!isStreaming && streamSources.length > 0 && (
                  <Card className="p-3">
                    <p className="text-xs font-semibold text-slate-500 mb-2">Sources</p>
                    <ul className="space-y-1">
                      {streamSources.map((s, i) => (
                        <li key={i} className="text-xs text-slate-600 flex items-start gap-1">
                          <ChevronRight className="h-3 w-3 mt-0.5 shrink-0" />
                          <span>
                            <span className="font-medium">{s.filename}</span>
                            {s.page_number ? ` p.${s.page_number}` : ""} — {s.text_preview}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}

                <div ref={messagesEndRef} />
              </div>

              <div className="border-t border-slate-200 bg-white p-4">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSend();
                  }}
                  className="flex gap-2"
                >
                  <Input
                    placeholder="Ask a question…"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    disabled={isStreaming}
                    className="flex-1"
                  />
                  {isStreaming ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        abortRef.current?.();
                        setIsStreaming(false);
                      }}
                    >
                      Stop
                    </Button>
                  ) : (
                    <Button type="submit" disabled={!question.trim() || !activeSessionId}>
                      <Send className="h-4 w-4" />
                    </Button>
                  )}
                </form>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
