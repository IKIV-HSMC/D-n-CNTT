import React from 'react';
import { DocumentStatus } from '@/lib/types';
import { cn } from '@/lib/utils';
import { CheckCircle2, Clock, Loader2, XCircle } from 'lucide-react';

const config: Record<DocumentStatus, { label: string; icon: React.ReactNode; className: string }> = {
  uploaded: {
    label: 'Đã tải lên',
    icon: <Clock size={12} />,
    className: 'bg-blue-500/10 text-blue-300 border-blue-500/20',
  },
  extracting: {
    label: 'Đang xử lý',
    icon: <Loader2 size={12} className="animate-spin" />,
    className: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
  },
  extracted: {
    label: 'Hoàn thành',
    icon: <CheckCircle2 size={12} />,
    className: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
  },
  failed: {
    label: 'Thất bại',
    icon: <XCircle size={12} />,
    className: 'bg-red-500/10 text-red-300 border-red-500/20',
  },
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const { label, icon, className } = config[status];
  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border',
      className,
    )}>
      {icon}
      {label}
    </span>
  );
}
