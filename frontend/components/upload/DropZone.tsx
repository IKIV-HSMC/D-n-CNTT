'use client';

import React, { useCallback, useRef, useState } from 'react';
import { Upload, FileText, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
};

const ACCEPTED_EXTENSIONS = new Set(['.pdf', '.docx', '.pptx']);
const MAX_MB = Number(process.env.NEXT_PUBLIC_MAX_MB ?? 20);
const MAX_BYTES = MAX_MB * 1024 * 1024;

interface DropZoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  multiple?: boolean;
}

export function DropZone({ onFilesSelected, disabled, multiple = true }: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFiles = useCallback((files: File[]): File[] => {
    const valid: File[] = [];
    const errors: string[] = [];

    for (const file of files) {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!ACCEPTED_EXTENSIONS.has(ext)) {
        errors.push(`"${file.name}": Định dạng không hỗ trợ`);
        continue;
      }
      if (file.size > MAX_BYTES) {
        errors.push(`"${file.name}": Vượt quá ${MAX_MB}MB`);
        continue;
      }
      if (file.size === 0) {
        errors.push(`"${file.name}": File rỗng`);
        continue;
      }
      valid.push(file);
    }

    if (errors.length > 0) {
      setValidationError(errors.join(' • '));
      setTimeout(() => setValidationError(null), 5000);
    } else {
      setValidationError(null);
    }

    return valid;
  }, []);

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return;
    const valid = validateFiles(Array.from(files));
    if (valid.length > 0) onFilesSelected(valid);
  }, [validateFiles, onFilesSelected]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    handleFiles(e.dataTransfer.files);
  }, [handleFiles, disabled]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  return (
    <div className="space-y-3">
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !disabled && inputRef.current?.click()}
        className={cn(
          'relative flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-12 cursor-pointer transition-all duration-300',
          'border-[rgba(90,108,240,0.25)] hover:border-[rgba(90,108,240,0.6)]',
          'hover:bg-[rgba(90,108,240,0.05)] hover:shadow-[0_0_40px_rgba(90,108,240,0.15)]',
          isDragging && 'drop-active',
          disabled && 'opacity-50 cursor-not-allowed',
        )}
      >
        {/* Background decoration */}
        <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
          <div className="absolute top-0 left-1/4 w-32 h-32 bg-brand-500/5 rounded-full blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-24 h-24 bg-purple-500/5 rounded-full blur-3xl" />
        </div>

        {/* Icon */}
        <div className={cn(
          'flex items-center justify-center w-20 h-20 rounded-2xl transition-all duration-300',
          'bg-[rgba(90,108,240,0.1)] border border-[rgba(90,108,240,0.2)]',
          isDragging && 'scale-110 bg-[rgba(90,108,240,0.2)]',
        )}>
          <Upload
            size={36}
            className={cn(
              'transition-all duration-300',
              isDragging ? 'text-brand-400 -translate-y-1' : 'text-brand-500',
            )}
          />
        </div>

        {/* Text */}
        <div className="text-center z-10">
          <p className="text-lg font-semibold text-slate-200">
            {isDragging ? 'Thả file vào đây' : 'Kéo & thả file vào đây'}
          </p>
          <p className="mt-1 text-sm text-slate-400">
            hoặc{' '}
            <span className="text-brand-400 font-medium hover:text-brand-300">
              chọn từ máy tính
            </span>
          </p>
          <div className="mt-3 flex items-center justify-center gap-2">
            {['.PDF', '.DOCX', '.PPTX'].map((ext) => (
              <span
                key={ext}
                className="px-2 py-0.5 text-xs font-mono text-brand-300 bg-brand-500/10 rounded border border-brand-500/20"
              >
                {ext}
              </span>
            ))}
            <span className="text-xs text-slate-500">• Tối đa {MAX_MB}MB</span>
          </div>
        </div>

        <input
          ref={inputRef}
          type="file"
          multiple={multiple}
          accept=".pdf,.docx,.pptx"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
          disabled={disabled}
        />
      </div>

      {/* Validation error */}
      {validationError && (
        <div className="flex items-start gap-2 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 animate-fade-in">
          <AlertCircle size={16} className="text-red-400 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-red-300">{validationError}</p>
        </div>
      )}
    </div>
  );
}
