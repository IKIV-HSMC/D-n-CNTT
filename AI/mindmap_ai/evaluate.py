"""
evaluate.py - Đo tỷ lệ JSON hợp lệ + đúng cây của model đã train trên tập validation. CẦN GPU.
Dùng:  python evaluate.py --model mindmap-model --val train.val.jsonl --n 50
"""
import argparse, json
from unsloth import FastLanguageModel
from make_training_data import valid, SYSTEM

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="mindmap-model")
ap.add_argument("--val", default="train.val.jsonl")
ap.add_argument("--n", type=int, default=50)
a = ap.parse_args()

model, tok = FastLanguageModel.from_pretrained(a.model, max_seq_length=4096, load_in_4bit=True)
FastLanguageModel.for_inference(model)

rows = [json.loads(l) for l in open(a.val, encoding="utf-8") if l.strip()][: a.n]
if not rows:
    raise SystemExit("File validation rỗng: cần nhiều tài liệu hơn (khoảng 10 file trở lên).")
ok, bad = 0, []
for r in rows:
    chunk = r["messages"][1]["content"]
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": chunk}]
    ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to("cuda")
    out = model.generate(input_ids=ids, max_new_tokens=1500, temperature=0.2, do_sample=True)
    text = tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
    try:
        good = bool(valid(json.loads(text), chunk))
    except Exception:
        good = False
    ok += good
    if not good:
        bad.append(text[:300])
print(f"Hợp lệ: {ok}/{len(rows)} = {ok / len(rows):.0%}")
for b in bad[:3]:
    print("--- mẫu lỗi ---\n", b)
