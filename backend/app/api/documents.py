"""
Document API – upload, save, list, read, download and delete endpoints:
  POST   /api/documents/upload
  GET    /api/documents
  GET    /api/documents/{id}
  DELETE /api/documents/{id}
"""
import uuid
from pathlib import Path
from typing import Optional
import json
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import validate_request_origin
from app.core.config import settings
from app.core.database import get_db
from app.models.document import Document, DocumentStatus
from app.models.processing_run import ProcessingRun
from app.models.subject import Subject
from app.models.user import User
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    ErrorResponse,
)
from app.schemas.mindmap_save import GeneratedMindmapSave
from app.services.file_validator import (
    FileTooLargeError,
    InvalidFileError,
    validate_and_read,
)
from app.services.text_extractor import extract_text_background, extract_text_from_bytes
from app.services.mindmap_generator import persist_mindmap_result

router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
    dependencies=[Depends(validate_request_origin)],
)


# ── POST /upload ─────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload tài liệu",
    responses={
        400: {"model": ErrorResponse, "description": "File không hợp lệ"},
        413: {"model": ErrorResponse, "description": "File quá lớn"},
    },
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File PDF, DOCX hoặc PPTX"),
    subject_id: Optional[uuid.UUID] = Form(None, description="ID môn học (tùy chọn)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Upload tài liệu và bắt đầu trích xuất văn bản nền."""

    # 1. Validate file (ext + magic bytes + size)
    try:
        ext, content = await validate_and_read(file, settings.max_upload_bytes)
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "FILE_TOO_LARGE", "message": str(exc)},
        )
    except InvalidFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE", "message": str(exc)},
        )

    if subject_id is not None:
        subject_result = await db.execute(
            select(Subject.id).where(
                Subject.id == subject_id,
                Subject.owner_user_id == user.id,
            )
        )
        if subject_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SUBJECT_NOT_FOUND", "message": "Không tìm thấy môn học"},
            )

    # 2. Lưu file với tên UUID (chống path traversal)
    stored_name = f"{uuid.uuid4()}.{ext}"
    storage_dir = Path(settings.STORAGE_PATH)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / stored_name
    file_path.write_bytes(content)

    # 3. Tạo bản ghi DB
    doc = Document(
        original_filename=file.filename or stored_name,
        stored_filename=stored_name,
        file_type=ext,
        file_size=len(content),
        user_id=user.id,
        subject_id=subject_id,
        status=DocumentStatus.uploaded,
    )
    db.add(doc)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        file_path.unlink(missing_ok=True)
        raise
    await db.refresh(doc)

    # 4. Thêm background task trích xuất (chạy SAU khi response được trả về)
    background_tasks.add_task(
        extract_text_background,
        document_id=str(doc.id),
        file_path=str(file_path),
        file_type=ext,
        original_filename=doc.original_filename,
    )

    return DocumentResponse.model_validate(doc)


# ── POST /save-generated (đưa mindmap khách vào thư viện) ────────────────────

@router.post(
    "/save-generated",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lưu mindmap đã tạo vào thư viện tài khoản",
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def save_generated_document(
    file: UploadFile = File(..., description="Tài liệu nguồn PDF, DOCX hoặc PPTX"),
    result_json: str = Form(..., description="Kết quả mindmap đã tạo"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Persist a guest result only after its owner has authenticated."""
    try:
        file_type, content = await validate_and_read(file, settings.max_upload_bytes)
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "FILE_TOO_LARGE", "message": str(exc)},
        ) from exc
    except InvalidFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE", "message": str(exc)},
        ) from exc

    try:
        generated = GeneratedMindmapSave.model_validate_json(result_json)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_MINDMAP", "message": "Dữ liệu mindmap không hợp lệ."},
        ) from exc

    try:
        extracted_text, page_count = extract_text_from_bytes(file_type, content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNREADABLE_FILE", "message": "Không thể đọc nội dung file này."},
        ) from exc
    if len(extracted_text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NO_EXTRACTABLE_TEXT", "message": "Tài liệu không có văn bản để lưu."},
        )

    original_filename = Path((file.filename or "tai-lieu").replace("\\", "/")).name[:255]
    stored_name = f"{uuid.uuid4()}.{file_type}"
    storage_dir = Path(settings.STORAGE_PATH)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / stored_name

    document = Document(
        original_filename=original_filename,
        stored_filename=stored_name,
        file_type=file_type,
        file_size=len(content),
        user_id=user.id,
        status=DocumentStatus.extracted,
        extracted_text=extracted_text,
        page_count=page_count,
    )
    now = datetime.now(timezone.utc)
    try:
        file_path.write_bytes(content)
        db.add(document)
        await db.flush()

        result_data = generated.model_dump(mode="json", exclude_none=True)
        result_data["document_id"] = str(document.id)
        result_data = await persist_mindmap_result(db, document, result_data)

        db.add(ProcessingRun(
            document_id=document.id,
            user_id=user.id,
            mode="ai" if generated.backend == "ai_pipeline" else "engine",
            status="completed",
            stage="completed",
            progress=100,
            attempts=1,
            result_data=json.dumps(result_data, ensure_ascii=False),
            started_at=now,
            completed_at=now,
        ))
        await db.commit()
    except Exception:
        await db.rollback()
        file_path.unlink(missing_ok=True)
        raise

    await db.refresh(document)
    return DocumentResponse.model_validate(document)


# ── GET / (danh sách + phân trang + tìm kiếm) ─────────────────────────────────

@router.get(
    "",
    response_model=DocumentListResponse,
    summary="Danh sách tài liệu",
)
async def list_documents(
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số bản ghi mỗi trang"),
    search: Optional[str] = Query(None, description="Tìm theo tên file"),
    status_filter: Optional[DocumentStatus] = Query(None, alias="status"),
    file_type: Optional[str] = Query(None, description="pdf | docx | pptx"),
    subject_id: Optional[uuid.UUID] = Query(None, description="Lọc theo môn học"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """Lấy danh sách tài liệu có phân trang, tìm kiếm và lọc."""
    stmt = select(Document).where(Document.user_id == user.id)

    if search:
        stmt = stmt.where(
            Document.original_filename.ilike(f"%{search}%")
        )
    if status_filter:
        stmt = stmt.where(Document.status == status_filter)
    if file_type:
        stmt = stmt.where(Document.file_type == file_type.lower())
    if subject_id:
        stmt = stmt.where(Document.subject_id == subject_id)

    # Đếm tổng
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Phân trang
    offset = (page - 1) * page_size
    stmt = stmt.order_by(Document.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    docs = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── GET /{id} (chi tiết) ───────────────────────────────────────────────────────

@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Chi tiết tài liệu",
    responses={404: {"model": ErrorResponse}},
)
async def get_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    """Lấy chi tiết một tài liệu, bao gồm 500 ký tự đầu của văn bản trích xuất."""
    doc = await _get_or_404(db, document_id, user.id)

    preview: Optional[str] = None
    if doc.extracted_text:
        preview = doc.extracted_text[:500]

    response = DocumentDetailResponse.model_validate(doc)
    response.extracted_text_preview = preview
    return response


# ── GET /{id}/json (tải file JSON trích xuất) ──────────────────────────────────

@router.get(
    "/{document_id}/json",
    summary="Tải về file JSON kết quả trích xuất",
    responses={
        400: {"model": ErrorResponse, "description": "Tài liệu chưa được trích xuất"},
        404: {"model": ErrorResponse, "description": "Không tìm thấy tài liệu"},
    },
)
async def get_document_json(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Trả về file JSON chứa toàn bộ nội dung và metadata đã trích xuất."""
    doc = await _get_or_404(db, document_id, user.id)
    if doc.status != DocumentStatus.extracted or not doc.extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NOT_EXTRACTED", "message": "Tài liệu chưa được trích xuất thành công"},
        )

    file_path = Path(settings.STORAGE_PATH) / doc.stored_filename
    json_path = file_path.with_suffix(".json")

    # Tạo file nếu chưa có trên disk
    if not json_path.exists():
        json_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "document_id": str(doc.id),
            "original_filename": doc.original_filename,
            "stored_filename": doc.stored_filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "page_count": doc.page_count,
            "status": doc.status.value,
            "extracted_at": doc.updated_at.isoformat() if doc.updated_at else None,
            "extracted_text": doc.extracted_text,
        }
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    clean_filename = f"{Path(doc.original_filename).stem}_extracted.json"
    return FileResponse(
        path=str(json_path),
        media_type="application/json",
        filename=clean_filename,
    )


# ── DELETE /{id} ───────────────────────────────────────────────────────────────

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa tài liệu",
    responses={404: {"model": ErrorResponse}},
)
async def delete_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Xóa bản ghi DB, file vật lý và file JSON."""
    doc = await _get_or_404(db, document_id, user.id)

    # Xóa file vật lý và file JSON nếu có
    file_path = Path(settings.STORAGE_PATH) / doc.stored_filename
    if file_path.exists():
        file_path.unlink()
    json_path = file_path.with_suffix(".json")
    if json_path.exists():
        json_path.unlink()

    await db.delete(doc)
    await db.commit()


# ── Helper ─────────────────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID) -> Document:
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Không tìm thấy tài liệu"},
        )
    return doc
