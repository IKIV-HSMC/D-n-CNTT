"""
teacher_local.py - Dùng model mã nguồn mở làm "giáo viên" ngay trên GPU Kaggle/Colab, KHÔNG cần API key.
Dùng qua:  python make_training_data.py "docs/*.json" --teacher local --out train.jsonl
(Phải chạy trên máy có GPU, đã cài unsloth.)
"""
import json, re
from unsloth import FastLanguageModel

MODEL = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"   # nếu hết bộ nhớ: unsloth/Qwen2.5-3B-Instruct
EXAMPLE = ('{"mindmap":{"nodes":[{"id":"n0","label":"Mô hình OSI","parent_id":null},'
           '{"id":"n1","label":"Tầng vật lý","parent_id":"n0"}]},'
           '"flashcards":[{"front":"Mô hình OSI có mấy tầng?","back":"7 tầng","node_id":"n0"}]}')
_model = _tok = None


def _load():
    global _model, _tok
    if _model is None:
        _model, _tok = FastLanguageModel.from_pretrained(MODEL, max_seq_length=4096, load_in_4bit=True)
        FastLanguageModel.for_inference(_model)
    return _model, _tok


def generate(system: str, chunk: str) -> dict:
    model, tok = _load()
    msgs = [{"role": "system", "content": system + "\nVí dụ định dạng đầu ra: " + EXAMPLE},
            {"role": "user", "content": chunk}]
    ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to("cuda")
    out = model.generate(input_ids=ids, max_new_tokens=1500, temperature=0.2, do_sample=True)
    text = tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0))
