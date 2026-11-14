from datetime import datetime
from typing import Literal
from uuid import UUID
from typing import Any

from pydantic import BaseModel

ReviewRating = Literal["again", "hard", "good", "easy"]


class FlashcardSessionCard(BaseModel):
    id: UUID
    document_id: UUID
    front: str
    back: str
    node_id: str | None = None
    due_at: datetime
    repetitions: int
    interval_days: int
    ease_factor: float
    total_reviews: int
    is_new: bool


class FlashcardSessionResponse(BaseModel):
    cards: list[FlashcardSessionCard]
    returned_count: int


class ReviewRequest(BaseModel):
    rating: ReviewRating


class ReviewResponse(BaseModel):
    flashcard_id: UUID
    rating: ReviewRating
    reviewed_at: datetime
    due_at: datetime
    repetitions: int
    interval_days: int
    ease_factor: float
    total_reviews: int
    lapses: int


class ProcessingRunResponse(BaseModel):
    id: UUID
    document_id: UUID
    mode: Literal["engine", "ai"]
    status: Literal["queued", "processing", "completed", "failed"]
    stage: str
    progress: int
    attempts: int
    error_message: str | None = None
    result: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
