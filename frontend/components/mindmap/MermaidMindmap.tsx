'use client';

import { useEffect, useId, useRef, useState, useCallback } from 'react';
import {
  Code2, Download, Minus, Plus, Printer, RotateCcw,
  Edit3, Save, CheckCircle2, AlertCircle, Sparkles, Check, X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface MermaidMindmapProps {
  source: string;
  filename?: string;
  canExport?: boolean;
  onExportBlocked?: () => void;
  onSourceChange?: (newSource: string) => void;
  onSave?: (newSource?: string) => Promise<void>;
  isSaving?: boolean;
  hasUnsavedChanges?: boolean;
}

function safeFilename(filename?: string) {
  return (filename || 'mindmap').replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9._-]+/g, '_').slice(0, 80) || 'mindmap';
}

function downloadText(content: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = window.document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function MermaidMindmap({
  source,
  filename,
  canExport = true,
  onExportBlocked,
  onSourceChange,
  onSave,
  isSaving = false,
  hasUnsavedChanges = false,
}: MermaidMindmapProps) {
  const diagramRef = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const [svg, setSvg] = useState('');
  const [renderError, setRenderError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  // ── Chế độ chỉnh sửa mã Mermaid ───────────────────────────────────────────
  const [isEditMode, setIsEditMode] = useState(false);
  const [editCode, setEditCode] = useState(source);
  const [localUnsaved, setLocalUnsaved] = useState(false);
  const [localSaving, setLocalSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  // Đồng bộ khi source từ ngoài thay đổi
  useEffect(() => {
    setEditCode(source);
    setLocalUnsaved(false);
  }, [source]);

  // Render diagram từ code (editCode khi đang sửa, hoặc source)
  const currentCode = isEditMode ? editCode : source;

  useEffect(() => {
    let current = true;
    setRenderError(null);

    const render = async () => {
      if (!currentCode.trim()) {
        setSvg('');
        if (diagramRef.current) diagramRef.current.replaceChildren();
        return;
      }

      const module = await import('mermaid');
      const mermaid = module.default;
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'dark',
        fontFamily: 'Inter, Arial, sans-serif',
        mindmap: { padding: 24 },
      });

      const renderId = `docmind-mermaid-${reactId}-${Math.random().toString(36).slice(2)}`;
      try {
        const result = await mermaid.render(renderId, currentCode);
        if (!current) return;
        setSvg(result.svg);
        if (diagramRef.current) {
          diagramRef.current.innerHTML = result.svg;
          result.bindFunctions?.(diagramRef.current);
        }
        setRenderError(null);
      } catch (err: unknown) {
        if (!current) return;
        const e = err as { message?: string };
        setRenderError(e.message || 'Cú pháp Mermaid chưa hợp lệ');
      }
    };

    const timer = setTimeout(render, 150);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [reactId, currentCode]);

  // Xử lý phím Tab trong ô nhập code
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const target = e.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const val = target.value;
      const nextVal = val.substring(0, start) + '  ' + val.substring(end);
      setEditCode(nextVal);
      setLocalUnsaved(true);
      onSourceChange?.(nextVal);
      setTimeout(() => {
        target.selectionStart = target.selectionEnd = start + 2;
      }, 0);
    }
  };

  const handleCodeChange = (newText: string) => {
    setEditCode(newText);
    setLocalUnsaved(true);
    setJustSaved(false);
    onSourceChange?.(newText);
  };

  const handleSave = async () => {
    setLocalSaving(true);
    try {
      if (onSave) {
        await onSave(editCode);
      }
      setLocalUnsaved(false);
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2500);
    } catch {
      // lỗi đã được xử lý ở caller
    } finally {
      setLocalSaving(false);
    }
  };

  const handleReset = () => {
    setEditCode(source);
    setLocalUnsaved(false);
    onSourceChange?.(source);
  };

  const insertSnippet = (snippet: string) => {
    const nextVal = editCode.trimEnd() + '\n' + snippet;
    handleCodeChange(nextVal);
  };

  const printAsPdf = () => {
    if (!svg) return;
    const title = safeFilename(filename);
    const printHtml = `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title><style>@page{margin:12mm}body{margin:0;font-family:Arial,sans-serif}svg{display:block;max-width:100%;height:auto;margin:0 auto}@media print{body{margin:0}}</style></head><body>${svg}</body></html>`;
    const url = URL.createObjectURL(new Blob([printHtml], { type: 'text/html;charset=utf-8' }));
    const popup = window.open(url, '_blank');
    if (!popup) {
      URL.revokeObjectURL(url);
      setRenderError('Trình duyệt đang chặn cửa sổ in. Hãy cho phép popup rồi thử lại.');
      return;
    }
    popup.addEventListener('load', () => {
      window.setTimeout(() => {
        popup.focus();
        popup.print();
        URL.revokeObjectURL(url);
      }, 250);
    }, { once: true });
  };

  const runExport = (action: () => void) => {
    if (!canExport) {
      onExportBlocked?.();
      return;
    }
    action();
  };

  const effectiveSaving = isSaving || localSaving;
  const effectiveUnsaved = hasUnsavedChanges || localUnsaved;

  return (
    <div className="overflow-hidden rounded-xl border border-[rgba(90,108,240,0.15)] bg-surface-800/40 flex flex-col">
      {/* ── THANH CÔNG CỤ ──────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 px-3 py-2 bg-surface-800/70">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Nút bật/tắt chế độ sửa mã */}
          <button
            onClick={() => setIsEditMode((prev) => !prev)}
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all cursor-pointer',
              isEditMode
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm shadow-amber-500/10'
                : 'bg-surface-700 hover:bg-surface-600 text-slate-300 border-[rgba(255,255,255,0.08)]'
            )}
            title="Bật/tắt trình soạn thảo mã nguồn Mermaid"
          >
            <Edit3 size={13} />
            {isEditMode ? 'Đóng trình sửa' : 'Chỉnh sửa mã Mermaid'}
          </button>

          {/* Nút lưu thay đổi */}
          {(onSave || onSourceChange) && isEditMode && (
            <button
              onClick={() => void handleSave()}
              disabled={effectiveSaving}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all cursor-pointer disabled:opacity-50',
                effectiveUnsaved
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm shadow-emerald-500/15 animate-pulse'
                  : 'bg-surface-700 text-slate-400 border-[rgba(255,255,255,0.06)] hover:text-slate-200'
              )}
              title="Lưu các thay đổi của mã Mermaid vào hệ thống"
            >
              {effectiveSaving ? (
                <>
                  <RotateCcw size={13} className="animate-spin" />
                  Đang lưu...
                </>
              ) : justSaved ? (
                <>
                  <CheckCircle2 size={13} className="text-emerald-400" />
                  Đã lưu!
                </>
              ) : effectiveUnsaved ? (
                <>
                  <Save size={13} />
                  Lưu thay đổi *
                </>
              ) : (
                <>
                  <CheckCircle2 size={13} className="text-emerald-400" />
                  Đã lưu
                </>
              )}
            </button>
          )}

          {isEditMode && effectiveUnsaved && (
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-slate-400 hover:text-slate-200 hover:bg-white/5"
              title="Khôi phục lại mã nguồn ban đầu"
            >
              <RotateCcw size={12} />
              Khôi phục
            </button>
          )}

          <div className="h-4 w-[1px] bg-white/10 mx-1 hidden sm:block" />

          {/* Xuất file */}
          <button
            onClick={() => runExport(() => downloadText(currentCode, `${safeFilename(filename)}.mmd`, 'text/plain;charset=utf-8'))}
            title={canExport ? 'Tải mã Mermaid' : 'Đăng nhập để tải mindmap'}
            className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs text-slate-400 hover:bg-white/5 hover:text-slate-200 border border-transparent hover:border-white/10"
          >
            <Download size={13} /> .mmd
          </button>
          <button
            disabled={!svg}
            onClick={() => runExport(() => downloadText(svg, `${safeFilename(filename)}.svg`, 'image/svg+xml;charset=utf-8'))}
            title={canExport ? 'Tải sơ đồ SVG' : 'Đăng nhập để tải mindmap'}
            className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs text-slate-400 hover:bg-white/5 hover:text-slate-200 border border-transparent hover:border-white/10 disabled:opacity-40"
          >
            <Download size={13} /> SVG
          </button>
          <button
            disabled={!svg}
            onClick={() => runExport(printAsPdf)}
            title={canExport ? 'In sơ đồ hoặc lưu thành PDF' : 'Đăng nhập để tải mindmap'}
            className="inline-flex items-center gap-1 rounded-md bg-brand-500/15 px-2.5 py-1.5 text-xs text-brand-300 hover:bg-brand-500/25 disabled:opacity-40 border border-brand-500/25"
          >
            <Printer size={13} /> In / PDF
          </button>
        </div>

        {/* Thu phóng */}
        <div className="flex items-center gap-1">
          <button onClick={() => setZoom((value) => Math.min(2.5, value + 0.1))} title="Phóng to" className="rounded p-1.5 text-slate-400 hover:bg-white/5 hover:text-slate-200">
            <Plus size={15} />
          </button>
          <span className="w-10 text-center text-[10px] text-slate-500 font-mono">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom((value) => Math.max(0.4, value - 0.1))} title="Thu nhỏ" className="rounded p-1.5 text-slate-400 hover:bg-white/5 hover:text-slate-200">
            <Minus size={15} />
          </button>
          <button onClick={() => setZoom(1)} title="Đặt lại tỉ lệ (100%)" className="rounded p-1.5 text-slate-400 hover:bg-white/5 hover:text-slate-200">
            <RotateCcw size={13} />
          </button>
        </div>
      </div>

      {/* ── BÁO LỖI CÚ PHÁP ─────────────────────────────────────────────────── */}
      {renderError && (
        <div className="flex items-center gap-2 px-4 py-2 bg-rose-500/15 border-b border-rose-500/20 text-xs text-rose-300">
          <AlertCircle size={14} className="shrink-0 text-rose-400" />
          <span className="truncate">Lỗi cú pháp Mermaid: {renderError}</span>
        </div>
      )}

      {/* ── NỘI DUNG CHÍNH (CHẾ ĐỘ XEM HOẶC CHẾ ĐỘ SỬA SPLIT VIEW) ─────────── */}
      {isEditMode ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-white/10 min-h-[480px]">
          {/* Cột trái: Trình soạn thảo mã */}
          <div className="flex flex-col bg-[#121220] p-4">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/5">
              <span className="text-xs font-semibold text-brand-300 flex items-center gap-1.5">
                <Code2 size={14} /> Mã nguồn Mermaid Mindmap
              </span>
              <div className="flex items-center gap-1 text-[11px] text-slate-400">
                <span>Thêm nhanh:</span>
                <button
                  type="button"
                  onClick={() => insertSnippet('    Nhánh mới')}
                  className="px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/10 text-slate-300 border border-white/5"
                  title="Thêm nhánh mới thụt lề 4 dấu cách"
                >
                  + Nhánh
                </button>
                <button
                  type="button"
                  onClick={() => insertSnippet('      Chi tiết')}
                  className="px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/10 text-slate-300 border border-white/5"
                  title="Thêm nhánh con thụt lề 6 dấu cách"
                >
                  + Nhánh con
                </button>
              </div>
            </div>

            <textarea
              value={editCode}
              onChange={(e) => handleCodeChange(e.target.value)}
              onKeyDown={handleKeyDown}
              spellCheck={false}
              rows={18}
              placeholder="mindmap&#10;  root((Chủ đề))&#10;    Nhánh chính&#10;      Nhánh con"
              className="w-full flex-1 rounded-lg border border-white/10 bg-[#0c0c16] p-3 font-mono text-xs text-emerald-300 focus:border-brand-400 focus:outline-none resize-none leading-relaxed"
            />

            <div className="mt-2 text-[11px] text-slate-500 leading-normal">
              💡 <span className="text-slate-400">Quy tắc thụt lề:</span> 2 dấu cách cho gốc `root((Tiêu đề))`, 4 dấu cách cho nhánh chính, 6 dấu cách cho nhánh con. Bấm <kbd className="bg-white/10 px-1 py-0.5 rounded text-slate-300">Tab</kbd> để thụt dòng.
            </div>
          </div>

          {/* Cột phải: Xem trước kết quả trực tiếp */}
          <div className="flex flex-col p-4 bg-[#0f0f1a] overflow-auto">
            <div className="text-xs font-medium text-slate-400 pb-2 mb-2 border-b border-white/5 flex items-center justify-between">
              <span>Xem trước sơ đồ (Live Preview)</span>
              {effectiveUnsaved && (
                <span className="text-[11px] text-amber-400">● Có thay đổi chưa lưu</span>
              )}
            </div>

            <div className="flex-1 overflow-auto flex items-center justify-center p-2 min-h-[360px]">
              <div
                ref={diagramRef}
                className="min-w-max origin-top-left [&_svg]:h-auto [&_svg]:max-w-none"
                style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
              />
            </div>
          </div>
        </div>
      ) : (
        /* Chế độ xem thông thường */
        <div className="max-h-[64vh] overflow-auto p-4 flex items-center justify-center min-h-[400px]">
          {!svg && !renderError && (
            <p className="px-4 py-8 text-center text-xs text-slate-500">Đang dựng sơ đồ Mermaid…</p>
          )}
          <div
            ref={diagramRef}
            className="min-w-max origin-top-left [&_svg]:h-auto [&_svg]:max-w-none"
            style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
          />
        </div>
      )}
    </div>
  );
}
