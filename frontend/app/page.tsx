'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { BrainCircuit, CheckCircle2, FileText, Loader2, LogOut, Sparkles } from 'lucide-react';
import { DropZone } from '@/components/upload/DropZone';
import { AuthPromptDialog } from '@/components/auth/AuthPromptDialog';
import { GuestResultPanel } from '@/components/mindmap/GuestResultPanel';
import { useAuth } from '@/components/auth/AuthProvider';
import { documentsApi, mindmapApi } from '@/lib/api';
import { GuestMindmapResponse } from '@/lib/types';

type GenerationMode = 'engine' | 'ai';

export default function Home() {
  const { user, logout } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<GenerationMode>('ai');
  const [generated, setGenerated] = useState<GuestMindmapResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedDocumentId, setSavedDocumentId] = useState<string | null>(null);
  const [pendingSave, setPendingSave] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMessage, setAuthMessage] = useState('Đăng nhập hoặc đăng ký để lưu mindmap và tải các file kết quả.');

  const handleFilesSelected = useCallback((files: File[]) => {
    const selected = files[0] ?? null;
    setFile(selected);
    setGenerated(null);
    setSavedDocumentId(null);
    setError(null);
  }, []);

  const handleGenerate = async () => {
    if (!file || generating) return;
    setGenerating(true);
    setError(null);
    setGenerated(null);
    setSavedDocumentId(null);
    try {
      setGenerated(await mindmapApi.generateGuest(file, mode));
    } catch (cause: unknown) {
      const apiError = cause as { displayMessage?: string };
      setError(apiError.displayMessage || 'Không thể tạo mindmap từ tài liệu này.');
    } finally {
      setGenerating(false);
    }
  };

  const requireAuth = useCallback((message: string) => {
    setAuthMessage(message);
    setAuthOpen(true);
  }, []);

  const saveGenerated = useCallback(async (): Promise<string | null> => {
    if (!generated || !file) return null;
    if (!user) {
      setPendingSave(true);
      requireAuth('Đăng nhập hoặc đăng ký để lưu mindmap vào thư viện của bạn.');
      return null;
    }
    if (savedDocumentId) return savedDocumentId;
    if (saving) return null;

    setSaving(true);
    try {
      const document = await documentsApi.saveGenerated(file, generated.result);
      setSavedDocumentId(document.id);
      return document.id;
    } finally {
      setSaving(false);
    }
  }, [file, generated, requireAuth, savedDocumentId, saving, user]);

  useEffect(() => {
    if (!pendingSave || !user || !generated || !file || saving || savedDocumentId) return;
    setPendingSave(false);
    void saveGenerated().catch((cause: unknown) => {
      const apiError = cause as { displayMessage?: string };
      setError(apiError.displayMessage || 'Không thể lưu mindmap');
    });
  }, [file, generated, pendingSave, savedDocumentId, saveGenerated, saving, user]);

  const handleLogout = async () => {
    await logout();
  };

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-4 pb-16 pt-7 sm:px-6 lg:px-8">
      <header className="mb-12 flex flex-wrap items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-brand-500/25 bg-brand-500/15">
            <BrainCircuit size={22} className="text-brand-300" />
          </span>
          <span>
            <span className="block text-lg font-bold text-slate-100">DocMind AI</span>
            <span className="block text-[11px] text-slate-500">Tài liệu thành mindmap</span>
          </span>
        </Link>
        <nav className="flex items-center gap-2">
          {user ? (
            <>
              <span className="hidden max-w-48 truncate text-sm text-slate-400 sm:inline">{user.email}</span>
              <Link href="/documents" className="rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-300 hover:bg-white/5">
                Thư viện
              </Link>
              <button type="button" onClick={() => void handleLogout()} className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-slate-400 hover:bg-white/5 hover:text-slate-200">
                <LogOut size={15} /> Đăng xuất
              </button>
            </>
          ) : (
            <Link href="/login" className="rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-300 hover:bg-white/5">
              Đăng nhập
            </Link>
          )}
        </nav>
      </header>

      <section className="mb-9 text-center">
        <div className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300">
          <CheckCircle2 size={14} /> Tạo mindmap không cần tài khoản
        </div>
        <h1 className="mx-auto max-w-3xl text-3xl font-bold leading-tight text-slate-100 sm:text-4xl">
          Hiểu tài liệu nhanh hơn với <span className="bg-gradient-to-r from-brand-300 to-purple-300 bg-clip-text text-transparent">mindmap và flashcard</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-slate-400 sm:text-base">
          Tải PDF, Word hoặc PowerPoint để tạo sơ đồ và xem flashcard ngay. Chỉ cần đăng nhập khi muốn lưu kết quả hoặc tải file.
        </p>
      </section>

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.65fr)_minmax(260px,0.8fr)]">
        <div className="glass-card p-4 sm:p-6">
          <div className="mb-4 flex items-center gap-2">
            <FileText size={17} className="text-brand-300" />
            <h2 className="font-semibold text-slate-100">Chọn tài liệu để bắt đầu</h2>
          </div>
          <DropZone onFilesSelected={handleFilesSelected} disabled={generating} multiple={false} />

          {file && (
            <div className="mt-4 flex flex-col gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-200">{file.name}</p>
                <p className="mt-1 text-xs text-slate-500">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
              </div>
              <button
                type="button"
                onClick={() => void handleGenerate()}
                disabled={generating}
                className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-500 disabled:cursor-wait disabled:opacity-60"
              >
                {generating ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                {generating ? 'Đang tạo mindmap...' : 'Tạo mindmap'}
              </button>
            </div>
          )}

          <div className="mt-5">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Cách tạo</p>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setMode('engine')}
                className={`rounded-xl border p-3 text-left transition-colors ${mode === 'engine' ? 'border-brand-500/50 bg-brand-500/10' : 'border-white/5 bg-white/[0.02] hover:bg-white/[0.04]'}`}
              >
                <span className="block text-sm font-medium text-slate-200">Theo bố cục tài liệu</span>
                <span className="mt-1 block text-xs text-slate-500">Nhanh, phù hợp file có tiêu đề và gạch đầu dòng rõ ràng.</span>
              </button>
              <button
                type="button"
                onClick={() => setMode('ai')}
                className={`rounded-xl border p-3 text-left transition-colors ${mode === 'ai' ? 'border-purple-500/50 bg-purple-500/10' : 'border-white/5 bg-white/[0.02] hover:bg-white/[0.04]'}`}
              >
                <span className="block text-sm font-medium text-purple-200">Phân tích nội dung bằng AI · Khuyên dùng</span>
                <span className="mt-1 block text-xs text-slate-400">Nhóm ý theo chủ đề, giải thích nhánh và tạo câu hỏi-đáp án có ngữ cảnh. Cần AI provider/model đang hoạt động.</span>
              </button>
            </div>
          </div>

          {generating && (
            <p role="status" className="mt-4 rounded-lg border border-brand-500/20 bg-brand-500/5 px-3 py-2.5 text-xs leading-relaxed text-brand-200">
              Đang trích xuất nội dung và tạo kết quả. Chế độ AI có thể cần thêm thời gian.
            </p>
          )}
          {error && (
            <p role="alert" className="mt-4 rounded-lg border border-rose-500/20 bg-rose-500/5 px-3 py-2.5 text-sm text-rose-300">
              {error}
            </p>
          )}
        </div>

        <aside className="glass-card p-5 sm:p-6">
          <h2 className="font-semibold text-slate-100">Dùng thử trước, lưu sau</h2>
          <ol className="mt-4 space-y-4 text-sm text-slate-400">
            <li className="flex gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-500/15 text-xs text-brand-300">1</span><span>Tải lên một file PDF, DOCX hoặc PPTX.</span></li>
            <li className="flex gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-500/15 text-xs text-brand-300">2</span><span>Tạo và xem mindmap, lật flashcard ngay trên trang.</span></li>
            <li className="flex gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-500/15 text-xs text-brand-300">3</span><span>Đăng nhập khi muốn lưu vào thư viện hoặc tải kết quả.</span></li>
          </ol>
          <div className="mt-6 rounded-xl border border-white/5 bg-black/10 p-3 text-xs leading-relaxed text-slate-500">
            Khi dùng thử, file chỉ được xử lý tạm thời và không lưu vào thư viện. Chọn chế độ AI có thể gửi nội dung tới AI provider được cấu hình cho hệ thống.
          </div>
        </aside>
      </section>

      {generated && (
        <GuestResultPanel
          filename={generated.original_filename}
          result={generated.result}
          canExport={Boolean(user)}
          savedDocumentId={savedDocumentId}
          saving={saving}
          onSave={saveGenerated}
          onAuthRequired={requireAuth}
        />
      )}

      <AuthPromptDialog
        open={authOpen}
        onOpenChange={setAuthOpen}
        message={authMessage}
      />
    </main>
  );
}
