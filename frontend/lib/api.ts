import axios, { AxiosProgressEvent } from 'axios';
import { Document, DocumentDetail, DocumentListResponse, DocumentFilters, MindmapResult } from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
});

// ── Response interceptor – chuẩn hóa lỗi ──────────────────────────────────────
apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail;
    if (detail && typeof detail === 'object' && detail.message) {
      err.displayMessage = detail.message;
    } else if (typeof detail === 'string') {
      err.displayMessage = detail;
    } else {
      err.displayMessage = 'Đã xảy ra lỗi, vui lòng thử lại';
    }
    return Promise.reject(err);
  },
);

// ── Document API ───────────────────────────────────────────────────────────────

export const documentsApi = {
  /** Upload một file với progress callback */
  upload(
    file: File,
    subjectId?: string,
    onProgress?: (percent: number) => void,
  ): Promise<Document> {
    const form = new FormData();
    form.append('file', file);
    if (subjectId) form.append('subject_id', subjectId);

    return apiClient
      .post<Document>('/api/documents/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e: AxiosProgressEvent) => {
          if (e.total && onProgress) {
            onProgress(Math.round((e.loaded * 100) / e.total));
          }
        },
      })
      .then((r) => r.data);
  },

  /** Danh sách documents với phân trang + filter */
  list(filters: Partial<DocumentFilters> = {}): Promise<DocumentListResponse> {
    const params: Record<string, string | number> = {
      page: filters.page ?? 1,
      page_size: 12,
    };
    if (filters.search) params.search = filters.search;
    if (filters.status) params.status = filters.status;
    if (filters.file_type) params.file_type = filters.file_type;

    return apiClient.get<DocumentListResponse>('/api/documents', { params }).then((r) => r.data);
  },

  /** Chi tiết một document */
  getById(id: string): Promise<DocumentDetail> {
    return apiClient.get<DocumentDetail>(`/api/documents/${id}`).then((r) => r.data);
  },

  /** Xóa document */
  delete(id: string): Promise<void> {
    return apiClient.delete(`/api/documents/${id}`).then(() => undefined);
  },
};

// ── Mindmap API ────────────────────────────────────────────────────────────────

export const mindmapApi = {
  /** Sinh mindmap + flashcards mới từ tài liệu (mặc định: 'engine' bóc tách cấu trúc tài liệu, hoặc 'ai' dùng Ollama) */
  generate(documentId: string, mode: 'engine' | 'ai' = 'engine'): Promise<MindmapResult> {
    return apiClient
      .post<MindmapResult>(`/api/mindmap/${documentId}`, null, {
        params: { mode },
        timeout: 180_000,
      })
      .then((r) => r.data);
  },

  /** Lấy kết quả mindmap đã sinh trước đó */
  get(documentId: string): Promise<MindmapResult> {
    return apiClient.get<MindmapResult>(`/api/mindmap/${documentId}`).then((r) => r.data);
  },

  /** Kiểm tra Ollama sẵn sàng chưa */
  health(): Promise<{ ollama_running: boolean; mindmap_model_loaded: boolean; models_available: string[] }> {
    return apiClient.get('/api/mindmap/health').then((r) => r.data);
  },
};
