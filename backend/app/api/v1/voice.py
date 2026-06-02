"""
Voice endpoints:
  POST /api/v1/voice/transcribe  — WAV/WebM → text (Whisper STT)
  POST /api/v1/voice/synthesize  — text → MP3 audio stream (ElevenLabs TTS)
"""

import logging

from fastapi import APIRouter, File, HTTPException, Security, UploadFile, status
from fastapi.responses import StreamingResponse

from app.middleware.auth import require_api_key
from app.schemas.voice import SynthesizeRequest, TranscriptionResponse
from app.services.tts import synthesize_stream
from app.services.whisper import transcribe

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])

_MAX_AUDIO_BYTES = 25 * 1024 * 1024   # 25 MB (OpenAI Whisper API limit)

_TTS_HEADERS = {
    "Cache-Control":    "no-cache",
    "X-Accel-Buffering": "no",         # disable nginx buffering for streaming
    "Content-Type":     "audio/mpeg",
}


@router.post("/voice/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="WAV or WebM audio file"),
    _auth: None = Security(require_api_key),
) -> TranscriptionResponse:
    """
    Transcribe user audio to text using Whisper STT.
    Accepts audio/webm (MediaRecorder default) or audio/wav.
    Returns the transcription and wall-clock duration.
    """
    data = await audio.read()

    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio payload")

    if len(data) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file exceeds {_MAX_AUDIO_BYTES // 1024 // 1024} MB limit",
        )

    content_type = (audio.content_type or "audio/webm").split(";")[0].strip()
    result = await transcribe(data, content_type)

    if not result.text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No speech detected in the audio",
        )

    logger.info("Transcribed %d bytes in %dms: %r", len(data), result.duration_ms, result.text[:60])
    return TranscriptionResponse(text=result.text, duration_ms=result.duration_ms)


@router.post("/voice/synthesize")
async def synthesize_audio(
    body: SynthesizeRequest,
    _auth: None = Security(require_api_key),
) -> StreamingResponse:
    """
    Convert text to speech using ElevenLabs TTS.
    Returns a streaming MP3 audio response for sub-100 ms first-byte latency.
    """
    if not body.text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty text")

    return StreamingResponse(
        synthesize_stream(body.text, body.voice_id, body.speed),
        media_type="audio/mpeg",
        headers=_TTS_HEADERS,
    )
