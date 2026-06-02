"""
Self-hosted Whisper v3 STT sidecar (OQ-03 self-hosted option).
Runs as a standalone FastAPI service on port 9000.
The main backend calls POST /transcribe with a multipart audio file.
"""

import logging
import os
import tempfile
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="ConvoAI Whisper STT Sidecar", version="1.0.0")

# Lazy-loaded model (loaded on first request to avoid blocking startup)
_model = None

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
WHISPER_DEVICE     = os.getenv("WHISPER_DEVICE",     "cpu")
WHISPER_COMPUTE    = os.getenv("WHISPER_COMPUTE",    "int8")   # int8 = fast CPU


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper model %s on %s ...", WHISPER_MODEL_SIZE, WHISPER_DEVICE)
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
        )
        logger.info("Whisper model loaded")
    return _model


def _ext(content_type: str) -> str:
    return {
        "audio/webm": "webm",
        "audio/wav":  "wav",
        "audio/mp4":  "mp4",
        "audio/ogg":  "ogg",
        "audio/mpeg": "mp3",
    }.get(content_type.split(";")[0].strip(), "webm")


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio payload")

    suffix = f".{_ext(audio.content_type or 'audio/webm')}"
    t0 = time.monotonic()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        model = _get_model()
        segments, info = model.transcribe(
            tmp_path,
            beam_size=5,
            language="en",
            vad_filter=True,             # skip silence
        )
        text = " ".join(seg.text for seg in segments).strip()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info("Transcribed %d bytes in %dms: %r", len(data), duration_ms, text[:60])

    return {
        "text":        text,
        "language":    info.language,
        "duration_ms": duration_ms,
    }


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _model is not None}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
