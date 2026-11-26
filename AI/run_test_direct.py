import json
import sys
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

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

chunk_test = """
Lập trình hướng đối tượng (OOP) là một phương pháp lập trình dựa trên khái niệm các "đối tượng".
Bốn tính chất cốt lõi của OOP bao gồm:
1. Đóng gói (Encapsulation): Che giấu trạng thái nội bộ của đối tượng và chỉ cho phép truy cập thông qua các phương thức công khai.
2. Kế thừa (Inheritance): Cho phép lớp con tái sử dụng và mở rộng các thuộc tính, phương thức từ lớp cha.
3. Đa hình (Polymorphism): Cho phép các đối tượng thuộc các lớp khác nhau phản hồi cùng một thông điệp theo các cách khác nhau.
4. Trừu tượng (Abstraction): Tập trung vào các đặc tính cốt lõi của đối tượng và ẩn đi các chi tiết triển khai phức tạp.
"""

model_path = r"D:\project\New folder\D-n-CNTT\AI\mindmap-model-gguf"

print("1. Đang nạp Tokenizer từ", model_path)
tok = AutoTokenizer.from_pretrained(model_path)

print("2. Đang nạp Mô hình với định dạng tiết kiệm RAM (bfloat16, ~3.2GB)...")
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    dtype=torch.bfloat16,
    low_cpu_mem_usage=True,
    device_map="cpu"
)
print("-> Nạp mô hình thành công!")

messages = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": chunk_test.strip()}
]
prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tok(prompt, return_tensors="pt").to("cpu")

print("\n3. Đang sinh Mindmap & Flashcard...")
with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=600,
        temperature=0.2,
        do_sample=True,
        pad_token_id=tok.eos_token_id
    )

input_len = inputs["input_ids"].shape[1]
generated_ids = outputs[0][input_len:]
output_text = tok.decode(generated_ids, skip_special_tokens=True).strip()

print("\n==================== KẾT QUẢ SINH TỪ MODEL ====================")
print(output_text)
print("================================================================")

try:
    data = json.loads(output_text)
    nodes = data.get("mindmap", {}).get("nodes", [])
    cards = data.get("flashcards", [])
    print(f"\n[XÁC THỰC THÀNH CÔNG]")
    print(f"- Số lượng nodes trong Mindmap: {len(nodes)}")
    print(f"- Số lượng Flashcards: {len(cards)}")
    for n in nodes:
        print(f"  * Node [{n.get('id')}]: {n.get('label')} (parent: {n.get('parent_id')}) -> {n.get('description', '')}")
    for c in cards:
        print(f"  * Card: [Hỏi] {c.get('front')} -> [Đáp] {c.get('back')}")
except Exception as e:
    print(f"\n[PARSING LỖI / RAW]: {e}")
