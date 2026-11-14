"""
extract_docx.py - Trích xuất file Word (.docx) thành JSON có cấp heading ("sections").
Dùng:  python extract_docx.py bai_giang.docx docs/bai_giang.json
Gom nhiều file:  for f in raw/*.docx; do python extract_docx.py "$f" "docs/$(basename "${f%.docx}").json"; done
Cần:   pip install python-docx
"""
import docx, json, sys

d = docx.Document(sys.argv[1])
sections, cur = [], None
for p in d.paragraphs:
    t = p.text.strip()
    if not t:
        continue
    name = p.style.name
    if name.startswith("Heading"):
        last = name.split()[-1]
        lv = int(last) if last.isdigit() else 1
        cur = {"heading": t, "level": lv, "text": ""}
        sections.append(cur)
    elif cur is not None:
        cur["text"] += t + "\n"

out = {
    "original_filename": sys.argv[1].replace("\\", "/").split("/")[-1],
    "extracted_text": "\n".join(p.text for p in d.paragraphs if p.text.strip()),
    "sections": sections,
}
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(sections)} sections -> {sys.argv[2]}")
