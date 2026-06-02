"""Unit tests for ingestion pipeline async paths — mocked OpenAI + DB."""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.ingestion import embed_texts, ingest_document


def _embedding(dim: int = 1536) -> list[float]:
    return [0.01] * dim


# ---------------------------------------------------------------------------
# embed_texts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_texts_empty_list():
    result = await embed_texts([])
    assert result == []


@pytest.mark.asyncio
async def test_embed_texts_single_batch():
    embeddings = [_embedding() for _ in range(3)]
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=e) for e in embeddings]

    with patch("app.rag.ingestion._openai") as mock_openai:
        mock_openai.embeddings.create = AsyncMock(return_value=mock_response)
        result = await embed_texts(["a", "b", "c"])

    assert len(result) == 3
    assert all(len(e) == 1536 for e in result)


@pytest.mark.asyncio
async def test_embed_texts_batches_large_input():
    """Inputs > 256 are sent in multiple API calls."""
    n = 300
    texts = [f"text {i}" for i in range(n)]

    batch1_resp = MagicMock()
    batch1_resp.data = [MagicMock(embedding=_embedding()) for _ in range(256)]
    batch2_resp = MagicMock()
    batch2_resp.data = [MagicMock(embedding=_embedding()) for _ in range(n - 256)]

    with patch("app.rag.ingestion._openai") as mock_openai:
        mock_openai.embeddings.create = AsyncMock(side_effect=[batch1_resp, batch2_resp])
        result = await embed_texts(texts)

    assert len(result) == n
    assert mock_openai.embeddings.create.await_count == 2


# ---------------------------------------------------------------------------
# ingest_document
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_document_happy_path():
    file_obj = io.BytesIO(b"dummy content")
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()

    with (
        patch("app.rag.ingestion.load_document", return_value="parsed text " * 30),
        patch("app.rag.ingestion.chunk_text", return_value=["chunk one", "chunk two"]),
        patch("app.rag.ingestion.embed_texts", new=AsyncMock(return_value=[_embedding(), _embedding()])),
    ):
        result = await ingest_document(
            db=db,
            file=file_obj,
            filename="test.txt",
            file_type="txt",
        )

    # db.add called (document) + db.add_all (chunks)
    assert db.add.called or db.add_all.called
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_ingest_document_marks_failed_on_error():
    file_obj = io.BytesIO(b"content")
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    with patch("app.rag.ingestion.load_document", side_effect=RuntimeError("parse error")):
        with pytest.raises(RuntimeError, match="parse error"):
            await ingest_document(
                db=db,
                file=file_obj,
                filename="bad.pdf",
                file_type="pdf",
            )

    db.rollback.assert_awaited()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_ingest_document_raises_on_empty_chunks():
    file_obj = io.BytesIO(b"content")
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    with (
        patch("app.rag.ingestion.load_document", return_value=""),
        patch("app.rag.ingestion.chunk_text", return_value=[]),
    ):
        with pytest.raises(ValueError, match="no text chunks"):
            await ingest_document(
                db=db,
                file=file_obj,
                filename="empty.txt",
                file_type="txt",
            )
