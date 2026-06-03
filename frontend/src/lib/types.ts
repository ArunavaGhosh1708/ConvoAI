// ---------------------------------------------------------------------------
// Shared domain types mirroring the backend Pydantic schemas
// ---------------------------------------------------------------------------

export interface SourceChunk {
  chunk_id: string
  document_id: string
  content_preview: string
  similarity: number
}

export interface EscalationPayload {
  conversation_id: string
  session_id: string
  channel: string
  escalation_reason: string
  prior_turns: Record<string, string>[]
  retrieved_sources: Record<string, unknown>[]
  escalated_at: string
}

// SSE event payloads
export interface SSETokenEvent   { token: string }
export interface SSESourcesEvent { chunks: SourceChunk[] }
export interface SSEDoneEvent {
  session_id: string
  conversation_id: string
  confidence: number
  escalated: boolean
  escalation_payload?: EscalationPayload | null
}

export type SSEEvent =
  | { event: 'token';   data: SSETokenEvent }
  | { event: 'sources'; data: SSESourcesEvent }
  | { event: 'done';    data: SSEDoneEvent }
  | { event: 'error';   data: { detail: string } }

// Chat UI message
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceChunk[]
  confidence?: number
  escalated?: boolean
  /** true while waiting for the first token */
  isTyping: boolean
  /** true while tokens are arriving */
  isStreaming: boolean
  timestamp: Date
}

// Admin / metrics
export interface MetricsResponse {
  total_sessions:  number
  active_sessions: number
  resolution_rate: number   // 0–100
  escalation_rate: number   // 0–100
  avg_confidence:  number   // 0–1
  avg_response_ms: number   // ms, last 24 h
  refreshed_at:    string
}

export interface ReviewQueueItem {
  conversation_id: string
  user_id: string
  channel: string
  avg_confidence: number
  message_count: number
  created_at: string
}

export interface VoiceConfig {
  voice_id: string
  speed:    number
  model:    string
}

export interface TranscriptionResponse {
  text:        string
  duration_ms: number
}

export interface MessageOut {
  id: string
  role: string
  content: string
  sources?: SourceChunk[] | null
  confidence?: number | null
  created_at: string
}

export interface ConversationOut {
  id: string
  user_id: string
  channel: string
  status: string
  created_at: string
  resolved_at?: string | null
  resolution_score?: number | null
  messages: MessageOut[]
}

export interface DocumentOut {
  id: string
  filename: string
  file_type: string
  status: 'pending' | 'processing' | 'indexed' | 'failed'
  chunk_count: number
  created_at: string
}

export interface EscalationTicketOut {
  id: string
  conversation_id: string
  session_id: string
  reason: string
  status: 'open' | 'in_progress' | 'resolved'
  context_chunks: Record<string, unknown> | null
  created_at: string
  resolved_at: string | null
}
