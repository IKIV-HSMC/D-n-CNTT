'use client';

import React, { useState, useCallback } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {
  X, BrainCircuit, Sparkles, Loader2, AlertCircle,
  ChevronRight, RotateCcw, BookOpen, FlipHorizontal2,
  GitBranch, ListTree,
} from 'lucide-react';
import { Document, MindmapResult, MindmapNode, Flashcard, MindmapStatus } from '@/lib/types';
import { mindmapApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { MindmapVisual } from './MindmapVisual';

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
// Flashcard component (flip effect)
// ─────────────────────────────────────────────────────────────────────────────

function FlashcardItem({ card, index }: { card: Flashcard; index: number }) {
  const [flipped, setFlipped] = useState(false);
  return (
    <div
      className="cursor-pointer"
      onClick={() => setFlipped((f) => !f)}
      title="Click để lật thẻ"
    >
      <div className="relative p-4 rounded-xl border border-[rgba(90,108,240,0.15)] bg-surface-800/60 hover:bg-surface-700/60 transition-colors min-h-[90px] flex flex-col justify-between">
        <span className="text-[10px] font-mono text-slate-600 uppercase tracking-wider mb-2">
          {flipped ? 'Đáp án' : `Thẻ #${index + 1}`}
        </span>
        <p className={cn(
          'text-sm leading-relaxed',
          flipped ? 'text-emerald-300' : 'text-slate-200',
        )}>
          {flipped ? card.back : card.front}
        </p>
        <div className="flex items-center gap-1 mt-2 text-[10px] text-slate-600">
          <FlipHorizontal2 size={10} />
          <span>{flipped ? 'Click để xem câu hỏi' : 'Click để xem đáp án'}</span>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Dialog
// ─────────────────────────────────────────────────────────────────────────────

type TabKey = 'mindmap' | 'flashcards';
type MindmapViewMode = 'visual' | 'tree';
type GenerationMode = 'engine' | 'ai';

export function MindmapDialog({ document, open, onClose }: MindmapDialogProps) {
  const [status, setStatus] = useState<MindmapStatus>('idle');
  const [result, setResult] = useState<MindmapResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>('mindmap');
  const [viewMode, setViewMode] = useState<MindmapViewMode>('visual');
  const [genMode, setGenMode] = useState<GenerationMode>('engine');

  const generate = useCallback(async (selectedMode: GenerationMode = genMode) => {
    if (!document) return;
    setStatus('loading');
    setError(null);
    try {
      const data = await mindmapApi.generate(document.id, selectedMode);
      setResult(data);
      setStatus('success');
    } catch (err: unknown) {
      const e = err as { displayMessage?: string };
      setError(e.displayMessage ?? 'Có lỗi xảy ra khi sinh mindmap');
      setStatus('error');
    }
  }, [document, genMode]);

  const handleOpenChange = (o: boolean) => {
    if (!o) {
      onClose();
      // Reset sau khi animation đóng xong
      setTimeout(() => {
        setStatus('idle');
        setResult(null);
        setError(null);
        setTab('mindmap');
      }, 300);
    }
  };

  // Build tree khi có result
  const tree = result ? buildTree(result.mindmap?.nodes ?? []) : null;
  const roots = tree?.get(null) ?? [];
  const nodeCount = result?.mindmap?.nodes?.length ?? 0;
  const cardCount = result?.flashcards?.length ?? 0;

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
                      <span className="text-sm font-semibold text-brand-300">📑 Bóc tách cấu trúc (Khuyên dùng)</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">Siêu nhanh</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Lấy chính xác theo các cấp Heading (H1, H2, H3), bullet points và định nghĩa gốc của bài học. Phân cấp sâu, chi tiết và không lo AI bịa hay thiếu ý.
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
                      <span className="text-sm font-semibold text-purple-300">🤖 Tóm tắt AI (Ollama)</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300">Qwen2.5</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Sử dụng mô hình AI để cô đọng và tóm tắt thành các ý cốt lõi ngắn gọn. Phù hợp khi muốn học nhanh cái nhìn tổng thể.
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => generate(genMode)}
                  className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-medium text-sm transition-all shadow-lg shadow-brand-500/25 hover:shadow-brand-500/40"
                >
                  <Sparkles size={16} />
                  Bắt đầu tạo Mindmap ({genMode === 'engine' ? 'Theo mục lục bài học' : 'Tóm tắt AI'})
                </button>
              </div>
            )}

            {/* ── Loading ── */}
            {status === 'loading' && (
              <div className="flex-1 flex flex-col items-center justify-center p-10 text-center">
                <Loader2 size={40} className="text-brand-400 animate-spin mb-5" />
                <h3 className="text-base font-semibold text-slate-200 mb-2">
                  Đang phân tích tài liệu…
                </h3>
                <p className="text-sm text-slate-500">
                  Model AI đang xử lý nội dung. Vui lòng chờ trong giây lát.
                </p>
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
                  <div className="ml-auto flex items-center gap-2">
                    <button
                      onClick={() => generate(result.backend === 'structure_engine' ? 'ai' : 'engine')}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-brand-500/30 bg-brand-500/10 text-brand-300 hover:bg-brand-500/20 text-xs transition-all"
                      title={result.backend === 'structure_engine' ? 'Chuyển sang tóm tắt bằng AI (Ollama)' : 'Chuyển sang bóc tách theo mục lục bài học'}
                    >
                      <Sparkles size={11} />
                      {result.backend === 'structure_engine' ? 'Đổi sang Tóm tắt AI' : 'Đổi sang Theo mục lục'}
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
                    ) : (
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
                    )
                  )}

                  {tab === 'flashcards' && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {result.flashcards.length === 0 ? (
                        <p className="text-sm text-slate-500 col-span-2 text-center py-6">
                          Không có flashcard nào
                        </p>
                      ) : (
                        result.flashcards.map((card, i) => (
                          <FlashcardItem key={i} card={card} index={i} />
                        ))
                      )}
                    </div>
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
