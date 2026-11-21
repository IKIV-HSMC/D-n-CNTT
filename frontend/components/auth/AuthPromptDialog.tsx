'use client';

import React, { FormEvent, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Loader2, X } from 'lucide-react';
import { useAuth } from '@/components/auth/AuthProvider';
import { GoogleSignInButton } from '@/components/auth/GoogleSignInButton';
import { cn } from '@/lib/utils';

interface AuthPromptDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  message: string;
}

export function AuthPromptDialog({ open, onOpenChange, message }: AuthPromptDialogProps) {
  const { login, googleLogin, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('register');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === 'login') await login(email, password);
      else await register(email, password);
      onOpenChange(false);
    } catch (cause: unknown) {
      const apiError = cause as { displayMessage?: string; response?: { data?: { detail?: string } } };
      setError(apiError.displayMessage || apiError.response?.data?.detail || 'Không thể xác thực tài khoản');
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogleLogin = async (credential: string) => {
    await googleLogin(credential);
    onOpenChange(false);
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[70] bg-black/70 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-[71] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 glass-card p-7 shadow-2xl">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-xl font-semibold text-slate-100">
                {mode === 'register' ? 'Tạo tài khoản miễn phí' : 'Đăng nhập'}
              </Dialog.Title>
              <Dialog.Description className="mt-2 text-sm leading-relaxed text-slate-400">
                {message}
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button type="button" className="rounded-lg p-1.5 text-slate-500 hover:bg-white/5 hover:text-slate-200" aria-label="Đóng">
                <X size={18} />
              </button>
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <label className="block text-sm text-slate-300">
              Email
              <input
                type="email"
                autoComplete="email"
                required
                maxLength={320}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-1 w-full rounded-lg border border-[rgba(90,108,240,0.2)] bg-surface-700 px-3 py-2.5 text-slate-100 focus:border-brand-500 focus:outline-none"
              />
            </label>
            <label className="block text-sm text-slate-300">
              Mật khẩu
              <input
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                minLength={mode === 'register' ? 8 : undefined}
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-1 w-full rounded-lg border border-[rgba(90,108,240,0.2)] bg-surface-700 px-3 py-2.5 text-slate-100 focus:border-brand-500 focus:outline-none"
              />
              {mode === 'register' && <span className="mt-1 block text-xs text-slate-500">Tối thiểu 8 ký tự.</span>}
            </label>
            {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
            <button
              type="submit"
              disabled={submitting}
              className={cn('inline-flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-60')}
            >
              {submitting && <Loader2 size={16} className="animate-spin" />}
              {mode === 'register' ? 'Tạo tài khoản' : 'Đăng nhập'}
            </button>
          </form>

          <div className="my-5 flex items-center gap-3 text-xs text-slate-500">
            <span className="h-px flex-1 bg-white/10" />
            <span>hoặc</span>
            <span className="h-px flex-1 bg-white/10" />
          </div>
          <GoogleSignInButton onSuccess={handleGoogleLogin} />

          <p className="mt-5 text-center text-sm text-slate-400">
            {mode === 'register' ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'}{' '}
            <button
              type="button"
              onClick={() => { setMode(mode === 'register' ? 'login' : 'register'); setError(null); }}
              className="font-medium text-brand-300 hover:text-brand-200"
            >
              {mode === 'register' ? 'Đăng nhập' : 'Đăng ký'}
            </button>
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
