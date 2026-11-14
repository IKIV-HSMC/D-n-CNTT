import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'DocMind – AI Chuyển Tài Liệu Thành Mindmap',
  description: 'Ứng dụng AI giúp chuyển tài liệu học tập (PDF, Word, PowerPoint) thành Mindmap và Flashcard thông minh.',
  keywords: ['mindmap', 'flashcard', 'AI', 'học tập', 'tài liệu'],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi" className="dark">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
