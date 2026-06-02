import { Search } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import clsx from 'clsx'
import { fetchConversation } from '../../lib/api'
import type { ConversationOut } from '../../lib/types'

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active:    'bg-blue-100 text-blue-700',
    resolved:  'bg-green-100 text-green-700',
    escalated: 'bg-amber-100 text-amber-700',
  }
  return (
    <span className={clsx('rounded-full px-2 py-0.5 text-xs font-medium', styles[status] ?? 'bg-gray-100 text-gray-600')}>
      {status}
    </span>
  )
}

export function TranscriptViewer() {
  const [query,        setQuery]       = useState('')
  const [conversation, setConversation] = useState<ConversationOut | null>(null)
  const [loading,      setLoading]     = useState(false)
  const [error,        setError]       = useState<string | null>(null)

  const lookup = async (e: FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await fetchConversation(query.trim())
      setConversation(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Not found')
      setConversation(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="mt-8">
      <h2 className="mb-4 text-lg font-semibold text-gray-800">Conversation Transcript</h2>

      {/* Search bar */}
      <form onSubmit={lookup} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Conversation UUID…"
            className="w-full rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition"
        >
          {loading ? 'Loading…' : 'Lookup'}
        </button>
      </form>

      {error && (
        <p className="mt-3 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
      )}

      {/* Transcript */}
      {conversation && (
        <div className="mt-4 rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
          {/* Meta bar */}
          <div className="flex flex-wrap items-center gap-4 border-b border-gray-100 px-4 py-3 text-xs text-gray-500">
            <span className="font-mono text-gray-400">{conversation.id}</span>
            <StatusBadge status={conversation.status} />
            <span>{conversation.channel}</span>
            <span>{new Date(conversation.created_at).toLocaleString()}</span>
            {conversation.resolution_score != null && (
              <span>confidence: {(conversation.resolution_score * 100).toFixed(0)}%</span>
            )}
          </div>

          {/* Messages */}
          <div className="max-h-[480px] divide-y divide-gray-50 overflow-y-auto">
            {conversation.messages.map((msg) => (
              <div key={msg.id} className="flex gap-3 px-4 py-3">
                <span
                  className={clsx(
                    'mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold',
                    msg.role === 'user'
                      ? 'bg-brand-100 text-brand-700'
                      : msg.role === 'assistant'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-500'
                  )}
                >
                  {msg.role}
                </span>
                <div className="flex-1">
                  <p className="text-sm text-gray-800 whitespace-pre-wrap">{msg.content}</p>
                  {msg.confidence != null && (
                    <p className="mt-0.5 text-xs text-gray-400">
                      confidence: {(msg.confidence * 100).toFixed(0)}%
                    </p>
                  )}
                </div>
                <span className="shrink-0 text-xs text-gray-400">
                  {new Date(msg.created_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
