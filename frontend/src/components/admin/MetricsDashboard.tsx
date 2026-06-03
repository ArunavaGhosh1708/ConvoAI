import { Activity, AlertTriangle, CheckCircle, Clock, MessageSquare, RefreshCw } from 'lucide-react'
import { useMetrics } from '../../hooks/useMetrics'
import { MetricsCard } from './MetricsCard'

export function MetricsDashboard() {
  const { metrics, loading, error, refresh } = useMetrics()

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">Live Metrics</h2>
        <button
          onClick={refresh}
          title="Refresh now"
          className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {error && (
        <p className="mb-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <MetricsCard
          label="Total Sessions"
          value={metrics?.total_sessions ?? '—'}
          sub={`${metrics?.active_sessions ?? 0} active now`}
          icon={<MessageSquare className="h-5 w-5" />}
          accent="blue"
          loading={loading}
        />
        <MetricsCard
          label="Resolution Rate"
          value={metrics ? `${metrics.resolution_rate.toFixed(1)}%` : '—'}
          sub="Target ≥ 87%"
          icon={<CheckCircle className="h-5 w-5" />}
          accent="green"
          loading={loading}
        />
        <MetricsCard
          label="Escalation Rate"
          value={metrics ? `${metrics.escalation_rate.toFixed(1)}%` : '—'}
          sub="Target ≤ 13%"
          icon={<AlertTriangle className="h-5 w-5" />}
          accent="amber"
          loading={loading}
        />
        <MetricsCard
          label="Avg Confidence"
          value={metrics ? `${(metrics.avg_confidence * 100).toFixed(0)}%` : '—'}
          sub="Retrieval quality"
          icon={<Activity className="h-5 w-5" />}
          accent="purple"
          loading={loading}
        />
        <MetricsCard
          label="Avg Response"
          value={metrics ? `${metrics.avg_response_ms.toFixed(0)} ms` : '—'}
          sub="Last 24 h · target < 3 000 ms"
          icon={<Clock className="h-5 w-5" />}
          accent="blue"
          loading={loading}
        />
      </div>

      {metrics && (
        <p className="mt-2 text-right text-xs text-gray-400">
          Last updated {new Date(metrics.refreshed_at).toLocaleTimeString()}
          {' · '}auto-refreshes every 30 s
        </p>
      )}
    </section>
  )
}
