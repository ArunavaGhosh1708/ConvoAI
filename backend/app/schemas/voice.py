from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    text:        str
    duration_ms: int


class SynthesizeRequest(BaseModel):
    text:     str   = Field(..., min_length=1, max_length=5000)
    voice_id: str | None = None
    speed:    float | None = Field(None, ge=0.5, le=2.0)


class VoiceConfigResponse(BaseModel):
    voice_id: str
    speed:    float
    model:    str


class VoiceConfigUpdate(BaseModel):
    voice_id: str | None = None
    speed:    float | None = Field(None, ge=0.5, le=2.0)
    model:    str | None = None
