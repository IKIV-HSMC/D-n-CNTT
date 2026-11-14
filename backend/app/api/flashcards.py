from __future__ import annotations

import hashlib
import html
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.api.auth import get_current_user
from app.api.dependencies import validate_request_origin
from app.core.database import get_db
from app.models.document import Document
from app.models.flashcard import Flashcard, FlashcardProgress, ReviewEvent
from app.models.user import User
from app.schemas.flashcard import (
    FlashcardSessionResponse,
    ReviewRequest,
    ReviewResponse,
)
from app.services.sm2 import schedule_review

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/flashcards",
    tags=["flashcards"],
    dependencies=[Depends(validate_request_origin)],
)


@router.get("/session", response_model=FlashcardSessionResponse)
async def get_review_session(
    document_id: uuid.UUID,
    limit: int = Query(30, ge=1, le=250),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FlashcardSessionResponse:
    """Return new and due cards owned by this account for one document."""
    owned = await db.execute(
        select(Document.id).where(Document.id == document_id, Document.user_id == user.id)
    )
    if owned.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Flashcard, FlashcardProgress)
        .join(Document, Document.id == Flashcard.document_id)
        .outerjoin(
            FlashcardProgress,
            and_(
                FlashcardProgress.flashcard_id == Flashcard.id,
                FlashcardProgress.user_id == user.id,
            ),
        )
        .where(
            Document.id == document_id,
            Document.user_id == user.id,
            Flashcard.is_active.is_(True),
            or_(FlashcardProgress.id.is_(None), FlashcardProgress.due_at <= now),
        )
        .order_by(FlashcardProgress.due_at.asc().nullsfirst(), Flashcard.created_at.asc())
        .limit(limit)
    )

    cards: list[dict[str, Any]] = []
    for card, progress in result.all():
        cards.append({
            "id": card.id,
            "document_id": card.document_id,
            "front": card.front,
            "back": card.back,
            "node_id": card.node_id,
            "due_at": progress.due_at if progress else now,
            "repetitions": progress.repetitions if progress else 0,
            "interval_days": progress.interval_days if progress else 0,
            "ease_factor": progress.ease_factor if progress else 2.5,
            "total_reviews": progress.total_reviews if progress else 0,
            "is_new": progress is None,
        })
    return FlashcardSessionResponse(cards=cards, returned_count=len(cards))


@router.post("/{flashcard_id}/review", response_model=ReviewResponse)
async def review_flashcard(
    flashcard_id: uuid.UUID,
    payload: ReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    result = await db.execute(
        select(Flashcard)
        .join(Document, Document.id == Flashcard.document_id)
        .where(
            Flashcard.id == flashcard_id,
            Flashcard.is_active.is_(True),
            Document.user_id == user.id,
        )
        .with_for_update()
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy flashcard")

    progress_result = await db.execute(
        select(FlashcardProgress)
        .where(
            FlashcardProgress.user_id == user.id,
            FlashcardProgress.flashcard_id == card.id,
        )
        .with_for_update()
    )
    progress = progress_result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if progress is None:
        progress = FlashcardProgress(
            user_id=user.id,
            flashcard_id=card.id,
            due_at=now,
        )
        db.add(progress)
        await db.flush()

    old_interval = progress.interval_days
    old_ease = progress.ease_factor
    next_schedule = schedule_review(
        rating=payload.rating,
        repetitions=progress.repetitions,
        interval_days=progress.interval_days,
        ease_factor=progress.ease_factor,
        lapses=progress.lapses,
        now=now,
    )
    progress.repetitions = next_schedule.repetitions
    progress.interval_days = next_schedule.interval_days
    progress.ease_factor = next_schedule.ease_factor
    progress.due_at = next_schedule.due_at
    progress.last_reviewed_at = now
    progress.total_reviews += 1
    progress.lapses = next_schedule.lapses
    total_reviews = progress.total_reviews
    db.add(
        ReviewEvent(
            user_id=user.id,
            flashcard_id=card.id,
            rating=payload.rating,
            reviewed_at=now,
            interval_before_days=old_interval,
            interval_after_days=next_schedule.interval_days,
            ease_before=old_ease,
            ease_after=next_schedule.ease_factor,
            due_at=next_schedule.due_at,
        )
    )
    await db.commit()
    return ReviewResponse(
        flashcard_id=card.id,
        rating=payload.rating,
        reviewed_at=now,
        due_at=next_schedule.due_at,
        repetitions=next_schedule.repetitions,
        interval_days=next_schedule.interval_days,
        ease_factor=next_schedule.ease_factor,
        total_reviews=total_reviews,
        lapses=next_schedule.lapses,
    )


@router.get("/{document_id}/export/anki", response_class=FileResponse)
async def export_anki_deck(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Build a portable .apkg package containing the document's active cards."""
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    card_result = await db.execute(
        select(Flashcard)
        .where(Flashcard.document_id == document_id, Flashcard.is_active.is_(True))
        .order_by(Flashcard.created_at.asc())
    )
    cards = list(card_result.scalars().all())
    if not cards:
        raise HTTPException(status_code=400, detail="Tài liệu chưa có flashcard để xuất")

    try:
        import genanki

        deck_id = _stable_anki_id(f"deck:{document_id}")
        model_id = _stable_anki_id("docmind-basic-model-v1")
        model = genanki.Model(
            model_id,
            "DocMind Basic",
            fields=[{"name": "Question"}, {"name": "Answer"}],
            templates=[{
                "name": "Card 1",
                "qfmt": "{{Question}}",
                "afmt": '{{FrontSide}}<hr id="answer">{{Answer}}',
            }],
        )
        deck_name = Path(doc.original_filename).stem.strip() or "DocMind"
        deck = genanki.Deck(deck_id, f"DocMind::{deck_name}")
        for card in cards:
            front = html.escape(card.front).replace("\n", "<br>")
            back = html.escape(card.back).replace("\n", "<br>")
            note = genanki.Note(model=model, fields=[front, back])
            deck.add_note(note)

        fd, file_path = tempfile.mkstemp(suffix=".apkg")
        os.close(fd)
        genanki.Package(deck).write_to_file(file_path)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Không thể tạo Anki package cho document %s", document_id)
        if "file_path" in locals() and os.path.exists(file_path):
            os.unlink(file_path)
        raise HTTPException(status_code=500, detail="Không thể tạo file Anki") from exc

    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(doc.original_filename).stem).strip("._")[:80]
    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=f"{stem or 'docmind'}_anki.apkg",
        background=BackgroundTask(os.unlink, file_path),
    )


def _stable_anki_id(value: str) -> int:
    """Return a deterministic 31-bit identifier in Anki's recommended range."""
    return 1_000_000_000 + int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16) % 1_000_000_000
