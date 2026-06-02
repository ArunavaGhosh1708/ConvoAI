import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchMetrics } from '../lib/api'
import type { MetricsResponse } from '../lib/types'

const POLL_INTERVAL_MS = 30_000   // 30 s — matches PRD FR-21 ≤ 30 s refresh lag

export function useMetrics() {
  const [metrics, setMetrics]   = useState<MetricsResponse | null>(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await fetchMetrics()
      setMetrics(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load metrics')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    timerRef.current = setInterval(refresh, POLL_INTERVAL_MS)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [refresh])

  return { metrics, loading, error, refresh }
}
