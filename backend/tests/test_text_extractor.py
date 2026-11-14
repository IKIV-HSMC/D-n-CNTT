import io
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.text_extractor import (
    _extract_pdf,
    _extract_docx,
    _extract_pptx,
    _normalize,
)


# ── Unit tests cho _normalize ─────────────────────────────────────────────────

def test_normalize_removes_control_chars():
    text = "Hello\x00World\x01Test"
    result = _normalize(text)
    assert "\x00" not in result
    assert "Hello" in result


def test_normalize_collapses_blank_lines():
    text = "Line1\n\n\n\n\nLine2"
    result = _normalize(text)
    assert "\n\n\n" not in result


def test_normalize_strips_extra_spaces():
    text = "Word1   Word2\t\tWord3"
    result = _normalize(text)
    assert "  " not in result


# ── Unit test cho PDF extraction (mock pdfplumber) ────────────────────────────

def test_extract_pdf_with_text():
    """PDF có text phải trả về text đầy đủ."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Nội dung trang 1"
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("app.services.text_extractor.pdfplumber.open", return_value=mock_pdf):
        text, page_count = _extract_pdf(b"%PDF fake content")

    assert "Nội dung trang 1" in text
    assert page_count == 1


def test_extract_pdf_empty_pages():
    """PDF không có text phải trả về chuỗi rỗng."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = None
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("app.services.text_extractor.pdfplumber.open", return_value=mock_pdf):
        text, page_count = _extract_pdf(b"%PDF fake")

    assert text == ""


# ── Unit test cho DOCX extraction ─────────────────────────────────────────────

def test_extract_docx_paragraphs():
    """DOCX phải trích xuất đoạn văn."""
    mock_para = MagicMock()
    mock_para.text = "Đây là đoạn văn bản mẫu"
    mock_doc = MagicMock()
    mock_doc.paragraphs = [mock_para]
    mock_doc.tables = []

    with patch("app.services.text_extractor.DocxDocument", return_value=mock_doc):
        text, count = _extract_docx(b"PK\x03\x04 fake docx")

    assert "đoạn văn bản mẫu" in text


def test_extract_docx_tables():
    """DOCX phải trích xuất nội dung bảng."""
    mock_cell1 = MagicMock()
    mock_cell1.text = "Cột 1"
    mock_cell2 = MagicMock()
    mock_cell2.text = "Cột 2"
    mock_row = MagicMock()
    mock_row.cells = [mock_cell1, mock_cell2]
    mock_table = MagicMock()
    mock_table.rows = [mock_row]
    mock_doc = MagicMock()
    mock_doc.paragraphs = []
    mock_doc.tables = [mock_table]

    with patch("app.services.text_extractor.DocxDocument", return_value=mock_doc):
        text, _ = _extract_docx(b"PK\x03\x04 fake")

    assert "Cột 1" in text
    assert "Cột 2" in text


# ── Unit test cho PPTX extraction ─────────────────────────────────────────────

def test_extract_pptx_slides():
    """PPTX phải trích xuất text từ slide."""
    mock_para = MagicMock()
    mock_para.text = "Tiêu đề slide"
    mock_text_frame = MagicMock()
    mock_text_frame.paragraphs = [mock_para]
    mock_shape = MagicMock()
    mock_shape.has_text_frame = True
    mock_shape.text_frame = mock_text_frame
    mock_slide = MagicMock()
    mock_slide.shapes = [mock_shape]
    mock_slide.has_notes_slide = False
    mock_prs = MagicMock()
    mock_prs.slides = [mock_slide]

    with patch("app.services.text_extractor.Presentation", return_value=mock_prs):
        text, slide_count = _extract_pptx(b"PK\x03\x04 fake pptx")

    assert "Tiêu đề slide" in text
    assert slide_count == 1


# ── Unit test cho extract_text_background ──────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_text_background_success():
    """Trích xuất thành công cập nhật status=extracted."""
    from app.services.text_extractor import extract_text_background
    import uuid

    doc_id = str(uuid.uuid4())
    mock_db = AsyncMock()

    with patch("app.services.text_extractor.AsyncSessionLocal") as mock_session_cls, \
         patch("pathlib.Path.read_bytes", return_value=b"%PDF content"), \
         patch("app.services.text_extractor._extract_pdf", return_value=("Hello world extracted text", 1)):
        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        await extract_text_background(doc_id, "/storage/uploads/sample.pdf", "pdf")

        assert mock_db.execute.call_count >= 2
        assert mock_db.commit.call_count >= 2


@pytest.mark.asyncio
async def test_extract_text_background_empty_fails():
    """File không có text chuyển status sang failed."""
    from app.services.text_extractor import extract_text_background
    import uuid

    doc_id = str(uuid.uuid4())
    mock_db = AsyncMock()

    with patch("app.services.text_extractor.AsyncSessionLocal") as mock_session_cls, \
         patch("pathlib.Path.read_bytes", return_value=b"%PDF content"), \
         patch("app.services.text_extractor._extract_pdf", return_value=("", 1)):
        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        await extract_text_background(doc_id, "/storage/uploads/sample.pdf", "pdf")

        assert mock_db.execute.call_count >= 2
        assert mock_db.commit.call_count >= 2


def test_save_extracted_json(tmp_path):
    """File JSON được ghi đúng định dạng và nội dung."""
    from app.services.text_extractor import _save_extracted_json
    import json

    test_file = tmp_path / "sample.pdf"
    test_file.write_bytes(b"%PDF dummy")

    json_path = _save_extracted_json(
        file_path=str(test_file),
        doc_uuid="12345678-1234-5678-1234-567812345678",
        file_type="pdf",
        page_count=3,
        text="Sample extracted text content",
        original_filename="tailieu.pdf",
    )

    assert json_path.exists()
    assert json_path.suffix == ".json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["document_id"] == "12345678-1234-5678-1234-567812345678"
    assert data["original_filename"] == "tailieu.pdf"
    assert data["extracted_text"] == "Sample extracted text content"
    assert data["page_count"] == 3
    assert data["status"] == "extracted"


