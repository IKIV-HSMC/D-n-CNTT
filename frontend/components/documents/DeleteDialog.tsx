'use client';

import React, { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, Trash2, X, Loader2 } from 'lucide-react';
import { Document } from '@/lib/types';
import { documentsApi } from '@/lib/api';

interface DeleteDialogProps {
  document: Document | null;
  open: boolean;
  onClose: () => void;
  onDeleted: (id: string) => void;
}

export function DeleteDialog({ document, open, onClose, onDeleted }: DeleteDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async () => {
    if (!document) return;
    setLoading(true);
    setError(null);
    try {
      await documentsApi.delete(document.id);
      onDeleted(document.id);
      onClose();
    } catch (err: unknown) {
      const e = err as { displayMessage?: string };
      setError(e.displayMessage ?? 'Không thể xóa tài liệu');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && !loading && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 animate-fade-in" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md glass-card shadow-2xl p-6 animate-slide-up">
          <div className="flex items-start justify-between mb-5">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-red-500/10 border border-red-500/20">
                <AlertTriangle size={20} className="text-red-400" />
              </div>
              <Dialog.Title className="text-base font-semibold text-slate-100">Xóa tài liệu</Dialog.Title>
            </div>
            <Dialog.Close asChild disabled={loading}>
              <button className="p-1.5 text-slate-500 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-all">
                <X size={18} />
              </button>
            </Dialog.Close>
          </div>

          <Dialog.Description className="text-sm text-slate-400 mb-6">
            Bạn có chắc muốn xóa{' '}
            <span className="font-medium text-slate-200">&ldquo;{document?.original_filename}&rdquo;</span>
            ? Hành động này không thể hoàn tác và sẽ xóa file vật lý khỏi server.
          </Dialog.Description>

          {error && (
            <p className="mb-4 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex gap-3 justify-end">
            <Dialog.Close asChild disabled={loading}>
              <button className="px-4 py-2 text-sm text-slate-300 border border-[rgba(255,255,255,0.1)] rounded-lg hover:border-[rgba(255,255,255,0.2)] hover:text-slate-100 transition-all disabled:opacity-50">
                Hủy
              </button>
            </Dialog.Close>
            <button
              onClick={handleDelete}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-500 rounded-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
              {loading ? 'Đang xóa...' : 'Xóa tài liệu'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
