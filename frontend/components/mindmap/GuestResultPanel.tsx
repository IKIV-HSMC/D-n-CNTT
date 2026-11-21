'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { BookOpen, CheckCircle2, Download, GitBranch, Loader2, Save, Sparkles } from 'lucide-react';
import { MindmapResult } from '@/lib/types';
import { flashcardsApi } from '@/lib/api';
import { MindmapVisual } from '@/components/mindmap/MindmapVisual';
import { MermaidMindmap } from '@/components/mindmap/MermaidMindmap';
import { FlashcardQuiz } from '@/components/mindmap/FlashcardQuiz';

interface GuestResultPanelProps {
  filename: string;
  result: MindmapResult;
  canExport: boolean;
  savedDocumentId: string | null;
  saving: boolean;
  onSave: () => Promise<string | null>;
  onAuthRequired: (message: string) => void;
}

export function GuestResultPanel({
  filename,
  result,
  canExport,
  savedDocumentId,
  saving,
  onSave,
  onAuthRequired,
}: GuestResultPanelProps) {
  const [tab, setTab] = useState<'mindmap' | 'flashcards'>('mindmap');
  const [view, setView] = useState<'visual' | 'mermaid'>('visual');
  const [ankiLoading, setAnkiLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const downloadAnki = async () => {
    if (!canExport) {
      onAuthRequired('Đăng nhập hoặc đăng ký để tải bộ flashcard Anki.');
      return;
    }
    setError(null);
    setAnkiLoading(true);
    try {
      const documentId = savedDocumentId ?? await onSave();
      if (!documentId) return;
      const blob = await flashcardsApi.exportAnki(documentId);
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement('a');
      link.href = url;
      link.download = `${filename.replace(/\.[^.]+$/, '')}_anki.apkg`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause: unknown) {
      const apiError = cause as { displayMessage?: string };
      setError(apiError.displayMessage || 'Không thể tải bộ Anki');
    } finally {
      setAnkiLoading(false);
    }
  };

  const save = async () => {
    setError(null);
    try {
      await onSave();
    } catch (cause: unknown) {
      const apiError = cause as { displayMessage?: string };
      setError(apiError.displayMessage || 'Không thể lưu mindmap');
    }
  };

  const nodeCount = result.mindmap?.nodes?.length ?? 0;
  const cardCount = result.flashcards?.length ?? 0;

  return (
    <section className="mt-8 overflow-hidden rounded-2xl border border-brand-500/20 bg-surface-800/45 shadow-xl">
      <header className="flex flex-col gap-4 border-b border-white/5 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-brand-300">
            <Sparkles size={16} />
            <span className="text-xs font-semibold uppercase tracking-wider">Kết quả mindmap</span>
          </div>
          <h2 className="mt-1 truncate text-lg font-semibold text-slate-100">{filename}</h2>
          <p className="mt-1 text-xs text-slate-500">{nodeCount} nhánh · {cardCount} flashcard{result.model ? ` · ${result.model}` : ''}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void save()}
            disabled={saving || Boolean(savedDocumentId)}
            className="inline-flex items-center gap-2 rounded-lg border border-brand-500/30 bg-brand-500/15 px-3 py-2 text-sm font-medium text-brand-200 hover:bg-brand-500/25 disabled:cursor-default disabled:opacity-70"
          >
            {saving ? <Loader2 size={15} className="animate-spin" /> : savedDocumentId ? <CheckCircle2 size={15} /> : <Save size={15} />}
            {saving ? 'Đang lưu...' : savedDocumentId ? 'Đã lưu vào thư viện' : 'Lưu vào thư viện'}
          </button>
          {savedDocumentId && (
            <Link href="/documents" className="rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-300 hover:bg-white/5">
              Mở thư viện
            </Link>
          )}
        </div>
      </header>

      <div className="flex items-center gap-1 border-b border-white/5 px-4">
        <button
          type="button"
          onClick={() => setTab('mindmap')}
          className={`border-b-2 px-4 py-3 text-sm ${tab === 'mindmap' ? 'border-brand-400 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
        >
          Mindmap
        </button>
        <button
          type="button"
          onClick={() => setTab('flashcards')}
          className={`border-b-2 px-4 py-3 text-sm ${tab === 'flashcards' ? 'border-brand-400 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
        >
          Flashcard ({cardCount})
        </button>
      </div>

      {tab === 'mindmap' ? (
        <div className="p-4 sm:p-5">
          <div className="mb-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setView('visual')}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs ${view === 'visual' ? 'bg-brand-500 text-white' : 'bg-white/5 text-slate-400 hover:text-slate-200'}`}
            >
              <GitBranch size={14} /> Sơ đồ
            </button>
            {result.mermaid && (
              <button
                type="button"
                onClick={() => setView('mermaid')}
                className={`rounded-lg px-3 py-2 text-xs ${view === 'mermaid' ? 'bg-brand-500 text-white' : 'bg-white/5 text-slate-400 hover:text-slate-200'}`}
              >
                Mermaid
              </button>
            )}
          </div>
          <div className="h-[560px] min-h-[360px]">
            {view === 'mermaid' && result.mermaid ? (
              <MermaidMindmap
                source={result.mermaid}
                filename={filename}
                canExport={canExport}
                onExportBlocked={() => onAuthRequired('Đăng nhập hoặc đăng ký để tải sơ đồ mindmap.')}
              />
            ) : (
              <MindmapVisual
                nodes={result.mindmap?.nodes ?? []}
                filename={filename}
                canExport={canExport}
                onExportBlocked={() => onAuthRequired('Đăng nhập hoặc đăng ký để tải sơ đồ mindmap.')}
              />
            )}
          </div>
        </div>
      ) : (
        <div className="p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-sm text-slate-400">
              <BookOpen size={15} /> Trả lời câu hỏi rồi lật thẻ để kiểm tra.
            </p>
            <button
              type="button"
              onClick={() => void downloadAnki()}
              disabled={ankiLoading || cardCount === 0}
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
              title={!canExport ? 'Đăng nhập để tải Anki' : !savedDocumentId ? 'Lưu kết quả trước khi tải Anki' : undefined}
            >
              {ankiLoading ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
              {ankiLoading ? 'Đang tạo file...' : 'Tải Anki .apkg'}
            </button>
          </div>
          {error && <p role="alert" className="mb-4 text-sm text-rose-300">{error}</p>}
          <FlashcardQuiz cards={result.flashcards} nodes={result.mindmap?.nodes ?? []} />
        </div>
      )}

      {!canExport && (
        <p className="border-t border-white/5 px-5 py-3 text-xs text-slate-500">
          Bạn có thể xem mindmap miễn phí. Đăng nhập hoặc đăng ký khi muốn lưu kết quả hay tải file.
        </p>
      )}
      {canExport && !savedDocumentId && (
        <p className="border-t border-white/5 px-5 py-3 text-xs text-slate-500">
          Lưu mindmap vào thư viện để dùng lịch ôn tập và tải bộ flashcard Anki.
        </p>
      )}
    </section>
  );
}
