from dataclasses import dataclass, field

from app.rag.retrieval import RetrievedChunk


@dataclass
class AgentContext:
    """Mutable request-scoped state shared between the agent and its tools."""

    session_id: str
    # Confidence of the top retrieved chunk (0.0 = no retrieval yet)
    last_confidence: float = 0.0
    # Whether the EscalationTool was called during this turn
    escalated: bool = False
    escalation_reason: str = ""
    # All chunks retrieved across tool calls this turn
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
