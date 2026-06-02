import { Mic, MicOff, Loader2, Volume2 } from 'lucide-react'
import clsx from 'clsx'
import type { VoiceState } from '../../hooks/useVoice'

interface Props {
  state:    VoiceState
  onPress:  () => void        // start recording
  onRelease: () => void       // stop recording
  disabled?: boolean
}

const LABELS: Record<VoiceState, string> = {
  idle:         'Hold to speak',
  recording:    'Recording… release to send',
  transcribing: 'Transcribing…',
  playing:      'Playing response',
}

export function VoiceButton({ state, onPress, onRelease, disabled }: Props) {
  const isRecording    = state === 'recording'
  const isBusy         = state === 'transcribing' || state === 'playing'

  return (
    <button
      onPointerDown={(e) => { e.preventDefault(); if (!disabled && !isBusy) onPress() }}
      onPointerUp={(e)   => { e.preventDefault(); if (isRecording) onRelease() }}
      onPointerLeave={(e) => { e.preventDefault(); if (isRecording) onRelease() }}
      disabled={disabled || isBusy}
      title={LABELS[state]}
      aria-label={LABELS[state]}
      className={clsx(
        'flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-all',
        isRecording && 'animate-pulse bg-red-500 text-white shadow-red-200 shadow-md',
        isBusy      && 'bg-amber-100 text-amber-600 cursor-not-allowed',
        !isRecording && !isBusy && 'bg-gray-100 text-gray-500 hover:bg-brand-50 hover:text-brand-600',
        disabled    && 'opacity-40 cursor-not-allowed',
      )}
    >
      {state === 'recording'    && <MicOff   className="h-4 w-4" />}
      {state === 'transcribing' && <Loader2  className="h-4 w-4 animate-spin" />}
      {state === 'playing'      && <Volume2  className="h-4 w-4" />}
      {state === 'idle'         && <Mic      className="h-4 w-4" />}
    </button>
  )
}
