"""Score computation from an Attempt's Responses.

Approximation (not the College Board's proprietary scaled-score curve):
  scaled_section = 200 + round(600 * correct/total)  clamped [200, 800]
  total = rw + math

Also builds per-topic and per-difficulty rollups used by the results page.
"""
from __future__ import annotations
import json
from collections import defaultdict
from typing import Dict, List

from app.extensions import db
from app.models.attempt import Attempt, AttemptScore, Response
from app.models.exam import ExamModule, ExamModuleQuestion
from app.models.bank import Question, Choice
from app.models.enums import Section, Difficulty, QuestionType


def compute_and_store(attempt: Attempt) -> AttemptScore:
    """Compute an AttemptScore for the attempt and persist it (upsert)."""
    per_section_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    per_topic: Dict[str, Dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0, "wrong": 0})
    per_difficulty_time: Dict[str, int] = defaultdict(int)
    per_difficulty_count: Dict[str, int] = defaultdict(int)

    module_ids = [am.module_id for am in attempt.attempt_modules]
    modules = {m.id: m for m in ExamModule.query.filter(ExamModule.id.in_(module_ids)).all()} if module_ids else {}

    # Map question_id -> Section
    q_section: Dict[int, str] = {}
    for module in modules.values():
        for mq in module.module_questions:
            q_section[mq.question_id] = module.section.value

    q_ids = list(q_section.keys())
    questions = {q.id: q for q in Question.query.filter(Question.id.in_(q_ids)).all()} if q_ids else {}
    responses = {r.question_id: r for r in attempt.responses}

    for qid, q in questions.items():
        section = q_section.get(qid, "unknown")
        per_section_totals[section]["total"] += 1
        topic = q.topic or "Uncategorized"
        per_topic[topic]["total"] += 1
        diff_val = q.difficulty.value if q.difficulty else "medium"
        per_difficulty_count[diff_val] += 1

        r = responses.get(qid)
        if r:
            per_difficulty_time[diff_val] += r.time_spent_seconds or 0
            if r.is_correct:
                per_section_totals[section]["correct"] += 1
                per_topic[topic]["correct"] += 1
            elif r.is_correct is False:
                per_topic[topic]["wrong"] += 1

    def scaled(section: str) -> int:
        totals = per_section_totals[section]
        if totals["total"] == 0:
            return 200
        return max(200, min(800, 200 + round(600 * totals["correct"] / totals["total"])))

    rw = scaled(Section.RW.value)
    math = scaled(Section.MATH.value)
    total = rw + math

    per_difficulty_avg = {
        d: (per_difficulty_time[d] // per_difficulty_count[d]) if per_difficulty_count[d] else 0
        for d in per_difficulty_time
    }

    score = attempt.score or AttemptScore(attempt_id=attempt.id, total=0, rw=0, math=0)
    score.total = total
    score.rw = rw
    score.math = math
    score.per_topic = per_topic  # dict of dicts is fine for JSON
    score.per_difficulty_time = per_difficulty_avg

    if attempt.score is None:
        db.session.add(score)
    db.session.commit()
    return score


def question_grid(attempt: Attempt) -> List[dict]:
    """Ordered per-question status for the results page grid."""
    module_ids = [am.module_id for am in attempt.attempt_modules]
    modules = {m.id: m for m in ExamModule.query.filter(ExamModule.id.in_(module_ids)).all()} if module_ids else {}
    responses = {r.question_id: r for r in attempt.responses}

    grid = []
    for am in attempt.attempt_modules:
        module = modules.get(am.module_id)
        if not module:
            continue
        for idx, mq in enumerate(module.module_questions, start=1):
            r = responses.get(mq.question_id)
            grid.append({
                "section": module.section.value,
                "module_num": module.module_number,
                "idx": idx,
                "correct": bool(r and r.is_correct),
                "wrong": bool(r and r.is_correct is False),
                "unattempted": not (r and (r.choice_id or r.free_response_text)),
                "time_spent": r.time_spent_seconds if r else 0,
            })
    return grid


def answer_review(attempt: Attempt) -> List[dict]:
    """Rich per-question review for the results page — student's answer vs
    correct answer, choice-by-choice. Grouped by module in the resulting list.

    Each entry:
      {
        "section": "rw"|"math",
        "module_num": int,
        "idx": int,                       # position within module (1-based)
        "question_id": int,
        "type": "mcq"|"grid_in",
        "stem": str,
        "topic": str | None,
        "difficulty": str,
        "is_correct": bool | None,        # None if unattempted
        "unattempted": bool,
        "choices": [                       # MCQ only, [] for grid-in
          {"label": "A", "text": "…", "is_correct": True,
           "chosen": True, "is_wrong_pick": False},
          ...
        ],
        "student_free_response": str | None,
        "acceptable_answers": [str, ...],  # grid-in only
      }
    """
    module_ids = [am.module_id for am in attempt.attempt_modules]
    modules = {m.id: m for m in ExamModule.query.filter(ExamModule.id.in_(module_ids)).all()} if module_ids else {}
    responses = {r.question_id: r for r in attempt.responses}

    review = []
    for am in attempt.attempt_modules:
        module = modules.get(am.module_id)
        if not module:
            continue
        for idx, mq in enumerate(module.module_questions, start=1):
            q: Question = mq.question
            r: Response | None = responses.get(mq.question_id)
            chosen_id = r.choice_id if r else None
            is_correct = r.is_correct if r else None
            unattempted = not (r and (r.choice_id or r.free_response_text))

            choices_out: List[dict] = []
            if q.type == QuestionType.MCQ:
                for c in q.choices:
                    chosen = (chosen_id == c.id)
                    choices_out.append({
                        "label": c.label,
                        "text": c.text,
                        "is_correct": bool(c.is_correct),
                        "chosen": chosen,
                        "is_wrong_pick": chosen and not c.is_correct,
                    })

            acceptable: List[str] = []
            if q.type == QuestionType.GRID_IN and q.acceptable_answers:
                try:
                    parsed = json.loads(q.acceptable_answers)
                    if isinstance(parsed, list):
                        acceptable = [str(x) for x in parsed]
                except (json.JSONDecodeError, TypeError):
                    acceptable = []

            review.append({
                "section": module.section.value,
                "module_num": module.module_number,
                "idx": idx,
                "question_id": q.id,
                "type": q.type.value,
                "stem": q.stem,
                "topic": q.topic,
                "difficulty": q.difficulty.value if q.difficulty else None,
                "is_correct": is_correct,
                "unattempted": unattempted,
                "choices": choices_out,
                "student_free_response": r.free_response_text if r else None,
                "acceptable_answers": acceptable,
            })
    return review


def topics_costing_most(score: AttemptScore) -> List[dict]:
    """Ranked list of topics by number of missed questions."""
    if not score.per_topic:
        return []
    rows = []
    for topic, data in score.per_topic.items():
        rows.append({
            "topic": topic,
            "wrong": data.get("wrong", 0),
            "total": data.get("total", 0),
            "accuracy": (data.get("correct", 0) / data["total"]) if data.get("total") else None,
        })
    rows.sort(key=lambda r: r["wrong"], reverse=True)
    return rows
