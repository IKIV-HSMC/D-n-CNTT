import axios, { AxiosProgressEvent } from 'axios';
import {
  Document, DocumentDetail, DocumentListResponse, DocumentFilters, MindmapResult,
  Subject, User, FlashcardSessionResponse, FlashcardReviewResult, ReviewRating,
  ProcessingRun, GuestMindmapResponse,
} from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  withCredentials: true,
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

export const authApi = {
  register(email: string, password: string): Promise<User> {
    return apiClient.post<User>('/api/auth/register', { email, password }).then((r) => r.data);
  },
  login(email: string, password: string): Promise<User> {
    return apiClient.post<User>('/api/auth/login', { email, password }).then((r) => r.data);
  },
  google(credential: string): Promise<User> {
    return apiClient.post<User>('/api/auth/google', { credential }).then((r) => r.data);
  },
  me(): Promise<User> {
    return apiClient.get<User>('/api/auth/me').then((r) => r.data);
  },
  async logout(): Promise<void> {
    await apiClient.post('/api/auth/logout');
  },
};

export const subjectsApi = {
  list(): Promise<Subject[]> {
    return apiClient.get<Subject[]>('/api/subjects').then((r) => r.data);
  },
  create(name: string): Promise<Subject> {
    return apiClient.post<Subject>('/api/subjects', { name }).then((r) => r.data);
  },
  rename(id: string, name: string): Promise<Subject> {
    return apiClient.patch<Subject>(`/api/subjects/${id}`, { name }).then((r) => r.data);
  },
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/api/subjects/${id}`);
  },
};

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

  /** Save a guest-generated result after authentication. */
  saveGenerated(file: File, result: MindmapResult): Promise<Document> {
    const form = new FormData();
    form.append('file', file);
    form.append('result_json', JSON.stringify(result));
    return apiClient
      .post<Document>('/api/documents/save-generated', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120_000,
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
    if (filters.subject_id) params.subject_id = filters.subject_id;

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
  /** Generate in memory for a guest; nothing is stored until the user saves. */
  generateGuest(file: File, mode: 'engine' | 'ai' = 'engine'): Promise<GuestMindmapResponse> {
    const form = new FormData();
    form.append('file', file);
    return apiClient
      .post<GuestMindmapResponse>('/api/mindmap/guest', form, {
        params: { mode },
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600_000,
      })
      .then((r) => r.data);
  },

  /** Xếp một tác vụ sinh mindmap + flashcards vào hàng đợi nền. */
  start(documentId: string, mode: 'engine' | 'ai' = 'engine'): Promise<ProcessingRun> {
    return apiClient
      .post<ProcessingRun>(`/api/mindmap/${documentId}`, null, {
        params: { mode },
      })
      .then((r) => r.data);
  },

  getRun(runId: string): Promise<ProcessingRun> {
    return apiClient.get<ProcessingRun>(`/api/mindmap/runs/${runId}`).then((r) => r.data);
  },

  getLatestRun(documentId: string): Promise<ProcessingRun> {
    return apiClient.get<ProcessingRun>(`/api/mindmap/${documentId}/runs/latest`).then((r) => r.data);
  },

  listRuns(documentId: string): Promise<ProcessingRun[]> {
    return apiClient.get<ProcessingRun[]>(`/api/mindmap/${documentId}/runs`).then((r) => r.data);
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

export const flashcardsApi = {
  session(documentId: string, limit = 30): Promise<FlashcardSessionResponse> {
    return apiClient
      .get<FlashcardSessionResponse>('/api/flashcards/session', { params: { document_id: documentId, limit } })
      .then((r) => r.data);
  },

  review(cardId: string, rating: ReviewRating): Promise<FlashcardReviewResult> {
    return apiClient
      .post<FlashcardReviewResult>(`/api/flashcards/${cardId}/review`, { rating })
      .then((r) => r.data);
  },

  exportAnki(documentId: string): Promise<Blob> {
    return apiClient
      .get(`/api/flashcards/${documentId}/export/anki`, { responseType: 'blob', timeout: 60_000 })
      .then((r) => r.data as Blob);
  },
};
