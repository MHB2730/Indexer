"""Text extraction from PDF and DOCX."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document


@dataclass
class ExtractedDoc:
    path: Path
    text: str
    pages: list[str]  # page-by-page text (single entry for DOCX)


def extract(path: Path) -> ExtractedDoc:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix in {".docx", ".doc"}:
        return _extract_docx(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def _extract_pdf(path: Path) -> ExtractedDoc:
    pages: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            pages.append(page.get_text("text") or "")
    return ExtractedDoc(path=path, text="\n".join(pages), pages=pages)


def _extract_docx(path: Path) -> ExtractedDoc:
    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text)
    text = "\n".join(parts)
    return ExtractedDoc(path=path, text=text, pages=[text])


def first_page_text(path: Path, max_chars: int = 4000) -> str:
    """Cheap fingerprint of a candidate document — first page or first N chars."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        with fitz.open(path) as doc:
            if len(doc) == 0:
                return ""
            return (doc[0].get_text("text") or "")[:max_chars]
    if suffix in {".docx", ".doc"}:
        return _extract_docx(path).text[:max_chars]
    return ""
