import hashlib
import io
import logging
import re
from dataclasses import dataclass

from docx import Document as WordDocument
from pypdf import PdfReader

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 25 * 1024 * 1024
TARGET_CHUNK_WORDS = 200
CHUNK_OVERLAP_WORDS = 35
MAX_CHUNK_WORDS = 250
HEADING_NUMBER = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?|[A-Z][.)])\s+\S")
TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class ScannedPdfError(ValueError):
    pass


@dataclass(frozen=True)
class TextBlock:
    text: str
    page: int | None
    section: str | None


@dataclass(frozen=True)
class ChunkData:
    text: str
    page: int | None
    section: str | None
    token_count: int
    content_hash: str


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_pdf(data: bytes) -> tuple[list[TextBlock], int]:
    reader = PdfReader(io.BytesIO(data))
    blocks: list[TextBlock] = []
    current_section: str | None = None
    extracted_any_text = False

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if page_text.strip():
            extracted_any_text = True
        for line in page_text.splitlines():
            line = " ".join(line.split())
            if not line:
                continue
            if _is_heading(line):
                current_section = line[:512]
                continue
            blocks.append(TextBlock(line, page_number, current_section))

    if not extracted_any_text:
        raise ScannedPdfError("Scanned PDF text extraction is not supported yet.")
    return blocks, len(reader.pages)


def extract_docx(data: bytes) -> tuple[list[TextBlock], None]:
    document = WordDocument(io.BytesIO(data))
    blocks: list[TextBlock] = []
    current_section: str | None = None

    for paragraph in document.paragraphs:
        text = " ".join(paragraph.text.split())
        if not text:
            continue
        style_name = paragraph.style.name if paragraph.style else ""
        if style_name.lower().startswith("heading") or _is_heading(text):
            current_section = text[:512]
            continue
        blocks.append(TextBlock(text, None, current_section))

    return blocks, None


def chunk_blocks(blocks: list[TextBlock]) -> list[ChunkData]:
    grouped: list[tuple[int | None, str | None, list[str]]] = []
    for block in blocks:
        if not block.text.strip():
            continue
        if grouped and grouped[-1][0:2] == (block.page, block.section):
            grouped[-1][2].append(block.text)
        else:
            grouped.append((block.page, block.section, [block.text]))

    chunks: list[ChunkData] = []
    for page, section, paragraphs in grouped:
        words = " ".join(paragraphs).split()
        start = 0
        while start < len(words):
            end = min(start + TARGET_CHUNK_WORDS, len(words))
            if end < len(words):
                sentence_boundary = max(
                    (index + 1 for index in range(start + TARGET_CHUNK_WORDS - 40, end)
                     if words[index].endswith((".", "!", "?"))),
                    default=end,
                )
                end = sentence_boundary
            chunk_text = " ".join(words[start:end]).strip()
            if chunk_text:
                chunks.append(
                    ChunkData(
                        text=chunk_text,
                        page=page,
                        section=section,
                        token_count=len(TOKEN_PATTERN.findall(chunk_text)),
                        content_hash=sha256_hex(chunk_text.encode("utf-8")),
                    )
                )
            if end == len(words):
                break
            next_start = max(start + 1, end - CHUNK_OVERLAP_WORDS)
            if end - start > MAX_CHUNK_WORDS:
                next_start = end - CHUNK_OVERLAP_WORDS
            start = next_start

    return chunks


def _is_heading(text: str) -> bool:
    words = text.split()
    if len(words) > 12 or text.endswith((".", "?", "!", ";", ",")):
        return False
    return bool(HEADING_NUMBER.match(text)) or (text.isupper() and len(words) <= 10)