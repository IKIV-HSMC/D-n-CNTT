'use client';

import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react';
import { Flashcard, MindmapNode } from '@/lib/types';

interface FlashcardQuizProps {
  cards: Flashcard[];
  nodes?: MindmapNode[];
}

export function FlashcardQuiz({ cards, nodes = [] }: FlashcardQuizProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const nodeLabels = useMemo(() => new Map(nodes.map((node) => [node.id, node.label])), [nodes]);

  useEffect(() => {
    setCurrentIndex(0);
    setFlipped(false);
  }, [cards]);

  if (!cards.length) {
    return <p className="py-10 text-center text-sm text-slate-500">Không có flashcard nào.</p>;
  }

  const card = cards[currentIndex];
  const topic = card.node_id ? nodeLabels.get(card.node_id) : undefined;
  const progress = ((currentIndex + 1) / cards.length) * 100;
  const moveTo = (index: number) => {
    setCurrentIndex(index);
    setFlipped(false);
  };
  const moveNext = () => moveTo(currentIndex === cards.length - 1 ? 0 : currentIndex + 1);

  return (
    <div className="mx-auto w-full max-w-2xl py-3">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>Thẻ {currentIndex + 1} / {cards.length}</span>
        <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1">
          {topic && <span className="max-w-[320px] truncate">Chủ đề: <span className="text-slate-300">{topic}</span></span>}
          <span>{flipped ? 'Mặt đáp án' : 'Mặt câu hỏi'}</span>
        </div>
      </div>
      <div className="mb-5 h-1.5 overflow-hidden rounded-full bg-white/5">
        <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-purple-500 transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>

      <div className="[perspective:1200px]">
        <button
          type="button"
          onClick={() => setFlipped((value) => !value)}
          aria-pressed={flipped}
          aria-label={flipped ? 'Lật về câu hỏi' : 'Lật thẻ để xem đáp án'}
          className="group relative block min-h-[300px] w-full rounded-3xl text-center outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
        >
          <span
            className="absolute inset-0 flex min-h-[300px] flex-col items-center justify-center rounded-3xl border border-brand-400/30 bg-gradient-to-br from-[#20254b] via-surface-800 to-[#282044] p-7 shadow-xl transition-transform duration-500 [transform-style:preserve-3d] group-hover:border-brand-300/50 sm:p-10"
            style={{ transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)', backfaceVisibility: 'hidden' }}
          >
            <span className="mb-5 rounded-full border border-brand-300/20 bg-brand-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-brand-200">
              Câu hỏi
            </span>
            <span className="whitespace-pre-wrap text-xl font-medium leading-relaxed text-slate-100 sm:text-2xl">
              {card.front}
            </span>
            <span className="mt-8 inline-flex items-center gap-2 text-xs text-slate-400">
              <RotateCcw size={13} /> Chạm hoặc nhấn để lật thẻ
            </span>
          </span>
          <span
            className="absolute inset-0 flex min-h-[300px] flex-col items-center justify-center rounded-3xl border border-emerald-400/30 bg-gradient-to-br from-[#12382f] via-surface-800 to-[#173044] p-7 shadow-xl transition-transform duration-500 [transform-style:preserve-3d] group-hover:border-emerald-300/50 sm:p-10"
            style={{ transform: flipped ? 'rotateY(0deg)' : 'rotateY(-180deg)', backfaceVisibility: 'hidden' }}
          >
            <span className="mb-5 rounded-full border border-emerald-300/20 bg-emerald-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-200">
              Đáp án và giải thích
            </span>
            <span className="whitespace-pre-wrap text-lg leading-relaxed text-emerald-50 sm:text-xl">
              {card.back}
            </span>
            <span className="mt-8 inline-flex items-center gap-2 text-xs text-emerald-100/60">
              <RotateCcw size={13} /> Chạm để xem lại câu hỏi
            </span>
          </span>
        </button>
      </div>

      <div className="mt-5 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => moveTo(Math.max(0, currentIndex - 1))}
          disabled={currentIndex === 0}
          className="inline-flex items-center gap-1 rounded-xl border border-white/10 px-4 py-2.5 text-sm text-slate-300 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-35"
        >
          <ChevronLeft size={17} /> Trước
        </button>
        <button
          type="button"
          onClick={() => setFlipped((value) => !value)}
          className="rounded-xl bg-brand-500/15 px-4 py-2.5 text-sm font-medium text-brand-200 transition-colors hover:bg-brand-500/25"
        >
          {flipped ? 'Ẩn đáp án' : 'Hiện đáp án'}
        </button>
        <button
          type="button"
          onClick={moveNext}
          className="inline-flex items-center gap-1 rounded-xl border border-white/10 px-4 py-2.5 text-sm text-slate-300 transition-colors hover:bg-white/5"
        >
          {currentIndex === cards.length - 1 ? 'Ôn lại' : 'Tiếp'} <ChevronRight size={17} />
        </button>
      </div>
      <p className="mt-3 text-center text-xs text-slate-500">
        Đọc câu hỏi, tự trả lời, rồi bấm <span className="text-brand-300">Hiện đáp án</span> hoặc chạm thẻ. Dùng <span className="text-slate-300">Tiếp</span> để sang câu sau.
      </p>
    </div>
  );
}
