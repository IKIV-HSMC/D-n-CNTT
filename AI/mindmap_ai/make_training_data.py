"""
make_training_data.py - tạo dataset (JSONL) để fine-tune model của riêng bạn.

Mỗi dòng: {"messages":[system, user(chunk văn bản), assistant(JSON mindmap+flashcards)]}

Teacher:
  --teacher gemini  : gọi Gemini 1 lần / chunk (cần GEMINI_API_KEY)  <- NÊN DÙNG, chất lượng cao
  --teacher local   : model mã nguồn mở chạy ngay trên GPU Kaggle/Colab, miễn phí, không cần API key
                      (xem teacher_local.py; chậm hơn và chất lượng thấp hơn Gemini, nhưng không tốn tiền)
  --teacher engine  : dùng luật trong mindmap_engine.py (chỉ để chạy thử pipeline, model học xong
                      sẽ chỉ bắt chước luật, không giỏi hơn engine)

Ví dụ:
  python make_training_data.py docs/*.json --teacher gemini --out train.jsonl
"""
import argparse, glob, json, os, random, re, sys, time
import mindmap_engine as me

SYSTEM = ("Bạn là chuyên gia tóm tắt học liệu. Từ đoạn tài liệu, trả về DUY NHẤT một JSON: "
          '{"mindmap":{"nodes":[{"id","label","parent_id"}]},"flashcards":[{"front","back","node_id"}]}. '
          "Node gốc có parent_id=null, nhãn ngắn (<=8 từ), flashcard hỏi-đáp chính xác theo nội dung.")

CHUNK_MIN, CHUNK_MAX = 300, 2500   # ký tự


def chunks_from_doc(doc):
    text = doc["extracted_text"]
    secs = me.sections_from_json_sections(doc["sections"]) if doc.get("sections") else me.parse_sections(text)
    for s in secs:
        raw = s.raw_text()
        if len(raw) < CHUNK_MIN:
            continue
        yield s, f"{s.title}\n{raw[:CHUNK_MAX]}"


def teacher_gemini(chunk):
    import requests
    key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    body = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"parts": [{"text": chunk}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    r = requests.post(url, json=body, timeout=60)
    r.raise_for_status()
    return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])


def valid(o, chunk):
    """Lọc mẫu hỏng: sai schema, cây lỗi, flashcard trỏ node không tồn tại, thẻ quá ngắn/trùng."""
    try:
        nodes, cards = o["mindmap"]["nodes"], o["flashcards"]
        if not isinstance(nodes, list) or not isinstance(cards, list):
            return False
        if any(not isinstance(n, dict) or "id" not in n for n in nodes):
            return False
        ids = {n["id"] for n in nodes}
        roots = [n for n in nodes if n.get("parent_id") is None]
        if len(roots) != 1 or len(ids) != len(nodes) or len(nodes) < 3:
            return False
        if any(n.get("parent_id") not in ids | {None} for n in nodes):
            return False
        if not cards or any(not isinstance(c, dict) or c.get("node_id") not in ids for c in cards):
            return False
        if any("front" not in c or "back" not in c for c in cards):
            return False
        fronts = [c["front"].strip().lower() for c in cards]
        return len(set(fronts)) == len(fronts) and all(len(c["back"]) >= 3 for c in cards)
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--teacher", choices=["gemini", "local", "engine"], default="engine")
    ap.add_argument("--out", default="train.jsonl")
    ap.add_argument("--val-ratio", type=float, default=0.1)
    a = ap.parse_args()

    files = [f for p in a.inputs for f in glob.glob(p)]
    random.seed(0)
    random.shuffle(files)
    n_val = max(1, int(len(files) * a.val_ratio)) if len(files) > 1 else 0
    split = {f: ("val" if i < n_val else "train") for i, f in enumerate(files)}   # tách theo TÀI LIỆU
    outs = {"train": open(a.out, "w", encoding="utf-8"),
            "val": open(a.out.replace(".jsonl", ".val.jsonl"), "w", encoding="utf-8")}
    kept = dropped = 0
    for f in files:
        doc = json.load(open(f, encoding="utf-8"))
        idf = me.Idf([doc["extracted_text"]])
        for sec, chunk in chunks_from_doc(doc):
            try:
                if a.teacher == "gemini":
                    o = teacher_gemini(chunk)
                    time.sleep(5)            # tránh bị giới hạn tốc độ (429)
                elif a.teacher == "local":
                    import teacher_local
                    o = teacher_local.generate(SYSTEM, chunk)
                else:
                    o = me.generate_for_section(sec, idf)
            except Exception as e:
                print("teacher lỗi:", e, file=sys.stderr)
                dropped += 1
                continue
            if not valid(o, chunk):
                dropped += 1
                continue
            row = {"messages": [{"role": "system", "content": SYSTEM},
                                {"role": "user", "content": chunk},
                                {"role": "assistant", "content": json.dumps(o, ensure_ascii=False)}]}
            outs[split[f]].write(json.dumps(row, ensure_ascii=False) + "\n")
            outs[split[f]].flush()           # ghi ngay để không mất dữ liệu nếu phiên bị ngắt
            kept += 1
    # print(f"giữ {kept} mẫu, bỏ {dropped} mẫu lỗi")


if __name__ == "__main__":
    main()
