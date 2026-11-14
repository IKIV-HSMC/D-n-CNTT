import io
import struct
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from fastapi import UploadFile
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_upload_file():
    """Factory tạo UploadFile mock từ bytes và filename."""
    def _make(content: bytes, filename: str) -> UploadFile:
        file_obj = io.BytesIO(content)
        upload = UploadFile(filename=filename, file=file_obj)
        return upload
    return _make


# Fixtures PDF nhỏ (valid + invalid)
@pytest.fixture
def valid_pdf_bytes() -> bytes:
    # PDF tối giản hợp lệ với 1 trang có chữ
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td (Hello World) Tj ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
    )


@pytest.fixture
def invalid_format_bytes() -> bytes:
    return b"This is just a text file, not PDF or Office"


@pytest.fixture
def large_file_bytes() -> bytes:
    # 21MB
    return b"%PDF" + b"A" * (21 * 1024 * 1024)
