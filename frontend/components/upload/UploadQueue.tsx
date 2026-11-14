'use client';

import React from 'react';
import { FileText, Presentation, File, CheckCircle2, XCircle, Loader2, X } from 'lucide-react';
import { cn, formatFileSize } from '@/lib/utils';
import { UploadItem } from '@/lib/types';

interface UploadQueueProps {
  items: UploadItem[];
  onRemove: (id: string) => void;
}

const FileIcon = ({ ext }: { ext: string }) => {
  const cls = 'w-8 h-8';
  if (ext === 'pdf') return <FileText className={cn(cls, 'text-red-400')} />;
  if (ext === 'docx') return <File className={cn(cls, 'text-blue-400')} />;
  if (ext === 'pptx') return <Presentation className={cn(cls, 'text-orange-400')} />;
  return <File className={cn(cls, 'text-slate-400')} />;
};

export function UploadQueue({ items, onRemove }: UploadQueueProps) {
  if (items.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-slate-400">Đang tải lên ({items.length} file)</h3>
      <div className="space-y-2">
        {items.map((item) => {
          const ext = item.file.name.split('.').pop()?.toLowerCase() ?? '';
          return (
            <div
              key={item.id}
              className="glass-card p-4 flex items-center gap-4 animate-fade-in"
            >
              {/* File icon */}
              <div className="flex-shrink-0">
                <FileIcon ext={ext} />
              </div>

              {/* Info + progress */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm font-medium text-slate-200 truncate pr-2">
                    {item.file.name}
                  </p>
                  <span className="text-xs text-slate-500 flex-shrink-0">
                    {formatFileSize(item.file.size)}
                  </span>
                </div>

                {/* Progress bar */}
                {(item.status === 'uploading' || item.status === 'pending') && (
                  <div className="h-1.5 bg-surface-600 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-brand-500 to-purple-500 rounded-full transition-all duration-300"
                      style={{ width: `${item.progress}%` }}
                    />
                  </div>
                )}

                {/* Status text */}
                <p className={cn('text-xs mt-1', {
                  'text-slate-500': item.status === 'pending',
                  'text-brand-400': item.status === 'uploading',
                  'text-emerald-400': item.status === 'success',
                  'text-red-400': item.status === 'error',
                })}>
                  {item.status === 'pending' && 'Đang chờ...'}
                  {item.status === 'uploading' && `Đang tải lên... ${item.progress}%`}
                  {item.status === 'success' && 'Tải lên thành công!'}
                  {item.status === 'error' && (item.error ?? 'Có lỗi xảy ra')}
                </p>
              </div>

              {/* Status icon / remove button */}
              <div className="flex-shrink-0">
                {item.status === 'uploading' && (
                  <Loader2 size={20} className="text-brand-400 animate-spin" />
                )}
                {item.status === 'success' && (
                  <CheckCircle2 size={20} className="text-emerald-400" />
                )}
                {item.status === 'error' && (
                  <button onClick={() => onRemove(item.id)} className="text-red-400 hover:text-red-300">
                    <XCircle size={20} />
                  </button>
                )}
                {item.status === 'pending' && (
                  <button onClick={() => onRemove(item.id)} className="text-slate-500 hover:text-slate-300 transition-colors">
                    <X size={16} />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
