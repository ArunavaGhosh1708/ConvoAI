"""Unit tests for the RAG ingestion pipeline (no DB, no OpenAI calls)."""

import io
import pytest

from app.rag.ingestion import chunk_text, load_document, _split_text
from pathlib import Path
import tempfile
import os


# ---------------------------------------------------------------------------
# chunk_text / _split_text
# ---------------------------------------------------------------------------

def test_short_text_is_single_chunk():
    text = "Hello world"
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_long_text_splits_into_multiple_chunks():
    # 600-char text should exceed default chunk_size=512
    text = "word " * 200  # 1000 chars
    chunks = chunk_text(text)
    assert len(chunks) > 1


def test_chunks_respect_size_limit():
    text = "A" * 2000
    chunks = _split_text(text, chunk_size=512, chunk_overlap=64)
    for chunk in chunks:
        # With character-level fallback, each chunk <= chunk_size + overlap
        assert len(chunk) <= 512 + 64


def test_chunk_overlap_creates_shared_content():
    # Build text where overlap is detectable
    text = "paragraph one. " * 40 + "paragraph two. " * 40
    chunks = _split_text(text, chunk_size=200, chunk_overlap=50)
    assert len(chunks) >= 2
    # The tail of chunk[0] should appear at the start of chunk[1]
    tail = chunks[0][-50:]
    assert tail in chunks[1]


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_whitespace_only_paragraphs_filtered():
    text = "Hello\n\n\n\n\nWorld"
    chunks = chunk_text(text)
    for chunk in chunks:
        assert chunk.strip() != ""


# ---------------------------------------------------------------------------
# load_document  (txt only — no binary deps needed)
# ---------------------------------------------------------------------------

def test_load_txt_file():
    content = "This is a test document.\nWith two lines."
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        path = Path(f.name)
    try:
        result = load_document(path, "txt")
        assert "This is a test document." in result
        assert "With two lines." in result
    finally:
        os.unlink(path)


def test_load_unsupported_type_raises():
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_document(Path("dummy.xyz"), "xyz")


def test_load_html_file():
    html = "<html><body><h1>Title</h1><p>Body text.</p></body></html>"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        path = Path(f.name)
    try:
        result = load_document(path, "html")
        assert "Title" in result
        assert "Body text." in result
    finally:
        os.unlink(path)
