'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Script from 'next/script';
import { Loader2 } from 'lucide-react';

interface GoogleCredentialResponse {
  credential?: string;
}

interface GoogleButtonOptions {
  type: 'standard';
  theme: 'filled_black';
  size: 'large';
  text: 'continue_with';
  shape: 'rectangular';
  width: number;
  locale: 'vi';
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
          }) => void;
          renderButton: (parent: HTMLElement, options: GoogleButtonOptions) => void;
        };
      };
    };
  }
}

interface GoogleSignInButtonProps {
  onSuccess: (credential: string) => Promise<void>;
}

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? '';

export function GoogleSignInButton({ onSuccess }: GoogleSignInButtonProps) {
  const buttonContainer = useRef<HTMLDivElement>(null);
  const onSuccessRef = useRef(onSuccess);
  const initialized = useRef(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onSuccessRef.current = onSuccess;
  }, [onSuccess]);

  const initializeButton = useCallback(() => {
    const google = window.google;
    const container = buttonContainer.current;
    if (!GOOGLE_CLIENT_ID || !google || !container || initialized.current) return;

    google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async ({ credential }) => {
        if (!credential) {
          setError('Google không trả về thông tin đăng nhập. Vui lòng thử lại.');
          return;
        }
        setError(null);
        setSubmitting(true);
        try {
          await onSuccessRef.current(credential);
        } catch (cause: unknown) {
          const apiError = cause as { displayMessage?: string; response?: { data?: { detail?: string } } };
          setError(apiError.displayMessage || apiError.response?.data?.detail || 'Không thể đăng nhập bằng Google');
        } finally {
          setSubmitting(false);
        }
      },
    });
    google.accounts.id.renderButton(container, {
      type: 'standard',
      theme: 'filled_black',
      size: 'large',
      text: 'continue_with',
      shape: 'rectangular',
      width: Math.max(200, Math.floor(container.getBoundingClientRect().width)),
      locale: 'vi',
    });
    initialized.current = true;
  }, []);

  if (!GOOGLE_CLIENT_ID) {
    return <p className="text-center text-xs text-slate-500">Đăng nhập Google chưa được cấu hình trên hệ thống này.</p>;
  }

  return (
    <div>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onReady={initializeButton}
        onError={() => setError('Không tải được dịch vụ đăng nhập Google. Vui lòng thử lại.')}
      />
      <div className={`relative flex min-h-10 justify-center ${submitting ? 'pointer-events-none opacity-60' : ''}`}>
        <div ref={buttonContainer} className="min-h-10 w-full" />
        {submitting && (
          <span className="absolute inset-0 flex items-center justify-center" aria-label="Đang đăng nhập">
            <Loader2 size={18} className="animate-spin text-brand-300" />
          </span>
        )}
      </div>
      {error && <p role="alert" className="mt-2 text-center text-sm text-red-300">{error}</p>}
    </div>
  );
}
