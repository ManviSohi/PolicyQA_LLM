import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Chunk, Document
from app.schemas.documents import DocumentDetailResponse, DocumentResponse
from app.services.document_ingestion import (
    MAX_FILE_SIZE,
    ScannedPdfError,
    chunk_blocks,
    extract_docx,
    extract_pdf,
    sha256_hex,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> DocumentResponse:
    filename = (file.filename or "").strip()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    extension = f".{extension}"
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only PDF and DOCX files are supported.")

    content = await file.read(MAX_FILE_SIZE + 1)
    if not content:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File exceeds the 25 MB size limit.")

    digest = sha256_hex(content)
    existing_id = db.scalar(select(Document.id).where(Document.sha256 == digest))
    if existing_id is not None:
        raise HTTPException(409, "This file has already been uploaded.")

    document = Document(
        filename=filename,
        file_type=extension[1:],
        file_size=len(content),
        sha256=digest,
        status="processing",
    )
    db.add(document)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        logger.info("Duplicate document upload rejected: %s", filename)
        raise HTTPException(409, "This file has already been uploaded.") from error
    db.refresh(document)

    try:
        blocks, page_count = extract_pdf(content) if extension == ".pdf" else extract_docx(content)
        chunks = chunk_blocks(blocks)
        if not chunks:
            raise ValueError("No extractable text was found in the uploaded document.")

        document.page_count = page_count
        db.add_all(
            [
                Chunk(
                    document_id=document.id,
                    chunk_index=index,
                    text=chunk.text,
                    page=chunk.page,
                    section=chunk.section,
                    token_count=chunk.token_count,
                    content_hash=chunk.content_hash,
                )
                for index, chunk in enumerate(chunks)
            ]
        )
        document.status = "indexed"
        document.error_message = None
        db.commit()
        db.refresh(document)
        logger.info("Indexed document %s (%s chunks)", document.id, len(chunks))
        return _document_response(document, len(chunks))
    except ScannedPdfError as error:
        _mark_failed(db, document, str(error))
        raise HTTPException(422, str(error)) from error
    except Exception as error:
        _mark_failed(db, document, "Document text extraction or indexing failed.")
        logger.exception("Failed to index document %s", document.id)
        if isinstance(error, ValueError):
            raise HTTPException(422, str(error)) from error
        raise HTTPException(422, "Document text extraction or indexing failed.") from error


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    chunk_counts = (
        select(Chunk.document_id, func.count(Chunk.id).label("chunk_count"))
        .group_by(Chunk.document_id)
        .subquery()
    )
    rows = db.execute(
        select(Document, func.coalesce(chunk_counts.c.chunk_count, 0))
        .outerjoin(chunk_counts, Document.id == chunk_counts.c.document_id)
        .order_by(Document.created_at.desc())
    )
    return [_document_response(document, count) for document, count in rows]


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: UUID, db: Session = Depends(get_db)) -> DocumentDetailResponse:
    document = db.scalar(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == document_id)
    )
    if document is None:
        raise HTTPException(404, "Document not found.")
    response = _document_response(document, len(document.chunks)).model_dump()
    response["chunks"] = document.chunks
    return DocumentDetailResponse.model_validate(response)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: UUID, db: Session = Depends(get_db)) -> None:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found.")
    db.delete(document)
    db.commit()
    logger.info("Deleted document %s", document_id)


def _mark_failed(db: Session, document: Document, message: str) -> None:
    db.rollback()
    document = db.get(Document, document.id)
    if document is not None:
        document.status = "failed"
        document.error_message = message
        db.commit()


def _document_response(document: Document, chunk_count: int) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        sha256=document.sha256,
        version=document.version,
        status=document.status,
        page_count=document.page_count,
        chunk_count=chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
        error_message=document.error_message,
    )