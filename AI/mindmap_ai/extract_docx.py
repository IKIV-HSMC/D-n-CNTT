"""
extract_docx.py - Trích xuất file Word (.docx) thành JSON có cấp heading ("sections")
Đã nâng cấp:
  1. Loại bỏ các dòng rác (header, footer, số trang, slide, ngày tháng, mã môn học, XML tag).
  2. Fallback nhận diện Heading thông minh (Chương, Bài, số La Mã, 1.1, in đậm, in hoa)
     kể cả khi file Word không định dạng đúng Heading style.
  3. Hỗ trợ trích xuất bảng (tables) sang dạng text có cấu trúc.
  4. Chuẩn hóa khoảng trắng, loại bỏ ký tự điều khiển.

Dùng:   python extract_docx.py bai_giang.docx docs/bai_giang.json
Cần:    pip install python-docx
"""
import sys
import json
import re
from pathlib import Path
import docx

# Danh sách boilerplate / phần phụ trợ không chứa kiến thức bài học
BOILERPLATE_HEADINGS = {
    "LỜI CẢM ƠN", "LỜI CAM ĐOAN", "DANH MỤC HÌNH ẢNH", "DANH MỤC BẢNG", 
    "MỤC LỤC", "DANH MỤC TỪ VIẾT TẮT", "DANH MỤC KÝ HIỆU", 
    "LỜI MỞ ĐẦU", "NHẬN XÉT CỦA GIẢNG VIÊN", "TÀI LIỆU THAM KHẢO", "PHỤ LỤC"
}

# Các mẫu regex nhận diện dòng rác
NOISE_PATTERNS = [
    re.compile(r"^\d{1,4}$"),  # Chỉ gồm số trang
    re.compile(r"^(?:trang|page|slide)\s*\d+(?:\s*(?:/\s*\d+|của\s*\d+))?$", re.I),
    re.compile(r"^(?:tháng|ngày|january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}$", re.I),
    re.compile(r"^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}$"),  # 24/11/2026
    re.compile(r"^(?:học phần|mã hp|mã môn|course code)\s*[:：]?\s*[A-Z0-9_\-]+", re.I),
    re.compile(r"^[A-Z0-9_\-]{6,}$"),  # Chuỗi hash hoặc mã định danh riêng
    re.compile(r"^(?:topics?\s+covered|nội\s+dung\s+chính|agenda|table\s+of\s+contents)$", re.I),
    re.compile(r"^<\/?(?:a|p|w|m|r|s|d):", re.I),  # XML rác
    re.compile(r"^(?:hình|bảng|ảnh|sơ đồ)\s+\d+[\.:]", re.I),  # Caption hình ảnh/bảng
]

HEADING_REGEX_RULES = [
    # Level 1: Chương 1, Bài 1, Phần I, Module 1...
    (re.compile(r"^(?:chương|bài|phần|module|chủ đề)\s+[IVXLCDM\d]+", re.I), 1),
    # Level 1: I., II., III.
    (re.compile(r"^[IVXLCDM]+\.\s+[A-ZÀ-ỸĐ]", re.UNICODE), 1),
    # Level 2: 1.1, 2.1...
    (re.compile(r"^\d+\.\d+\s+[A-ZÀ-ỸĐ]", re.UNICODE), 2),
    # Level 3: 1.1.1, 2.1.3...
    (re.compile(r"^\d+\.\d+\.\d+\s+[A-ZÀ-ỸĐ]", re.UNICODE), 3),
]


def clean_text(text: str) -> str:
    """Xóa XML tags, ký tự điều khiển, chuẩn hóa khoảng trắng."""
    if not text:
        return ""
    # Xóa xml tags nếu có lọt vào
    text = re.sub(r"<[^>]+>", "", text)
    # Xóa ký tự điều khiển (trừ \n và \t)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Chuẩn hóa khoảng trắng ngang
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def is_noise(line: str) -> bool:
    """Kiểm tra xem dòng có phải là rác không."""
    s = clean_text(line)
    if not s or len(s) < 2:
        return True
    for pat in NOISE_PATTERNS:
        if pat.match(s):
            return True
    return False


def detect_heading(para) -> tuple[bool, int, str]:
    """
    Xác định paragraph có phải heading không.
    Trả về: (is_heading, level, clean_title)
    """
    text = clean_text(para.text)
    if not text:
        return False, 0, ""

    # 1. Kiểm tra Word Style Heading 1, 2, 3...
    style_name = para.style.name if para.style else ""
    if style_name.lower().startswith("heading"):
        last_part = style_name.split()[-1]
        lv = int(last_part) if last_part.isdigit() else 1
        return True, lv, text

    # Không nhận diện heading nếu văn bản quá dài hoặc kết thúc bằng dấu chấm kết câu thông thường
    if len(text) > 120 or text.endswith((".", ";", ",", ":")):
        return False, 0, ""

    # Bỏ qua nếu là caption hoặc bảng
    if is_noise(text):
        return False, 0, ""

    # 2. Kiểm tra Regex quy chuẩn (Chương, 1.1, ...)
    for pat, lv in HEADING_REGEX_RULES:
        if pat.match(text):
            return True, lv, text

    # 3. Kiểm tra chữ in đậm toàn phần và ngắn (< 80 ký tự)
    runs = [r for r in para.runs if r.text.strip()]
    if runs and all(r.bold for r in runs) and len(text) <= 80 and not text.endswith("."):
        return True, 2, text

    # 4. Kiểm tra in hoa toàn bộ và ngắn
    if text.isupper() and 4 <= len(text) <= 80:
        return True, 1, text

    return False, 0, ""


def extract_docx_file(input_path: str, output_path: str):
    doc = docx.Document(input_path)
    sections = []
    current_sec = None
    all_clean_paras = []
    
    in_boilerplate = False

    for para in doc.paragraphs:
        raw_text = clean_text(para.text)
        if not raw_text:
            continue

        # Kiểm tra dòng rác
        if is_noise(raw_text):
            continue

        is_h, lv, title = detect_heading(para)

        if is_h:
            # Kiểm tra xem có bắt đầu mục phụ/boilerplate không
            upper_title = title.upper()
            if any(b in upper_title for b in BOILERPLATE_HEADINGS):
                in_boilerplate = True
                continue
            else:
                in_boilerplate = False

            current_sec = {
                "heading": title,
                "level": lv,
                "text": ""
            }
            sections.append(current_sec)
            all_clean_paras.append(title)
        else:
            if in_boilerplate:
                continue

            if current_sec is not None:
                current_sec["text"] += raw_text + "\n"
            all_clean_paras.append(raw_text)

    # Trích xuất nội dung bảng (tables) nếu có
    for table in doc.tables:
        table_rows = []
        for row in table.rows:
            cells = [clean_text(cell.text) for cell in row.cells]
            # Loại bỏ ô trống liên tiếp
            row_str = " | ".join(c for c in cells if c)
            if row_str and not is_noise(row_str):
                table_rows.append(row_str)
        if table_rows:
            table_text = "\n".join(table_rows)
            if current_sec is not None:
                current_sec["text"] += "\n[Bảng dữ liệu]:\n" + table_text + "\n"
            all_clean_paras.append(table_text)

    # Đảm bảo mỗi section text được trim gọn gàng
    for s in sections:
        s["text"] = s["text"].strip()

    file_name = Path(input_path).name
    result = {
        "original_filename": file_name,
        "extracted_text": "\n".join(all_clean_paras).strip(),
        "sections": sections
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Trích xuất thành công: {len(sections)} sections -> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Sử dụng: python extract_docx.py <input.docx> <output.json>")
        sys.exit(1)
    extract_docx_file(sys.argv[1], sys.argv[2])
