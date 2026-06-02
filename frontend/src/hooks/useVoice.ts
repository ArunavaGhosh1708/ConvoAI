import { useCallback, useRef, useState } from 'react'
import { synthesizeAudio, transcribeAudio } from '../lib/api'

export type VoiceState = 'idle' | 'recording' | 'transcribing' | 'playing'

interface UseVoiceReturn {
  state:          VoiceState
  error:          string | null
  startRecording: () => Promise<void>
  stopRecording:  () => Promise<string>   // resolves with transcription text
  playTTS:        (text: string) => Promise<void>
  stopTTS:        () => void
}

export function useVoice(): UseVoiceReturn {
  const [state, setState] = useState<VoiceState>('idle')
  const [error, setError] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef        = useRef<Blob[]>([])
  const audioRef         = useRef<HTMLAudioElement | null>(null)
  const audioUrlRef      = useRef<string | null>(null)

  // ---------------------------------------------------------------------------
  // Recording
  // ---------------------------------------------------------------------------

  const startRecording = useCallback(async () => {
    // FR-10: interrupt any playing TTS when user starts speaking
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current)
        audioUrlRef.current = null
      }
    }

    setError(null)

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setError('Microphone access denied. Please allow microphone permission.')
      return
    }

    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm'

    const recorder      = new MediaRecorder(stream, { mimeType })
    chunksRef.current   = []
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }

    mediaRecorderRef.current = recorder
    recorder.start(250)   // collect chunks every 250 ms
    setState('recording')
  }, [])

  const stopRecording = useCallback((): Promise<string> => {
    return new Promise((resolve, reject) => {
      const recorder = mediaRecorderRef.current
      if (!recorder || recorder.state === 'inactive') {
        reject(new Error('No active recording'))
        return
      }

      recorder.onstop = async () => {
        // Stop all mic tracks
        recorder.stream.getTracks().forEach((t) => t.stop())
        mediaRecorderRef.current = null

        setState('transcribing')
        const mimeType = recorder.mimeType || 'audio/webm'
        const blob     = new Blob(chunksRef.current, { type: mimeType })
        chunksRef.current = []

        try {
          const result = await transcribeAudio(blob, mimeType)
          setState('idle')
          resolve(result.text)
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'Transcription failed'
          setError(msg)
          setState('idle')
          reject(new Error(msg))
        }
      }

      recorder.stop()
    })
  }, [])

  // ---------------------------------------------------------------------------
  // TTS playback
  // ---------------------------------------------------------------------------

  const playTTS = useCallback(async (text: string) => {
    setError(null)
    setState('playing')

    try {
      const blob = await synthesizeAudio(text)
      const url  = URL.createObjectURL(blob)
      audioUrlRef.current = url

      const audio       = new Audio(url)
      audioRef.current  = audio

      audio.onended = () => {
        URL.revokeObjectURL(url)
        audioUrlRef.current = null
        audioRef.current    = null
        setState('idle')
      }
      audio.onerror = () => {
        URL.revokeObjectURL(url)
        audioUrlRef.current = null
        audioRef.current    = null
        setState('idle')
      }

      await audio.play()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'TTS playback failed')
      setState('idle')
    }
  }, [])

  const stopTTS = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current)
      audioUrlRef.current = null
    }
    setState('idle')
  }, [])

  return { state, error, startRecording, stopRecording, playTTS, stopTTS }
}
