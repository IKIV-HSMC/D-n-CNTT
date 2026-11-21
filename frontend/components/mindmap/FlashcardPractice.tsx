'use client';

import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Loader2, RotateCcw } from 'lucide-react';
import { flashcardsApi } from '@/lib/api';
import { FlashcardSessionCard, ReviewRating } from '@/lib/types';

const RATINGS: { value: ReviewRating; label: string; className: string }[] = [
  { value: 'again', label: 'Again', className: 'bg-rose-500/15 text-rose-300 hover:bg-rose-500/25' },
  { value: 'hard', label: 'Hard', className: 'bg-amber-500/15 text-amber-300 hover:bg-amber-500/25' },
  { value: 'good', label: 'Good', className: 'bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25' },
  { value: 'easy', label: 'Easy', className: 'bg-sky-500/15 text-sky-300 hover:bg-sky-500/25' },
];

interface FlashcardPracticeProps {
  documentId: string;
}

export function FlashcardPractice({ documentId }: FlashcardPracticeProps) {
  const [cards, setCards] = useState<FlashcardSessionCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [revealed, setRevealed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    flashcardsApi.session(documentId, 250)
      .then((result) => {
        if (!cancelled) setCards(result.cards);
      })
      .catch((cause: unknown) => {
        const apiError = cause as { displayMessage?: string };
        if (!cancelled) setError(apiError.displayMessage || 'Không thể tải thẻ đến hạn');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [documentId]);

  const submitRating = async (rating: ReviewRating) => {
    const card = cards[0];
    if (!card || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await flashcardsApi.review(card.id, rating);
      setCards((current) => current.filter((item) => item.id !== card.id));
      setRevealed(false);
    } catch (cause: unknown) {
      const apiError = cause as { displayMessage?: string };
      setError(apiError.displayMessage || 'Không thể lưu kết quả ôn tập');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center gap-2 text-sm text-slate-400">
        <Loader2 size={18} className="animate-spin" /> Đang tải thẻ đến hạn…
      </div>
    );
  }

  if (!cards.length) {
    return (
      <div className="flex min-h-64 flex-col items-center justify-center text-center">
        {error ? <AlertCircle size={34} className="mb-3 text-rose-400" /> : <CheckCircle2 size={34} className="mb-3 text-emerald-400" />}
        <p className="font-medium text-slate-200">{error || 'Bạn đã ôn xong các thẻ đang đến hạn'}</p>
        {error ? (
          <button
            onClick={() => {
              setLoading(true);
              setError(null);
              flashcardsApi.session(documentId, 250)
                .then((result) => setCards(result.cards))
                .catch((cause: unknown) => {
                  const apiError = cause as { displayMessage?: string };
                  setError(apiError.displayMessage || 'Không thể tải thẻ đến hạn');
                })
                .finally(() => setLoading(false));
            }}
            className="mt-3 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
          >
            Thử tải lại
          </button>
        ) : (
          <p className="mt-1 text-xs text-slate-500">Thẻ mới sẽ xuất hiện sau khi tạo hoặc đồng bộ flashcard.</p>
        )}
      </div>
    );
  }

  const card = cards[0];
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 py-3">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{cards.length} thẻ trong phiên này</span>
        <span>{card.is_new ? 'Thẻ mới' : `Đã ôn ${card.total_reviews} lần`}</span>
      </div>

      <div className="[perspective:1200px]">
        <button
          type="button"
          onClick={() => setRevealed((value) => !value)}
          disabled={submitting}
          aria-pressed={revealed}
          aria-label={revealed ? 'Lật về câu hỏi' : 'Lật thẻ để xem đáp án'}
          className="group relative block min-h-56 w-full rounded-2xl text-center outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-wait"
        >
          <span
            className="absolute inset-0 flex min-h-56 flex-col items-center justify-center rounded-2xl border border-brand-400/25 bg-gradient-to-br from-[#20254b] via-surface-800 to-[#282044] p-7 shadow-lg transition-transform duration-500 group-hover:border-brand-300/50"
            style={{ transform: revealed ? 'rotateY(180deg)' : 'rotateY(0deg)', backfaceVisibility: 'hidden' }}
          >
            <span className="mb-3 text-[10px] uppercase tracking-widest text-brand-200">Câu hỏi</span>
            <span className="whitespace-pre-wrap text-lg leading-relaxed text-slate-100">{card.front}</span>
            <span className="mt-6 text-xs text-slate-500">Nhấn thẻ để lật xem đáp án</span>
          </span>
          <span
            className="absolute inset-0 flex min-h-56 flex-col items-center justify-center rounded-2xl border border-emerald-400/25 bg-gradient-to-br from-[#12382f] via-surface-800 to-[#173044] p-7 shadow-lg transition-transform duration-500 group-hover:border-emerald-300/50"
            style={{ transform: revealed ? 'rotateY(0deg)' : 'rotateY(-180deg)', backfaceVisibility: 'hidden' }}
          >
            <span className="mb-3 text-[10px] uppercase tracking-widest text-emerald-200">Đáp án</span>
            <span className="whitespace-pre-wrap text-lg leading-relaxed text-emerald-50">{card.back}</span>
            <span className="mt-6 text-xs text-emerald-100/60">Nhấn thẻ để quay lại câu hỏi</span>
          </span>
        </button>
      </div>

      {!revealed ? (
        <button
          onClick={() => setRevealed(true)}
          className="mx-auto inline-flex items-center gap-2 rounded-lg bg-brand-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-brand-600"
        >
          <RotateCcw size={15} /> Hiện đáp án
        </button>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {RATINGS.map((rating) => (
            <button
              key={rating.value}
              disabled={submitting}
              onClick={() => submitRating(rating.value)}
              className={`rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50 ${rating.className}`}
            >
              {rating.label}
            </button>
          ))}
        </div>
      )}

      {submitting && <p className="text-center text-xs text-slate-500">Đang cập nhật lịch ôn…</p>}
      {error && (
        <p role="alert" className="flex items-center justify-center gap-2 text-xs text-rose-300">
          <AlertCircle size={14} /> {error}
        </p>
      )}
    </div>
  );
}
