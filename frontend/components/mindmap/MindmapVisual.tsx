'use client';

import React, { useRef, useMemo, useState, useEffect, useCallback } from 'react';
import {
  Download, Image as ImageIcon, ZoomIn, ZoomOut, RotateCcw, FileCode,
  Edit3, Plus, Trash2, Save, Check, X, Palette, FolderPlus, CheckCircle2, Move,
} from 'lucide-react';
import { MindmapNode } from '@/lib/types';
import { cn } from '@/lib/utils';

interface MindmapVisualProps {
  nodes: MindmapNode[];
  filename?: string;
  canExport?: boolean;
  onExportBlocked?: () => void;
  onNodesChange?: (updatedNodes: MindmapNode[]) => void;
  onSave?: () => Promise<void>;
  isSaving?: boolean;
  hasUnsavedChanges?: boolean;
}

interface LayoutNode {
  id: string;
  label: string;
  description: string;
  parentId: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  depth: number;
  colorIndex: number;
  customColor?: string;
}

interface LayoutEdge {
  id: string;
  source: LayoutNode;
  target: LayoutNode;
  color: string;
}

const BRANCH_COLORS = [
  '#5a6cf0', // Brand Blue
  '#a855f7', // Purple
  '#06b6d4', // Cyan
  '#10b981', // Emerald
  '#f59e0b', // Amber
  '#ec4899', // Pink
  '#6366f1', // Indigo
];

export function MindmapVisual({
  nodes,
  filename = 'docmind',
  canExport = true,
  onExportBlocked,
  onNodesChange,
  onSave,
  isSaving = false,
  hasUnsavedChanges = false,
}: MindmapVisualProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [zoom, setZoom] = useState(1);
  const [exporting, setExporting] = useState(false);

  // ── Drag to Pan states ─────────────────────────────────────────────────────
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({ startX: 0, startY: 0, scrollLeft: 0, scrollTop: 0 });

  // ── Trạng thái chỉnh sửa sơ đồ ──────────────────────────────────────────────
  const [isEditMode, setIsEditMode] = useState(false);
  const [selectedNode, setSelectedNode] = useState<MindmapNode | null>(null);
  const [isEditingNode, setIsEditingNode] = useState(false);
  const [isAddingChild, setIsAddingChild] = useState(false);
  const [isAddingRoot, setIsAddingRoot] = useState(false);

  // Form states
  const [formLabel, setFormLabel] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formColor, setFormColor] = useState('');

  // ── Tính toán tọa độ cây Mindmap ──────────────────────────────────────────
  const { layoutNodes, layoutEdges, viewBoxWidth, viewBoxHeight, rootY } = useMemo(() => {
    if (!nodes || nodes.length === 0) {
      return { layoutNodes: [], layoutEdges: [], viewBoxWidth: 800, viewBoxHeight: 400, rootY: 200 };
    }

    const childrenMap = new Map<string | null, MindmapNode[]>();
    const nodeMap = new Map<string, MindmapNode>();

    nodes.forEach((n) => {
      nodeMap.set(n.id, n);
      const pid = n.parent_id ?? null;
      if (!childrenMap.has(pid)) childrenMap.set(pid, []);
      childrenMap.get(pid)!.push(n);
    });

    let roots = childrenMap.get(null) ?? [];
    if (roots.length === 0 && nodes.length > 0) {
      roots = [nodes[0]];
    }

    const HORIZONTAL_GAP = 90;
    const VERTICAL_GAP = 28;
    const NODE_HEIGHT = 42;
    const DESCRIBED_NODE_HEIGHT = 64;

    let currentY = 0;
    const calculatedNodes: LayoutNode[] = [];
    const calculatedEdges: LayoutEdge[] = [];
    const idToLayoutNode = new Map<string, LayoutNode>();

    function layoutSubtree(
      node: MindmapNode,
      depth: number,
      colorIdx: number
    ): { y: number; height: number } {
      const children = childrenMap.get(node.id) ?? [];
      const description = (node.description || '').replace(/\s+/g, ' ').trim();
      const textLen = Math.max((node.label || '').length, Math.min(description.length, 38));
      const width = Math.max(130, Math.min(300, textLen * 8 + 36));
      const height = description ? DESCRIBED_NODE_HEIGHT : NODE_HEIGHT;

      if (children.length === 0) {
        const y = currentY;
        currentY += height + VERTICAL_GAP;

        const layoutNode: LayoutNode = {
          id: node.id,
          label: node.label,
          description,
          parentId: node.parent_id,
          x: 0,
          y,
          width,
          height,
          depth,
          colorIndex: colorIdx,
          customColor: node.color,
        };
        calculatedNodes.push(layoutNode);
        idToLayoutNode.set(node.id, layoutNode);
        return { y: y + height / 2, height };
      }

      const childYPositions: number[] = [];
      children.forEach((child, idx) => {
        const branchColor = depth === 0 ? idx % BRANCH_COLORS.length : colorIdx;
        const res = layoutSubtree(child, depth + 1, branchColor);
        childYPositions.push(res.y);
      });

      const avgY = childYPositions.reduce((a, b) => a + b, 0) / childYPositions.length;
      const nodeY = avgY - height / 2;

      const layoutNode: LayoutNode = {
        id: node.id,
        label: node.label,
        description,
        parentId: node.parent_id,
        x: 0,
        y: nodeY,
        width,
        height,
        depth,
        colorIndex: colorIdx,
        customColor: node.color,
      };
      calculatedNodes.push(layoutNode);
      idToLayoutNode.set(node.id, layoutNode);
      return { y: avgY, height };
    }

    roots.forEach((root, idx) => {
      layoutSubtree(root, 0, idx % BRANCH_COLORS.length);
      currentY += 40;
    });

    // ── Căn chỉnh trục X theo từng độ sâu ───────────────────────────────────
    const depthMaxWidth = new Map<number, number>();
    calculatedNodes.forEach((n) => {
      const maxW = depthMaxWidth.get(n.depth) ?? 0;
      if (n.width > maxW) depthMaxWidth.set(n.depth, n.width);
    });

    const depthXOffset = new Map<number, number>();
    let runningX = 0;
    const maxDepth = Math.max(...calculatedNodes.map((n) => n.depth), 0);

    for (let d = 0; d <= maxDepth; d++) {
      depthXOffset.set(d, runningX);
      const w = depthMaxWidth.get(d) ?? 160;
      runningX += w + HORIZONTAL_GAP;
    }

    calculatedNodes.forEach((n) => {
      n.x = depthXOffset.get(n.depth) ?? 0;
    });

    // ── QUAN TRỌNG: Chuẩn hóa tọa độ để không bao giờ bị cắt mất phần trên ──
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    calculatedNodes.forEach((n) => {
      if (n.x < minX) minX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.x + n.width > maxX) maxX = n.x + n.width;
      if (n.y + n.height > maxY) maxY = n.y + n.height;
    });

    const PADDING_TOP = 80;
    const PADDING_LEFT = 80;
    const PADDING_BOTTOM = 120;
    const PADDING_RIGHT = 120;

    const shiftX = PADDING_LEFT - (minX === Infinity ? 0 : minX);
    const shiftY = PADDING_TOP - (minY === Infinity ? 0 : minY);

    calculatedNodes.forEach((n) => {
      n.x += shiftX;
      n.y += shiftY;
    });

    // Tạo Edges
    calculatedNodes.forEach((n) => {
      if (n.parentId && idToLayoutNode.has(n.parentId)) {
        const parent = idToLayoutNode.get(n.parentId)!;
        const edgeColor = n.customColor || BRANCH_COLORS[n.colorIndex % BRANCH_COLORS.length];
        calculatedEdges.push({
          id: `e-${parent.id}-${n.id}`,
          source: parent,
          target: n,
          color: edgeColor,
        });
      }
    });

    const totalWidth = Math.max(900, (maxX - minX) + PADDING_LEFT + PADDING_RIGHT);
    const totalHeight = Math.max(550, (maxY - minY) + PADDING_TOP + PADDING_BOTTOM);

    const firstRoot = calculatedNodes.find((n) => n.parentId === null);

    return {
      layoutNodes: calculatedNodes,
      layoutEdges: calculatedEdges,
      viewBoxWidth: totalWidth,
      viewBoxHeight: totalHeight,
      rootY: firstRoot ? firstRoot.y : totalHeight / 2,
    };
  }, [nodes]);

  // Cuộn vào vị trí nút gốc khi mở lần đầu
  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const targetScrollY = Math.max(0, rootY * zoom - container.clientHeight / 2 + 50);
    container.scrollTo({ top: targetScrollY, behavior: 'smooth' });
  }, [rootY]);

  // ── Kéo chuột để di chuyển canvas (Drag to Pan) ───────────────────────────
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    // Bỏ qua nếu bấm vào nút, input, hoặc modal
    if (target.closest('button') || target.closest('input') || target.closest('textarea')) return;
    if (!containerRef.current) return;

    setIsPanning(true);
    panStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      scrollLeft: containerRef.current.scrollLeft,
      scrollTop: containerRef.current.scrollTop,
    };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning || !containerRef.current) return;
    e.preventDefault();
    const dx = e.clientX - panStartRef.current.startX;
    const dy = e.clientY - panStartRef.current.startY;
    containerRef.current.scrollLeft = panStartRef.current.scrollLeft - dx;
    containerRef.current.scrollTop = panStartRef.current.scrollTop - dy;
  }, [isPanning]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  // ── Thao tác sửa Node ──────────────────────────────────────────────────────
  const handleOpenEditNode = (node: MindmapNode) => {
    setSelectedNode(node);
    setFormLabel(node.label);
    setFormDesc(node.description || '');
    setFormColor(node.color || '');
    setIsEditingNode(true);
  };

  const handleSaveNodeEdit = () => {
    if (!selectedNode || !onNodesChange) return;
    const updated = nodes.map((n) => {
      if (n.id === selectedNode.id) {
        return {
          ...n,
          label: formLabel.trim() || n.label,
          description: formDesc.trim(),
          color: formColor || undefined,
        };
      }
      return n;
    });
    onNodesChange(updated);
    setIsEditingNode(false);
    setSelectedNode(null);
  };

  const handleOpenAddChild = (parentNode: MindmapNode) => {
    setSelectedNode(parentNode);
    setFormLabel('');
    setFormDesc('');
    setFormColor(parentNode.color || '');
    setIsAddingChild(true);
    setIsEditingNode(false);
  };

  const handleConfirmAddChild = () => {
    if (!selectedNode || !onNodesChange) return;
    const newId = `node_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 6)}`;
    const newNode: MindmapNode = {
      id: newId,
      label: formLabel.trim() || 'Nhánh con mới',
      description: formDesc.trim(),
      parent_id: selectedNode.id,
      color: formColor || selectedNode.color,
    };
    onNodesChange([...nodes, newNode]);
    setIsAddingChild(false);
    setSelectedNode(null);
  };

  const handleOpenAddRoot = () => {
    setFormLabel('');
    setFormDesc('');
    setFormColor(BRANCH_COLORS[nodes.length % BRANCH_COLORS.length]);
    setIsAddingRoot(true);
  };

  const handleConfirmAddRoot = () => {
    if (!onNodesChange) return;
    const newId = `node_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 6)}`;
    const newNode: MindmapNode = {
      id: newId,
      label: formLabel.trim() || 'Chủ đề mới',
      description: formDesc.trim(),
      parent_id: null,
      color: formColor,
    };
    onNodesChange([...nodes, newNode]);
    setIsAddingRoot(false);
  };

  const handleDeleteNode = (nodeId: string) => {
    if (!onNodesChange) return;
    const toDelete = new Set<string>([nodeId]);
    let added = true;
    while (added) {
      added = false;
      for (const n of nodes) {
        if (n.parent_id && toDelete.has(n.parent_id) && !toDelete.has(n.id)) {
          toDelete.add(n.id);
          added = true;
        }
      }
    }
    const remaining = nodes.filter((n) => !toDelete.has(n.id));
    onNodesChange(remaining);
    setIsEditingNode(false);
    setSelectedNode(null);
  };

  // ── Xuất file ──────────────────────────────────────────────────────────────
  const exportAsPng = async () => {
    if (!svgRef.current) return;
    setExporting(true);

    try {
      const svg = svgRef.current;
      const svgString = new XMLSerializer().serializeToString(svg);
      const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(svgBlob);

      const img = new Image();
      img.onload = () => {
        const scale = 2;
        const canvas = document.createElement('canvas');
        canvas.width = viewBoxWidth * scale;
        canvas.height = viewBoxHeight * scale;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.fillStyle = '#0f0f1a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
        for (let x = 0; x < canvas.width; x += 40 * scale) {
          for (let y = 0; y < canvas.height; y += 40 * scale) {
            ctx.beginPath();
            ctx.arc(x, y, 1.5 * scale, 0, Math.PI * 2);
            ctx.fill();
          }
        }

        ctx.scale(scale, scale);
        ctx.drawImage(img, 0, 0);

        const pngUrl = canvas.toDataURL('image/png');
        const link = document.createElement('a');
        const cleanName = filename.replace(/\.[^/.]+$/, '');
        link.download = `${cleanName}_mindmap.png`;
        link.href = pngUrl;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        setExporting(false);
      };

      img.src = url;
    } catch (e) {
      console.error('Lỗi xuất PNG:', e);
      setExporting(false);
    }
  };

  const exportAsSvg = () => {
    if (!svgRef.current) return;
    const svgString = new XMLSerializer().serializeToString(svgRef.current);
    const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const cleanName = filename.replace(/\.[^/.]+$/, '');
    link.download = `${cleanName}_mindmap.svg`;
    link.href = url;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full space-y-3 relative">
      {/* Thanh công cụ: Xuất ảnh, Chỉnh sửa, Pan & Thu phóng */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 bg-surface-800/70 rounded-xl border border-[rgba(90,108,240,0.15)]">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Nút bật/tắt chế độ sửa */}
          {onNodesChange && (
            <button
              onClick={() => setIsEditMode((prev) => !prev)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all cursor-pointer',
                isEditMode
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm shadow-amber-500/10'
                  : 'bg-surface-700/80 hover:bg-surface-600 text-slate-300 border-[rgba(255,255,255,0.1)]'
              )}
              title="Bật/tắt chế độ chỉnh sửa nhãn, màu sắc và thêm/xóa nhánh"
            >
              <Edit3 size={13} />
              {isEditMode ? 'Hoàn tất sửa' : 'Chỉnh sửa sơ đồ'}
            </button>
          )}

          {isEditMode && onNodesChange && (
            <button
              onClick={handleOpenAddRoot}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 border border-brand-500/30 transition-all cursor-pointer"
              title="Thêm một chủ đề/nhánh chính mới"
            >
              <Plus size={13} />
              Thêm nhánh chính
            </button>
          )}

          {/* Nút lưu thay đổi */}
          {onSave && (
            <button
              onClick={() => void onSave()}
              disabled={isSaving}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all cursor-pointer disabled:opacity-50',
                hasUnsavedChanges
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm shadow-emerald-500/15 animate-pulse'
                  : 'bg-surface-700 text-slate-400 border-[rgba(255,255,255,0.06)] hover:text-slate-200'
              )}
              title={hasUnsavedChanges ? 'Có thay đổi chưa lưu vào hệ thống' : 'Lưu sơ đồ'}
            >
              {isSaving ? (
                <>
                  <RotateCcw size={13} className="animate-spin" />
                  Đang lưu...
                </>
              ) : hasUnsavedChanges ? (
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

          <div className="h-4 w-[1px] bg-white/10 mx-1 hidden sm:block" />

          {/* Xuất file */}
          <button
            onClick={() => canExport ? exportAsPng() : onExportBlocked?.()}
            disabled={exporting}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-surface-700 hover:bg-surface-600 text-slate-300 border border-[rgba(255,255,255,0.08)] transition-all cursor-pointer disabled:opacity-50"
            title={canExport ? 'Xuất thành ảnh PNG chất lượng cao' : 'Đăng nhập để tải mindmap'}
          >
            <ImageIcon size={13} />
            {exporting ? 'Đang xuất...' : 'Xuất PNG'}
          </button>

          <button
            onClick={() => canExport ? exportAsSvg() : onExportBlocked?.()}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-surface-700 hover:bg-surface-600 text-slate-300 border border-[rgba(255,255,255,0.08)] transition-all cursor-pointer"
            title={canExport ? 'Xuất file vector SVG không vỡ nét' : 'Đăng nhập để tải mindmap'}
          >
            <FileCode size={13} />
            Xuất SVG
          </button>
        </div>

        {/* Bộ điều khiển thu phóng & Hướng dẫn Pan */}
        <div className="flex items-center gap-1">
          <span className="hidden md:inline-flex items-center gap-1 text-[11px] text-slate-500 mr-2">
            <Move size={12} /> Giữ chuột để kéo xem
          </span>
          <button
            onClick={() => setZoom((z) => Math.max(0.3, z - 0.15))}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-all"
            title="Thu nhỏ"
          >
            <ZoomOut size={15} />
          </button>
          <span className="text-[11px] font-mono text-slate-400 min-w-[42px] text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom((z) => Math.min(2.5, z + 0.15))}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-all"
            title="Phóng to"
          >
            <ZoomIn size={15} />
          </button>
          <button
            onClick={() => setZoom(1)}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-all ml-1"
            title="Đặt lại zoom (100%)"
          >
            <RotateCcw size={13} />
          </button>
        </div>
      </div>

      {/* Thông báo chế độ sửa */}
      {isEditMode && (
        <div className="flex items-center justify-between px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-lg text-xs text-amber-300">
          <span className="flex items-center gap-1.5">
            <Edit3 size={13} />
            Chế độ chỉnh sửa: Bấm trực tiếp vào bất kỳ nút nào trên sơ đồ để đổi tên, mô tả, màu sắc hoặc thêm/xóa nhánh con.
          </span>
          <button
            onClick={() => setIsEditMode(false)}
            className="text-amber-400 hover:text-amber-200 underline font-medium ml-2 cursor-pointer"
          >
            Đóng
          </button>
        </div>
      )}

      {/* ── KHU VỰC VẼ SƠ ĐỒ SVG (Hỗ trợ kéo chuột Pan & Cuộn tự do không bao giờ bị cắt trên) ── */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className={cn(
          "flex-1 overflow-auto rounded-xl border border-[rgba(90,108,240,0.12)] bg-[#0f0f1a] relative min-h-[460px] p-6 select-none",
          isPanning ? "cursor-grabbing" : "cursor-grab"
        )}
      >
        <div
          style={{
            width: `${Math.round(viewBoxWidth * zoom)}px`,
            height: `${Math.round(viewBoxHeight * zoom)}px`,
            minWidth: '100%',
            minHeight: '100%',
            position: 'relative',
          }}
        >
          <svg
            ref={svgRef}
            width={Math.round(viewBoxWidth * zoom)}
            height={Math.round(viewBoxHeight * zoom)}
            viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
            xmlns="http://www.w3.org/2000/svg"
            className="select-none block"
            style={{ backgroundColor: '#0f0f1a' }}
          >
            <defs>
              <pattern id="dot-grid" width="24" height="24" patternUnits="userSpaceOnUse">
                <circle cx="2" cy="2" r="1" fill="rgba(255,255,255,0.06)" />
              </pattern>

              <linearGradient id="root-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#4f46e5" />
                <stop offset="100%" stopColor="#7c3aed" />
              </linearGradient>

              <filter id="node-shadow" x="-10%" y="-10%" width="130%" height="130%">
                <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="#000000" floodOpacity="0.4" />
              </filter>
            </defs>

            <rect width={viewBoxWidth} height={viewBoxHeight} fill="#0f0f1a" />
            <rect width={viewBoxWidth} height={viewBoxHeight} fill="url(#dot-grid)" />

            {/* Các đường nối cong Bézier */}
            <g className="edges">
              {layoutEdges.map((e) => {
                const x1 = e.source.x + e.source.width;
                const y1 = e.source.y + e.source.height / 2;
                const x2 = e.target.x;
                const y2 = e.target.y + e.target.height / 2;
                const cx1 = x1 + (x2 - x1) * 0.5;
                const cy1 = y1;
                const cx2 = x1 + (x2 - x1) * 0.5;
                const cy2 = y2;
                const path = `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;

                return (
                  <path
                    key={e.id}
                    d={path}
                    fill="none"
                    stroke={e.color}
                    strokeWidth="2.2"
                    strokeOpacity="0.75"
                    strokeLinecap="round"
                  />
                );
              })}
            </g>

            {/* Các Node */}
            <g className="nodes">
              {layoutNodes.map((n) => {
                const isRoot = n.depth === 0;
                const color = n.customColor || BRANCH_COLORS[n.colorIndex % BRANCH_COLORS.length];
                const rawNode = nodes.find((item) => item.id === n.id);

                return (
                  <g
                    key={n.id}
                    transform={`translate(${n.x}, ${n.y})`}
                    filter="url(#node-shadow)"
                    className={cn(
                      'cursor-pointer transition-transform duration-150',
                      isEditMode && 'hover:opacity-90'
                    )}
                    onClick={() => {
                      if (rawNode) {
                        handleOpenEditNode(rawNode);
                      }
                    }}
                  >
                    {n.description && <title>{`${n.label}\n${n.description}`}</title>}
                    
                    {/* Viền ngoài khi ở chế độ Edit Mode */}
                    {isEditMode && (
                      <rect
                        width={n.width + 6}
                        height={n.height + 6}
                        x={-3}
                        y={-3}
                        rx={isRoot ? 17 : 13}
                        fill="none"
                        stroke="#f59e0b"
                        strokeWidth={1.5}
                        strokeDasharray="4 3"
                        strokeOpacity={0.7}
                      />
                    )}

                    {/* Hộp node */}
                    <rect
                      width={n.width}
                      height={n.height}
                      rx={isRoot ? 14 : 10}
                      fill={isRoot ? 'url(#root-grad)' : '#1e1e35'}
                      stroke={isRoot ? 'rgba(255,255,255,0.4)' : color}
                      strokeWidth={isRoot ? 1.5 : 1.2}
                      strokeOpacity={isRoot ? 0.8 : 0.6}
                    />

                    {!isRoot && (
                      <rect
                        x={0}
                        y={4}
                        width={4}
                        height={n.height - 8}
                        rx={2}
                        fill={color}
                      />
                    )}

                    {/* Nhãn và nội dung */}
                    <text
                      x={isRoot ? n.width / 2 : 14}
                      y={n.description ? 23 : n.height / 2 + 4}
                      textAnchor={isRoot ? 'middle' : 'start'}
                      fill={isRoot ? '#ffffff' : '#e2e8f0'}
                      fontSize={isRoot ? '13' : '12'}
                      fontWeight={isRoot ? '700' : '500'}
                      fontFamily="Inter, -apple-system, sans-serif"
                    >
                      {n.label}
                    </text>
                    {n.description && (
                      <text
                        x={14}
                        y={48}
                        textAnchor="start"
                        fill="#94a3b8"
                        fontSize="10"
                        fontFamily="Inter, -apple-system, sans-serif"
                      >
                        {n.description.length > Math.floor((n.width - 28) / 6)
                          ? `${n.description.slice(0, Math.floor((n.width - 34) / 6)).trimEnd()}…`
                          : n.description}
                      </text>
                    )}

                    {isEditMode && (
                      <g transform={`translate(${n.width - 20}, 6)`}>
                        <circle cx={7} cy={7} r={7} fill="rgba(245, 158, 11, 0.25)" />
                        <path d="M4 10 L10 4 L11 5 L5 11 Z" fill="#f59e0b" />
                      </g>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
      </div>

      {/* ── MODAL CHỈNH SỬA NODE ────────────────────────────────────────────── */}
      {isEditingNode && selectedNode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-[rgba(90,108,240,0.25)] bg-[#141424] p-5 shadow-2xl animate-scale-in">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2 text-brand-300 font-semibold text-sm">
                <Edit3 size={16} />
                <span>Chỉnh sửa nhánh</span>
              </div>
              <button
                onClick={() => {
                  setIsEditingNode(false);
                  setSelectedNode(null);
                }}
                className="rounded-lg p-1 text-slate-400 hover:bg-white/10 hover:text-slate-200"
              >
                <X size={16} />
              </button>
            </div>

            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Tên nhánh (Nhãn nút) *
                </label>
                <input
                  type="text"
                  value={formLabel}
                  onChange={(e) => setFormLabel(e.target.value)}
                  placeholder="Nhập tên nhánh..."
                  className="w-full rounded-lg border border-white/10 bg-surface-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-brand-400 focus:outline-none"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Giải thích / Ngữ cảnh tóm tắt
                </label>
                <textarea
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  placeholder="Nhập phần giải thích ngắn của nhánh..."
                  rows={3}
                  className="w-full rounded-lg border border-white/10 bg-surface-800 px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-brand-400 focus:outline-none resize-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5 flex items-center gap-1.5">
                  <Palette size={13} />
                  Màu sắc nhánh
                </label>
                <div className="flex items-center gap-2">
                  {BRANCH_COLORS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setFormColor(c)}
                      className={cn(
                        'w-6 h-6 rounded-full transition-transform cursor-pointer border-2',
                        formColor === c ? 'scale-125 border-white shadow-md' : 'border-transparent hover:scale-110'
                      )}
                      style={{ backgroundColor: c }}
                      title={c}
                    />
                  ))}
                  {formColor && (
                    <button
                      type="button"
                      onClick={() => setFormColor('')}
                      className="text-[11px] text-slate-400 hover:text-slate-200 underline ml-2"
                    >
                      Mặc định
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="mt-6 flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-4">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleOpenAddChild(selectedNode)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 border border-brand-500/30 transition-all cursor-pointer"
                  title="Thêm một nhánh con mới trực thuộc nhánh này"
                >
                  <Plus size={13} />
                  Thêm nhánh con
                </button>

                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`Bạn có chắc muốn xóa nhánh "${selectedNode.label}" và các nhánh con của nó?`)) {
                      handleDeleteNode(selectedNode.id);
                    }
                  }}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-rose-400 hover:bg-rose-500/15 border border-rose-500/30 transition-all cursor-pointer"
                  title="Xóa nhánh này"
                >
                  <Trash2 size={13} />
                  Xóa
                </button>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsEditingNode(false);
                    setSelectedNode(null);
                  }}
                  className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
                >
                  Hủy
                </button>
                <button
                  type="button"
                  onClick={handleSaveNodeEdit}
                  className="inline-flex items-center gap-1 rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-600 shadow-md shadow-brand-500/20"
                >
                  <Check size={13} />
                  Áp dụng
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL THÊM NHÁNH CON ─────────────────────────────────────────── */}
      {isAddingChild && selectedNode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-[rgba(90,108,240,0.25)] bg-[#141424] p-5 shadow-2xl animate-scale-in">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2 text-brand-300 font-semibold text-sm">
                <Plus size={16} />
                <span>Thêm nhánh con vào &quot;{selectedNode.label}&quot;</span>
              </div>
              <button
                onClick={() => {
                  setIsAddingChild(false);
                  setSelectedNode(null);
                }}
                className="rounded-lg p-1 text-slate-400 hover:bg-white/10 hover:text-slate-200"
              >
                <X size={16} />
              </button>
            </div>

            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Tên nhánh con mới *
                </label>
                <input
                  type="text"
                  value={formLabel}
                  onChange={(e) => setFormLabel(e.target.value)}
                  placeholder="Nhập tên nhánh con..."
                  className="w-full rounded-lg border border-white/10 bg-surface-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-brand-400 focus:outline-none"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Mô tả / Ngữ cảnh (tùy chọn)
                </label>
                <textarea
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  placeholder="Nhập nội dung giải thích..."
                  rows={2}
                  className="w-full rounded-lg border border-white/10 bg-surface-800 px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-brand-400 focus:outline-none resize-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5 flex items-center gap-1.5">
                  <Palette size={13} />
                  Màu sắc nhánh
                </label>
                <div className="flex items-center gap-2">
                  {BRANCH_COLORS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setFormColor(c)}
                      className={cn(
                        'w-6 h-6 rounded-full transition-transform cursor-pointer border-2',
                        formColor === c ? 'scale-125 border-white shadow-md' : 'border-transparent hover:scale-110'
                      )}
                      style={{ backgroundColor: c }}
                      title={c}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-end gap-2 border-t border-white/10 pt-4">
              <button
                type="button"
                onClick={() => {
                  setIsAddingChild(false);
                  setSelectedNode(null);
                }}
                className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleConfirmAddChild}
                disabled={!formLabel.trim()}
                className="inline-flex items-center gap-1 rounded-lg bg-brand-500 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-brand-600 disabled:opacity-50 shadow-md shadow-brand-500/20"
              >
                <Plus size={13} />
                Thêm nhánh
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL THÊM NHÁNH CHÍNH (ROOT) ─────────────────────────────────── */}
      {isAddingRoot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-[rgba(90,108,240,0.25)] bg-[#141424] p-5 shadow-2xl animate-scale-in">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2 text-brand-300 font-semibold text-sm">
                <FolderPlus size={16} />
                <span>Thêm nhánh chính / Chủ đề mới</span>
              </div>
              <button
                onClick={() => setIsAddingRoot(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-white/10 hover:text-slate-200"
              >
                <X size={16} />
              </button>
            </div>

            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Tên chủ đề / nhánh chính *
                </label>
                <input
                  type="text"
                  value={formLabel}
                  onChange={(e) => setFormLabel(e.target.value)}
                  placeholder="Nhập tên chủ đề..."
                  className="w-full rounded-lg border border-white/10 bg-surface-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-brand-400 focus:outline-none"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Mô tả tổng quan (tùy chọn)
                </label>
                <textarea
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  placeholder="Nhập phần giải thích..."
                  rows={2}
                  className="w-full rounded-lg border border-white/10 bg-surface-800 px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-brand-400 focus:outline-none resize-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5 flex items-center gap-1.5">
                  <Palette size={13} />
                  Màu sắc nhánh
                </label>
                <div className="flex items-center gap-2">
                  {BRANCH_COLORS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setFormColor(c)}
                      className={cn(
                        'w-6 h-6 rounded-full transition-transform cursor-pointer border-2',
                        formColor === c ? 'scale-125 border-white shadow-md' : 'border-transparent hover:scale-110'
                      )}
                      style={{ backgroundColor: c }}
                      title={c}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-end gap-2 border-t border-white/10 pt-4">
              <button
                type="button"
                onClick={() => setIsAddingRoot(false)}
                className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleConfirmAddRoot}
                disabled={!formLabel.trim()}
                className="inline-flex items-center gap-1 rounded-lg bg-brand-500 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-brand-600 disabled:opacity-50 shadow-md shadow-brand-500/20"
              >
                <Plus size={13} />
                Tạo nhánh chính
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
