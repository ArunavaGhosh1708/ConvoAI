import { MessageCircle, Minimize2, Mic, MicOff, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import { useChat } from '../../hooks/useChat'
import { useVoice } from '../../hooks/useVoice'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'
import { VoiceButton } from './VoiceButton'

interface Props {
  /** When true, renders the widget in full-page mode (no floating button). */
  fullPage?: boolean
}

export function ChatWidget({ fullPage = false }: Props) {
  const [isOpen,     setIsOpen]     = useState(fullPage)
  const [voiceMode,  setVoiceMode]  = useState(false)

  const { messages, isTyping, isStreaming, sendMessage } = useChat()
  const voice = useVoice()

  // ---------------------------------------------------------------------------
  // Auto-TTS: when voice mode is on and an assistant message finishes streaming,
  // synthesize and play it automatically.
  // ---------------------------------------------------------------------------
  const lastMsgCountRef = useRef(messages.length)

  useEffect(() => {
    if (!voiceMode) return
    if (messages.length <= lastMsgCountRef.current) return

    const lastMsg = messages[messages.length - 1]
    if (
      lastMsg?.role === 'assistant' &&
      !lastMsg.isStreaming &&
      !lastMsg.isTyping &&
      lastMsg.content.trim()
    ) {
      voice.playTTS(lastMsg.content)
    }
    lastMsgCountRef.current = messages.length
  }, [messages, voiceMode, voice])

  // ---------------------------------------------------------------------------
  // Voice recording flow
  // ---------------------------------------------------------------------------
  const handleVoicePress = async () => {
    if (voice.state === 'idle') {
      await voice.startRecording()
    }
  }

  const handleVoiceRelease = async () => {
    if (voice.state !== 'recording') return
    try {
      const text = await voice.stopRecording()
      if (text.trim()) sendMessage(text)
    } catch {
      // error already set in useVoice
    }
  }

  const statusText = () => {
    if (voice.state === 'recording')    return 'Recording…'
    if (voice.state === 'transcribing') return 'Transcribing…'
    if (voice.state === 'playing')      return 'Playing response…'
    if (isTyping)    return 'Thinking…'
    if (isStreaming) return 'Responding…'
    return voiceMode ? 'Voice mode on' : 'Online'
  }

  const panel = (
    <div
      className={clsx(
        'flex flex-col bg-white shadow-2xl',
        fullPage
          ? 'h-full w-full'
          : 'fixed bottom-20 right-4 z-50 h-[540px] w-[390px] rounded-2xl'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between rounded-t-2xl bg-brand-700 px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/20">
            <MessageCircle className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-semibold">ConvoAI Support</p>
            <p className="text-xs text-brand-200">{statusText()}</p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {/* Voice mode toggle */}
          <button
            onClick={() => { setVoiceMode((v) => !v); if (voiceMode) voice.stopTTS() }}
            title={voiceMode ? 'Disable voice mode' : 'Enable voice mode'}
            className={clsx(
              'rounded-lg p-1.5 transition',
              voiceMode ? 'bg-white/30 text-white' : 'hover:bg-white/20 text-white/70'
            )}
          >
            {voiceMode ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
          </button>

          {!fullPage && (
            <button
              onClick={() => setIsOpen(false)}
              className="rounded-lg p-1 transition hover:bg-white/20"
              aria-label="Minimise chat"
            >
              <Minimize2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Voice error banner */}
      {voice.error && (
        <div className="bg-red-50 px-4 py-2 text-xs text-red-600">{voice.error}</div>
      )}

      {/* Message list */}
      <MessageList messages={messages} />

      {/* Input row */}
      <div className="flex items-end border-t border-gray-100 bg-white px-3 py-3 gap-2">
        {voiceMode && (
          <VoiceButton
            state={voice.state}
            onPress={handleVoicePress}
            onRelease={handleVoiceRelease}
            disabled={isTyping || isStreaming}
          />
        )}
        <div className="flex-1">
          <ChatInput
            onSend={sendMessage}
            disabled={isTyping || isStreaming || voice.state === 'recording' || voice.state === 'transcribing'}
          />
        </div>
      </div>
    </div>
  )

  if (fullPage) return panel

  return (
    <>
      <button
        onClick={() => setIsOpen((v) => !v)}
        aria-label={isOpen ? 'Close chat' : 'Open chat'}
        className={clsx(
          'fixed bottom-4 right-4 z-50 flex h-14 w-14 items-center justify-center',
          'rounded-full bg-brand-600 text-white shadow-lg transition-all',
          'hover:bg-brand-700 active:scale-95'
        )}
      >
        {isOpen ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      </button>
      {isOpen && panel}
    </>
  )
}
