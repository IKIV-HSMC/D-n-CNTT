'use client';

import React, { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { BrainCircuit, Loader2 } from 'lucide-react';
import { useAuth } from '@/components/auth/AuthProvider';
import { cn } from '@/lib/utils';

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) router.replace('/documents');
  }, [user, router]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === 'login') await login(email, password);
      else await register(email, password);
      router.replace('/documents');
    } catch (cause: unknown) {
      const err = cause as { displayMessage?: string; response?: { data?: { detail?: string } } };
      setError(err.displayMessage || err.response?.data?.detail || 'Không thể xác thực tài khoản');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || user) {
    return <div className="min-h-screen flex items-center justify-center text-slate-400">Đang kiểm tra phiên đăng nhập...</div>;
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4 py-12">
      <section className="glass-card w-full max-w-md p-8">
        <div className="flex items-center justify-center gap-2 mb-2">
          <BrainCircuit className="text-brand-400" size={28} />
          <h1 className="text-2xl font-bold text-slate-100">DocMind AI</h1>
        </div>
        <p className="text-center text-sm text-slate-400 mb-8">
          {mode === 'login' ? 'Đăng nhập để tiếp tục học tập' : 'Tạo tài khoản để lưu tài liệu và tiến độ học'}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block text-sm text-slate-300">
            Email
            <input
              type="email"
              autoComplete="email"
              required
              maxLength={320}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-1 w-full px-3 py-2.5 bg-surface-700 border border-[rgba(90,108,240,0.2)] rounded-lg text-slate-100 focus:outline-none focus:border-brand-500"
            />
          </label>
          <label className="block text-sm text-slate-300">
            Mật khẩu
            <input
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
              minLength={8}
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1 w-full px-3 py-2.5 bg-surface-700 border border-[rgba(90,108,240,0.2)] rounded-lg text-slate-100 focus:outline-none focus:border-brand-500"
            />
            {mode === 'register' && <span className="block mt-1 text-xs text-slate-500">Tối thiểu 8 ký tự.</span>}
          </label>

          {error && <p role="alert" className="text-sm text-red-300">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className={cn('w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium text-white bg-brand-600 hover:bg-brand-500 transition-colors disabled:opacity-60')}
          >
            {submitting && <Loader2 size={16} className="animate-spin" />}
            {mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}
          </button>
        </form>

        <p className="text-sm text-center text-slate-400 mt-6">
          {mode === 'login' ? 'Chưa có tài khoản?' : 'Đã có tài khoản?'}{' '}
          <button
            type="button"
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null); }}
            className="text-brand-300 hover:text-brand-200 font-medium"
          >
            {mode === 'login' ? 'Đăng ký' : 'Đăng nhập'}
          </button>
        </p>
      </section>
    </main>
  );
}
