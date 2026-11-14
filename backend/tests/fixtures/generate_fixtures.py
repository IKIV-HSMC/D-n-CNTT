"""
Script tạo file fixtures mẫu (.pdf, .docx, .pptx) cho test và manual test.
"""
import io
import zipfile
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def create_sample_pdf(path: Path) -> None:
    """Tạo file PDF hợp lệ tối giản."""
    content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 54 >>\nstream\n"
        b"BT /F1 14 Tf 70 700 Td (Tai lieu mau AI Mindmap) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000010 00000 n \n"
        b"0000000060 00000 n \n"
        b"0000000117 00000 n \n"
        b"0000000251 00000 n \n"
        b"0000000355 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n428\n%%EOF\n"
    )
    path.write_bytes(content)


def create_sample_docx(path: Path) -> None:
    """Tạo file DOCX hợp lệ tối giản dưới dạng ZIP cấu trúc OOXML."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
            '</Types>',
        )
        # _rels/.rels
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n'
            '</Relationships>',
        )
        # word/document.xml
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
            '  <w:body>\n'
            '    <w:p><w:r><w:t>Chuong 1: Tong quan he thong cong nghe thong tin</w:t></w:r></w:p>\n'
            '    <w:p><w:r><w:t>Day la tai lieu kiem thu cho module upload van ban.</w:t></w:r></w:p>\n'
            '  </w:body>\n'
            '</w:document>',
        )
    path.write_bytes(buf.getvalue())


def create_sample_pptx(path: Path) -> None:
    """Tạo file PPTX hợp lệ tối giản dưới dạng ZIP cấu trúc OOXML."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>\n'
            '  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>\n'
            '</Types>',
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>\n'
            '</Relationships>',
        )
        zf.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
            '  <p:sldIdLst><p:sldId id="256" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></p:sldIdLst>\n'
            '</p:presentation>',
        )
        zf.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>\n'
            '</Relationships>',
        )
        zf.writestr(
            "ppt/slides/slide1.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">\n'
            '  <p:cSld><p:spTree>\n'
            '    <p:sp><p:txBody><a:p><a:r><a:t>Slide 1: Gioi thieu Mindmap AI</a:t></a:r></a:p></p:txBody></p:sp>\n'
            '  </p:spTree></p:cSld>\n'
            '</p:sld>',
        )
    path.write_bytes(buf.getvalue())


def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    create_sample_pdf(FIXTURES_DIR / "sample.pdf")
    create_sample_docx(FIXTURES_DIR / "sample.docx")
    create_sample_pptx(FIXTURES_DIR / "sample.pptx")
    print("Fixtures created successfully.")


if __name__ == "__main__":
    main()
