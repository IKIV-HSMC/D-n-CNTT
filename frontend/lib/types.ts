// ── Document domain types ──────────────────────────────────────────────────────

export type DocumentStatus = 'uploaded' | 'extracting' | 'extracted' | 'failed';

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface Subject {
  id: string;
  name: string;
  created_at: string;
}

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
  subject_id: string;
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
  id?: string;
  front: string;
  back: string;
  node_id: string | null;
}

export type ReviewRating = 'again' | 'hard' | 'good' | 'easy';

export interface FlashcardSessionCard extends Flashcard {
  id: string;
  document_id: string;
  due_at: string;
  repetitions: number;
  interval_days: number;
  ease_factor: number;
  total_reviews: number;
  is_new: boolean;
}

export interface FlashcardSessionResponse {
  cards: FlashcardSessionCard[];
  returned_count: number;
}

export interface FlashcardReviewResult {
  flashcard_id: string;
  rating: ReviewRating;
  reviewed_at: string;
  due_at: string;
  repetitions: number;
  interval_days: number;
  ease_factor: number;
  total_reviews: number;
  lapses: number;
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
  mermaid?: string;
  knowledge?: {
    title: string;
    summary: string;
    sections: Array<{ heading: string; level: number; summary: string; facts: string[] }>;
  };
  reactflow?: { nodes: ReactFlowNode[]; edges: ReactFlowEdge[] };
  backend?: string;
  model?: string;
  pipeline?: {
    step1_provider: string;
    step1_model: string;
    step2_provider: string;
    step2_model: string;
    chunk_count: number;
  };
}

export type MindmapStatus = 'idle' | 'loading' | 'success' | 'error';

export interface ProcessingRun {
  id: string;
  document_id: string;
  mode: 'engine' | 'ai';
  status: 'queued' | 'processing' | 'completed' | 'failed';
  stage: string;
  progress: number;
  attempts: number;
  error_message: string | null;
  result: MindmapResult | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}
