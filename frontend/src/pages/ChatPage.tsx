import { ChatWidget } from '../components/chat/ChatWidget'

/** Standalone full-page chat (widget embedded in a demo page). */
export function ChatPage() {
  return (
    <div className="relative min-h-screen bg-gradient-to-br from-brand-50 to-blue-50">
      {/* Hero text */}
      <div className="flex flex-col items-center justify-center gap-4 pt-24 text-center">
        <h1 className="text-4xl font-bold text-brand-800">ConvoAI</h1>
        <p className="max-w-md text-gray-500">
          AI-powered customer service. Click the chat button in the bottom-right corner to start.
        </p>
      </div>

      {/* Floating widget */}
      <ChatWidget />
    </div>
  )
}
