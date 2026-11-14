'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { BrainCircuit, RefreshCw } from 'lucide-react';
import { DropZone } from '@/components/upload/DropZone';
import { UploadQueue } from '@/components/upload/UploadQueue';
import { DocumentTable } from '@/components/documents/DocumentTable';
import { DocumentFiltersBar } from '@/components/documents/DocumentFilters';
import { DetailDialog } from '@/components/documents/DetailDialog';
import { DeleteDialog } from '@/components/documents/DeleteDialog';
import { MindmapDialog } from '@/components/mindmap/MindmapDialog';
import { documentsApi } from '@/lib/api';
import { Document, DocumentFilters, UploadItem } from '@/lib/types';
import { cn } from '@/lib/utils';

const MAX_CONCURRENT_UPLOADS = 3;
const POLL_INTERVAL_MS = 3_000;
const DEFAULT_FILTERS: DocumentFilters = { search: '', status: '', file_type: '', page: 1 };

export default function DocumentsPage() {
  // ── State ──────────────────────────────────────────────────────────────────
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [filters, setFilters] = useState<DocumentFilters>(DEFAULT_FILTERS);

  const [uploadQueue, setUploadQueue] = useState<UploadItem[]>([]);

  const [viewDoc, setViewDoc] = useState<Document | null>(null);
  const [deleteDoc, setDeleteDoc] = useState<Document | null>(null);
  const [mindmapDoc, setMindmapDoc] = useState<Document | null>(null);

  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Ref để tracking polling interval
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch list ─────────────────────────────────────────────────────────────
  const fetchDocuments = useCallback(async (f: DocumentFilters) => {
    try {
      setListLoading(true);
      setListError(null);
      const res = await documentsApi.list(f);
      setDocuments(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch {
      setListError('Không thể tải danh sách tài liệu');
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments(filters);
  }, [filters, fetchDocuments]);

  // ── Polling cho documents đang extracting ──────────────────────────────────
  useEffect(() => {
    const needsPoll = documents.some(
      (d) => d.status === 'uploaded' || d.status === 'extracting',
    );

    if (needsPoll && !pollRef.current) {
      pollRef.current = setInterval(() => {
        fetchDocuments(filters);
      }, POLL_INTERVAL_MS);
    } else if (!needsPoll && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [documents, filters, fetchDocuments]);

  // ── Show toast helper ──────────────────────────────────────────────────────
  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  }, []);

  // ── Upload logic ───────────────────────────────────────────────────────────
  const handleFilesSelected = useCallback((files: File[]) => {
    const newItems: UploadItem[] = files.map((file) => ({
      id: crypto.randomUUID(),
      file,
      status: 'pending',
      progress: 0,
    }));
    setUploadQueue((prev) => [...prev, ...newItems]);
    processUploads(newItems);
  }, []);

  const processUploads = useCallback((items: UploadItem[]) => {
    // Tối đa MAX_CONCURRENT_UPLOADS file cùng lúc
    const batches: UploadItem[][] = [];
    for (let i = 0; i < items.length; i += MAX_CONCURRENT_UPLOADS) {
      batches.push(items.slice(i, i + MAX_CONCURRENT_UPLOADS));
    }

    const runBatch = async (batch: UploadItem[]) => {
      await Promise.all(
        batch.map((item) => uploadSingle(item)),
      );
    };

    const runAll = async () => {
      for (const batch of batches) {
        await runBatch(batch);
      }
      // Refresh list after all done
      setTimeout(() => fetchDocuments(filters), 500);
    };

    runAll();
  }, [filters, fetchDocuments]);

  const uploadSingle = async (item: UploadItem) => {
    setUploadQueue((prev) =>
      prev.map((i) => i.id === item.id ? { ...i, status: 'uploading' } : i),
    );

    try {
      await documentsApi.upload(item.file, undefined, (percent) => {
        setUploadQueue((prev) =>
          prev.map((i) => i.id === item.id ? { ...i, progress: percent } : i),
        );
      });

      setUploadQueue((prev) =>
        prev.map((i) => i.id === item.id ? { ...i, status: 'success', progress: 100 } : i),
      );
      showToast(`Đã tải lên "${item.file.name}" thành công`, 'success');

      // Auto-remove success items after 3s
      setTimeout(() => {
        setUploadQueue((prev) => prev.filter((i) => i.id !== item.id));
      }, 3000);
    } catch (err: unknown) {
      const e = err as { displayMessage?: string };
      const errorMsg = e.displayMessage || 'Có lỗi xảy ra';
      setUploadQueue((prev) =>
        prev.map((i) => i.id === item.id ? { ...i, status: 'error', error: errorMsg } : i),
      );
      showToast(`Lỗi tải lên "${item.file.name}": ${errorMsg}`, 'error');
    }
  };

  const handleRemoveUpload = useCallback((id: string) => {
    setUploadQueue((prev) => prev.filter((i) => i.id !== id));
  }, []);

  return (
    <div className="min-h-screen pb-20 pt-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <BrainCircuit size={28} className="text-brand-400" />
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-brand-300 to-purple-300">
              DocMind AI
            </h1>
          </div>
          <p className="text-sm text-slate-400">
            Chuyển đổi tài liệu của bạn thành Mindmap và Flashcard thông minh.
          </p>
        </div>
      </header>

      {/* Upload Section */}
      <section className="mb-10 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <DropZone onFilesSelected={handleFilesSelected} />
        </div>
        <div className="lg:col-span-1">
          <div className="glass-card h-full min-h-[200px] p-4 overflow-y-auto">
            {uploadQueue.length > 0 ? (
              <UploadQueue items={uploadQueue} onRemove={handleRemoveUpload} />
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center opacity-50">
                <RefreshCw size={32} className="text-slate-500 mb-3" />
                <p className="text-sm text-slate-400">Chưa có file nào đang tải lên</p>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Document List Section */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-slate-200">Tài liệu của bạn</h2>
          <DocumentFiltersBar
            filters={filters}
            onChange={(f) => setFilters((prev) => ({ ...prev, ...f }))}
            onReset={() => setFilters(DEFAULT_FILTERS)}
          />
        </div>

        {listError && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
            {listError}
          </div>
        )}

        <DocumentTable
          documents={documents}
          total={total}
          page={filters.page}
          totalPages={totalPages}
          loading={listLoading}
          onPageChange={(p) => setFilters((prev) => ({ ...prev, page: p }))}
          onView={setViewDoc}
          onDelete={setDeleteDoc}
          onMindmap={setMindmapDoc}
        />
      </section>

      {/* Dialogs */}
      <DetailDialog
        document={viewDoc}
        open={!!viewDoc}
        onClose={() => setViewDoc(null)}
      />
      <DeleteDialog
        document={deleteDoc}
        open={!!deleteDoc}
        onClose={() => setDeleteDoc(null)}
        onDeleted={() => {
          showToast('Xóa tài liệu thành công', 'success');
          fetchDocuments(filters);
        }}
      />
      <MindmapDialog
        document={mindmapDoc}
        open={!!mindmapDoc}
        onClose={() => setMindmapDoc(null)}
      />

      {/* Toast */}
      {toast && (
        <div className={cn(
          'fixed bottom-6 right-6 p-4 rounded-xl shadow-2xl animate-slide-up z-50 border backdrop-blur-md',
          toast.type === 'success' 
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
            : 'bg-red-500/10 border-red-500/20 text-red-400'
        )}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
