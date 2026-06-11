import { create } from "zustand";
import type { ChatSession, ChatMessage } from "@/types";

interface StreamMessage {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

interface ChatState {
  activeSessions: ChatSession[];
  currentSessionId: string | null;
  messages: ChatMessage[];
  streamMessages: StreamMessage[];
  isStreaming: boolean;
  setCurrentSession: (id: string | null) => void;
  setMessages: (msgs: ChatMessage[]) => void;
  appendStreamToken: (token: string) => void;
  startStream: (userMessage: string) => void;
  finalizeStream: (assistantContent: string) => void;
  clearStream: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  activeSessions: [],
  currentSessionId: null,
  messages: [],
  streamMessages: [],
  isStreaming: false,

  setCurrentSession: (id) => set({ currentSessionId: id, streamMessages: [] }),
  setMessages: (msgs) => set({ messages: msgs, streamMessages: [] }),

  startStream: (userMessage) =>
    set({
      isStreaming: true,
      streamMessages: [
        { role: "user", content: userMessage },
        { role: "assistant", content: "", isStreaming: true },
      ],
    }),

  appendStreamToken: (token) =>
    set((state) => {
      const msgs = [...state.streamMessages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, content: last.content + token };
      }
      return { streamMessages: msgs };
    }),

  finalizeStream: (assistantContent) =>
    set((state) => {
      const msgs = [...state.streamMessages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant") {
        msgs[msgs.length - 1] = {
          ...last,
          content: assistantContent,
          isStreaming: false,
        };
      }
      return { streamMessages: msgs, isStreaming: false };
    }),

  clearStream: () => set({ streamMessages: [], isStreaming: false }),
}));
