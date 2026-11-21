'use client';

import React, { useState, useCallback, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {
  X, BrainCircuit, Sparkles, Loader2, AlertCircle,
  ChevronRight, RotateCcw, BookOpen,
  GitBranch, ListTree, Download,
} from 'lucide-react';
import { Document, MindmapResult, MindmapNode, MindmapStatus, ProcessingRun } from '@/lib/types';
import { flashcardsApi, mindmapApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { MindmapVisual } from './MindmapVisual';
import { FlashcardPractice } from './FlashcardPractice';
import { FlashcardQuiz } from './FlashcardQuiz';
import { MermaidMindmap } from './MermaidMindmap';

interface MindmapDialogProps {
  document: Document | null;
  open: boolean;
  onClose: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tree node component
// ─────────────────────────────────────────────────────────────────────────────

function buildTree(nodes: MindmapNode[]): Map<string | null, MindmapNode[]> {
  const map = new Map<string | null, MindmapNode[]>();
  for (const node of nodes) {
    const parentKey = node.parent_id ?? null;
    if (!map.has(parentKey)) map.set(parentKey, []);
    map.get(parentKey)!.push(node);
  }
  return map;
}

function TreeNode({
  node,
  tree,
  depth = 0,
}: {
  node: MindmapNode;
  tree: Map<string | null, MindmapNode[]>;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const children = tree.get(node.id) ?? [];
  const hasChildren = children.length > 0;

  const depthColors = [
    'text-brand-300 font-semibold text-sm',
    'text-purple-300 font-medium text-sm',
    'text-cyan-300 text-sm',
    'text-slate-300 text-sm',
    'text-slate-400 text-xs',
  ];
  const colorClass = depthColors[Math.min(depth, depthColors.length - 1)];

  return (
    <div className="select-none">
      <div
        className={cn(
          'flex items-start gap-1.5 py-1 px-2 rounded-lg hover:bg-white/5 cursor-pointer transition-colors',
          depth === 0 && 'mb-1',
        )}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => hasChildren && setExpanded((e) => !e)}
      >
        {hasChildren ? (
          <ChevronRight
            size={14}
            className={cn(
              'mt-0.5 shrink-0 text-slate-500 transition-transform',
              expanded && 'rotate-90',
            )}
          />
        ) : (
          <span className="w-3.5 shrink-0 mt-0.5 flex items-center justify-center">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-600 inline-block" />
          </span>
        )}
        <span className={colorClass}>{node.label}</span>
        {node.description && (
          <span className="text-[11px] text-slate-500 leading-snug ml-1 italic truncate max-w-[320px]">
            — {node.description}
          </span>
        )}
      </div>

      {expanded && hasChildren && (
        <div>
          {children.map((child) => (
            <TreeNode key={child.id} node={child} tree={tree} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Dialog
// ─────────────────────────────────────────────────────────────────────────────

type TabKey = 'mindmap' | 'flashcards';
type MindmapViewMode = 'visual' | 'tree' | 'mermaid';
type GenerationMode = 'engine' | 'ai';

export function MindmapDialog({ document, open, onClose }: MindmapDialogProps) {
  const [status, setStatus] = useState<MindmapStatus>('idle');
  const [result, setResult] = useState<MindmapResult | null>(null);
  const [run, setRun] = useState<ProcessingRun | null>(null);
  const [runHistory, setRunHistory] = useState<ProcessingRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>('mindmap');
  const [viewMode, setViewMode] = useState<MindmapViewMode>('visual');
  const [genMode, setGenMode] = useState<GenerationMode>('ai');
  const [practiceMode, setPracticeMode] = useState(false);
  const [ankiLoading, setAnkiLoading] = useState(false);
  const [ankiError, setAnkiError] = useState<string | null>(null);

  const generate = useCallback(async (selectedMode: GenerationMode = genMode) => {
    if (!document) return;
    setGenMode(selectedMode);
    setStatus('loading');
    setResult(null);
    setRun(null);
    setError(null);
    try {
      const started = await mindmapApi.start(document.id, selectedMode);
      setRun(started);
    } catch (err: unknown) {
      const e = err as { displayMessage?: string };
      setError(e.displayMessage ?? 'Có lỗi xảy ra khi sinh mindmap');
      setStatus('error');
    }
  }, [document, genMode]);

  const applyRun = useCallback((latest: ProcessingRun) => {
    setRun(latest);
    setGenMode(latest.mode);
    if (latest.status === 'completed' && latest.result) {
      setResult(latest.result);
      setError(null);
      setStatus('success');
    } else if (latest.status === 'completed') {
      setError('Tác vụ đã hoàn tất nhưng không đọc được dữ liệu kết quả.');
      setStatus('error');
    } else if (latest.status === 'failed') {
      setError(latest.error_message || 'Tác vụ xử lý thất bại. Bạn có thể thử lại.');
      setStatus('error');
    } else {
      setStatus('loading');
    }
  }, []);

  // Khôi phục tác vụ mới nhất khi mở lại hộp thoại, kể cả sau khi tải lại trang.
  useEffect(() => {
    if (!open || !document?.id) return;
    let cancelled = false;
    setStatus('loading');
    setError(null);
    setRun(null);
    setResult(null);
    setRunHistory([]);
    mindmapApi.getLatestRun(document.id)
      .then((latest) => {
        if (!cancelled) applyRun(latest);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        const apiError = cause as { response?: { status?: number }; displayMessage?: string };
        if (apiError.response?.status === 404) {
          setRun(null);
          setResult(null);
          setStatus('idle');
        } else {
          setError(apiError.displayMessage || 'Không thể tải trạng thái xử lý');
          setStatus('error');
        }
      });
    return () => { cancelled = true; };
  }, [open, document?.id, applyRun]);

  // Worker xử lý lâu ở backend; giao diện chỉ poll trạng thái tác vụ đang hoạt động.
  useEffect(() => {
    if (!open || !run || (run.status !== 'queued' && run.status !== 'processing')) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      mindmapApi.getRun(run.id)
        .then((latest) => { if (!cancelled) applyRun(latest); })
        .catch(() => { /* Lỗi mạng tạm thời: giữ trạng thái hiện tại và poll lần tiếp theo. */ });
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [open, run?.id, run?.status, applyRun]);

  useEffect(() => {
    if (!open || !document?.id || run?.status !== 'completed') return;
    mindmapApi.listRuns(document.id).then(setRunHistory).catch(() => setRunHistory([]));
  }, [open, document?.id, run?.status]);

  const handleRunHistoryChange = async (runId: string) => {
    if (!runId || runId === run?.id) return;
    setStatus('loading');
    try {
      setPracticeMode(false);
      applyRun(await mindmapApi.getRun(runId));
    } catch (cause: unknown) {
      const apiError = cause as { displayMessage?: string };
      setError(apiError.displayMessage || 'Không thể mở phiên bản mindmap này');
      setStatus('error');
    }
  };

  const handleOpenChange = (o: boolean) => {
    if (!o) {
      onClose();
      // Reset sau khi animation đóng xong
      setTimeout(() => {
        setStatus('idle');
        setRun(null);
        setRunHistory([]);
        setResult(null);
        setError(null);
        setTab('mindmap');
        setPracticeMode(false);
        setAnkiError(null);
      }, 300);
    }
  };

  const handleDownloadAnki = async () => {
    if (!document || ankiLoading) return;
    setAnkiLoading(true);
    setAnkiError(null);
    try {
      const blob = await flashcardsApi.exportAnki(document.id);
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement('a');
      link.href = url;
      link.download = `${document.original_filename.replace(/\.[^.]+$/, '')}_anki.apkg`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause: unknown) {
      const apiError = cause as { displayMessage?: string };
      setAnkiError(apiError.displayMessage || 'Không thể xuất bộ thẻ Anki');
    } finally {
      setAnkiLoading(false);
    }
  };

  // Build tree khi có result
  const tree = result ? buildTree(result.mindmap?.nodes ?? []) : null;
  const roots = tree?.get(null) ?? [];
  const nodeCount = result?.mindmap?.nodes?.length ?? 0;
  const cardCount = result?.flashcards?.length ?? 0;
  const completedRunHistory = runHistory.filter((item) => item.status === 'completed');
  const isLatestRun = !completedRunHistory.length || run?.id === completedRunHistory[0].id;

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 animate-fade-in" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-5xl h-[88vh] flex flex-col glass-card shadow-2xl animate-slide-up">

          {/* Header */}
          <div className="flex items-start justify-between p-6 border-b border-[rgba(90,108,240,0.15)]">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-brand-500/15 border border-brand-500/25">
                <BrainCircuit size={20} className="text-brand-400" />
              </div>
              <div>
                <Dialog.Title className="text-base font-semibold text-slate-100">
                  Mindmap AI
                </Dialog.Title>
                <p className="text-xs text-slate-500 mt-0.5 truncate max-w-[400px]">
                  {document?.original_filename}
                </p>
              </div>
            </div>
            <Dialog.Close asChild>
              <button className="p-2 text-slate-500 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-all">
                <X size={20} />
              </button>
            </Dialog.Close>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-hidden flex flex-col">

            {/* ── Idle: chưa sinh ── */}
            {status === 'idle' && (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center max-w-2xl mx-auto">
                <div className="w-16 h-16 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mb-4">
                  <Sparkles size={28} className="text-brand-400" />
                </div>
                <h3 className="text-xl font-semibold text-slate-100 mb-2">
                  Chọn phương pháp tạo Mindmap
                </h3>
                <p className="text-sm text-slate-400 mb-6">
                  Tùy theo nhu cầu ôn tập, bạn có thể chọn trích xuất theo bố cục mục lục gốc hoặc dùng mô hình AI tóm lược.
                </p>

                {/* Chế độ sinh lựa chọn */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full mb-8 text-left">
                  <div
                    onClick={() => setGenMode('engine')}
                    className={cn(
                      'p-4 rounded-xl border cursor-pointer transition-all',
                      genMode === 'engine'
                        ? 'border-brand-500 bg-brand-500/15 ring-2 ring-brand-500/30'
                        : 'border-[rgba(255,255,255,0.08)] bg-surface-800/40 hover:bg-surface-800/70'
                    )}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-brand-300">📑 Theo bố cục tài liệu</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">Nhanh · không tóm ý</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Bám theo Heading, bullet và định nghĩa có sẵn. Phù hợp tài liệu có mục lục rõ; văn xuôi hoặc thơ có thể thành sơ đồ phẳng và thẻ hỏi đáp đơn giản.
                    </p>
                  </div>

                  <div
                    onClick={() => setGenMode('ai')}
                    className={cn(
                      'p-4 rounded-xl border cursor-pointer transition-all',
                      genMode === 'ai'
                        ? 'border-purple-500 bg-purple-500/15 ring-2 ring-purple-500/30'
                        : 'border-[rgba(255,255,255,0.08)] bg-surface-800/40 hover:bg-surface-800/70'
                    )}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-purple-300">🤖 Phân tích nội dung bằng AI</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300">Khuyên dùng</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Gom các ý liên quan thành nhánh, giải thích từng ý và tạo câu hỏi-đáp án có ngữ cảnh. Cần cấu hình AI provider/model ở backend.
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => generate(genMode)}
                  className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-medium text-sm transition-all shadow-lg shadow-brand-500/25 hover:shadow-brand-500/40"
                >
                  <Sparkles size={16} />
                  {genMode === 'ai' ? 'Phân tích nội dung và tạo Mindmap bằng AI' : 'Tạo Mindmap theo bố cục tài liệu'}
                </button>
              </div>
            )}

            {/* ── Loading ── */}
            {status === 'loading' && (
              <div className="flex-1 flex flex-col items-center justify-center p-10 text-center">
                <Loader2 size={40} className="text-brand-400 animate-spin mb-5" />
                <h3 className="text-base font-semibold text-slate-200 mb-2">
                  {run?.status === 'queued' ? 'Đang chờ worker…' : 'Đang phân tích tài liệu…'}
                </h3>
                <p className="text-sm text-slate-500">
                  {run?.stage === 'ai_step1'
                    ? 'AI bước 1 đang chuẩn hóa kiến thức từ tài liệu.'
                    : run?.stage === 'ai_step2'
                      ? 'AI bước 2 đang tạo mindmap và flashcard.'
                      : run?.stage === 'retrying'
                        ? `Đang chờ thử lại lần ${Math.min((run.attempts || 0) + 1, 3)} sau lỗi tạm thời.`
                        : 'Tác vụ đang chạy ở máy chủ; bạn có thể đóng cửa sổ và quay lại sau.'}
                </p>
                {run && (
                  <div className="w-full max-w-sm mt-6">
                    <div className="mb-1.5 flex justify-between text-xs text-slate-500">
                      <span>{run.stage}</span><span>{run.progress}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-surface-700">
                      <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${run.progress}%` }} />
                    </div>
                  </div>
                )}
                <div className="mt-6 flex gap-1.5">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="w-2 h-2 rounded-full bg-brand-500 animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* ── Error ── */}
            {status === 'error' && (
              <div className="flex-1 flex flex-col items-center justify-center p-10 text-center">
                <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-4">
                  <AlertCircle size={26} className="text-red-400" />
                </div>
                <h3 className="text-base font-semibold text-slate-200 mb-2">Có lỗi xảy ra</h3>
                <p className="text-sm text-red-400 max-w-sm mb-6">{error}</p>
                <button
                  onClick={() => generate(genMode)}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-[rgba(255,255,255,0.1)] text-slate-300 hover:bg-white/5 text-sm transition-all"
                >
                  <RotateCcw size={14} />
                  Thử lại
                </button>
              </div>
            )}

            {/* ── Success ── */}
            {status === 'success' && result && (
              <>
                {/* Stats bar */}
                <div className="flex items-center gap-4 px-6 py-3 border-b border-[rgba(90,108,240,0.1)] bg-surface-800/30 text-xs text-slate-500">
                  <span className="flex items-center gap-1.5">
                    <BrainCircuit size={12} className="text-brand-400" />
                    <span className="text-slate-300 font-medium">{nodeCount}</span> nút mindmap
                  </span>
                  <span className="text-slate-700">·</span>
                  <span className="flex items-center gap-1.5">
                    <BookOpen size={12} className="text-purple-400" />
                    <span className="text-slate-300 font-medium">{cardCount}</span> flashcard
                  </span>
                  {result.model && (
                    <>
                      <span className="text-slate-700">·</span>
                      <span className="font-mono text-slate-600">{result.model}</span>
                    </>
                  )}
                  {completedRunHistory.length > 1 && (
                    <label className="flex items-center gap-2 text-xs text-slate-500">
                      <span>Phiên bản</span>
                      <select
                        value={run?.id ?? ''}
                        onChange={(event) => void handleRunHistoryChange(event.target.value)}
                        className="max-w-[210px] rounded-lg border border-[rgba(255,255,255,0.1)] bg-surface-800 px-2 py-1.5 text-xs text-slate-300"
                        aria-label="Chọn phiên bản mindmap"
                      >
                        {completedRunHistory.map((item) => (
                          <option key={item.id} value={item.id}>
                            {new Date(item.created_at).toLocaleString()} · {item.mode}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <div className="ml-auto flex items-center gap-2">
                    <button
                      onClick={() => generate(result.backend === 'structure_engine' ? 'ai' : 'engine')}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-brand-500/30 bg-brand-500/10 text-brand-300 hover:bg-brand-500/20 text-xs transition-all"
                      title={result.backend === 'structure_engine' ? 'Chuyển sang pipeline AI hai bước' : 'Chuyển sang bóc tách theo mục lục bài học'}
                    >
                      <Sparkles size={11} />
                      {result.backend === 'structure_engine' ? 'Phân tích sâu bằng AI' : 'Đổi sang theo bố cục'}
                    </button>
                    <button
                      onClick={() => generate(genMode)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-[rgba(255,255,255,0.08)] hover:bg-white/5 text-slate-500 hover:text-slate-300 transition-all text-xs"
                      title="Sinh lại"
                    >
                      <RotateCcw size={11} />
                      Sinh lại
                    </button>
                  </div>
                </div>

                {/* Tabs & View Switcher */}
                <div className="flex items-center justify-between border-b border-[rgba(90,108,240,0.1)] px-6">
                  <div className="flex">
                    {(['mindmap', 'flashcards'] as TabKey[]).map((t) => (
                      <button
                        key={t}
                        onClick={() => setTab(t)}
                        className={cn(
                          'px-4 py-3 text-sm font-medium border-b-2 transition-all -mb-px',
                          tab === t
                            ? 'border-brand-400 text-brand-300'
                            : 'border-transparent text-slate-500 hover:text-slate-300',
                        )}
                      >
                        {t === 'mindmap' ? `🧠 Sơ đồ Mindmap (${nodeCount})` : `🃏 Flashcard (${cardCount})`}
                      </button>
                    ))}
                  </div>

                  {tab === 'mindmap' && (
                    <div className="flex items-center gap-1 bg-surface-700/60 p-1 rounded-lg border border-[rgba(255,255,255,0.06)]">
                      <button
                        onClick={() => setViewMode('visual')}
                        className={cn(
                          'flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-all',
                          viewMode === 'visual'
                            ? 'bg-brand-500 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        )}
                        title="Xem sơ đồ đồ họa trực quan (có thể xuất ảnh)"
                      >
                        <GitBranch size={13} />
                        Sơ đồ đồ họa
                      </button>
                      <button
                        onClick={() => setViewMode('tree')}
                        className={cn(
                          'flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-all',
                          viewMode === 'tree'
                            ? 'bg-brand-500 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        )}
                        title="Xem dạng cây danh sách"
                      >
                        <ListTree size={13} />
                        Dạng cây
                      </button>
                      {result.mermaid && (
                        <button
                          onClick={() => setViewMode('mermaid')}
                          className={cn(
                            'flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-all',
                            viewMode === 'mermaid'
                              ? 'bg-brand-500 text-white shadow-sm'
                              : 'text-slate-400 hover:text-slate-200'
                          )}
                          title="Xem mã Mermaid và tải xuống"
                        >
                          <span className="font-mono">M</span>
                          Mermaid
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-4">
                  {tab === 'mindmap' && (
                    viewMode === 'visual' ? (
                      <MindmapVisual
                        nodes={result.mindmap?.nodes ?? []}
                        filename={document?.original_filename}
                      />
                    ) : viewMode === 'tree' ? (
                      <div className="rounded-xl border border-[rgba(90,108,240,0.12)] bg-surface-800/40 p-4">
                        {roots.length === 0 ? (
                          <p className="text-sm text-slate-500 p-4 text-center">
                            Không có dữ liệu mindmap
                          </p>
                        ) : (
                          roots.map((root) => (
                            <TreeNode key={root.id} node={root} tree={tree!} depth={0} />
                          ))
                        )}
                      </div>
                    ) : (
                      <MermaidMindmap
                        source={result.mermaid ?? ''}
                        filename={document?.original_filename}
                      />
                    )
                  )}

                  {tab === 'flashcards' && (
                    <>
                      <div className="mb-4 flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => {
                            setPracticeMode((current) => !current);
                            setAnkiError(null);
                          }}
                          disabled={!isLatestRun}
                          title={!isLatestRun ? 'Lịch ôn dùng bộ thẻ mới nhất của tài liệu' : undefined}
                          className="rounded-lg border border-brand-500/30 bg-brand-500/10 px-3 py-2 text-xs font-medium text-brand-300 hover:bg-brand-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {practiceMode ? 'Quay lại danh sách thẻ' : 'Luyện thẻ đến hạn'}
                        </button>
                        <button
                          onClick={handleDownloadAnki}
                          disabled={ankiLoading || result.flashcards.length === 0 || !isLatestRun}
                          title={!isLatestRun ? 'Anki xuất bộ thẻ mới nhất của tài liệu' : undefined}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-[rgba(255,255,255,0.1)] px-3 py-2 text-xs text-slate-300 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {ankiLoading ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                          {ankiLoading ? 'Đang tạo .apkg…' : 'Tải Anki .apkg'}
                        </button>
                        {ankiError && <span role="alert" className="text-xs text-rose-300">{ankiError}</span>}
                      </div>

                      {!isLatestRun && (
                        <p className="mb-4 text-xs text-slate-500">
                          Đây là snapshot cũ. Luyện tập và xuất Anki dùng bộ thẻ của lần xử lý mới nhất.
                        </p>
                      )}

                      {practiceMode && document ? (
                        <FlashcardPractice documentId={document.id} />
                      ) : result.flashcards.length === 0 ? (
                        <p className="py-6 text-center text-sm text-slate-500">Không có flashcard nào</p>
                      ) : (
                        <FlashcardQuiz cards={result.flashcards} nodes={result.mindmap?.nodes ?? []} />
                      )}
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
