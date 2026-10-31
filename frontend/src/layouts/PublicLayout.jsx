import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import { Terminal } from 'lucide-react';
import ToastContainer from '@/components/feedback/Toast';

export function PublicLayout() {
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex flex-col font-sans antialiased selection:bg-accent-primary selection:text-white">
      {/* Header */}
      <header className="h-14 border-b border-border bg-bg-secondary flex items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded bg-surface-elevated border border-accent-primary flex items-center justify-center">
            <Terminal className="w-4 h-4 text-accent-secondary" />
          </div>
          <span className="font-display font-bold text-sm tracking-wider uppercase text-text-primary">
            NEX
          </span>
        </Link>

        <div className="flex items-center gap-4 text-xs font-mono">
          <Link to="/" className="text-text-secondary hover:text-white transition-colors">
            Workspace
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-bg-secondary py-4 px-6 text-center text-xs font-mono text-text-secondary">
        <span>NEX — Autonomous Intelligence for Software Engineering</span>
      </footer>

      <ToastContainer />
    </div>
  );
}

export default PublicLayout;

