"""RAG retrieval: cosine similarity search + MMR re-ranking."""

import logging
import math
from dataclasses import dataclass

from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge import KnowledgeChunk

logger = logging.getLogger(__name__)

_openai = AsyncOpenAI(api_key=settings.openai_api_key)


@dataclass
class RetrievedChunk:
    id: str
    document_id: str
    content: str
    metadata: dict
    similarity: float


# ---------------------------------------------------------------------------
# Embedding query
# ---------------------------------------------------------------------------

async def embed_query(query: str) -> list[float]:
    response = await _openai.embeddings.create(
        model=settings.embedding_model,
        input=[query],
        dimensions=settings.embedding_dimensions,
    )
    return response.data[0].embedding


# ---------------------------------------------------------------------------
# Cosine similarity search via pgvector
# ---------------------------------------------------------------------------

async def similarity_search(
    db: AsyncSession,
    query_embedding: list[float],
    fetch_k: int | None = None,
    metadata_filter: dict | None = None,
) -> list[RetrievedChunk]:
    """
    Return up to fetch_k chunks ordered by cosine similarity (descending).
    Optionally filter by metadata key-value pairs using JSONB containment.
    """
    k = fetch_k or settings.retrieval_fetch_k

    # pgvector cosine distance: 1 - cosine_similarity
    # We cast the Python list to a vector literal for pgvector operator (<=>)
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    stmt = (
        select(
            KnowledgeChunk,
            text(f"1 - (embedding <=> '{embedding_str}'::vector) AS similarity"),
        )
        .order_by(text(f"embedding <=> '{embedding_str}'::vector"))
        .limit(k)
    )

    if metadata_filter:
        import json
        filter_json = json.dumps(metadata_filter)
        stmt = stmt.where(text(f"metadata @> '{filter_json}'::jsonb"))

    result = await db.execute(stmt)
    rows = result.all()

    return [
        RetrievedChunk(
            id=str(chunk.id),
            document_id=str(chunk.document_id),
            content=chunk.content,
            metadata=chunk.metadata_,
            similarity=float(similarity),
        )
        for chunk, similarity in rows
    ]


# ---------------------------------------------------------------------------
# MMR re-ranking
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def mmr_rerank(
    query_embedding: list[float],
    candidates: list[RetrievedChunk],
    candidate_embeddings: list[list[float]],
    top_k: int | None = None,
    lambda_: float | None = None,
) -> list[RetrievedChunk]:
    """
    Maximal Marginal Relevance selection.

    Selects top_k chunks that maximise:
        λ * sim(chunk, query) - (1 - λ) * max_sim(chunk, already_selected)
    """
    k = top_k or settings.retrieval_top_k
    lam = lambda_ if lambda_ is not None else settings.mmr_lambda

    if not candidates:
        return []

    k = min(k, len(candidates))
    selected_indices: list[int] = []
    remaining = list(range(len(candidates)))

    # Bootstrap: pick the most relevant candidate first
    best = max(remaining, key=lambda i: candidates[i].similarity)
    selected_indices.append(best)
    remaining.remove(best)

    while len(selected_indices) < k and remaining:
        best_score = float("-inf")
        best_idx = -1

        for i in remaining:
            relevance = candidates[i].similarity
            max_redundancy = max(
                _cosine_similarity(candidate_embeddings[i], candidate_embeddings[j])
                for j in selected_indices
            )
            score = lam * relevance - (1 - lam) * max_redundancy
            if score > best_score:
                best_score = score
                best_idx = i

        selected_indices.append(best_idx)
        remaining.remove(best_idx)

    return [candidates[i] for i in selected_indices]


# ---------------------------------------------------------------------------
# High-level retrieval entry point
# ---------------------------------------------------------------------------

async def retrieve(
    db: AsyncSession,
    query: str,
    top_k: int | None = None,
    metadata_filter: dict | None = None,
) -> list[RetrievedChunk]:
    """
    Full retrieval pipeline:
      1. Embed the query.
      2. Fetch fetch_k candidates by cosine similarity from pgvector.
      3. Apply MMR re-ranking and return top_k diverse, relevant chunks.
    """
    query_embedding = await embed_query(query)
    candidates = await similarity_search(
        db, query_embedding, metadata_filter=metadata_filter
    )

    if not candidates:
        return []

    # Embed each candidate for MMR inter-chunk similarity computation.
    # These are already stored as vectors in the DB — re-fetch them.
    chunk_ids = [c.id for c in candidates]
    stmt = select(KnowledgeChunk).where(
        KnowledgeChunk.id.in_(chunk_ids)  # type: ignore[arg-type]
    )
    result = await db.execute(stmt)
    chunk_map = {str(row.id): row.embedding for row in result.scalars()}
    candidate_embeddings = [chunk_map[c.id] for c in candidates]

    reranked = mmr_rerank(
        query_embedding,
        candidates,
        candidate_embeddings,
        top_k=top_k,
    )

    logger.debug(
        "Retrieval: query=%r fetched=%d reranked=%d",
        query[:60],
        len(candidates),
        len(reranked),
    )
    return reranked
