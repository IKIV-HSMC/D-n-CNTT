import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

SYSTEM = (
    "Bạn là chuyên gia tóm tắt học liệu. Từ đoạn tài liệu, trả về DUY NHẤT một JSON: "
    '{"mindmap":{"nodes":[{"id","label","parent_id"}]},"flashcards":[{"front","back","node_id"}]}. '
    "Node gốc có parent_id=null, nhãn ngắn (<=8 từ), flashcard hỏi-đáp chính xác theo nội dung."
)

chunk_test = """
Software Engineering là ngành kỹ thuật áp dụng các nguyên lý khoa học máy tính và quản lý dự án để xây dựng phần mềm chất lượng cao, đúng hạn và trong ngân sách.
Các giai đoạn chính trong quy trình phát triển phần mềm bao gồm:
1. Thu thập và phân tích yêu cầu (Requirements Analysis)
2. Thiết kế hệ thống và kiến trúc (System Design)
3. Lập trình và cài đặt (Implementation/Coding)
4. Kiểm thử phần mềm (Testing & QA)
5. Triển khai và bảo trì (Deployment & Maintenance)
"""

model_path = "D:/AI/mindmap-model"
print("1. Đang nạp Tokenizer...")
tok = AutoTokenizer.from_pretrained(model_path)

print("2. Đang nạp Model (low_cpu_mem_usage=True)...")
try:
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        device_map="cpu"
    )
    print("3. Nạp Model thành công! Đang sinh Mindmap & Flashcard thử nghiệm...")

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": chunk_test.strip()}
    ]
    prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(prompt, return_tensors="pt").to("cpu")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=800,
            temperature=0.2,
            do_sample=True,
            pad_token_id=tok.eos_token_id
        )

    response = tok.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    print("\n========== KẾT QUẢ SINH TỪ MODEL ==========")
    print(response)

    # Thử parse JSON
    data = json.loads(response.strip())
    print("\n-> Parse JSON thành công 100%!")
    print(f"-> Số nodes Mindmap: {len(data.get('mindmap', {}).get('nodes', []))}")
    print(f"-> Số Flashcards: {len(data.get('flashcards', []))}")

except Exception as e:
    print(f"\n[LỖI]: {e}", file=sys.stderr)
