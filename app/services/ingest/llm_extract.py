"""LLM extraction step per §2.10 of the plan.

Given raw extracted text, returns a list of ExtractedItem dicts:

    {
      "raw_text": str,
      "stem": str,
      "choices": [{"label": "A", "text": "..."}, ...] | None,   # None for grid-in
      "answer": str | None,                                     # choice label or acceptable answer(s)
      "answer_source": "extracted" | "ai_generated" | "missing",
      "confidence": float | None,
      "topic": str | None,
      "difficulty": str | None,
    }

If ANTHROPIC_API_KEY is configured we call Claude; otherwise we fall back to a
deterministic heuristic parser suitable for well-structured markdown / text
input. That keeps dev + tests fast and offline.
"""
from __future__ import annotations
import json
import re
from typing import List, Dict, Any, Optional

from flask import current_app


PROMPT_TEMPLATE = """You are an expert exam-question extractor for the SAT.
The following document contains one or more practice questions. Extract every question you find into a JSON array.

For each question, return a JSON object with these keys:
- "stem": the question stem (string, required)
- "choices": array of {"label": "A"|"B"|"C"|"D", "text": "..."} for multiple-choice, or null for free-response (grid-in) questions
- "answer": the correct answer. For MCQ, the letter of the correct choice. For grid-in, a JSON-array-encoded string of acceptable numeric-equivalent answers, e.g. "[\"0.5\", \"1/2\"]"
- "answer_source": one of "extracted" (the document explicitly stated the answer, e.g. an answer key or bolded choice), "ai_generated" (you solved the question yourself), or "missing" (no answer stated and you cannot confidently solve it)
- "confidence": float 0.0-1.0 when answer_source is "ai_generated"; null otherwise
- "topic": your best guess of the topic (e.g. "Algebra", "Geometry", "Reading Comprehension"), or null
- "difficulty": one of "easy", "medium", "hard", or null

Return ONLY the JSON array. No preamble, no explanation, no markdown fences.

Document:
---
{text}
---
"""


def extract(text: str) -> List[Dict[str, Any]]:
    """Return a list of extracted item dicts; keeps raw_text alongside each."""
    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            items = _extract_via_anthropic(text, api_key)
        except Exception as e:  # noqa: BLE001
            current_app.logger.warning("Anthropic extraction failed, falling back to heuristic: %s", e)
            items = _extract_heuristic(text)
    else:
        items = _extract_heuristic(text)

    # Attach a slice of raw text to each item for teacher reference
    for it in items:
        it.setdefault("raw_text", it.get("stem", "")[:500])
    return items


# ---------------------------------------------------------------------------
# Anthropic path
# ---------------------------------------------------------------------------

def _extract_via_anthropic(text: str, api_key: str) -> List[Dict[str, Any]]:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(text=text[:60_000])}],
    )
    content = "".join(getattr(part, "text", "") for part in msg.content)
    content = content.strip()
    # Strip possible ```json fences even though we asked not to
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.M)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Anthropic returned non-JSON: {content[:200]}") from e
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array")
    return data


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------

_Q_HEADER_RE = re.compile(r"^\s*(?:Question\s+)?(\d+)[\.\)\:]\s*", re.IGNORECASE)
_CHOICE_RE = re.compile(r"^\s*\(?([A-D])[\)\.]\s*(.+)$")
_ANSWER_RE = re.compile(r"^\s*Answer\s*:\s*([A-D]|[\d\.\-\/]+)\s*$", re.IGNORECASE)


def _extract_heuristic(text: str) -> List[Dict[str, Any]]:
    lines = [ln.rstrip() for ln in text.splitlines()]
    items: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    stem_buffer: List[str] = []

    def flush():
        if current is None:
            return
        current["stem"] = " ".join(stem_buffer).strip()
        stem_buffer.clear()
        items.append(current)

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        m = _Q_HEADER_RE.match(line)
        if m:
            flush()
            rest = line[m.end():].strip()
            current = {
                "stem": "",
                "choices": [],
                "answer": None,
                "answer_source": "missing",
                "confidence": None,
                "topic": None,
                "difficulty": None,
                "raw_text": line,
            }
            stem_buffer = [rest] if rest else []
            continue

        if current is None:
            continue

        current["raw_text"] += "\n" + line

        ans = _ANSWER_RE.match(line)
        if ans:
            current["answer"] = ans.group(1).upper() if len(ans.group(1)) == 1 else ans.group(1)
            current["answer_source"] = "extracted"
            continue

        ch = _CHOICE_RE.match(line)
        if ch:
            label, ctext = ch.group(1), ch.group(2).strip()
            # If choice text ends with **A** or [X] marker, capture the correct choice
            marker = re.search(r"\*\*correct\*\*|\[correct\]|\(correct\)", ctext, re.IGNORECASE)
            if marker:
                ctext = re.sub(r"\*\*correct\*\*|\[correct\]|\(correct\)", "", ctext, flags=re.IGNORECASE).strip()
                current["answer"] = label
                current["answer_source"] = "extracted"
            current["choices"].append({"label": label, "text": ctext})
            continue

        stem_buffer.append(line)

    flush()

    # Normalize free-response questions (no choices detected)
    for it in items:
        if not it["choices"]:
            it["choices"] = None
            if it.get("answer") and it.get("answer_source") == "extracted":
                # Wrap single-value answer into a JSON array for grid-in grading
                it["answer"] = json.dumps([str(it["answer"])])

    return items
