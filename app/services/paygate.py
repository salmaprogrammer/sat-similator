"""ProGate helper — free/Pro tier gating pattern reused across the results page."""
from __future__ import annotations
from typing import Iterable, Any

from flask_login import current_user


def is_pro() -> bool:
    if not current_user.is_authenticated or not current_user.is_student:
        return False
    student = getattr(current_user, "student", None)
    return bool(student and student.is_pro)


def gated_slice(items: Iterable[Any], rows_visible: int = 2):
    """Return (visible, hidden_count). Pro users see all; free users see first N."""
    items = list(items)
    if is_pro():
        return items, 0
    return items[:rows_visible], max(0, len(items) - rows_visible)
