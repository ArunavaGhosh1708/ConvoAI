"""Celery worker tests live in test_services.py (avoids pytest-asyncio session teardown
race that occurs when this file is the last collected module)."""


async def test_worker_module_importable():
    from app.worker import tasks, celery_app  # noqa: F401
