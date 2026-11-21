'use client';

import React, { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { BrainCircuit, Check, LogOut, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react';
import { DropZone } from '@/components/upload/DropZone';
import { UploadQueue } from '@/components/upload/UploadQueue';
import { DocumentTable } from '@/components/documents/DocumentTable';
import { DocumentFiltersBar } from '@/components/documents/DocumentFilters';
import { DetailDialog } from '@/components/documents/DetailDialog';
import { DeleteDialog } from '@/components/documents/DeleteDialog';
import { MindmapDialog } from '@/components/mindmap/MindmapDialog';
import { documentsApi, subjectsApi } from '@/lib/api';
import { Document, DocumentFilters, Subject, UploadItem } from '@/lib/types';
import { cn } from '@/lib/utils';
import { useAuth } from '@/components/auth/AuthProvider';

const MAX_CONCURRENT_UPLOADS = 3;
const POLL_INTERVAL_MS = 3_000;
const DEFAULT_FILTERS: DocumentFilters = { search: '', status: '', file_type: '', subject_id: '', page: 1 };

export default function DocumentsPage() {
  const router = useRouter();
  const { user, loading: authLoading, logout } = useAuth();

  // ── State ──────────────────────────────────────────────────────────────────
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [filters, setFilters] = useState<DocumentFilters>(DEFAULT_FILTERS);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState('');
  const [newSubjectName, setNewSubjectName] = useState('');
  const [editingSubjectId, setEditingSubjectId] = useState<string | null>(null);
  const [editingSubjectName, setEditingSubjectName] = useState('');

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
    if (authLoading) return;
    if (!user) {
      setDocuments([]);
      setListLoading(false);
      router.replace('/login');
      return;
    }
    fetchDocuments(filters);
  }, [filters, fetchDocuments, authLoading, user, router]);

  useEffect(() => {
    if (authLoading || !user) return;
    subjectsApi.list().then(setSubjects).catch(() => {
      setListError('Không thể tải danh sách môn học');
    });
  }, [authLoading, user]);

  // ── Polling cho documents đang extracting ──────────────────────────────────
  useEffect(() => {
    const needsPoll = Boolean(user) && documents.some(
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
  }, [documents, filters, fetchDocuments, user]);

  // ── Show toast helper ──────────────────────────────────────────────────────
  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  }, []);

  const handleCreateSubject = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = newSubjectName.trim();
    if (!name) return;
    try {
      const subject = await subjectsApi.create(name);
      setSubjects((previous) => [...previous, subject].sort((a, b) => a.name.localeCompare(b.name)));
      setSelectedSubjectId(subject.id);
      setNewSubjectName('');
      showToast(`Đã thêm môn học "${subject.name}"`, 'success');
    } catch (cause: unknown) {
      const err = cause as { displayMessage?: string };
      showToast(err.displayMessage || 'Không thể thêm môn học', 'error');
    }
  };

  const handleRenameSubject = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editingSubjectId || !editingSubjectName.trim()) return;
    try {
      const subject = await subjectsApi.rename(editingSubjectId, editingSubjectName.trim());
      setSubjects((previous) => previous.map((item) => item.id === subject.id ? subject : item).sort((a, b) => a.name.localeCompare(b.name)));
      setEditingSubjectId(null);
      setEditingSubjectName('');
      showToast(`Đã đổi tên môn học thành "${subject.name}"`, 'success');
    } catch (cause: unknown) {
      const err = cause as { displayMessage?: string };
      showToast(err.displayMessage || 'Không thể đổi tên môn học', 'error');
    }
  };

  const handleDeleteSubject = async (subject: Subject) => {
    if (!window.confirm(`Xóa môn học "${subject.name}"? Tài liệu sẽ được giữ lại và bỏ phân loại.`)) return;
    try {
      await subjectsApi.delete(subject.id);
      setSubjects((previous) => previous.filter((item) => item.id !== subject.id));
      if (selectedSubjectId === subject.id) setSelectedSubjectId('');
      if (filters.subject_id === subject.id) setFilters((previous) => ({ ...previous, subject_id: '', page: 1 }));
      showToast(`Đã xóa môn học "${subject.name}"`, 'success');
    } catch (cause: unknown) {
      const err = cause as { displayMessage?: string };
      showToast(err.displayMessage || 'Không thể xóa môn học', 'error');
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      router.replace('/');
    }
  };

  // ── Upload logic ───────────────────────────────────────────────────────────
  const uploadSingle = useCallback(async (item: UploadItem) => {
    setUploadQueue((prev) =>
      prev.map((i) => i.id === item.id ? { ...i, status: 'uploading' } : i),
    );

    try {
      await documentsApi.upload(item.file, selectedSubjectId || undefined, (percent) => {
        setUploadQueue((prev) =>
          prev.map((i) => i.id === item.id ? { ...i, progress: percent } : i),
        );
      });

      setUploadQueue((prev) =>
        prev.map((i) => i.id === item.id ? { ...i, status: 'success', progress: 100 } : i),
      );
      showToast(`Đã tải lên "${item.file.name}" thành công`, 'success');

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
  }, [selectedSubjectId, showToast]);

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
  }, [filters, fetchDocuments, uploadSingle]);

  const handleFilesSelected = useCallback((files: File[]) => {
    const newItems: UploadItem[] = files.map((file) => ({
      id: crypto.randomUUID(),
      file,
      status: 'pending',
      progress: 0,
    }));
    setUploadQueue((prev) => [...prev, ...newItems]);
    processUploads(newItems);
  }, [processUploads]);

  const handleRemoveUpload = useCallback((id: string) => {
    setUploadQueue((prev) => prev.filter((i) => i.id !== id));
  }, []);

  if (authLoading || !user) {
    return <div className="min-h-screen flex items-center justify-center text-slate-400">Đang kiểm tra phiên đăng nhập...</div>;
  }

  return (
    <div className="min-h-screen pb-20 pt-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <Link
          href="/"
          aria-label="Quay về trang chủ DocMind AI"
          className="group block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
        >
          <div className="flex items-center gap-2 mb-1">
            <BrainCircuit size={28} className="text-brand-400 transition-transform group-hover:scale-105" />
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-brand-300 to-purple-300">
              DocMind AI
            </h1>
          </div>
          <p className="text-sm text-slate-400">
            Chuyển đổi tài liệu của bạn thành Mindmap và Flashcard thông minh.
          </p>
        </Link>
        <div className="flex items-center gap-3">
          <span className="hidden sm:block text-sm text-slate-400">{user.email}</span>
          <button
            type="button"
            onClick={handleLogout}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 border border-[rgba(255,255,255,0.1)] hover:bg-white/5"
          >
            <LogOut size={15} /> Đăng xuất
          </button>
        </div>
      </header>

      <section className="glass-card p-4 mb-6 flex flex-col md:flex-row md:items-end gap-4">
        <label className="flex-1 text-sm text-slate-300">
          Môn học cho tài liệu tải lên
          <select
            value={selectedSubjectId}
            onChange={(event) => setSelectedSubjectId(event.target.value)}
            className="mt-1 w-full px-3 py-2 bg-surface-700 border border-[rgba(90,108,240,0.2)] rounded-lg text-slate-200"
          >
            <option value="">Không phân loại</option>
            {subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}
          </select>
        </label>
        <form onSubmit={handleCreateSubject} className="flex flex-1 items-end gap-2">
          <label className="flex-1 text-sm text-slate-300">
            Thêm môn học
            <input
              value={newSubjectName}
              onChange={(event) => setNewSubjectName(event.target.value)}
              maxLength={100}
              placeholder="Ví dụ: Công nghệ phần mềm"
              className="mt-1 w-full px-3 py-2 bg-surface-700 border border-[rgba(90,108,240,0.2)] rounded-lg text-slate-200 placeholder:text-slate-500"
            />
          </label>
          <button type="submit" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-sm text-white">
            <Plus size={16} /> Thêm
          </button>
        </form>
        {subjects.length > 0 && (
          <div className="basis-full border-t border-white/5 pt-3">
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-2">Môn học của bạn</p>
            <div className="flex flex-wrap gap-2">
              {subjects.map((subject) => (
                <div key={subject.id} className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-surface-700 border border-white/5 text-sm text-slate-300">
                  {editingSubjectId === subject.id ? (
                    <form onSubmit={handleRenameSubject} className="inline-flex items-center gap-1">
                      <input
                        autoFocus
                        value={editingSubjectName}
                        onChange={(event) => setEditingSubjectName(event.target.value)}
                        maxLength={100}
                        className="w-44 bg-surface-800 px-2 py-1 rounded text-slate-100 outline-none"
                        aria-label="Tên môn học mới"
                      />
                      <button type="submit" title="Lưu tên môn học" className="text-emerald-400 hover:text-emerald-300"><Check size={15} /></button>
                      <button type="button" title="Hủy đổi tên" onClick={() => setEditingSubjectId(null)} className="text-slate-500 hover:text-slate-300"><X size={15} /></button>
                    </form>
                  ) : (
                    <>
                      <span>{subject.name}</span>
                      <button
                        type="button"
                        title={`Đổi tên ${subject.name}`}
                        onClick={() => { setEditingSubjectId(subject.id); setEditingSubjectName(subject.name); }}
                        className="text-slate-500 hover:text-brand-300"
                      ><Pencil size={14} /></button>
                      <button
                        type="button"
                        title={`Xóa ${subject.name}`}
                        onClick={() => handleDeleteSubject(subject)}
                        className="text-slate-500 hover:text-red-300"
                      ><Trash2 size={14} /></button>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

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
            subjects={subjects}
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
