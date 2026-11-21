# DocMind – AI Document-to-Mindmap

> Người dùng có thể tạo và xem mindmap từ PDF/DOCX/PPTX mà không cần tài khoản. Đăng nhập hoặc đăng ký khi muốn lưu tài liệu, lịch sử học tập hoặc tải kết quả.

---

## Yêu cầu hệ thống

| Công cụ | Phiên bản tối thiểu |
|---------|---------------------|
| Docker  | 24+ |
| Docker Compose | 2.20+ |
| Git | bất kỳ |

> Không cần cài Python hay Node.js – tất cả chạy trong container.

---

## Cài đặt và chạy

### 1. Clone và cấu hình môi trường

```bash
git clone <repo-url>
cd "Dự án công nghệ thông tin"

# Sao chép file cấu hình mẫu
copy .env.example .env
```

Mở `.env` và chỉnh mật khẩu PostgreSQL nếu cần (mặc định: `changeme`).

### 2. Khởi động toàn bộ hệ thống

```bash
docker compose up --build
```

Lần đầu chạy sẽ mất 3–5 phút để tải image và cài dependencies.

> Nếu đã có tài liệu từ phiên bản chưa có tài khoản, migration giữ lại file nhưng không tự gán chúng cho tài khoản mới. Hãy sao lưu hoặc upload lại các tài liệu cần tiếp tục dùng.

### 3. Kiểm tra

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

---

## Chạy Unit Tests

```bash
# Vào container backend
docker compose exec backend pytest tests/ -v

# Hoặc chạy trực tiếp (cần Python 3.11+ và dependencies)
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

---

## Cấu trúc thư mục

```
.
├── backend/
│   ├── app/
│   │   ├── api/          # Endpoints
│   │   ├── core/         # Config, Database
│   │   ├── models/       # ORM Models
│   │   ├── schemas/      # Pydantic Schemas
│   │   └── services/     # Business Logic
│   ├── alembic/          # Database migrations
│   └── tests/            # Unit tests
├── frontend/
│   ├── app/              # Next.js App Router
│   ├── components/       # UI Components
│   └── lib/              # API client, Types
├── storage/              # File uploads (Docker volume)
├── AI/                   # Module AI (giai đoạn sau)
├── docker-compose.yml
└── .env.example
```

---

## API Endpoints

Các API tài khoản và dữ liệu trong thư viện yêu cầu đăng nhập; phiên đăng nhập dùng cookie HTTPOnly. API tạo mindmap khách không lưu file hay kết quả vào tài khoản.

### Tài khoản
```
POST /api/auth/register
POST /api/auth/login
POST /api/auth/google
POST /api/auth/logout
GET  /api/auth/me
```

Đăng nhập Google dùng Google Identity Services để gửi ID token tới backend. Backend xác minh chữ ký, audience và thời hạn token trước khi tạo cookie phiên. Đặt cùng một OAuth Client ID vào `GOOGLE_CLIENT_ID` và `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. Trong Google Cloud Console, tạo OAuth Client ID loại **Web application** và thêm origin của frontend vào **Authorized JavaScript origins** (ví dụ `http://localhost:3000`; nếu truy cập qua Nginx, thêm `http://localhost:8080`). Luồng này không cần Client Secret hay redirect URI.

### Môn học
```
GET    /api/subjects
POST   /api/subjects
PATCH  /api/subjects/{id}
DELETE /api/subjects/{id}
```

### Upload tài liệu
```
POST /api/documents/upload
Content-Type: multipart/form-data

Fields:
  file        - File PDF, DOCX hoặc PPTX (bắt buộc)
  subject_id  - UUID môn học của tài khoản hiện tại (tùy chọn)
```

### Tạo mindmap không cần tài khoản
```
POST /api/mindmap/guest?mode=engine
Content-Type: multipart/form-data

Fields:
  file - File PDF, DOCX hoặc PPTX
  mode - engine hoặc ai (query parameter)
```

File được xử lý tạm trong bộ nhớ. Để lưu kết quả vào thư viện, người dùng đăng nhập rồi gọi API dưới đây:
```
POST /api/documents/save-generated
Content-Type: multipart/form-data

Fields:
  file        - Tài liệu nguồn
  result_json - Kết quả mindmap nhận từ API guest
```

### Danh sách tài liệu
```
GET /api/documents?page=1&page_size=20&search=&status=&file_type=
```

### Chi tiết tài liệu
```
GET /api/documents/{id}
```

### Xóa tài liệu
```
DELETE /api/documents/{id}
```

### Mindmap
```
POST /api/mindmap/guest?mode=engine # Tạo và xem kết quả tạm thời, không cần tài khoản
POST /api/mindmap/{id}?mode=engine  # Xếp tác vụ nền, trả 202 + run_id
POST /api/mindmap/{id}?mode=ai      # Hai bước AI: knowledge JSON → mindmap + flashcard
GET  /api/mindmap/runs/{run_id}    # Trạng thái, tiến độ và kết quả khi hoàn tất
GET  /api/mindmap/{id}/runs/latest # Khôi phục tác vụ mới nhất của tài liệu
GET  /api/mindmap/{id}/runs       # Liệt kê các lần xử lý để mở snapshot cũ
GET  /api/mindmap/{id}
GET  /api/mindmap/{id}/reactflow
GET  /api/mindmap/{id}/export/svg
GET  /api/mindmap/{id}/export/mermaid
GET  /api/mindmap/health            # Health check Ollama, không cần đăng nhập
```

Mỗi bước có thể chọn `ollama`, `gemini` hoặc `openai` qua `AI_STEP1_PROVIDER` và `AI_STEP2_PROVIDER`. Mặc định cả hai dùng Ollama local. Nếu chọn provider cloud, điền API key và tên model cho bước tương ứng trong `.env`; khóa chỉ được đọc ở backend. Khi dùng provider cloud, nội dung trích xuất của tài liệu được gửi tới nhà cung cấp đó để xử lý.

### Luyện flashcard và Anki
```
GET  /api/flashcards/session?document_id={id}&limit=30
POST /api/flashcards/{flashcard_id}/review
GET  /api/flashcards/{document_id}/export/anki
```

Gửi `{"rating":"again"}`, `{"rating":"hard"}`, `{"rating":"good"}` hoặc `{"rating":"easy"}` để cập nhật lịch SM-2. Lịch và lịch sử từng lần đánh giá được lưu trong PostgreSQL. API Anki xuất các thẻ đang hoạt động của tài liệu thành `.apkg`.

---

## Các trường hợp lỗi

| Mã lỗi | HTTP | Nguyên nhân |
|--------|------|-------------|
| `INVALID_FILE` | 400 | Sai định dạng hoặc magic bytes không khớp |
| `FILE_TOO_LARGE` | 413 | Vượt quá giới hạn MAX_UPLOAD_MB |
| `NOT_FOUND` | 404 | Document không tồn tại |
| `INTERNAL_ERROR` | 500 | Lỗi server |

---

## Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `DATABASE_URL` | bắt buộc | Connection string PostgreSQL (asyncpg) |
| `MAX_UPLOAD_MB` | `20` | Giới hạn dung lượng file |
| `STORAGE_PATH` | `/storage/uploads` | Thư mục lưu file trên server |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Origins được phép |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL backend cho frontend |
| `AUTH_SESSION_TTL_DAYS` | `7` | Thời hạn phiên đăng nhập |
| `AUTH_COOKIE_SECURE` | `false` | Đặt `true` khi triển khai HTTPS |
| `GOOGLE_CLIENT_ID` | trống | OAuth Client ID dùng để backend xác minh ID token Google |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | trống | Cùng OAuth Client ID để hiển thị nút đăng nhập Google ở frontend |
| `AI_STEP1_PROVIDER` | `ollama` | Provider chuẩn hóa kiến thức |
| `AI_STEP2_PROVIDER` | `ollama` | Provider tạo mindmap và flashcard |
| `AI_STEP1_MODEL` | model Ollama mặc định | Model cho bước 1; để trống dùng `OLLAMA_MODEL` |
| `AI_STEP2_MODEL` | model Ollama mặc định | Model cho bước 2; để trống dùng `OLLAMA_MODEL` |
| `AI_TIMEOUT` | `180` giây | Giới hạn thời gian cho một lần gọi provider |
| `GEMINI_API_KEY` | trống | Khóa server-side nếu chọn Gemini |
| `OPENAI_API_KEY` | trống | Khóa server-side nếu chọn OpenAI |

---

## Dừng và dọn dẹp

```bash
# Dừng services
docker compose down

# Dừng và xóa volumes (XÓA DỮ LIỆU)
docker compose down -v
```

---

## Tình trạng tính năng

- [x] Tài khoản email/mật khẩu và Google Sign-In, cookie phiên và phân quyền tài liệu theo chủ sở hữu
- [x] Tạo môn học, gắn và lọc tài liệu theo môn
- [x] Pipeline hai bước AI: JSON kiến thức rồi Mermaid/Flashcard; provider cấu hình riêng cho từng bước
- [x] Hàng đợi PostgreSQL và worker bền vững cho tác vụ AI dài; có tiến độ, lease và retry
- [x] Mermaid renderer có zoom/pan, tải `.mmd`/SVG và in ra PDF; chế độ sơ đồ hiện có PNG/SVG
- [x] Flashcard có lịch ôn SM-2, lưu tiến độ và xuất Anki `.apkg`
- [ ] OCR cho PDF scan

Worker chạy riêng trong Docker Compose và dùng PostgreSQL làm hàng đợi. API trả ngay 202; giao diện theo dõi tiến độ, khôi phục tác vụ gần nhất và chọn snapshot mindmap đã hoàn tất. Mỗi tác vụ có tối đa ba lần thử. Luyện tập và Anki luôn dùng bộ thẻ mới nhất của tài liệu.
