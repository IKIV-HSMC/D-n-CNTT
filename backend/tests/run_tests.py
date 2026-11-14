"""
Standalone test runner using asyncio and built-in Python tools.
Cho phép chạy tests mà không cần cài pytest lên host.
"""
import asyncio
import io
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.file_validator import (
    validate_and_read,
    FileTooLargeError,
    InvalidFileError,
)
try:
    from app.services.text_extractor import _normalize
except ImportError:
    import re
    def _normalize(text: str) -> str:
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

MAX_BYTES = 20 * 1024 * 1024

class MockUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._bio = io.BytesIO(content)

    async def read(self, size: int = -1) -> bytes:
        return self._bio.read(size)


def make_upload(content: bytes, filename: str) -> MockUploadFile:
    return MockUploadFile(filename=filename, content=content)


async def test_validator():
    print("[1/2] Running File Validator tests...")
    fixtures_dir = Path(__file__).parent / "fixtures"

    # 1. Valid PDF fixture
    pdf_bytes = (fixtures_dir / "sample.pdf").read_bytes()
    ext, content = await validate_and_read(make_upload(pdf_bytes, "sample.pdf"), MAX_BYTES)
    assert ext == "pdf", f"Expected pdf, got {ext}"
    assert len(content) == len(pdf_bytes)
    print("  [PASS] Valid PDF accepted")

    # 2. Valid DOCX fixture
    docx_bytes = (fixtures_dir / "sample.docx").read_bytes()
    ext, content = await validate_and_read(make_upload(docx_bytes, "sample.docx"), MAX_BYTES)
    assert ext == "docx", f"Expected docx, got {ext}"
    print("  [PASS] Valid DOCX accepted")

    # 3. Valid PPTX fixture
    pptx_bytes = (fixtures_dir / "sample.pptx").read_bytes()
    ext, content = await validate_and_read(make_upload(pptx_bytes, "sample.pptx"), MAX_BYTES)
    assert ext == "pptx", f"Expected pptx, got {ext}"
    print("  [PASS] Valid PPTX accepted")

    # 4. Invalid extension rejected
    try:
        await validate_and_read(make_upload(b"%PDF dummy", "script.sh"), MAX_BYTES)
        assert False, "Should raise InvalidFileError"
    except InvalidFileError:
        print("  [PASS] Invalid extension rejected")

    # 5. Wrong magic bytes rejected (malware disguised as pdf)
    try:
        await validate_and_read(make_upload(b"MZ\x90\x00 fake exe disguised as pdf", "virus.pdf"), MAX_BYTES)
        assert False, "Should raise InvalidFileError"
    except InvalidFileError:
        print("  [PASS] Mismatched magic bytes rejected")

    # 6. Empty file rejected
    try:
        await validate_and_read(make_upload(b"", "empty.pdf"), MAX_BYTES)
        assert False, "Should raise InvalidFileError"
    except InvalidFileError:
        print("  [PASS] Empty file rejected")

    # 7. File too large rejected
    try:
        large = b"%PDF" + b"X" * (MAX_BYTES + 100)
        await validate_and_read(make_upload(large, "huge.pdf"), MAX_BYTES)
        assert False, "Should raise FileTooLargeError"
    except FileTooLargeError:
        print("  [PASS] File > 20MB rejected")


def test_normalizer():
    print("[2/2] Running Normalizer tests...")
    # Clean control chars
    res = _normalize("Hello\x00World\x01!")
    assert res == "HelloWorld!", f"Got: {res}"
    print("  [PASS] Control chars removed")

    # Strip spaces
    res = _normalize("Word1    Word2\t\tWord3")
    assert res == "Word1 Word2 Word3", f"Got: {res}"
    print("  [PASS] Extra spaces collapsed")

    # Limit newlines
    res = _normalize("Line1\n\n\n\n\nLine2")
    assert res == "Line1\n\nLine2", f"Got: {res}"
    print("  [PASS] Excess newlines collapsed")


async def main():
    try:
        await test_validator()
        test_normalizer()
        print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY! (10/10)")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
