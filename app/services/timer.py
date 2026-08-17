"""Server-authoritative timer.

Compute the deadline from AttemptModule.started_at + effective_time_limit_seconds
on every request. Never cache in worker memory.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

from app.models.attempt import AttemptModule


def module_deadline(am: AttemptModule) -> Optional[datetime]:
    if am.started_at is None:
        return None
    return am.started_at + timedelta(seconds=am.effective_time_limit_seconds)


def module_seconds_remaining(am: AttemptModule, now: Optional[datetime] = None) -> int:
    deadline = module_deadline(am)
    if deadline is None:
        return am.effective_time_limit_seconds
    now = now or datetime.utcnow()
    return max(0, int((deadline - now).total_seconds()))


def module_is_expired(am: AttemptModule, now: Optional[datetime] = None) -> bool:
    return module_seconds_remaining(am, now) <= 0
