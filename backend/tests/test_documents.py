"""Unit tests for document upload endpoint helpers — no DB, no OpenAI."""

import pytest

from app.api.v1.documents import _file_type_from, _ALLOWED_TYPES


# ---------------------------------------------------------------------------
# _file_type_from: extension-based detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,expected", [
    ("manual.pdf",  "pdf"),
    ("guide.docx",  "docx"),
    ("faq.html",    "html"),
    ("notes.txt",   "txt"),
    ("REPORT.PDF",  "pdf"),   # case-insensitive
    ("data.TXT",    "txt"),
])
def test_file_type_from_extension(filename: str, expected: str):
    assert _file_type_from(filename, None) == expected


@pytest.mark.parametrize("filename,content_type,expected", [
    ("upload",       "application/pdf",   "pdf"),
    ("upload",       "text/plain",        "txt"),
    ("upload",       "text/html",         "html"),
    ("upload",       "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    ("upload",       "text/plain; charset=utf-8",  "txt"),   # strips charset param
])
def test_file_type_from_content_type_fallback(filename: str, content_type: str, expected: str):
    assert _file_type_from(filename, content_type) == expected


@pytest.mark.parametrize("filename,content_type", [
    ("image.png",   "image/png"),
    ("sheet.xlsx",  "application/vnd.ms-excel"),
    ("archive.zip", "application/zip"),
    ("data",        None),
])
def test_file_type_from_unsupported_returns_none(filename: str, content_type):
    assert _file_type_from(filename, content_type) is None


def test_allowed_types_set():
    assert _ALLOWED_TYPES == {"pdf", "docx", "html", "txt"}
