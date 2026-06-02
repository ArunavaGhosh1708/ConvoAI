FROM python:3.12-slim

# ffmpeg is required by faster-whisper for audio decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    faster-whisper==1.0.3 \
    fastapi==0.111.1 \
    uvicorn[standard]==0.30.1 \
    python-multipart==0.0.9

WORKDIR /app
COPY server.py .

ENV WHISPER_MODEL_SIZE=large-v3
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE=int8

# Optionally pre-download the model at build time (adds ~3 GB to the image):
# RUN python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', device='cpu')"

EXPOSE 9000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "9000"]
