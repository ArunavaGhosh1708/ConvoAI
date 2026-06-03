import asyncio
import base64
import logging
import os
import tempfile
import uuid
from pathlib import Path

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.worker.tasks.ingest_document",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def ingest_document(
    self,
    doc_id: str,
    file_bytes_b64: str,
    filename: str,
    file_type: str,
    extra_metadata: dict,
) -> dict:
    """
    Celery task: ingest a document into the RAG vector store.
    File bytes are base64-encoded for JSON serialisation over Redis.
    Returns a summary dict with chunk_count on success.
    """
    file_bytes = base64.b64decode(file_bytes_b64)
    try:
        result = asyncio.run(
            _run_ingestion_async(doc_id, file_bytes, filename, file_type, extra_metadata)
        )
        return result
    except Exception as exc:
        logger.exception("Ingestion task failed for doc %s: %s", doc_id, exc)
        raise


async def _run_ingestion_async(
    doc_id: str,
    file_bytes: bytes,
    filename: str,
    file_type: str,
    extra_metadata: dict,
) -> dict:
    from sqlalchemy import update

    from app.database import AsyncSessionLocal
    from app.models.knowledge import Document, KnowledgeChunk
    from app.rag.ingestion import chunk_text, embed_texts, load_document

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Document)
            .where(Document.id == uuid.UUID(doc_id))
            .values(status="processing")
        )
        await db.commit()

    suffix = f".{file_type}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        raw_text = load_document(tmp_path, file_type)
    finally:
        os.unlink(tmp_path)

    chunks_text = chunk_text(raw_text)
    if not chunks_text:
        raise ValueError("Document produced no text chunks")

    embeddings = await embed_texts(chunks_text)
    base_meta = {**extra_metadata, "filename": filename}

    chunks = [
        KnowledgeChunk(
            id=uuid.uuid4(),
            document_id=uuid.UUID(doc_id),
            content=text,
            embedding=emb,
            metadata_={**base_meta, "chunk_index": idx},
        )
        for idx, (text, emb) in enumerate(zip(chunks_text, embeddings))
    ]

    async with AsyncSessionLocal() as db:
        db.add_all(chunks)
        await db.execute(
            update(Document)
            .where(Document.id == uuid.UUID(doc_id))
            .values(status="indexed", chunk_count=len(chunks))
        )
        await db.commit()

    logger.info("Ingestion complete: doc=%s chunks=%d", doc_id, len(chunks))
    return {"doc_id": doc_id, "chunk_count": len(chunks)}
