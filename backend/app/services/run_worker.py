from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update

from app.core.database import AsyncSessionLocal
from app.models.document import Document
from app.models.processing_run import ProcessingRun
from app.services.ai_pipeline import AIServiceError
from app.services.mindmap_generator import generate_mindmap_result, persist_mindmap_result

logger = logging.getLogger(__name__)
LEASE_SECONDS = 90
HEARTBEAT_SECONDS = 25
POLL_SECONDS = 2


@dataclass(frozen=True)
class RunPayload:
    id: uuid.UUID
    document_id: uuid.UUID
    user_id: uuid.UUID
    mode: str
    worker_id: str


async def run_worker_forever() -> None:
    worker_id = str(uuid.uuid4())
    logger.info("Mindmap worker %s started", worker_id)
    while True:
        try:
            payload = await _claim_next(worker_id)
        except Exception:
            logger.exception("Could not claim a processing run")
            await asyncio.sleep(POLL_SECONDS)
            continue
        if payload is None:
            await asyncio.sleep(POLL_SECONDS)
            continue
        await _process(payload)


async def _claim_next(worker_id: str) -> RunPayload | None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        # Expired leases at the retry limit are terminal rather than silently stuck.
        exhausted_result = await db.execute(
            select(ProcessingRun)
            .where(
                ProcessingRun.status == "processing",
                ProcessingRun.lease_expires_at <= now,
                ProcessingRun.attempts >= ProcessingRun.max_attempts,
            )
            .with_for_update(skip_locked=True)
        )
        exhausted_runs = list(exhausted_result.scalars().all())
        for expired in exhausted_runs:
            expired.status = "failed"
            expired.stage = "failed"
            expired.error_message = "Worker mất lease và tác vụ đã hết số lần thử lại."
            expired.completed_at = now
            expired.lease_expires_at = None
        if exhausted_runs:
            await db.commit()

        candidate = await db.execute(
            select(ProcessingRun)
            .where(
                ProcessingRun.attempts < ProcessingRun.max_attempts,
                or_(
                    and_(
                        ProcessingRun.status == "queued",
                        or_(ProcessingRun.retry_after.is_(None), ProcessingRun.retry_after <= now),
                    ),
                    and_(
                        ProcessingRun.status == "processing",
                        ProcessingRun.lease_expires_at <= now,
                    ),
                ),
            )
            .order_by(ProcessingRun.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        run = candidate.scalar_one_or_none()
        if run is None:
            await db.commit()
            return None

        run.status = "processing"
        run.stage = "starting"
        run.progress = 1
        run.attempts += 1
        run.worker_id = worker_id
        run.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        run.retry_after = None
        run.started_at = run.started_at or now
        run.error_message = None
        await db.commit()
        return RunPayload(run.id, run.document_id, run.user_id, run.mode, worker_id)


async def _process(payload: RunPayload) -> None:
    heartbeat = asyncio.create_task(_heartbeat(payload))
    try:
        async with AsyncSessionLocal() as db:
            document_result = await db.execute(
                select(Document).where(
                    Document.id == payload.document_id,
                    Document.user_id == payload.user_id,
                )
            )
            doc = document_result.scalar_one_or_none()
            if doc is None or not doc.extracted_text:
                raise ValueError("Không tìm thấy nội dung đã trích xuất của tài liệu.")
            extracted_text = doc.extracted_text
            filename = doc.original_filename

        async def update_progress(stage: str, progress: int) -> None:
            await _renew_lease(payload, stage=stage, progress=progress)

        result = await generate_mindmap_result(
            mode=payload.mode,
            extracted_text=extracted_text,
            original_filename=filename,
            on_progress=update_progress,
        )
        result["document_id"] = str(payload.document_id)

        async with AsyncSessionLocal() as db:
            run_result = await db.execute(
                select(ProcessingRun)
                .where(
                    ProcessingRun.id == payload.id,
                    ProcessingRun.worker_id == payload.worker_id,
                    ProcessingRun.status == "processing",
                )
                .with_for_update()
            )
            run = run_result.scalar_one_or_none()
            if run is None:
                logger.warning("Worker %s lost run lease for %s", payload.worker_id, payload.id)
                return

            doc_result = await db.execute(
                select(Document).where(
                    Document.id == payload.document_id,
                    Document.user_id == payload.user_id,
                )
            )
            doc = doc_result.scalar_one_or_none()
            if doc is None:
                raise ValueError("Tài liệu đã bị xóa trong khi đang xử lý.")

            await persist_mindmap_result(db, doc, result)
            run.result_data = json.dumps(result, ensure_ascii=False)
            run.status = "completed"
            run.stage = "completed"
            run.progress = 100
            run.error_message = None
            run.completed_at = datetime.now(timezone.utc)
            run.lease_expires_at = None
            await db.commit()
    except asyncio.CancelledError:
        raise
    except AIServiceError as exc:
        await _safe_mark_failed(payload, str(exc))
    except Exception as exc:
        logger.exception("Processing run %s failed", payload.id)
        await _safe_mark_failed(payload, str(exc) or "Lỗi xử lý không xác định")
    finally:
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass


async def _heartbeat(payload: RunPayload) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        try:
            await _renew_lease(payload)
        except Exception:
            logger.exception("Could not renew processing-run lease %s", payload.id)


async def _renew_lease(
    payload: RunPayload,
    *,
    stage: str | None = None,
    progress: int | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    values = {"lease_expires_at": now + timedelta(seconds=LEASE_SECONDS), "updated_at": now}
    if stage is not None:
        values["stage"] = stage
    if progress is not None:
        values["progress"] = min(99, max(0, progress))
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(ProcessingRun)
            .where(
                ProcessingRun.id == payload.id,
                ProcessingRun.worker_id == payload.worker_id,
                ProcessingRun.status == "processing",
            )
            .values(**values)
        )
        await db.commit()
        if result.rowcount == 0:
            raise RuntimeError("Tác vụ không còn thuộc worker hiện tại")


async def _safe_mark_failed(payload: RunPayload, message: str) -> None:
    try:
        await _schedule_retry_or_fail(payload, message)
    except Exception:
        logger.exception("Could not persist failure for processing run %s", payload.id)


async def _schedule_retry_or_fail(payload: RunPayload, message: str) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProcessingRun)
            .where(
                ProcessingRun.id == payload.id,
                ProcessingRun.worker_id == payload.worker_id,
                ProcessingRun.status == "processing",
            )
            .with_for_update()
        )
        run = result.scalar_one_or_none()
        if run is None:
            return

        run.error_message = message[:4000]
        run.lease_expires_at = None
        if run.attempts < run.max_attempts:
            run.status = "queued"
            run.stage = "retrying"
            run.progress = 0
            run.retry_after = now + timedelta(seconds=min(60, 5 * (2 ** (run.attempts - 1))))
        else:
            run.status = "failed"
            run.stage = "failed"
            run.completed_at = now
        await db.commit()
