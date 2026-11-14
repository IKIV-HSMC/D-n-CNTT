'use client';

import React from 'react';
import { Search, Filter, X } from 'lucide-react';
import { DocumentFilters, DocumentStatus, Subject } from '@/lib/types';

interface DocumentFiltersProps {
  filters: DocumentFilters;
  subjects: Subject[];
  onChange: (f: Partial<DocumentFilters>) => void;
  onReset: () => void;
}

const STATUS_OPTIONS: { value: DocumentStatus | ''; label: string }[] = [
  { value: '', label: 'Tất cả trạng thái' },
  { value: 'uploaded', label: 'Đã tải lên' },
  { value: 'extracting', label: 'Đang xử lý' },
  { value: 'extracted', label: 'Hoàn thành' },
  { value: 'failed', label: 'Thất bại' },
];

const TYPE_OPTIONS: { value: 'pdf' | 'docx' | 'pptx' | ''; label: string }[] = [
  { value: '', label: 'Tất cả loại file' },
  { value: 'pdf', label: 'PDF' },
  { value: 'docx', label: 'Word (DOCX)' },
  { value: 'pptx', label: 'PowerPoint (PPTX)' },
];

const selectCls = 'px-3 py-2 text-sm bg-surface-700 border border-[rgba(90,108,240,0.2)] rounded-lg text-slate-200 focus:outline-none focus:border-brand-500 transition-colors';

export function DocumentFiltersBar({ filters, subjects, onChange, onReset }: DocumentFiltersProps) {
  const hasActiveFilter = filters.search || filters.status || filters.file_type || filters.subject_id;

  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Search */}
      <div className="relative flex-1 min-w-[200px]">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          placeholder="Tìm theo tên file..."
          value={filters.search}
          onChange={(e) => onChange({ search: e.target.value, page: 1 })}
          className="w-full pl-9 pr-4 py-2 text-sm bg-surface-700 border border-[rgba(90,108,240,0.2)] rounded-lg text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
        />
      </div>

      {/* Status filter */}
      <select
        value={filters.status}
        onChange={(e) => onChange({ status: e.target.value as DocumentStatus | '', page: 1 })}
        className={selectCls}
      >
        {STATUS_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* File type filter */}
      <select
        value={filters.file_type}
        onChange={(e) => onChange({ file_type: e.target.value as 'pdf' | 'docx' | 'pptx' | '', page: 1 })}
        className={selectCls}
      >
        {TYPE_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      <select
        value={filters.subject_id}
        onChange={(e) => onChange({ subject_id: e.target.value, page: 1 })}
        className={selectCls}
        aria-label="Lọc theo môn học"
      >
        <option value="">Tất cả môn học</option>
        {subjects.map((subject) => (
          <option key={subject.id} value={subject.id}>{subject.name}</option>
        ))}
      </select>

      {/* Reset */}
      {hasActiveFilter && (
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 px-3 py-2 text-sm text-slate-400 hover:text-slate-200 border border-[rgba(255,255,255,0.08)] rounded-lg hover:border-[rgba(255,255,255,0.15)] transition-all"
        >
          <X size={14} />
          Xóa bộ lọc
        </button>
      )}
    </div>
  );
}
