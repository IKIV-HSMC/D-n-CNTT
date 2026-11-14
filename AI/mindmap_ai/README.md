# Doc → Mindmap & Flashcards: bộ công cụ đầy đủ

## Các file
| File | Dùng để |
|---|---|
| `extract_docx.py` | Word (.docx) → JSON có cấp heading (`sections`) |
| `mindmap_engine.py` | Engine luật chạy ngay trên CPU (dự phòng + chuẩn hoá dữ liệu) |
| `make_training_data.py` | Cắt đoạn + tạo dataset JSONL (`--teacher local / gemini / engine`) |
| `teacher_local.py` | "Giáo viên" mã nguồn mở chạy trên GPU, không cần API key |
| `train_lora.py` | Fine-tune Qwen2.5 bằng QLoRA (Unsloth) |
| `evaluate.py` | Đo tỷ lệ JSON hợp lệ trên tập validation |
| `kaggle_train.ipynb` | Notebook chạy toàn bộ quy trình trên Kaggle |
| `api.py` | FastAPI `POST /api/generate` (engine; nối model tại `run_model`) |
| `sample_output.json`, `sample_reactflow.json` | Kết quả mẫu trên file UniLearn |

## Quy trình
1. **Gom 30–100 tài liệu .docx** vào `raw/`, rồi trích xuất:
   `pip install python-docx` → `for f in raw/*.docx; do python extract_docx.py "$f" "docs/$(basename "${f%.docx}").json"; done`
   (PDF/PPT: tự trích xuất thành JSON có khoá `extracted_text`, đặt vào `docs/`.)
2. **Kaggle**: xác minh số điện thoại → New Dataset: tải lên toàn bộ file `.py` + thư mục `docs/` (đặt tên `mindmap-train`).
3. **New Notebook** → Import `kaggle_train.ipynb` → bật GPU T4 + Internet → Add Input = dataset trên.
4. Chạy lần lượt các ô: cài đặt → xem trước cách cắt → tạo dữ liệu → kiểm tra mẫu → chạy thử nhỏ → train → đánh giá → nén model.
5. Tải `mindmap-model.zip` ở tab Output. Chạy bằng Ollama/vLLM và nối vào `run_model()` trong `api.py`; giữ engine làm dự phòng.

## Lưu ý
- Cần ≥ 10 tài liệu để có tập validation; ít hơn thì `train.val.jsonl` rỗng và bước train/đánh giá sẽ lỗi.
- `train_lora.py`, `teacher_local.py`, `evaluate.py` chưa được chạy thử trên GPU (lúc viết không có GPU). Nếu lỗi, gửi toàn bộ thông báo lỗi.
- Hướng dẫn chi tiết từng bước và bảng xử lý lỗi nằm trong tài liệu Claude Doc đi kèm.
