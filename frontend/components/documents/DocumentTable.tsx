'use client';

import React from 'react';
import { FileText, File, Presentation, Eye, Trash2, ChevronLeft, ChevronRight, BrainCircuit } from 'lucide-react';
import { Document } from '@/lib/types';
import { StatusBadge } from './StatusBadge';
import { formatFileSize, formatDate } from '@/lib/utils';
import { cn } from '@/lib/utils';

interface DocumentTableProps {
  documents: Document[];
  total: number;
  page: number;
  totalPages: number;
  loading: boolean;
  onPageChange: (p: number) => void;
  onView: (doc: Document) => void;
  onDelete: (doc: Document) => void;
  onMindmap: (doc: Document) => void;
}

const FileIcon = ({ type }: { type: string }) => {
  if (type === 'pdf') return <FileText size={18} className="text-red-400" />;
  if (type === 'docx') return <File size={18} className="text-blue-400" />;
  if (type === 'pptx') return <Presentation size={18} className="text-orange-400" />;
  return <File size={18} className="text-slate-400" />;
};

// Skeleton row
function SkeletonRow() {
  return (
    <tr className="border-b border-[rgba(255,255,255,0.04)]">
      {[200, 80, 100, 100, 120, 90].map((w, i) => (
        <td key={i} className="px-4 py-4">
          <div className={`h-4 rounded shimmer`} style={{ width: w }} />
        </td>
      ))}
    </tr>
  );
}

export function DocumentTable({
  documents, total, page, totalPages, loading, onPageChange, onView, onDelete, onMindmap,
}: DocumentTableProps) {
  if (!loading && documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-16 h-16 rounded-2xl bg-surface-700 border border-[rgba(90,108,240,0.15)] flex items-center justify-center mb-4">
          <FileText size={28} className="text-slate-600" />
        </div>
        <p className="text-slate-400 font-medium">Chưa có tài liệu nào</p>
        <p className="text-sm text-slate-600 mt-1">Kéo thả file vào khu vực phía trên để bắt đầu</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-x-auto rounded-2xl border border-[rgba(90,108,240,0.12)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[rgba(255,255,255,0.06)] bg-surface-800/40">
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Tên file</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Loại</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Dung lượng</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Trang</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Ngày tải</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Trạng thái</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[rgba(255,255,255,0.04)]">
            {loading
              ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
              : documents.map((doc) => (
                  <tr
                    key={doc.id}
                    className="hover:bg-white/[0.02] transition-colors group"
                  >
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <FileIcon type={doc.file_type} />
                        <span className="font-medium text-slate-200 truncate max-w-[200px]" title={doc.original_filename}>
                          {doc.original_filename}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className="px-2 py-0.5 text-xs font-mono uppercase text-slate-400 bg-surface-600 rounded">
                        {doc.file_type}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-slate-400">{formatFileSize(doc.file_size)}</td>
                    <td className="px-4 py-4 text-slate-400">{doc.page_count ?? '—'}</td>
                    <td className="px-4 py-4 text-slate-400 whitespace-nowrap">{formatDate(doc.created_at)}</td>
                    <td className="px-4 py-4"><StatusBadge status={doc.status} /></td>
                    <td className="px-4 py-4">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => onView(doc)}
                          className="p-2 text-slate-500 hover:text-brand-400 hover:bg-brand-500/10 rounded-lg transition-all"
                          title="Xem chi tiết"
                        >
                          <Eye size={16} />
                        </button>
                        {doc.status === 'extracted' && (
                          <button
                            onClick={() => onMindmap(doc)}
                            className="p-2 text-slate-500 hover:text-purple-400 hover:bg-purple-500/10 rounded-lg transition-all"
                            title="Sinh Mindmap & Flashcard"
                          >
                            <BrainCircuit size={16} />
                          </button>
                        )}
                        <button
                          onClick={() => onDelete(doc)}
                          className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all"
                          title="Xóa"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-500">
            Tổng <span className="font-medium text-slate-300">{total}</span> tài liệu
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="p-2 text-slate-400 hover:text-slate-200 border border-[rgba(255,255,255,0.08)] rounded-lg hover:border-[rgba(255,255,255,0.15)] transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="px-3 py-1 text-sm text-slate-300">
              Trang {page} / {totalPages}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="p-2 text-slate-400 hover:text-slate-200 border border-[rgba(255,255,255,0.08)] rounded-lg hover:border-[rgba(255,255,255,0.15)] transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
