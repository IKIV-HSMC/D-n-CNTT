import uuid
import enum
from sqlalchemy import Column, String, Integer, Text, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    """Trạng thái vòng đời của một tài liệu."""
    uploaded = "uploaded"      # Vừa upload, chưa trích xuất
    extracting = "extracting"  # Đang trích xuất nền
    extracted = "extracted"    # Trích xuất thành công
    failed = "failed"          # Lỗi trích xuất


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Mở rộng tương lai: gắn vào user và môn học
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    subject_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Thông tin file
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_type = Column(String(10), nullable=False)   # pdf | docx | pptx
    file_size = Column(Integer, nullable=False)       # bytes

    # Trạng thái xử lý
    status = Column(
        SAEnum(DocumentStatus, name="documentstatus"),
        default=DocumentStatus.uploaded,
        nullable=False,
    )

    # Kết quả trích xuất
    extracted_text = Column(Text, nullable=True)       # Toàn bộ text
    page_count = Column(Integer, nullable=True)        # Số trang/slide
    error_message = Column(Text, nullable=True)        # Mô tả lỗi nếu failed

    # Kết quả sinh Mindmap + Flashcards (JSON string từ Ollama)
    mindmap_data = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
