from pydantic import BaseModel


class MetricsResponse(BaseModel):
    total_sessions:  int
    active_sessions: int
    resolution_rate: float    # 0–100
    escalation_rate: float    # 0–100
    avg_confidence:  float    # 0–1
    refreshed_at:    str
