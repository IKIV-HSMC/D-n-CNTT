from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import validate_request_origin
from app.core.database import get_db
from app.models.subject import Subject
from app.models.user import User
from app.schemas.subject import SubjectCreate, SubjectResponse, SubjectUpdate

router = APIRouter(
    prefix="/api/subjects",
    tags=["subjects"],
    dependencies=[Depends(validate_request_origin)],
)


@router.get("", response_model=list[SubjectResponse])
async def list_subjects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Subject]:
    result = await db.execute(
        select(Subject)
        .where(Subject.owner_user_id == user.id)
        .order_by(Subject.name.asc())
    )
    return list(result.scalars().all())


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    payload: SubjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Subject:
    duplicate = await db.execute(
        select(Subject.id).where(
            Subject.owner_user_id == user.id,
            func.lower(Subject.name) == payload.name.lower(),
        )
    )
    if duplicate.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Môn học đã tồn tại")

    subject = Subject(owner_user_id=user.id, name=payload.name)
    db.add(subject)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Môn học đã tồn tại") from exc
    await db.refresh(subject)
    return subject


@router.patch("/{subject_id}", response_model=SubjectResponse)
async def rename_subject(
    subject_id: UUID,
    payload: SubjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Subject:
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.owner_user_id == user.id)
    )
    subject = result.scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy môn học")

    duplicate = await db.execute(
        select(Subject.id).where(
            Subject.owner_user_id == user.id,
            Subject.id != subject_id,
            func.lower(Subject.name) == payload.name.lower(),
        )
    )
    if duplicate.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Môn học đã tồn tại")

    subject.name = payload.name
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Môn học đã tồn tại") from exc
    await db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.owner_user_id == user.id)
    )
    subject = result.scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy môn học")
    await db.delete(subject)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
