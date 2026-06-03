import type { ConversationOut, DocumentOut, EscalationTicketOut, MetricsResponse, ReviewQueueItem, TranscriptionResponse, VoiceConfig } from './types'

const BASE      = import.meta.env.VITE_API_URL  ?? ''
const API_KEY   = import.meta.env.VITE_API_KEY  ?? 'dev-api-key'
const ADMIN_JWT = import.meta.env.VITE_ADMIN_JWT ?? ''

// ---------------------------------------------------------------------------
// Chat  (returns raw Response so the caller can stream it)
// ---------------------------------------------------------------------------

export interface ChatPayload {
  session_id: string
  message: string
  channel?: 'chat' | 'voice'
  stream?: boolean
}

export function chatStream(payload: ChatPayload): Promise<Response> {
  return fetch(`${BASE}/api/v1/chat`, {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key':    API_KEY,
    },
    body: JSON.stringify({ stream: true, channel: 'chat', ...payload }),
  })
}

// ---------------------------------------------------------------------------
// Conversations (JWT-protected)
// ---------------------------------------------------------------------------

function adminHeaders(): HeadersInit {
  return { Authorization: `Bearer ${ADMIN_JWT}` }
}

export async function fetchConversation(id: string): Promise<ConversationOut> {
  const res = await fetch(`${BASE}/api/v1/conversations/${id}`, {
    headers: adminHeaders(),
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export async function fetchMetrics(): Promise<MetricsResponse> {
  const res = await fetch(`${BASE}/api/v1/admin/metrics`, {
    headers: adminHeaders(),
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Voice (API-key-protected)
// ---------------------------------------------------------------------------

/** Upload audio blob and return the Whisper transcription text. */
export async function transcribeAudio(blob: Blob, mimeType: string): Promise<TranscriptionResponse> {
  const ext  = mimeType.split('/')[1]?.split(';')[0] ?? 'webm'
  const form = new FormData()
  form.append('audio', blob, `recording.${ext}`)

  const res = await fetch(`${BASE}/api/v1/voice/transcribe`, {
    method:  'POST',
    headers: { 'X-API-Key': API_KEY },
    body:    form,
  })
  if (!res.ok) throw new Error(`Transcription failed: ${res.status}`)
  return res.json()
}

/** Synthesize text and return the full MP3 audio blob. */
export async function synthesizeAudio(text: string): Promise<Blob> {
  const res = await fetch(`${BASE}/api/v1/voice/synthesize`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
    body:    JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`TTS failed: ${res.status}`)
  return res.blob()
}

export async function fetchVoiceConfig(): Promise<VoiceConfig> {
  const res = await fetch(`${BASE}/api/v1/admin/voice-config`, {
    headers: adminHeaders(),
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export async function updateVoiceConfig(config: Partial<VoiceConfig>): Promise<VoiceConfig> {
  const res = await fetch(`${BASE}/api/v1/admin/voice-config`, {
    method:  'PUT',
    headers: { ...adminHeaders(), 'Content-Type': 'application/json' },
    body:    JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Documents (admin JWT-protected)
// ---------------------------------------------------------------------------

export async function fetchDocuments(
  filters: { category?: string; product?: string; version?: string } = {},
): Promise<DocumentOut[]> {
  const url = new URL(`${BASE}/api/v1/admin/documents`, window.location.origin)
  if (filters.category) url.searchParams.set('category', filters.category)
  if (filters.product)  url.searchParams.set('product',  filters.product)
  if (filters.version)  url.searchParams.set('version',  filters.version)
  const res = await fetch(url.toString(), { headers: adminHeaders() })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export async function uploadDocuments(
  files: File[],
  meta: { category?: string; product?: string; version?: string } = {},
): Promise<{ documents: DocumentOut[]; message: string }> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  if (meta.category) form.append('category', meta.category)
  if (meta.product)  form.append('product',  meta.product)
  if (meta.version)  form.append('version',  meta.version)

  const res = await fetch(`${BASE}/api/v1/admin/documents`, {
    method:  'POST',
    headers: adminHeaders(),   // no Content-Type — browser sets multipart boundary
    body:    form,
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/admin/documents/${id}`, {
    method:  'DELETE',
    headers: adminHeaders(),
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
}

// ---------------------------------------------------------------------------
// Escalation tickets (admin JWT-protected)
// ---------------------------------------------------------------------------

export async function fetchEscalations(
  status?: 'open' | 'in_progress' | 'resolved',
): Promise<EscalationTicketOut[]> {
  const url = new URL(`${BASE}/api/v1/admin/escalations`, window.location.origin)
  if (status) url.searchParams.set('status', status)
  const res = await fetch(url.toString(), { headers: adminHeaders() })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export async function patchEscalationStatus(
  id: string,
  status: 'open' | 'in_progress' | 'resolved',
): Promise<EscalationTicketOut> {
  const res = await fetch(`${BASE}/api/v1/admin/escalations/${id}`, {
    method:  'PATCH',
    headers: { ...adminHeaders(), 'Content-Type': 'application/json' },
    body:    JSON.stringify({ status }),
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Review queue — low-confidence sessions (admin JWT-protected)
// ---------------------------------------------------------------------------

export async function fetchReviewQueue(): Promise<ReviewQueueItem[]> {
  const res = await fetch(`${BASE}/api/v1/admin/review-queue`, {
    headers: adminHeaders(),
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}
