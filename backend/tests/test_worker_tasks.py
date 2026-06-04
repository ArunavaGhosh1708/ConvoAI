"""Unit tests for Celery worker task definitions and celery app config."""


async def test_ingest_document_task_is_registered():
    from app.worker.tasks import ingest_document
    assert ingest_document.name == "app.worker.tasks.ingest_document"


async def test_ingest_document_task_retries_on_failure():
    from app.worker.tasks import ingest_document
    assert ingest_document.max_retries == 3


async def test_ingest_document_task_autoretry_configured():
    from app.worker.tasks import ingest_document
    assert Exception in ingest_document.autoretry_for


async def test_celery_app_has_correct_broker():
    from app.config import settings
    from app.worker.celery_app import celery_app
    assert celery_app.conf.broker_url == settings.celery_broker_url


async def test_celery_app_task_acks_late():
    from app.worker.celery_app import celery_app
    assert celery_app.conf.task_acks_late is True
