"""Read the text of a generated PDF, one string per drawn text operation."""
from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def pdf_strings(pdf_bytes: bytes) -> list[str]:
    strings: list[str] = []

    def collect(text, _cm, _tm, _font_dict, _font_size) -> None:
        text = text.strip()
        if text.strip():
            strings.append(text)

    for page in PdfReader(BytesIO(pdf_bytes)).pages:
        page.extract_text(visitor_text=collect)
    return strings


def pdf_text(pdf_bytes: bytes) -> str:
    return "\n".join(pdf_strings(pdf_bytes))


def pdf_pages(pdf_bytes: bytes) -> list[str]:
    """The text of each page, in drawing order."""
    pages: list[str] = []
    for page in PdfReader(BytesIO(pdf_bytes)).pages:
        parts: list[str] = []

        def collect(text, _cm, _tm, _font_dict, _font_size, parts=parts) -> None:
            text = text.strip()
            if text.strip():
                parts.append(text)

        page.extract_text(visitor_text=collect)
        pages.append("\n".join(parts))
    return pages
