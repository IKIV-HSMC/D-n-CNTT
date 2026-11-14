from pydantic import BaseModel, UUID4, field_validator
from datetime import datetime
from typing import Optional, List
from app.models.document import DocumentStatus


# ── Response schemas ──────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    """Thông tin cơ bản của document, dùng trong list."""
    id: UUID4
    user_id: Optional[UUID4] = None
    subject_id: Optional[UUID4] = None
    original_filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    page_count: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    """Chi tiết document, bao gồm 500 ký tự preview."""
    extracted_text_preview: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Kết quả phân trang danh sách documents."""
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Error schema ──────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Format lỗi thống nhất cho tất cả API."""
    code: str
    message: str
