"""Extract raw text from a PDF using pdfplumber.

Note: scanned/image-only PDFs won't extract text this way. Surface this as a
known limitation (§2.10); OCR is a post-v1 enhancement.
"""
from __future__ import annotations
from io import BytesIO

import pdfplumber


def extract_text(data: bytes) -> str:
    parts = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)
    return "\n\n".join(parts)
