"""
Validate file upload:
- Kiểm tra phần mở rộng
- Kiểm tra magic bytes (không tin vào tên file)
- Kiểm tra dung lượng
- Kiểm tra file không rỗng
"""
from pathlib import Path
from typing import Any
try:
    from fastapi import UploadFile
except ImportError:
    UploadFile = Any  # type: ignore


# Magic bytes để nhận diện định dạng thực của file
_MAGIC: dict[str, bytes] = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",
    "pptx": b"PK\x03\x04",
}

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"pdf", "docx", "pptx"})


class FileTooLargeError(ValueError):
    """Raised khi file vượt giới hạn dung lượng."""
    pass


class InvalidFileError(ValueError):
    """Raised khi file sai định dạng hoặc hỏng."""
    pass


async def validate_and_read(
    file: UploadFile,
    max_bytes: int,
) -> tuple[str, bytes]:
    """
    Validate file upload và trả về (ext, content).

    Args:
        file: FastAPI UploadFile object
        max_bytes: Dung lượng tối đa tính bằng bytes

    Returns:
        Tuple (extension_without_dot, file_bytes)

    Raises:
        InvalidFileError: Định dạng sai, magic bytes không khớp, file rỗng/hỏng
        FileTooLargeError: Vượt giới hạn dung lượng
    """
    if not file.filename:
        raise InvalidFileError("Tên file không hợp lệ")

    # 1. Kiểm tra phần mở rộng
    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidFileError(
            f"Định dạng '{ext or 'không rõ'}' không được hỗ trợ. "
            "Chỉ chấp nhận .pdf, .docx, .pptx"
        )

    # 2. Đọc 8 bytes đầu để kiểm tra magic bytes
    header = await file.read(8)
    if not header:
        raise InvalidFileError("File rỗng hoặc không thể đọc")

    expected_magic = _MAGIC[ext]
    if not header.startswith(expected_magic):
        raise InvalidFileError(
            f"File không phải định dạng {ext.upper()} hợp lệ "
            "(nội dung file không khớp phần mở rộng)"
        )

    # 3. Đọc phần còn lại và kiểm tra tổng dung lượng
    rest = await file.read()
    content = header + rest

    if len(content) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise FileTooLargeError(
            f"Kích thước file ({len(content) / 1024 / 1024:.1f} MB) "
            f"vượt quá giới hạn {max_mb} MB cho phép"
        )

    if len(content) < 16:
        raise InvalidFileError("File quá nhỏ, có thể bị hỏng hoặc rỗng")

    return ext, content
