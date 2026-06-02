"""Unit tests for RAG retrieval — mocked OpenAI + DB."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.retrieval import (
    RetrievedChunk,
    embed_query,
    mmr_rerank,
    similarity_search,
    retrieve,
)


def _embedding(dim: int = 1536, value: float = 0.1) -> list[float]:
    return [value] * dim


def _chunk(sim: float = 0.9, content: str = "chunk") -> RetrievedChunk:
    return RetrievedChunk(
        id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        content=content,
        metadata={"filename": "doc.pdf"},
        similarity=sim,
    )


# ---------------------------------------------------------------------------
# embed_query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_query_returns_vector():
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=_embedding())]

    with patch("app.rag.retrieval._openai") as mock_openai:
        mock_openai.embeddings.create = AsyncMock(return_value=mock_response)
        result = await embed_query("what is the return policy?")

    assert len(result) == 1536
    assert all(isinstance(x, float) for x in result)


@pytest.mark.asyncio
async def test_embed_query_uses_correct_model():
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=_embedding())]

    with patch("app.rag.retrieval._openai") as mock_openai:
        mock_openai.embeddings.create = AsyncMock(return_value=mock_response)
        await embed_query("test query")

    call_kwargs = mock_openai.embeddings.create.call_args.kwargs
    assert call_kwargs["model"] == "text-embedding-3-small"
    assert call_kwargs["input"] == ["test query"]


# ---------------------------------------------------------------------------
# similarity_search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_similarity_search_returns_chunks():
    chunk_row = MagicMock()
    chunk_row.id = uuid.uuid4()
    chunk_row.content = "relevant info"
    chunk_row.metadata_ = {"filename": "faq.pdf"}

    result_mock = MagicMock()
    result_mock.all.return_value = [(chunk_row, 0.91)]
    db = AsyncMock()
    db.execute.return_value = result_mock

    chunks = await similarity_search(db, _embedding(), fetch_k=5)

    assert len(chunks) == 1
    assert chunks[0].similarity == pytest.approx(0.91)
    assert chunks[0].content == "relevant info"


@pytest.mark.asyncio
async def test_similarity_search_empty_result():
    result_mock = MagicMock()
    result_mock.all.return_value = []
    db = AsyncMock()
    db.execute.return_value = result_mock

    chunks = await similarity_search(db, _embedding())

    assert chunks == []


# ---------------------------------------------------------------------------
# retrieve (full pipeline)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_returns_reranked_chunks():
    query_emb = _embedding(value=0.5)
    candidate = _chunk(sim=0.88)

    chunk_row = MagicMock()
    chunk_row.id = uuid.UUID(candidate.id)
    chunk_row.embedding = _embedding(value=0.5)

    result_mock = MagicMock()
    result_mock.scalars.return_value = [chunk_row]
    db = AsyncMock()
    db.execute.return_value = result_mock

    with (
        patch("app.rag.retrieval.embed_query", new=AsyncMock(return_value=query_emb)),
        patch("app.rag.retrieval.similarity_search", new=AsyncMock(return_value=[candidate])),
    ):
        results = await retrieve(db, "some question")

    assert len(results) >= 1
    assert results[0].similarity == pytest.approx(0.88)


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_no_candidates():
    db = AsyncMock()
    query_emb = _embedding()

    with (
        patch("app.rag.retrieval.embed_query", new=AsyncMock(return_value=query_emb)),
        patch("app.rag.retrieval.similarity_search", new=AsyncMock(return_value=[])),
    ):
        results = await retrieve(db, "obscure question")

    assert results == []
