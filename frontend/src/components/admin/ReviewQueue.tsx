import clsx from 'clsx'
import { Eye, RefreshCw, ShieldAlert } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { fetchReviewQueue } from '../../lib/api'
import type { ReviewQueueItem } from '../../lib/types'

function ConfidenceBadge({ value }: { value: number }) {
  const pct = (value * 100).toFixed(0)
  return (
    <span className={clsx(
      'rounded-full px-2 py-0.5 text-xs font-medium tabular-nums',
      value < 0.4  ? 'bg-red-100 text-red-700'
      : value < 0.55 ? 'bg-amber-100 text-amber-700'
      : 'bg-yellow-100 text-yellow-700',
    )}>
      {pct}%
    </span>
  )
}

export function ReviewQueue() {
  const [items,   setItems]   = useState<ReviewQueueItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setItems(await fetchReviewQueue())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load review queue')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <section className="mt-8">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 text-red-500" />
          <h2 className="text-lg font-semibold text-gray-800">Low-Confidence Review Queue</h2>
          {!loading && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
              {items.length}
            </span>
          )}
        </div>
        <button
          onClick={load}
          title="Refresh"
          className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      <p className="mb-3 text-xs text-gray-400">
        Sessions whose average retrieval confidence is below the escalation threshold and have not yet been escalated.
      </p>

      {error && (
        <p className="mb-3 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
      )}

      <div className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
        {loading && !items.length ? (
          <p className="px-4 py-6 text-center text-sm text-gray-400">Loading…</p>
        ) : items.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-gray-400">
            No sessions below confidence threshold.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs font-medium text-gray-500">
                <th className="px-4 py-3 text-left">Conversation ID</th>
                <th className="px-4 py-3 text-left">Channel</th>
                <th className="px-4 py-3 text-center">Avg Confidence</th>
                <th className="px-4 py-3 text-right">Messages</th>
                <th className="px-4 py-3 text-right">Started</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {items.map((item) => (
                <tr key={item.conversation_id} className="hover:bg-gray-50/60 transition">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">
                    {item.conversation_id.slice(0, 12)}…
                  </td>
                  <td className="px-4 py-3 text-xs uppercase text-gray-500">{item.channel}</td>
                  <td className="px-4 py-3 text-center">
                    <ConfidenceBadge value={item.avg_confidence} />
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-600">
                    {item.message_count}
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-gray-400 whitespace-nowrap">
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <a
                      href={`/admin?transcript=${item.conversation_id}`}
                      title="View transcript"
                      className="inline-flex rounded p-1 text-gray-400 hover:bg-brand-50 hover:text-brand-600 transition"
                    >
                      <Eye className="h-4 w-4" />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
