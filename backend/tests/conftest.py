import os
from collections.abc import Iterator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app import database
from app.database import Base
from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
	test_engine = create_engine(
		"sqlite+pysqlite:///:memory:",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	Base.metadata.create_all(bind=test_engine)
	monkeypatch.setattr(
		database,
		"SessionLocal",
		sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False),
	)
	monkeypatch.setattr(database, "create_schema", lambda: None)
	with TestClient(app) as test_client:
		yield test_client
	test_engine.dispose()


@pytest.fixture
def pdf_factory():
	return make_text_pdf


def make_text_pdf(text: str) -> bytes:
	stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
	objects = [
		b"<< /Type /Catalog /Pages 2 0 R >>",
		b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
		b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
		b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
		b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
		b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
	]
	pdf = b"%PDF-1.4\n"
	offsets = [0]
	for object_number, body in enumerate(objects, start=1):
		offsets.append(len(pdf))
		pdf += f"{object_number} 0 obj\n".encode() + body + b"\nendobj\n"

	xref_offset = len(pdf)
	pdf += f"xref\n0 {len(offsets)}\n".encode()
	pdf += b"0000000000 65535 f \n"
	pdf += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
	pdf += (
		f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
		f"startxref\n{xref_offset}\n%%EOF\n"
	).encode()
	return pdf