"""Unit tests for admin document endpoints — mocked DB + background tasks."""

import uuid
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import admin_jwt


def _mock_doc(status: str = "indexed") -> MagicMock:
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.filename = "manual.pdf"
    doc.file_type = "pdf"
    doc.status = status
    doc.chunk_count = 42
    doc.created_at = datetime.now(timezone.utc)
    return doc


# ---------------------------------------------------------------------------
# GET /admin/documents
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_documents_empty(mock_client):
    client, mock_db, _ = mock_client

    result = MagicMock()
    result.scalars.return_value = []
    mock_db.execute.return_value = result

    resp = await client.get(
        "/api/v1/admin/documents",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_documents_returns_docs(mock_client):
    client, mock_db, _ = mock_client
    docs = [_mock_doc("indexed"), _mock_doc("pending")]

    result = MagicMock()
    result.scalars.return_value = docs
    mock_db.execute.return_value = result

    resp = await client.get(
        "/api/v1/admin/documents",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_documents_requires_admin(mock_client):
    client, _, _ = mock_client
    resp = await client.get("/api/v1/admin/documents")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /admin/documents
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_document_accepted(mock_client):
    client, mock_db, _ = mock_client
    pending_doc = _mock_doc("pending")
    mock_db.flush = AsyncMock()

    with patch("app.api.v1.documents.Document") as mock_doc_cls, \
         patch("app.api.v1.documents.ingest_document_task") as mock_task:
        mock_doc_cls.return_value = pending_doc
        mock_task.delay.return_value = None

        resp = await client.post(
            "/api/v1/admin/documents",
            headers={"Authorization": f"Bearer {admin_jwt()}"},
            files={"files": ("test.pdf", BytesIO(b"%PDF-1.4 sample"), "application/pdf")},
            data={"category": "manual"},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert len(body["documents"]) == 1
    assert "queued" in body["message"]


@pytest.mark.asyncio
async def test_upload_unsupported_type_rejected(mock_client):
    client, _, _ = mock_client

    resp = await client.post(
        "/api/v1/admin/documents",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
        files={"files": ("image.png", BytesIO(b"\x89PNG"), "image/png")},
    )

    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_empty_file_rejected(mock_client):
    client, _, _ = mock_client

    resp = await client.post(
        "/api/v1/admin/documents",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
        files={"files": ("empty.txt", BytesIO(b""), "text/plain")},
    )

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /admin/documents/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_document_success(mock_client):
    client, mock_db, _ = mock_client
    doc = _mock_doc()

    result = MagicMock()
    result.scalar_one_or_none.return_value = doc
    mock_db.execute.return_value = result

    resp = await client.delete(
        f"/api/v1/admin/documents/{doc.id}",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_document_not_found(mock_client):
    client, mock_db, _ = mock_client

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    resp = await client.delete(
        f"/api/v1/admin/documents/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_invalid_uuid(mock_client):
    client, _, _ = mock_client
    resp = await client.delete(
        "/api/v1/admin/documents/not-a-uuid",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )
    assert resp.status_code == 422
