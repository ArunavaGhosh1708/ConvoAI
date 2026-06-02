import { Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { fetchVoiceConfig, updateVoiceConfig } from '../../lib/api'
import type { VoiceConfig } from '../../lib/types'

export function VoiceSettings() {
  const [config,  setConfig]  = useState<VoiceConfig | null>(null)
  const [saving,  setSaving]  = useState(false)
  const [saved,   setSaved]   = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchVoiceConfig()
      .then(setConfig)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const save = async () => {
    if (!config) return
    setSaving(true)
    setError(null)
    try {
      const updated = await updateVoiceConfig(config)
      setConfig(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="h-24 animate-pulse rounded-2xl bg-gray-100" />

  return (
    <section className="mt-8">
      <h2 className="mb-4 text-lg font-semibold text-gray-800">Voice Persona (FR-11)</h2>

      {error && (
        <p className="mb-3 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
      )}

      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm space-y-4">
        {/* Voice ID */}
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            ElevenLabs Voice ID
          </label>
          <input
            type="text"
            value={config?.voice_id ?? ''}
            onChange={(e) => setConfig((c) => c ? { ...c, voice_id: e.target.value } : c)}
            placeholder="21m00Tcm4TlvDq8ikWAM"
            className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 font-mono"
          />
          <p className="mt-1 text-xs text-gray-400">
            Find IDs at elevenlabs.io/voice-lab
          </p>
        </div>

        {/* Speed */}
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Speed — {config?.speed.toFixed(1)}×
          </label>
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.1"
            value={config?.speed ?? 1.0}
            onChange={(e) =>
              setConfig((c) => c ? { ...c, speed: parseFloat(e.target.value) } : c)
            }
            className="w-full accent-brand-600"
          />
          <div className="mt-0.5 flex justify-between text-xs text-gray-400">
            <span>0.5×</span><span>1.0× (normal)</span><span>2.0×</span>
          </div>
        </div>

        {/* Model */}
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Model</label>
          <select
            value={config?.model ?? 'eleven_turbo_v2_5'}
            onChange={(e) => setConfig((c) => c ? { ...c, model: e.target.value } : c)}
            className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
          >
            <option value="eleven_turbo_v2_5">Turbo v2.5 (lowest latency)</option>
            <option value="eleven_turbo_v2">Turbo v2</option>
            <option value="eleven_multilingual_v2">Multilingual v2</option>
            <option value="eleven_monolingual_v1">Monolingual v1</option>
          </select>
        </div>

        {/* Save */}
        <button
          onClick={save}
          disabled={saving}
          className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition"
        >
          <Save className="h-4 w-4" />
          {saving ? 'Saving…' : saved ? 'Saved ✓' : 'Save changes'}
        </button>
      </div>

      <p className="mt-2 text-xs text-gray-400">
        Changes apply to the next synthesis call — no deployment required.
      </p>
    </section>
  )
}
