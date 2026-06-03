"""Unit tests for Celery worker task definitions."""

from unittest.mock import AsyncMock, MagicMock, patch


def test_ingest_document_task_is_registered():
    from app.worker.tasks import ingest_document
    assert ingest_document.name == "app.worker.tasks.ingest_document"


def test_ingest_document_task_retries_on_failure():
    from app.worker.tasks import ingest_document
    assert ingest_document.max_retries == 3


def test_celery_app_has_correct_broker():
    from app.worker.celery_app import celery_app
    from app.config import settings
    assert celery_app.conf.broker_url == settings.celery_broker_url


def test_celery_app_task_acks_late():
    from app.worker.celery_app import celery_app
    assert celery_app.conf.task_acks_late is True


@patch("app.worker.tasks.asyncio.run")
def test_ingest_document_decodes_base64_and_calls_async(mock_run):
    import base64
    from app.worker.tasks import ingest_document

    file_bytes = b"fake pdf content"
    encoded = base64.b64encode(file_bytes).decode()

    mock_run.return_value = {"doc_id": "abc", "chunk_count": 3}

    # Call the underlying function directly (bypass Celery task infrastructure)
    result = ingest_document.run(
        doc_id="test-doc-id",
        file_bytes_b64=encoded,
        filename="test.pdf",
        file_type="pdf",
        extra_metadata={"category": "test"},
    )

    mock_run.assert_called_once()
    assert result == {"doc_id": "abc", "chunk_count": 3}
