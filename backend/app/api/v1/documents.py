"""
Document management endpoints (FR-12, FR-15, FR-16).

  POST   /api/v1/admin/documents           — upload 1+ files; ingests in background
  GET    /api/v1/admin/documents           — list all documents
  DELETE /api/v1/admin/documents/{id}      — remove document + all its chunks
"""

import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.middleware.auth import require_admin_jwt
from app.models.knowledge import Document, KnowledgeChunk
from app.rag.ingestion import ingest_document
from app.schemas.document import DocumentOut, DocumentUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])

_ALLOWED_TYPES = {"pdf", "docx", "html", "txt"}
_MAX_FILE_MB   = 50


def _file_type_from(filename: str, content_type: str | None) -> str | None:
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext in _ALLOWED_TYPES:
        return ext
    # fallback: infer from content-type
    mime_map = {
        "application/pdf":              "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/html":                    "html",
        "text/plain":                   "txt",
    }
    return mime_map.get((content_type or "").split(";")[0].strip())


def _doc_to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id),
        filename=doc.filename,
        file_type=doc.file_type,
        status=doc.status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Background ingestion task
# ---------------------------------------------------------------------------

async def _run_ingestion(
    doc_id: str,
    file_bytes: bytes,
    filename: str,
    file_type: str,
    extra_metadata: dict,
) -> None:
    """Opens its own DB session — runs outside the request/response lifecycle."""
    async with AsyncSessionLocal() as db:
        try:
            file_obj = io.BytesIO(file_bytes)
            file_obj.name = filename
            # Update existing pending document rather than creating a new one
            from sqlalchemy import update
            await db.execute(
                update(Document)
                .where(Document.id == uuid.UUID(doc_id))
                .values(status="processing")
            )
            await db.commit()

            # Re-fetch the document and run ingestion on it
            # We do this by bypassing ingest_document's document creation
            # and calling the chunking/embedding pipeline directly
            from app.rag.ingestion import load_document, chunk_text, embed_texts
            import os
            import tempfile

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
            base_meta  = {**extra_metadata, "filename": filename}

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
            async with AsyncSessionLocal() as db2:
                db2.add_all(chunks)
                await db2.execute(
                    update(Document)
                    .where(Document.id == uuid.UUID(doc_id))
                    .values(status="indexed", chunk_count=len(chunks))
                )
                await db2.commit()
            logger.info("Background ingestion complete: doc=%s chunks=%d", doc_id, len(chunks))

        except Exception as exc:
            logger.exception("Background ingestion failed for doc %s: %s", doc_id, exc)
            async with AsyncSessionLocal() as db_err:
                from sqlalchemy import update
                await db_err.execute(
                    update(Document)
                    .where(Document.id == uuid.UUID(doc_id))
                    .values(status="failed")
                )
                await db_err.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/admin/documents", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentUploadResponse)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    category: str = Form(""),
    product:  str = Form(""),
    version:  str = Form(""),
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_admin_jwt),
) -> DocumentUploadResponse:
    """
    Upload one or more documents for RAG ingestion.
    Returns 202 immediately; ingestion runs in the background.
    Poll GET /admin/documents to check status (FR-15: available within 5 min).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    docs_out: list[DocumentOut] = []
    extra_meta = {k: v for k, v in {"category": category, "product": product, "version": version}.items() if v}

    for upload in files:
        filename = upload.filename or "unnamed"
        file_type = _file_type_from(filename, upload.content_type)
        if not file_type:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type for '{filename}'. Allowed: {_ALLOWED_TYPES}",
            )

        file_bytes = await upload.read()
        if len(file_bytes) > _MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"'{filename}' exceeds {_MAX_FILE_MB} MB limit")
        if not file_bytes:
            raise HTTPException(status_code=400, detail=f"'{filename}' is empty")

        # Create a pending document record
        doc = Document(
            id=uuid.uuid4(),
            filename=filename,
            file_type=file_type,
            status="pending",
            chunk_count=0,
            created_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        await db.flush()

        background_tasks.add_task(
            _run_ingestion,
            doc_id=str(doc.id),
            file_bytes=file_bytes,
            filename=filename,
            file_type=file_type,
            extra_metadata=extra_meta,
        )
        docs_out.append(_doc_to_out(doc))

    await db.commit()
    return DocumentUploadResponse(
        documents=docs_out,
        message=f"{len(docs_out)} document(s) queued for ingestion",
    )


@router.get("/admin/documents", response_model=list[DocumentOut])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_admin_jwt),
) -> list[DocumentOut]:
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    return [_doc_to_out(d) for d in result.scalars()]


@router.delete("/admin/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_admin_jwt),
) -> None:
    """Remove document and all its knowledge chunks from the vector store."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    result = await db.execute(select(Document).where(Document.id == doc_uuid))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_uuid))
    await db.delete(doc)
    await db.commit()
    logger.info("Deleted document %s and its chunks", document_id)
