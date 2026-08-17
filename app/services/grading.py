"""Grading for MCQ and grid-in (free-response) responses.

Grid-in grading must match numerically, not by string: "1/2" and "0.5" both grade
correct against an acceptable-answer-set containing either representation.
Same helper is used by ingestion (§2.10) to validate parsed grid-in answers.
"""
from __future__ import annotations
import json
import re
from fractions import Fraction
from typing import Iterable, Optional

from app.models.bank import Question, Choice
from app.models.attempt import Response


_NUMERIC_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:/\d+)?$|^-?\d+/\d+$")


def _to_fraction(s: str) -> Optional[Fraction]:
    s = s.strip().replace(" ", "")
    if not s:
        return None
    try:
        if "/" in s:
            num, den = s.split("/", 1)
            return Fraction(int(num), int(den))
        if "." in s:
            return Fraction(s).limit_denominator(1_000_000)
        return Fraction(int(s))
    except (ValueError, ZeroDivisionError):
        return None


def numeric_equivalent(user_input: str, acceptable: Iterable[str]) -> bool:
    """True if user_input is numerically equal to any string in `acceptable`."""
    if user_input is None:
        return False
    u = _to_fraction(user_input)
    if u is None:
        # non-numeric grid-in (rare) — fall back to trimmed string comparison
        stripped = user_input.strip().lower()
        return any(stripped == a.strip().lower() for a in acceptable)
    for a in acceptable:
        av = _to_fraction(a)
        if av is not None and av == u:
            return True
    return False


def grade_response(response: Response, question: Question) -> Optional[bool]:
    """Return True/False/None (None if unanswered)."""
    if question.type.value == "mcq":
        if response.choice_id is None:
            return None
        chosen: Optional[Choice] = next((c for c in question.choices if c.id == response.choice_id), None)
        return bool(chosen and chosen.is_correct)

    # grid-in
    if not response.free_response_text:
        return None
    try:
        acceptable = json.loads(question.acceptable_answers or "[]")
    except json.JSONDecodeError:
        acceptable = []
    if not acceptable:
        return None
    return numeric_equivalent(response.free_response_text, acceptable)
