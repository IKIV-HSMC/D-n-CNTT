'use client';

import React, { useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, FileText, Calendar, HardDrive, BookOpen, Layers, Download } from 'lucide-react';
import { Document, DocumentDetail } from '@/lib/types';
import { documentsApi } from '@/lib/api';
import { StatusBadge } from './StatusBadge';
import { formatFileSize, formatDate } from '@/lib/utils';

interface DetailDialogProps {
  document: Document | null;
  open: boolean;
  onClose: () => void;
}

const FILE_TYPE_LABELS: Record<string, string> = { pdf: 'PDF', docx: 'Word', pptx: 'PowerPoint' };

export function DetailDialog({ document, open, onClose }: DetailDialogProps) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && document) {
      setLoading(true);
      documentsApi
        .getById(document.id)
        .then(setDetail)
        .finally(() => setLoading(false));
    } else {
      setDetail(null);
    }
  }, [open, document]);

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 animate-fade-in" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-2xl max-h-[90vh] flex flex-col glass-card shadow-2xl animate-slide-up">
          {/* Header */}
          <div className="flex items-start justify-between p-6 border-b border-[rgba(90,108,240,0.15)]">
            <div className="flex-1 min-w-0 pr-4">
              <Dialog.Title className="text-lg font-semibold text-slate-100 truncate">
                {document?.original_filename}
              </Dialog.Title>
              <div className="mt-2 flex items-center gap-3">
                {document && <StatusBadge status={document.status} />}
                {document?.status === 'extracted' && (
                  <a
                    href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/documents/${document.id}/json`}
                    target="_blank"
                    rel="noopener noreferrer"
                    download
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 border border-brand-500/30 transition-all cursor-pointer"
                  >
                    <Download size={13} />
                    Tải file JSON
                  </a>
                )}
              </div>
            </div>
            <Dialog.Close asChild>
              <button className="p-2 text-slate-500 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-all">
                <X size={20} />
              </button>
            </Dialog.Close>
          </div>

          {/* Metadata */}
          {document && (
            <div className="px-6 py-4 grid grid-cols-2 gap-3 border-b border-[rgba(90,108,240,0.1)]">
              <InfoRow icon={<HardDrive size={14} />} label="Dung lượng" value={formatFileSize(document.file_size)} />
              <InfoRow icon={<FileText size={14} />} label="Định dạng" value={FILE_TYPE_LABELS[document.file_type] ?? document.file_type.toUpperCase()} />
              <InfoRow icon={<Calendar size={14} />} label="Ngày tải" value={formatDate(document.created_at)} />
              {detail?.page_count != null && (
                <InfoRow icon={<Layers size={14} />} label="Số trang/slide" value={String(detail.page_count)} />
              )}
            </div>
          )}

          {/* Preview text */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {loading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className={`h-4 rounded shimmer ${i === 4 ? 'w-2/3' : 'w-full'}`} />
                ))}
              </div>
            ) : detail?.extracted_text_preview ? (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <BookOpen size={14} className="text-brand-400" />
                  <span className="text-xs font-medium text-slate-400 uppercase tracking-wide">Xem trước nội dung (500 ký tự đầu)</span>
                </div>
                <div className="p-4 rounded-xl bg-surface-800/50 border border-[rgba(255,255,255,0.05)]">
                  <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                    {detail.extracted_text_preview}
                  </p>
                </div>
              </div>
            ) : document?.status === 'failed' ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <p className="text-sm text-red-400">{document.error_message ?? 'Trích xuất thất bại'}</p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <p className="text-sm text-slate-500">Chưa có nội dung được trích xuất</p>
              </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function InfoRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-slate-500">{icon}</span>
      <span className="text-xs text-slate-500">{label}:</span>
      <span className="text-xs font-medium text-slate-200">{value}</span>
    </div>
  );
}
