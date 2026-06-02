import clsx from 'clsx'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { fetchEscalations, patchEscalationStatus } from '../../lib/api'
import type { EscalationTicketOut } from '../../lib/types'

type TicketStatus = 'open' | 'in_progress' | 'resolved'

const STATUS_STYLES: Record<TicketStatus, string> = {
  open:        'bg-red-100    text-red-700',
  in_progress: 'bg-amber-100  text-amber-700',
  resolved:    'bg-green-100  text-green-700',
}

const NEXT_STATUS: Record<TicketStatus, TicketStatus | null> = {
  open:        'in_progress',
  in_progress: 'resolved',
  resolved:    null,
}

const NEXT_LABEL: Record<TicketStatus, string> = {
  open:        'Claim',
  in_progress: 'Resolve',
  resolved:    '',
}

const FILTER_TABS: { label: string; value: TicketStatus | undefined }[] = [
  { label: 'Open',        value: 'open' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Resolved',    value: 'resolved' },
  { label: 'All',         value: undefined },
]

export function EscalationQueue() {
  const [tickets,  setTickets]  = useState<EscalationTicketOut[]>([])
  const [filter,   setFilter]   = useState<TicketStatus | undefined>('open')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)
  const [updating, setUpdating] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setTickets(await fetchEscalations(filter))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load escalations')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load])

  const advance = async (ticket: EscalationTicketOut) => {
    const next = NEXT_STATUS[ticket.status]
    if (!next) return
    setUpdating(ticket.id)
    try {
      const updated = await patchEscalationStatus(ticket.id, next)
      setTickets((prev) => prev.map((t) => t.id === updated.id ? updated : t))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed')
    } finally {
      setUpdating(null)
    }
  }

  return (
    <section className="mt-8">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-amber-500" />
          <h2 className="text-lg font-semibold text-gray-800">Escalation Queue</h2>
          {!loading && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
              {tickets.length}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Filter tabs */}
          <div className="flex rounded-lg border border-gray-200 bg-white overflow-hidden text-xs font-medium">
            {FILTER_TABS.map((tab) => (
              <button
                key={tab.label}
                onClick={() => setFilter(tab.value)}
                className={clsx(
                  'px-3 py-1.5 transition',
                  filter === tab.value
                    ? 'bg-brand-600 text-white'
                    : 'text-gray-600 hover:bg-gray-50',
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <button
            onClick={load}
            title="Refresh"
            className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 transition"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {error && (
        <p className="mb-3 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
      )}

      <div className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
        {loading && !tickets.length ? (
          <p className="px-4 py-6 text-center text-sm text-gray-400">Loading…</p>
        ) : tickets.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-gray-400">
            No {filter ?? ''} escalations.
          </p>
        ) : (
          <ul className="divide-y divide-gray-50">
            {tickets.map((ticket) => (
              <li key={ticket.id} className="px-4 py-3">
                {/* Header row */}
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <button
                      className="text-left text-sm font-medium text-gray-800 hover:text-brand-600 transition"
                      onClick={() => setExpanded((prev) => prev === ticket.id ? null : ticket.id)}
                    >
                      {ticket.reason}
                    </button>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-400">
                      <span className="font-mono">{ticket.session_id.slice(0, 12)}…</span>
                      <span>·</span>
                      <span>{new Date(ticket.created_at).toLocaleString()}</span>
                      {ticket.resolved_at && (
                        <>
                          <span>·</span>
                          <span>resolved {new Date(ticket.resolved_at).toLocaleString()}</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <span className={clsx('rounded-full px-2 py-0.5 text-xs font-medium', STATUS_STYLES[ticket.status])}>
                      {ticket.status.replace('_', ' ')}
                    </span>
                    {NEXT_STATUS[ticket.status] && (
                      <button
                        onClick={() => advance(ticket)}
                        disabled={updating === ticket.id}
                        className="rounded-lg bg-brand-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition"
                      >
                        {updating === ticket.id ? '…' : NEXT_LABEL[ticket.status]}
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded context */}
                {expanded === ticket.id && ticket.context_chunks && (
                  <div className="mt-3 rounded-xl bg-gray-50 p-3 text-xs text-gray-600">
                    {/* Prior turns */}
                    {Array.isArray((ticket.context_chunks as Record<string, unknown>).prior_turns) && (
                      <div className="mb-2">
                        <p className="mb-1 font-semibold text-gray-500">Prior turns</p>
                        <ul className="space-y-1">
                          {((ticket.context_chunks as Record<string, unknown[]>).prior_turns as Array<Record<string, string>>).map((turn, i) => (
                            <li key={i} className="flex gap-2">
                              <span className={clsx(
                                'shrink-0 rounded px-1 py-0.5 font-semibold',
                                turn.role === 'user' ? 'text-brand-600' : 'text-green-600',
                              )}>
                                {turn.role}
                              </span>
                              <span className="truncate">{turn.content}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {/* Retrieved sources */}
                    {Array.isArray((ticket.context_chunks as Record<string, unknown>).retrieved_sources) && (
                      <div>
                        <p className="mb-1 font-semibold text-gray-500">Retrieved sources</p>
                        <ul className="space-y-0.5">
                          {((ticket.context_chunks as Record<string, unknown[]>).retrieved_sources as Array<Record<string, unknown>>).map((src, i) => (
                            <li key={i} className="flex gap-2">
                              <span className="text-gray-400">#{i + 1}</span>
                              <span>sim={(src.similarity as number).toFixed(3)}</span>
                              <span className="truncate text-gray-500">{src.content_preview as string}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
