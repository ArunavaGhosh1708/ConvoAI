import { create } from 'zustand'
import { v4 as uuid } from 'uuid'
import type { ChatMessage, SourceChunk } from '../lib/types'

interface ChatStore {
  sessionId:   string
  messages:    ChatMessage[]
  isTyping:    boolean   // waiting for first token after send
  isStreaming: boolean   // tokens arriving

  addUserMessage:       (content: string) => void
  addTypingPlaceholder: () => string         // returns the placeholder id
  appendToken:          (id: string, token: string) => void
  finaliseMessage:      (id: string, opts: {
    sources?:    SourceChunk[]
    confidence?: number
    escalated?:  boolean
  }) => void
  setTyping:    (v: boolean) => void
  setStreaming: (v: boolean) => void
  failMessage:  (id: string, text: string) => void
  reset:        () => void
}

const INITIAL_SESSION = uuid()

export const useChatStore = create<ChatStore>((set) => ({
  sessionId:   INITIAL_SESSION,
  messages:    [],
  isTyping:    false,
  isStreaming: false,

  addUserMessage: (content) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { id: uuid(), role: 'user', content, isTyping: false, isStreaming: false, timestamp: new Date() },
      ],
    })),

  addTypingPlaceholder: () => {
    const id = uuid()
    set((s) => ({
      messages: [
        ...s.messages,
        { id, role: 'assistant', content: '', isTyping: true, isStreaming: false, timestamp: new Date() },
      ],
      isTyping: true,
    }))
    return id
  },

  appendToken: (id, token) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id
          ? { ...m, content: m.content + token, isTyping: false, isStreaming: true }
          : m
      ),
      isTyping:    false,
      isStreaming: true,
    })),

  finaliseMessage: (id, { sources, confidence, escalated }) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id
          ? { ...m, sources, confidence, escalated, isTyping: false, isStreaming: false }
          : m
      ),
      isStreaming: false,
    })),

  setTyping:    (v) => set({ isTyping: v }),
  setStreaming: (v) => set({ isStreaming: v }),

  failMessage: (id, text) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id
          ? { ...m, content: text, isTyping: false, isStreaming: false }
          : m
      ),
      isTyping:    false,
      isStreaming: false,
    })),

  reset: () =>
    set({ messages: [], isTyping: false, isStreaming: false, sessionId: uuid() }),
}))
