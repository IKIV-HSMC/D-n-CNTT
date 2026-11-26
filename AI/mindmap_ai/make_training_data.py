"""
make_training_data.py - tạo dataset (JSONL) để fine-tune model của riêng bạn.

Mỗi dòng: {"messages":[system, user(chunk văn bản), assistant(JSON mindmap+flashcards)]}

Teacher:
  --teacher gemini  : gọi Gemini sinh nhãn chất lượng cao sư phạm (cần GEMINI_API_KEY) <- KHUYÊN DÙNG
  --teacher local   : model mã nguồn mở chạy ngay trên GPU Kaggle/Colab, miễn phí, không cần API key
  --teacher engine  : dùng luật trích xuất và lọc rác trong mindmap_engine.py (offline, nhanh, 0 tốn token)

Ví dụ:
  python make_training_data.py "docs/*.json" --teacher gemini --out train.jsonl
  python make_training_data.py "docs/*.json" --teacher engine --out train.jsonl
"""
import argparse
import glob
import json
import os
import random
import re
import sys
import time

import mindmap_engine as me

SYSTEM = (
    "Bạn là chuyên gia sư phạm và tóm tắt học liệu. Từ đoạn tài liệu cung cấp, trả về DUY NHẤT một JSON hợp lệ theo đúng cấu trúc sau:\n"
    '{"mindmap":{"nodes":[{"id":"1","label":"Tên chủ đề chính","description":"Giải thích ngắn 1-2 câu","parent_id":null},{"id":"2","label":"Nhánh con","description":"Mô tả chi tiết","parent_id":"1"}]},"flashcards":[{"front":"Câu hỏi trọng tâm?","back":"Câu trả lời chi tiết và chính xác","node_id":"2"}]}\n'
    "Quy tắc:\n"
    "1. Node gốc bắt buộc có parent_id=null, id dạng số nguyên tăng dần bắt đầu từ 1.\n"
    "2. Nhãn (label) súc tích (dưới 8 từ).\n"
    "3. description giải thích cô đọng bản chất kiến thức.\n"
    "4. Phân cấp logic rõ ràng: Chủ đề gốc -> Nhánh chính -> Ý chi tiết.\n"
    "5. Flashcard hỏi-đáp chính xác, sâu sắc theo nội dung đoạn trích.\n"
    "6. KHÔNG giải thích dông dài, CHỈ TRẢ VỀ DUY NHẤT ĐÚNG MỘT JSON HỢP LỆ."
)

CHUNK_MIN, CHUNK_MAX = 250, 3000   # ký tự


def chunks_from_doc(doc):
    text = doc.get("extracted_text", "")
    secs = me.sections_from_json_sections(doc["sections"]) if doc.get("sections") else me.parse_sections(text)
    for s in secs:
        raw = s.raw_text()
        if len(raw) < CHUNK_MIN:
            continue
        yield s, f"{s.title}\n{raw[:CHUNK_MAX]}"


def teacher_gemini(chunk):
    import requests
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("Chưa thiết lập biến môi trường GEMINI_API_KEY!")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"parts": [{"text": chunk}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }
    r = requests.post(url, json=body, timeout=60)
    r.raise_for_status()
    raw_resp = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw_resp)


def valid(o, chunk):
    """Lọc mẫu hỏng: sai schema, cây lỗi, flashcard trỏ node không tồn tại, thẻ quá ngắn/trùng."""
    try:
        if not isinstance(o, dict):
            return False
        if "mindmap" not in o or "flashcards" not in o:
            return False
        nodes = o["mindmap"].get("nodes", [])
        cards = o["flashcards"]
        if not isinstance(nodes, list) or not isinstance(cards, list):
            return False
        if len(nodes) < 2 or len(cards) < 1:
            return False

        ids = set()
        for n in nodes:
            if not isinstance(n, dict) or "id" not in n or "label" not in n:
                return False
            ids.add(str(n["id"]))

        roots = [n for n in nodes if n.get("parent_id") is None]
        if len(roots) != 1 or len(ids) != len(nodes):
            return False

        # Kiểm tra parent_id của các node con
        for n in nodes:
            pid = n.get("parent_id")
            if pid is not None and str(pid) not in ids:
                return False

        # Kiểm tra flashcards
        for c in cards:
            if not isinstance(c, dict) or "front" not in c or "back" not in c:
                return False
            if str(c.get("node_id", "")) not in ids:
                return False
            if len(c["front"].strip()) < 5 or len(c["back"].strip()) < 3:
                return False

        fronts = [c["front"].strip().lower() for c in cards]
        if len(set(fronts)) != len(fronts):
            return False

        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="Đường dẫn tới file docs/*.json")
    ap.add_argument("--teacher", choices=["gemini", "local", "engine"], default="engine")
    ap.add_argument("--out", default="train.jsonl")
    ap.add_argument("--val-ratio", type=float, default=0.1)
    a = ap.parse_args()

    files = [f for p in a.inputs for f in glob.glob(p)]
    if not files:
        print(f"Không tìm thấy file nào khớp với: {a.inputs}", file=sys.stderr)
        sys.exit(1)

    random.seed(42)
    random.shuffle(files)
    n_val = max(1, int(len(files) * a.val_ratio)) if len(files) > 1 else 0
    split = {f: ("val" if i < n_val else "train") for i, f in enumerate(files)}

    val_out_name = a.out.replace(".jsonl", ".val.jsonl") if ".jsonl" in a.out else f"{a.out}.val"
    outs = {
        "train": open(a.out, "w", encoding="utf-8"),
        "val": open(val_out_name, "w", encoding="utf-8")
    }

    kept = 0
    dropped = 0
    print(f"Bắt đầu tạo dữ liệu từ {len(files)} tài liệu (Teacher: {a.teacher})...")

    for f_idx, f in enumerate(files, 1):
        try:
            with open(f, encoding="utf-8") as fp:
                doc = json.load(fp)
        except Exception as e:
            print(f"[{f_idx}/{len(files)}] Lỗi đọc file {f}: {e}", file=sys.stderr)
            continue

        idf = me.Idf([doc.get("extracted_text", "")])
        doc_chunks = list(chunks_from_doc(doc))
        print(f"[{f_idx}/{len(files)}] {os.path.basename(f)}: trích xuất {len(doc_chunks)} chunks")

        for sec, chunk in doc_chunks:
            try:
                if a.teacher == "gemini":
                    o = teacher_gemini(chunk)
                    time.sleep(2.5)  # Tránh rate limit
                elif a.teacher == "local":
                    import teacher_local
                    o = teacher_local.generate(SYSTEM, chunk)
                else:
                    o = me.generate_for_section(sec, idf)
            except Exception as e:
                dropped += 1
                continue

            if not valid(o, chunk):
                dropped += 1
                continue

            row = {
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": chunk},
                    {"role": "assistant", "content": json.dumps(o, ensure_ascii=False)}
                ]
            }
            target_file = outs[split[f]]
            target_file.write(json.dumps(row, ensure_ascii=False) + "\n")
            target_file.flush()
            kept += 1

    outs["train"].close()
    outs["val"].close()
    print(f"==> Hoàn thành! Giữ lại: {kept} mẫu hợp lệ, loại bỏ: {dropped} mẫu không đạt chuẩn.")
    print(f"Tập train: {a.out} | Tập val: {val_out_name}")


if __name__ == "__main__":
    main()
