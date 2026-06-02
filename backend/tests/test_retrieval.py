"""Unit tests for MMR re-ranking (pure Python, no DB or OpenAI calls)."""

import math
import pytest

from app.rag.retrieval import RetrievedChunk, mmr_rerank, _cosine_similarity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit_vec(dims: int, hot: int) -> list[float]:
    """One-hot unit vector at position `hot`."""
    v = [0.0] * dims
    v[hot] = 1.0
    return v


def _make_chunk(id_: str, similarity: float) -> RetrievedChunk:
    return RetrievedChunk(
        id=id_,
        document_id="doc-1",
        content=f"content {id_}",
        metadata={},
        similarity=similarity,
    )


# ---------------------------------------------------------------------------
# _cosine_similarity
# ---------------------------------------------------------------------------

def test_cosine_same_vector():
    v = [1.0, 0.0, 0.0]
    assert math.isclose(_cosine_similarity(v, v), 1.0)


def test_cosine_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert math.isclose(_cosine_similarity(a, b), 0.0)


def test_cosine_opposite_vectors():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert math.isclose(_cosine_similarity(a, b), -1.0)


def test_cosine_zero_vector_returns_zero():
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


# ---------------------------------------------------------------------------
# mmr_rerank
# ---------------------------------------------------------------------------

def test_mmr_returns_top_k():
    dims = 4
    candidates = [_make_chunk(str(i), 1.0 - i * 0.1) for i in range(4)]
    embeddings = [_unit_vec(dims, i) for i in range(4)]
    query_emb = _unit_vec(dims, 0)

    result = mmr_rerank(query_emb, candidates, embeddings, top_k=2)
    assert len(result) == 2


def test_mmr_empty_candidates():
    assert mmr_rerank([1.0, 0.0], [], [], top_k=5) == []


def test_mmr_fewer_candidates_than_k():
    dims = 2
    candidates = [_make_chunk("a", 0.9)]
    embeddings = [[1.0, 0.0]]
    result = mmr_rerank([1.0, 0.0], candidates, embeddings, top_k=5)
    assert len(result) == 1


def test_mmr_selects_diverse_results():
    """
    Two candidates with the same relevance but one is identical to the first
    selected; MMR should prefer the orthogonal (diverse) candidate.
    """
    dims = 2
    query_emb = [1.0, 0.0]

    # chunk0 is most relevant (cos sim = 1.0)
    # chunk1 is identical to chunk0 (redundant)
    # chunk2 is orthogonal to chunk0 (diverse)
    candidates = [
        _make_chunk("0", 1.0),   # most relevant
        _make_chunk("1", 0.95),  # nearly as relevant but same direction
        _make_chunk("2", 0.90),  # slightly less relevant but orthogonal
    ]
    embeddings = [
        [1.0, 0.0],   # chunk0: same direction as query
        [0.99, 0.14], # chunk1: almost same direction
        [0.0, 1.0],   # chunk2: orthogonal
    ]

    result = mmr_rerank(query_emb, candidates, embeddings, top_k=2, lambda_=0.5)
    ids = [r.id for r in result]

    # First pick must be chunk0 (highest relevance)
    assert ids[0] == "0"
    # Second pick should be chunk2 (diverse) over chunk1 (redundant)
    assert ids[1] == "2"


def test_mmr_lambda_1_is_pure_relevance():
    """λ=1 → no diversity penalty → picks top-k by similarity only."""
    dims = 3
    query_emb = [1.0, 0.0, 0.0]
    candidates = [
        _make_chunk("a", 0.9),
        _make_chunk("b", 0.8),
        _make_chunk("c", 0.7),
    ]
    # All identical direction — diversity is zero
    embeddings = [[1.0, 0.0, 0.0]] * 3

    result = mmr_rerank(query_emb, candidates, embeddings, top_k=2, lambda_=1.0)
    assert [r.id for r in result] == ["a", "b"]
