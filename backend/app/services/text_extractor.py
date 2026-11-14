"""
Trích xuất văn bản từ 3 định dạng: PDF, DOCX, PPTX.
Chạy trong BackgroundTasks của FastAPI – mọi lỗi đều được bắt và ghi vào DB.
"""
import re
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pdfplumber
from docx import Document as DocxDocument
from pptx import Presentation
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.core.database import AsyncSessionLocal


# ── Text normalization ────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Chuẩn hóa văn bản: bỏ ký tự điều khiển, chuẩn hóa khoảng trắng."""
    # Xóa ký tự điều khiển (trừ newline và tab)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Chuẩn hóa nhiều khoảng trắng liên tiếp trên cùng dòng
    text = re.sub(r"[ \t]+", " ", text)
    # Chuẩn hóa nhiều dòng trống liên tiếp thành tối đa 2 dòng trống
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Extractors ────────────────────────────────────────────────────────────────

def _extract_pdf(content: bytes) -> tuple[str, int]:
    """Trích xuất text từ PDF. Trả về (text, page_count)."""
    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    full_text = "\n\n".join(pages)
    return _normalize(full_text), page_count


def _extract_docx(content: bytes) -> tuple[str, int]:
    """Trích xuất text từ DOCX (đoạn văn + bảng). Trả về (text, paragraph_count)."""
    doc = DocxDocument(io.BytesIO(content))
    parts: list[str] = []

    # Đoạn văn thường
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)

    # Bảng
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(
                cell.text.strip() for cell in row.cells if cell.text.strip()
            )
            if row_text:
                parts.append(row_text)

    full_text = "\n".join(parts)
    return _normalize(full_text), len(doc.paragraphs)


def _extract_pptx(content: bytes) -> tuple[str, int]:
    """Trích xuất text từ PPTX (text + ghi chú từng slide). Trả về (text, slide_count)."""
    prs = Presentation(io.BytesIO(content))
    slides_text: list[str] = []

    for i, slide in enumerate(prs.slides, start=1):
        slide_parts: list[str] = [f"[Slide {i}]"]

        # Text từ các shape
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        slide_parts.append(text)

        # Ghi chú (notes)
        if slide.has_notes_slide:
            notes_frame = slide.notes_slide.notes_text_frame
            if notes_frame:
                notes = notes_frame.text.strip()
                if notes:
                    slide_parts.append(f"[Ghi chú]: {notes}")

        slides_text.append("\n".join(slide_parts))

    full_text = "\n\n".join(slides_text)
    return _normalize(full_text), len(prs.slides)


def _save_extracted_json(
    file_path: str,
    doc_uuid: str,
    file_type: str,
    page_count: int,
    text: str,
    original_filename: Optional[str] = None,
) -> Path:
    """Ghi kết quả trích xuất ra file JSON trong thư mục storage."""
    json_path = Path(file_path).with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "document_id": str(doc_uuid),
        "original_filename": original_filename or Path(file_path).name,
        "stored_filename": Path(file_path).name,
        "file_type": file_type,
        "page_count": page_count,
        "status": DocumentStatus.extracted.value,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "extracted_text": text,
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


# ── Background task entry point ───────────────────────────────────────────────

async def extract_text_background(
    document_id: str,
    file_path: str,
    file_type: str,
    original_filename: Optional[str] = None,
) -> None:
    """
    Được gọi từ FastAPI BackgroundTasks sau khi upload thành công.
    Đọc file từ disk, trích xuất text, cập nhật DB và xuất file JSON trong storage.
    """
    doc_uuid = uuid.UUID(str(document_id)) if isinstance(document_id, str) else document_id
    async with AsyncSessionLocal() as db:
        try:
            # Cập nhật status -> extracting
            await _update_status(db, doc_uuid, DocumentStatus.extracting)

            # Đọc file từ disk
            file_bytes = Path(file_path).read_bytes()

            # Trích xuất theo loại file
            if file_type == "pdf":
                text, page_count = _extract_pdf(file_bytes)
            elif file_type == "docx":
                text, page_count = _extract_docx(file_bytes)
            elif file_type == "pptx":
                text, page_count = _extract_pptx(file_bytes)
            else:
                raise ValueError(f"Loại file không hỗ trợ: {file_type}")

            # Kiểm tra file có text không (PDF scan)
            if not text or len(text.strip()) < 10:
                await _update_failed(
                    db,
                    doc_uuid,
                    "Tài liệu không chứa văn bản có thể trích xuất (có thể là file scan ảnh)",
                )
                return

            # Cập nhật status -> extracted
            await db.execute(
                update(Document)
                .where(Document.id == doc_uuid)
                .values(
                    status=DocumentStatus.extracted,
                    extracted_text=text,
                    page_count=page_count,
                    error_message=None,
                )
            )
            await db.commit()

            # Ghi kết quả trích xuất ra file JSON trong storage
            try:
                _save_extracted_json(
                    file_path=file_path,
                    doc_uuid=str(doc_uuid),
                    file_type=file_type,
                    page_count=page_count,
                    text=text,
                    original_filename=original_filename,
                )
            except Exception:
                pass

        except Exception as exc:  # noqa: BLE001
            await _update_failed(db, doc_uuid, str(exc))


async def _update_status(
    db: AsyncSession, doc_uuid: uuid.UUID, status: DocumentStatus
) -> None:
    await db.execute(
        update(Document).where(Document.id == doc_uuid).values(status=status)
    )
    await db.commit()


async def _update_failed(
    db: AsyncSession, doc_uuid: uuid.UUID, error_message: str
) -> None:
    await db.execute(
        update(Document)
        .where(Document.id == doc_uuid)
        .values(status=DocumentStatus.failed, error_message=error_message)
    )
    await db.commit()
