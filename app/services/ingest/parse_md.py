"""Markdown is already structured text; pass it through as-is."""
from __future__ import annotations


def extract_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")
