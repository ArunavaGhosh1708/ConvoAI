import { LayoutDashboard } from 'lucide-react'
import { DocumentManager } from '../components/admin/DocumentManager'
import { EscalationQueue } from '../components/admin/EscalationQueue'
import { MetricsDashboard } from '../components/admin/MetricsDashboard'
import { TranscriptViewer } from '../components/admin/TranscriptViewer'
import { VoiceSettings } from '../components/admin/VoiceSettings'

export function AdminPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top nav */}
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
            <LayoutDashboard className="h-4 w-4 text-white" />
          </div>
          <span className="text-base font-semibold text-gray-800">ConvoAI Admin</span>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-6xl px-6 py-8">
        <MetricsDashboard />
        <EscalationQueue />
        <DocumentManager />
        <TranscriptViewer />
        <VoiceSettings />
      </main>
    </div>
  )
}
