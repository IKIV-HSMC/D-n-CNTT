"""
Document API – 4 endpoints:
  POST   /api/documents/upload
  GET    /api/documents
  GET    /api/documents/{id}
  DELETE /api/documents/{id}
"""
import uuid
from pathlib import Path
from typing import Optional
import json

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
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.document import Document, DocumentStatus
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    ErrorResponse,
)
from app.services.file_validator import (
    FileTooLargeError,
    InvalidFileError,
    validate_and_read,
)
from app.services.text_extractor import extract_text_background

router = APIRouter(prefix="/api/documents", tags=["documents"])


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
        subject_id=subject_id,
        status=DocumentStatus.uploaded,
    )
    db.add(doc)
    await db.commit()
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
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """Lấy danh sách tài liệu có phân trang, tìm kiếm và lọc."""
    stmt = select(Document)

    if search:
        stmt = stmt.where(
            Document.original_filename.ilike(f"%{search}%")
        )
    if status_filter:
        stmt = stmt.where(Document.status == status_filter)
    if file_type:
        stmt = stmt.where(Document.file_type == file_type.lower())

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
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    """Lấy chi tiết một tài liệu, bao gồm 500 ký tự đầu của văn bản trích xuất."""
    doc = await _get_or_404(db, document_id)

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
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Trả về file JSON chứa toàn bộ nội dung và metadata đã trích xuất."""
    doc = await _get_or_404(db, document_id)
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
    db: AsyncSession = Depends(get_db),
) -> None:
    """Xóa bản ghi DB, file vật lý và file JSON."""
    doc = await _get_or_404(db, document_id)

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

async def _get_or_404(db: AsyncSession, document_id: uuid.UUID) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Không tìm thấy tài liệu"},
        )
    return doc
