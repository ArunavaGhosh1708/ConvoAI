import { Send } from 'lucide-react'
import { type KeyboardEvent, useRef, useState } from 'react'
import clsx from 'clsx'

interface Props {
  onSend:     (text: string) => void
  disabled?:  boolean
}

export function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const canSend = text.trim().length > 0 && !disabled

  const submit = () => {
    if (!canSend) return
    onSend(text.trim())
    setText('')
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const handleInput = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`
  }

  return (
    <div className="flex items-end gap-2 border-t border-gray-100 bg-white px-4 py-3">
      <textarea
        ref={textareaRef}
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKey}
        onInput={handleInput}
        placeholder="Type a message… (Enter to send)"
        disabled={disabled}
        className={clsx(
          'flex-1 resize-none rounded-xl border border-gray-200 bg-gray-50 px-3 py-2',
          'text-sm text-gray-800 placeholder-gray-400 outline-none',
          'focus:border-brand-500 focus:ring-1 focus:ring-brand-500',
          'transition-colors disabled:opacity-50',
          'max-h-[120px] overflow-y-auto'
        )}
      />
      <button
        onClick={submit}
        disabled={!canSend}
        aria-label="Send message"
        className={clsx(
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-colors',
          canSend
            ? 'bg-brand-600 text-white hover:bg-brand-700 active:bg-brand-800'
            : 'bg-gray-100 text-gray-300 cursor-not-allowed'
        )}
      >
        <Send className="h-4 w-4" />
      </button>
    </div>
  )
}
