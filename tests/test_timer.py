from datetime import datetime, timedelta

from app.models.attempt import AttemptModule
from app.services.timer import module_deadline, module_seconds_remaining, module_is_expired


def test_timer_none_when_not_started():
    am = AttemptModule(started_at=None, effective_time_limit_seconds=600, attempt_id=1, module_id=1)
    assert module_deadline(am) is None
    assert module_seconds_remaining(am) == 600


def test_timer_deadline_computed():
    start = datetime(2024, 1, 1, 12, 0, 0)
    am = AttemptModule(started_at=start, effective_time_limit_seconds=1800, attempt_id=1, module_id=1)
    assert module_deadline(am) == start + timedelta(seconds=1800)


def test_timer_remaining_clamped_at_zero():
    long_ago = datetime.utcnow() - timedelta(hours=2)
    am = AttemptModule(started_at=long_ago, effective_time_limit_seconds=600, attempt_id=1, module_id=1)
    assert module_seconds_remaining(am) == 0
    assert module_is_expired(am)
