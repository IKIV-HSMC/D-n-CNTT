"""
test_trained_model.py - Kiểm tra model docmind-model trên Ollama cục bộ.
Chạy: python test_trained_model.py
"""
import requests
import json
import sys

SAMPLE_TEXT = """
Object-Oriented Programming (OOP) là một phương pháp lập trình dựa trên khái niệm các "đối tượng".
Bốn tính chất cốt lõi của OOP bao gồm:
1. Đóng gói (Encapsulation): Che giấu trạng thái nội bộ và chỉ cho phép truy cập thông qua các phương thức công khai.
2. Kế thừa (Inheritance): Cho phép một lớp con tái sử dụng và mở rộng các thuộc tính, phương thức của lớp cha.
3. Đa hình (Polymorphism): Cho phép các đối tượng khác nhau phản hồi cùng một thông điệp theo các cách khác nhau.
4. Trừu tượng (Abstraction): Ẩn các chi tiết triển khai phức tạp và chỉ hiển thị các tính năng cốt lõi cho người dùng.
"""

def test_model(model_name="docmind-model"):
    print(f"=== Đang gửi yêu cầu kiểm tra tới Ollama (Model: {model_name}) ===")
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "prompt": SAMPLE_TEXT,
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(url, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()
        raw_output = data.get("response", "").strip()

        print("\n=== KẾT QUẢ ĐẦU RA TỪ MODEL ===")
        print(raw_output)

        parsed = json.loads(raw_output)
        nodes = parsed.get("mindmap", {}).get("nodes", [])
        cards = parsed.get("flashcards", [])

        print("\n=== ĐÁNH GIÁ CẤU TRÚC ===")
        print(f"-> Số nodes mindmap : {len(nodes)}")
        print(f"-> Số flashcards     : {len(cards)}")

        if len(nodes) >= 4 and len(cards) >= 2:
            print("\n[CHÚC MỪNG] Model hoạt động hoàn hảo! Đạt đầy đủ tiêu chuẩn mindmap và flashcard.")
        else:
            print("\n[CẢNH BÁO] Số lượng node hoặc card ít hơn dự kiến.")

    except requests.exceptions.ConnectionError:
        print("[LỖI] Không kết nối được với Ollama! Hãy chắc chắn lệnh 'ollama serve' hoặc app Ollama đang chạy.", file=sys.stderr)
    except Exception as e:
        print(f"[LỖI] Xảy ra ngoại lệ: {e}", file=sys.stderr)

if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "docmind-model"
    test_model(model)
