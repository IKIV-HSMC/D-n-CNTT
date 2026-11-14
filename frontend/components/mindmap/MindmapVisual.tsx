'use client';

import React, { useRef, useMemo, useState } from 'react';
import { Download, Image as ImageIcon, ZoomIn, ZoomOut, RotateCcw, FileCode } from 'lucide-react';
import { MindmapNode } from '@/lib/types';
import { cn } from '@/lib/utils';

interface MindmapVisualProps {
  nodes: MindmapNode[];
  filename?: string;
}

interface LayoutNode {
  id: string;
  label: string;
  parentId: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  depth: number;
  colorIndex: number;
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

export function MindmapVisual({ nodes, filename = 'docmind' }: MindmapVisualProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [zoom, setZoom] = useState(1);
  const [exporting, setExporting] = useState(false);

  // ── Tính toán tọa độ cây Mindmap ──────────────────────────────────────────
  const { layoutNodes, layoutEdges, viewBoxWidth, viewBoxHeight } = useMemo(() => {
    if (!nodes || nodes.length === 0) {
      return { layoutNodes: [], layoutEdges: [], viewBoxWidth: 800, viewBoxHeight: 400 };
    }

    // Xây dựng cây quan hệ cha-con
    const childrenMap = new Map<string | null, MindmapNode[]>();
    const nodeMap = new Map<string, MindmapNode>();

    nodes.forEach((n) => {
      nodeMap.set(n.id, n);
      const pid = n.parent_id ?? null;
      if (!childrenMap.has(pid)) childrenMap.set(pid, []);
      childrenMap.get(pid)!.push(n);
    });

    // Tìm các node gốc
    let roots = childrenMap.get(null) ?? [];
    if (roots.length === 0 && nodes.length > 0) {
      // Fallback nếu không có parent_id null
      roots = [nodes[0]];
    }

    const HORIZONTAL_GAP = 90;
    const VERTICAL_GAP = 28;
    const NODE_HEIGHT = 42;
    const PADDING = 60;

    let currentY = PADDING;
    const calculatedNodes: LayoutNode[] = [];
    const calculatedEdges: LayoutEdge[] = [];
    const idToLayoutNode = new Map<string, LayoutNode>();

    // Đệ quy tính vị trí Y cho các node
    function layoutSubtree(
      node: MindmapNode,
      depth: number,
      colorIdx: number
    ): { y: number; height: number } {
      const children = childrenMap.get(node.id) ?? [];
      const textLen = (node.label || '').length;
      const width = Math.max(130, Math.min(260, textLen * 9 + 36));

      if (children.length === 0) {
        // Node lá
        const y = currentY;
        currentY += NODE_HEIGHT + VERTICAL_GAP;

        const layoutNode: LayoutNode = {
          id: node.id,
          label: node.label,
          parentId: node.parent_id,
          x: 0, // sẽ gán x sau
          y,
          width,
          height: NODE_HEIGHT,
          depth,
          colorIndex: colorIdx,
        };
        calculatedNodes.push(layoutNode);
        idToLayoutNode.set(node.id, layoutNode);
        return { y: y + NODE_HEIGHT / 2, height: NODE_HEIGHT };
      }

      // Có con: vị trí Y của cha là trung bình vị trí Y của các con
      const childYPositions: number[] = [];
      children.forEach((child, idx) => {
        const branchColor = depth === 0 ? idx % BRANCH_COLORS.length : colorIdx;
        const res = layoutSubtree(child, depth + 1, branchColor);
        childYPositions.push(res.y);
      });

      const avgY = childYPositions.reduce((a, b) => a + b, 0) / childYPositions.length;
      const nodeY = avgY - NODE_HEIGHT / 2;

      const layoutNode: LayoutNode = {
        id: node.id,
        label: node.label,
        parentId: node.parent_id,
        x: 0,
        y: nodeY,
        width,
        height: NODE_HEIGHT,
        depth,
        colorIndex: colorIdx,
      };
      calculatedNodes.push(layoutNode);
      idToLayoutNode.set(node.id, layoutNode);
      return { y: avgY, height: NODE_HEIGHT };
    }

    // Duyệt qua các root
    roots.forEach((root, idx) => {
      layoutSubtree(root, 0, idx % BRANCH_COLORS.length);
      currentY += 40; // khoảng cách giữa các cây gốc
    });

    // Tính tọa độ X dựa theo depth
    // Tìm max width của mỗi depth level để căn thẳng hàng
    const depthMaxWidth = new Map<number, number>();
    calculatedNodes.forEach((n) => {
      const maxW = depthMaxWidth.get(n.depth) ?? 0;
      if (n.width > maxW) depthMaxWidth.set(n.depth, n.width);
    });

    // Tính offset X cho từng depth
    const depthXOffset = new Map<number, number>();
    let runningX = PADDING;
    const maxDepth = Math.max(...calculatedNodes.map((n) => n.depth), 0);

    for (let d = 0; d <= maxDepth; d++) {
      depthXOffset.set(d, runningX);
      const w = depthMaxWidth.get(d) ?? 160;
      runningX += w + HORIZONTAL_GAP;
    }

    calculatedNodes.forEach((n) => {
      n.x = depthXOffset.get(n.depth) ?? PADDING;
    });

    // Tạo edges nối cha -> con
    calculatedNodes.forEach((n) => {
      if (n.parentId && idToLayoutNode.has(n.parentId)) {
        const parent = idToLayoutNode.get(n.parentId)!;
        calculatedEdges.push({
          id: `e-${parent.id}-${n.id}`,
          source: parent,
          target: n,
          color: BRANCH_COLORS[n.colorIndex % BRANCH_COLORS.length],
        });
      }
    });

    // Tính viewBox tổng thể
    let maxX = 800;
    let maxY = 400;
    calculatedNodes.forEach((n) => {
      if (n.x + n.width + PADDING > maxX) maxX = n.x + n.width + PADDING;
      if (n.y + n.height + PADDING > maxY) maxY = n.y + n.height + PADDING;
    });

    return {
      layoutNodes: calculatedNodes,
      layoutEdges: calculatedEdges,
      viewBoxWidth: maxX,
      viewBoxHeight: Math.max(maxY, 350),
    };
  }, [nodes]);

  // ── Xuất ảnh PNG chất lượng cao (2x DPI) ──────────────────────────────────
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
        const scale = 2; // Độ nét gấp đôi (HD)
        const canvas = document.createElement('canvas');
        canvas.width = viewBoxWidth * scale;
        canvas.height = viewBoxHeight * scale;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Vẽ nền tối đồng bộ UI
        ctx.fillStyle = '#0f0f1a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Vẽ lưới chấm mờ nhẹ phía sau
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

        // Tạo liên kết tải về
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

  // ── Xuất file vector SVG ───────────────────────────────────────────────────
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
    <div className="flex flex-col h-full space-y-3">
      {/* Thanh công cụ xuất ảnh & phóng to */}
      <div className="flex items-center justify-between px-2 py-1 bg-surface-800/40 rounded-xl border border-[rgba(90,108,240,0.12)]">
        <div className="flex items-center gap-2">
          <button
            onClick={exportAsPng}
            disabled={exporting}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 border border-brand-500/30 transition-all cursor-pointer disabled:opacity-50"
            title="Xuất thành ảnh PNG chất lượng cao"
          >
            <ImageIcon size={14} />
            {exporting ? 'Đang xuất...' : 'Xuất ảnh PNG'}
          </button>

          <button
            onClick={exportAsSvg}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-700 hover:bg-surface-600 text-slate-300 border border-[rgba(255,255,255,0.08)] transition-all cursor-pointer"
            title="Xuất file vector SVG không vỡ nét"
          >
            <FileCode size={14} />
            Xuất SVG
          </button>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setZoom((z) => Math.max(0.4, z - 0.15))}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-all"
            title="Thu nhỏ"
          >
            <ZoomOut size={15} />
          </button>
          <span className="text-[11px] font-mono text-slate-400 min-w-[42px] text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom((z) => Math.min(2.0, z + 0.15))}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-all"
            title="Phóng to"
          >
            <ZoomIn size={15} />
          </button>
          <button
            onClick={() => setZoom(1)}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-all ml-1"
            title="Đặt lại zoom"
          >
            <RotateCcw size={13} />
          </button>
        </div>
      </div>

      {/* Khu vực vẽ sơ đồ SVG */}
      <div className="flex-1 overflow-auto rounded-xl border border-[rgba(90,108,240,0.12)] bg-[#0f0f1a] relative min-h-[360px] p-4 flex items-center justify-center">
        <div
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: 'top left',
            transition: 'transform 0.15s ease-out',
          }}
        >
          <svg
            ref={svgRef}
            width={viewBoxWidth}
            height={viewBoxHeight}
            viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
            xmlns="http://www.w3.org/2000/svg"
            className="select-none block"
            style={{ backgroundColor: '#0f0f1a' }}
          >
            <defs>
              {/* Lưới chấm nền */}
              <pattern id="dot-grid" width="24" height="24" patternUnits="userSpaceOnUse">
                <circle cx="2" cy="2" r="1" fill="rgba(255,255,255,0.06)" />
              </pattern>

              {/* Gradient cho node gốc */}
              <linearGradient id="root-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#4f46e5" />
                <stop offset="100%" stopColor="#7c3aed" />
              </linearGradient>

              {/* Filter đổ bóng */}
              <filter id="node-shadow" x="-10%" y="-10%" width="130%" height="130%">
                <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="#000000" floodOpacity="0.4" />
              </filter>
            </defs>

            {/* Nền lưới */}
            <rect width={viewBoxWidth} height={viewBoxHeight} fill="#0f0f1a" />
            <rect width={viewBoxWidth} height={viewBoxHeight} fill="url(#dot-grid)" />

            {/* Các đường nhánh cong (Bézier curves) */}
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
                const color = BRANCH_COLORS[n.colorIndex % BRANCH_COLORS.length];

                return (
                  <g
                    key={n.id}
                    transform={`translate(${n.x}, ${n.y})`}
                    filter="url(#node-shadow)"
                    className="cursor-pointer"
                  >
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

                    {/* Vạch màu bên trái cho node con */}
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

                    {/* Nhãn chữ */}
                    <text
                      x={isRoot ? n.width / 2 : 14}
                      y={n.height / 2 + 4}
                      textAnchor={isRoot ? 'middle' : 'start'}
                      fill={isRoot ? '#ffffff' : '#e2e8f0'}
                      fontSize={isRoot ? '13' : '12'}
                      fontWeight={isRoot ? '700' : '500'}
                      fontFamily="Inter, -apple-system, sans-serif"
                    >
                      {n.label}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
      </div>
    </div>
  );
}
