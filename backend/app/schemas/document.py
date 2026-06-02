from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id:          str
    filename:    str
    file_type:   str
    status:      str
    chunk_count: int
    created_at:  str


class DocumentUploadResponse(BaseModel):
    documents: list[DocumentOut]
    message:   str


class AgentConfigSchema(BaseModel):
    escalation_confidence_threshold: float = Field(ge=0.0, le=1.0)
    llm_temperature:                 float = Field(ge=0.0, le=2.0)
    retrieval_top_k:                 int   = Field(ge=1, le=50)
    memory_window:                   int   = Field(ge=1, le=100)


class AgentConfigUpdate(BaseModel):
    escalation_confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)
    llm_temperature:                 float | None = Field(None, ge=0.0, le=2.0)
    retrieval_top_k:                 int   | None = Field(None, ge=1, le=50)
    memory_window:                   int   | None = Field(None, ge=1, le=100)


class ReviewItem(BaseModel):
    conversation_id: str
    user_id:         str
    channel:         str
    status:          str
    resolution_score: float | None
    created_at:      str
    resolved_at:     str | None
