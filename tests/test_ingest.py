from app.services.ingest.llm_extract import _extract_heuristic


SAMPLE = """
1. If 3x + 5 = 20, what is the value of x?
A. 3
B. 5
C. 15
D. 25
Answer: B

2. A circle has radius 4. What is its area, in terms of π?
A. 4π
B. 8π
C. 16π
D. 32π
"""


def test_heuristic_splits_questions():
    items = _extract_heuristic(SAMPLE)
    assert len(items) == 2


def test_heuristic_extracts_answer_key():
    items = _extract_heuristic(SAMPLE)
    assert items[0]["answer_source"] == "extracted"
    assert items[0]["answer"] == "B"


def test_heuristic_marks_missing_answer():
    items = _extract_heuristic(SAMPLE)
    assert items[1]["answer_source"] == "missing"
    assert items[1]["answer"] is None


def test_heuristic_parses_all_choices():
    items = _extract_heuristic(SAMPLE)
    labels = [c["label"] for c in items[0]["choices"]]
    assert labels == ["A", "B", "C", "D"]
