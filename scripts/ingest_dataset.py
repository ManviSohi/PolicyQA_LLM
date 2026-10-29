from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.chdir(BACKEND_DIR)

from sqlalchemy import select

from app.database import SessionLocal, create_schema
from app.models import Chunk, Document
from app.services.document_ingestion import chunk_blocks, extract_pdf, sha256_hex

DATASET_DIR = ROOT / "dataset"


def ingest_dataset() -> None:
    create_schema()

    with SessionLocal() as db:
        for pdf_path in sorted(DATASET_DIR.glob("*.pdf")):
            content = pdf_path.read_bytes()
            digest = sha256_hex(content)
            existing = db.scalar(select(Document.id).where(Document.sha256 == digest))
            if existing is not None:
                print(f"Skipped {pdf_path.name}: already ingested")
                continue

            document = Document(
                filename=pdf_path.name,
                file_type="pdf",
                file_size=len(content),
                sha256=digest,
                status="processing",
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            blocks, page_count = extract_pdf(content)
            chunks = chunk_blocks(blocks)
            if not chunks:
                document.status = "failed"
                document.error_message = "No extractable text was found in the uploaded document."
                db.commit()
                print(f"Failed {pdf_path.name}: no extractable text")
                continue

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
            print(f"Indexed {pdf_path.name} ({len(chunks)} chunks)")


if __name__ == "__main__":
    ingest_dataset()
