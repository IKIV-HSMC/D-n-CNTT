import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class Flashcard(Base):
    __tablename__ = "flashcards"
    __table_args__ = (
        UniqueConstraint("document_id", "card_key", name="uq_flashcard_document_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    card_key = Column(String(64), nullable=False)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    node_id = Column(String(80), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FlashcardProgress(Base):
    __tablename__ = "flashcard_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "flashcard_id", name="uq_flashcard_progress_user_card"),
        CheckConstraint("repetitions >= 0", name="ck_flashcard_progress_repetitions"),
        CheckConstraint("interval_days >= 0", name="ck_flashcard_progress_interval"),
        CheckConstraint("ease_factor >= 1.3", name="ck_flashcard_progress_ease"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    flashcard_id = Column(
        UUID(as_uuid=True), ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repetitions = Column(Integer, nullable=False, default=0, server_default="0")
    interval_days = Column(Integer, nullable=False, default=0, server_default="0")
    ease_factor = Column(Float, nullable=False, default=2.5, server_default="2.5")
    due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    total_reviews = Column(Integer, nullable=False, default=0, server_default="0")
    lapses = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ReviewEvent(Base):
    __tablename__ = "review_events"
    __table_args__ = (
        CheckConstraint("rating IN ('again', 'hard', 'good', 'easy')", name="ck_review_event_rating"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    flashcard_id = Column(
        UUID(as_uuid=True), ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating = Column(String(8), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=False)
    interval_before_days = Column(Integer, nullable=False)
    interval_after_days = Column(Integer, nullable=False)
    ease_before = Column(Float, nullable=False)
    ease_after = Column(Float, nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=False)
