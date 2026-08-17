"""Extract raw text from a PDF using pdfplumber.

Note: scanned/image-only PDFs won't extract text this way. Surface this as a
known limitation (§2.10); OCR is a post-v1 enhancement.

pdfplumber pulls in pdfminer.six + PIL — ~80MB resident. Import it lazily
inside extract_text so the Flask boot on a 512MB container doesn't OOM.
"""
from __future__ import annotations
from io import BytesIO


def extract_text(data: bytes) -> str:
    import pdfplumber  # lazy — heavy import
    parts = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)
    return "\n\n".join(parts)
