import io
import pytest
import pytest_asyncio
from fastapi import UploadFile
from app.services.file_validator import (
    validate_and_read,
    FileTooLargeError,
    InvalidFileError,
)


MAX_BYTES = 20 * 1024 * 1024  # 20MB


def make_upload(content: bytes, filename: str) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(content))


@pytest.mark.asyncio
async def test_valid_pdf_accepted(valid_pdf_bytes):
    """PDF hợp lệ phải được chấp nhận."""
    upload = make_upload(valid_pdf_bytes, "test.pdf")
    ext, content = await validate_and_read(upload, MAX_BYTES)
    assert ext == "pdf"
    assert content == valid_pdf_bytes


@pytest.mark.asyncio
async def test_invalid_extension_rejected():
    """File có phần mở rộng không hỗ trợ phải bị từ chối."""
    upload = make_upload(b"%PDF content", "malware.exe")
    with pytest.raises(InvalidFileError, match="không được hỗ trợ"):
        await validate_and_read(upload, MAX_BYTES)


@pytest.mark.asyncio
async def test_wrong_magic_bytes_rejected():
    """File đổi tên thành .pdf nhưng magic bytes sai phải bị từ chối."""
    upload = make_upload(b"This is not a PDF file at all", "fake.pdf")
    with pytest.raises(InvalidFileError, match="hợp lệ"):
        await validate_and_read(upload, MAX_BYTES)


@pytest.mark.asyncio
async def test_empty_file_rejected():
    """File rỗng phải bị từ chối."""
    upload = make_upload(b"", "empty.pdf")
    with pytest.raises(InvalidFileError):
        await validate_and_read(upload, MAX_BYTES)


@pytest.mark.asyncio
async def test_file_too_large_rejected():
    """File > 20MB phải bị từ chối với FileTooLargeError."""
    large_content = b"%PDF" + b"X" * (21 * 1024 * 1024)
    upload = make_upload(large_content, "large.pdf")
    with pytest.raises(FileTooLargeError):
        await validate_and_read(upload, MAX_BYTES)


@pytest.mark.asyncio
async def test_exactly_max_size_accepted():
    """File đúng 20MB phải được chấp nhận."""
    exact_content = b"%PDF" + b"X" * (MAX_BYTES - 4)
    upload = make_upload(exact_content, "exact.pdf")
    ext, content = await validate_and_read(upload, MAX_BYTES)
    assert ext == "pdf"


@pytest.mark.asyncio
async def test_docx_magic_bytes_accepted():
    """DOCX phải có magic bytes PK (ZIP format)."""
    # PK header của ZIP/DOCX
    docx_header = b"PK\x03\x04" + b"\x00" * 100
    upload = make_upload(docx_header, "document.docx")
    ext, _ = await validate_and_read(upload, MAX_BYTES)
    assert ext == "docx"


@pytest.mark.asyncio
async def test_no_filename_rejected():
    """File không có tên phải bị từ chối."""
    upload = make_upload(b"%PDF content", "")
    with pytest.raises(InvalidFileError):
        await validate_and_read(upload, MAX_BYTES)
