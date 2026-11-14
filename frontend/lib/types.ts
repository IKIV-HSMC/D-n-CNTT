// ── Document domain types ──────────────────────────────────────────────────────

export type DocumentStatus = 'uploaded' | 'extracting' | 'extracted' | 'failed';

export interface Document {
  id: string;
  user_id: string | null;
  subject_id: string | null;
  original_filename: string;
  file_type: 'pdf' | 'docx' | 'pptx';
  file_size: number;      // bytes
  status: DocumentStatus;
  page_count: number | null;
  error_message: string | null;
  created_at: string;     // ISO datetime
  updated_at: string;
}

export interface DocumentDetail extends Document {
  extracted_text_preview: string | null;  // First 500 chars
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ── Upload queue ────────────────────────────────────────────────────────────────

export type UploadStatus = 'pending' | 'uploading' | 'success' | 'error';

export interface UploadItem {
  id: string;           // Local UUID for tracking
  file: File;
  status: UploadStatus;
  progress: number;     // 0-100
  error?: string;
  documentId?: string;  // Set after successful upload
}

// ── API error ──────────────────────────────────────────────────────────────────

export interface ApiError {
  code: string;
  message: string;
}

// ── Filters ────────────────────────────────────────────────────────────────────

export interface DocumentFilters {
  search: string;
  status: DocumentStatus | '';
  file_type: 'pdf' | 'docx' | 'pptx' | '';
  page: number;
}

// ── Mindmap / Flashcard ────────────────────────────────────────────────────────

export interface MindmapNode {
  id: string;
  label: string;
  description?: string;   // Giải thích ngắn của node (AI mode)
  parent_id: string | null;
}

export interface Flashcard {
  front: string;
  back: string;
  node_id: string;
}

export interface ReactFlowNode {
  id: string;
  data: { label: string };
  position: { x: number; y: number };
  type?: string;
}

export interface ReactFlowEdge {
  id: string;
  source: string;
  target: string;
}

export interface MindmapResult {
  document_id: string;
  mindmap: { nodes: MindmapNode[] };
  flashcards: Flashcard[];
  reactflow?: { nodes: ReactFlowNode[]; edges: ReactFlowEdge[] };
  backend?: string;
  model?: string;
}

export type MindmapStatus = 'idle' | 'loading' | 'success' | 'error';
