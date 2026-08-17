"""Extract raw text from a .docx file using python-docx."""
from __future__ import annotations
from io import BytesIO

from docx import Document


def extract_text(data: bytes) -> str:
    doc = Document(BytesIO(data))
    parts = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            parts.append(text)
    # Include table contents too (many question docs use tables for choices)
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells)
            if row_text.strip(" |"):
                parts.append(row_text)
    return "\n".join(parts)
