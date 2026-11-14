from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

Rating = Literal["again", "hard", "good", "easy"]


@dataclass(frozen=True)
class ReviewSchedule:
    repetitions: int
    interval_days: int
    ease_factor: float
    due_at: datetime
    lapses: int


def schedule_review(
    *,
    rating: Rating,
    repetitions: int,
    interval_days: int,
    ease_factor: float,
    lapses: int,
    now: datetime,
) -> ReviewSchedule:
    """Schedule a review using SM-2 ease updates and four user-facing grades."""
    quality = {"again": 0, "hard": 3, "good": 4, "easy": 5}[rating]
    ease_delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    next_ease = max(1.3, ease_factor + ease_delta)

    if rating == "again":
        next_repetitions = 0
        next_interval = 0
        due_at = now + timedelta(minutes=10)
        next_lapses = lapses + 1
    else:
        next_repetitions = repetitions + 1
        next_lapses = lapses

        if rating == "easy":
            if next_repetitions == 1:
                next_interval = 4
            elif next_repetitions == 2:
                next_interval = 10
            else:
                next_interval = max(1, round(interval_days * ease_factor * 1.3))
        else:
            if next_repetitions == 1:
                next_interval = 1
            elif next_repetitions == 2:
                next_interval = 6
            else:
                next_interval = max(1, round(interval_days * ease_factor))
            if rating == "hard" and next_repetitions > 1:
                next_interval = max(1, round(next_interval * 0.75))

        due_at = now + timedelta(days=next_interval)

    return ReviewSchedule(
        repetitions=next_repetitions,
        interval_days=next_interval,
        ease_factor=next_ease,
        due_at=due_at,
        lapses=next_lapses,
    )
