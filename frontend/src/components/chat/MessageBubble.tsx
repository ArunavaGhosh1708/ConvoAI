import { AlertTriangle, BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import clsx from 'clsx'
import type { ChatMessage } from '../../lib/types'
import { TypingIndicator } from './TypingIndicator'

interface Props {
  message: ChatMessage
}

export function MessageBubble({ message }: Props) {
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const isUser = message.role === 'user'

  return (
    <div className={clsx('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'max-w-[80%] rounded-2xl text-sm leading-relaxed',
          isUser
            ? 'bg-brand-600 text-white px-4 py-3 rounded-br-sm'
            : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-sm'
        )}
      >
        {/* Typing indicator or message content */}
        {message.isTyping ? (
          <TypingIndicator />
        ) : (
          <div className={clsx('px-4 py-3', !isUser && 'pr-3')}>
            <p className="whitespace-pre-wrap break-words">{message.content}</p>

            {/* Streaming cursor */}
            {message.isStreaming && (
              <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-current" />
            )}

            {/* Escalation badge */}
            {message.escalated && (
              <div className="mt-2 flex items-center gap-1.5 text-xs text-amber-600">
                <AlertTriangle className="h-3.5 w-3.5" />
                <span>Transferred to human agent</span>
              </div>
            )}

            {/* Confidence badge */}
            {message.confidence !== undefined && !isUser && (
              <div className="mt-1 text-xs text-gray-400">
                Confidence: {(message.confidence * 100).toFixed(0)}%
              </div>
            )}
          </div>
        )}

        {/* Sources accordion */}
        {!isUser && (message.sources?.length ?? 0) > 0 && !message.isTyping && (
          <div className="border-t border-gray-100 px-4 pb-2">
            <button
              onClick={() => setSourcesOpen((v) => !v)}
              className="flex w-full items-center justify-between py-2 text-xs text-gray-500 hover:text-gray-700"
            >
              <span className="flex items-center gap-1">
                <BookOpen className="h-3 w-3" />
                {message.sources!.length} source{message.sources!.length !== 1 ? 's' : ''}
              </span>
              {sourcesOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </button>

            {sourcesOpen && (
              <ul className="space-y-2 pb-1">
                {message.sources!.map((s) => (
                  <li key={s.chunk_id} className="rounded bg-gray-50 p-2 text-xs text-gray-600">
                    <div className="mb-0.5 flex justify-between font-medium text-gray-700">
                      <span className="truncate">{s.content_preview.slice(0, 60)}…</span>
                      <span className="ml-2 shrink-0 text-gray-400">
                        {(s.similarity * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="line-clamp-2 text-gray-500">{s.content_preview}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
