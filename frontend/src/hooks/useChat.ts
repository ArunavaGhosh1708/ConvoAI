import { useCallback } from 'react'
import { chatStream } from '../lib/api'
import { parseSSE } from '../lib/sse'
import { useChatStore } from '../store/chatStore'

const FALLBACK = "I'm sorry, something went wrong. Please try again."

export function useChat() {
  const store = useChatStore()

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || store.isStreaming || store.isTyping) return

    // 1. Add user bubble
    store.addUserMessage(text)

    // 2. Add typing placeholder — captures the placeholder's ID
    const placeholderId = store.addTypingPlaceholder()

    try {
      const response = await chatStream({
        session_id: store.sessionId,
        message:    text,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      for await (const sseEvent of parseSSE(response)) {
        if (sseEvent.event === 'token') {
          store.appendToken(placeholderId, sseEvent.data.token)
        } else if (sseEvent.event === 'sources') {
          // sources arrive before 'done' — attach them early so they show up
          store.finaliseMessage(placeholderId, { sources: sseEvent.data.chunks })
        } else if (sseEvent.event === 'done') {
          store.finaliseMessage(placeholderId, {
            confidence: sseEvent.data.confidence,
            escalated:  sseEvent.data.escalated,
          })
        } else if (sseEvent.event === 'error') {
          store.failMessage(placeholderId, sseEvent.data.detail ?? FALLBACK)
          return
        }
      }
    } catch {
      store.failMessage(placeholderId, FALLBACK)
    }
  }, [store])

  return {
    messages:    store.messages,
    isTyping:    store.isTyping,
    isStreaming: store.isStreaming,
    sessionId:   store.sessionId,
    sendMessage,
    reset:       store.reset,
  }
}
