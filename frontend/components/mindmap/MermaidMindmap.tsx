'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { Code2, Download, Minus, Plus, Printer, RotateCcw } from 'lucide-react';

interface MermaidMindmapProps {
  source: string;
  filename?: string;
  canExport?: boolean;
  onExportBlocked?: () => void;
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
}: MermaidMindmapProps) {
  const diagramRef = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const [svg, setSvg] = useState('');
  const [renderError, setRenderError] = useState<string | null>(null);
  const [showSource, setShowSource] = useState(false);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    let current = true;
    setSvg('');
    setRenderError(null);
    if (diagramRef.current) diagramRef.current.replaceChildren();

    const render = async () => {
      const module = await import('mermaid');
      const mermaid = module.default;
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'dark',
        fontFamily: 'Arial, sans-serif',
        mindmap: { padding: 24 },
      });
      const renderId = `docmind-mermaid-${reactId}-${Math.random().toString(36).slice(2)}`;
      const result = await mermaid.render(renderId, source);
      if (!current) return;
      setSvg(result.svg);
      if (diagramRef.current) {
        diagramRef.current.innerHTML = result.svg;
        result.bindFunctions?.(diagramRef.current);
      }
    };

    render().catch((cause: unknown) => {
      if (!current) return;
      const error = cause as { message?: string };
      setRenderError(error.message || 'Không thể hiển thị sơ đồ Mermaid');
    });

    return () => { current = false; };
  }, [reactId, source]);

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

  return (
    <div className="overflow-hidden rounded-xl border border-[rgba(90,108,240,0.12)] bg-surface-800/40">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 px-3 py-2">
        <div className="flex items-center gap-1">
          <button onClick={() => setZoom((value) => Math.min(2, value + 0.1))} title="Phóng to" className="rounded p-1.5 text-slate-400 hover:bg-white/5 hover:text-slate-200">
            <Plus size={15} />
          </button>
          <span className="w-10 text-center text-[10px] text-slate-500">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom((value) => Math.max(0.5, value - 0.1))} title="Thu nhỏ" className="rounded p-1.5 text-slate-400 hover:bg-white/5 hover:text-slate-200">
            <Minus size={15} />
          </button>
          <button onClick={() => setZoom(1)} title="Đặt lại tỉ lệ" className="rounded p-1.5 text-slate-400 hover:bg-white/5 hover:text-slate-200">
            <RotateCcw size={13} />
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <button onClick={() => setShowSource((value) => !value)} className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] text-slate-400 hover:bg-white/5 hover:text-slate-200">
            <Code2 size={13} /> {showSource ? 'Ẩn mã' : 'Mã Mermaid'}
          </button>
          <button onClick={() => runExport(() => downloadText(source, `${safeFilename(filename)}.mmd`, 'text/plain;charset=utf-8'))} title={canExport ? 'Tải mã Mermaid' : 'Đăng nhập để tải mindmap'} className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] text-slate-400 hover:bg-white/5 hover:text-slate-200">
            <Download size={13} /> .mmd
          </button>
          <button disabled={!svg} onClick={() => runExport(() => downloadText(svg, `${safeFilename(filename)}.svg`, 'image/svg+xml;charset=utf-8'))} title={canExport ? 'Tải sơ đồ SVG' : 'Đăng nhập để tải mindmap'} className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] text-slate-400 hover:bg-white/5 hover:text-slate-200 disabled:opacity-40">
            <Download size={13} /> SVG
          </button>
          <button disabled={!svg} onClick={() => runExport(printAsPdf)} title={canExport ? 'In sơ đồ hoặc lưu thành PDF' : 'Đăng nhập để tải mindmap'} className="inline-flex items-center gap-1 rounded-md bg-brand-500/15 px-2 py-1.5 text-[11px] text-brand-300 hover:bg-brand-500/25 disabled:opacity-40">
            <Printer size={13} /> In / PDF
          </button>
        </div>
      </div>

      {renderError && <p role="alert" className="px-4 py-2 text-xs text-rose-300">{renderError}</p>}
      {!svg && !renderError && <p className="px-4 py-8 text-center text-xs text-slate-500">Đang dựng sơ đồ Mermaid…</p>}
      <div className="max-h-[58vh] overflow-auto p-4">
        <div
          ref={diagramRef}
          className="min-w-max origin-top-left [&_svg]:h-auto [&_svg]:max-w-none"
          style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
        />
      </div>
      {showSource && (
        <pre className="max-h-64 overflow-auto border-t border-white/5 p-4 text-xs leading-relaxed text-emerald-200">
          {source}
        </pre>
      )}
    </div>
  );
}
