import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import { Terminal } from 'lucide-react';
import ToastContainer from '@/components/feedback/Toast';

export function AuthLayout() {
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex flex-col items-center justify-center p-6 font-sans antialiased selection:bg-accent-primary selection:text-white bg-grid-pattern">
      <div className="w-full max-w-md flex flex-col gap-6">
        {/* Identity Header */}
        <div className="flex flex-col items-center gap-2 text-center">
          <Link to="/" className="w-12 h-12 rounded bg-surface-elevated border border-accent-primary flex items-center justify-center shadow-brutal-accent mb-2">
            <Terminal className="w-6 h-6 text-accent-secondary" />
          </Link>
          <h1 className="font-display font-bold text-2xl tracking-wider uppercase text-text-primary">
            NEX PLATFORM
          </h1>
          <p className="font-mono text-xs text-text-secondary tracking-widest uppercase">
            Authentication & Security Gateway
          </p>
        </div>

        {/* Content Box */}
        <div className="bg-surface-elevated border-2 border-border p-6 rounded shadow-2xl">
          <Outlet />
        </div>

        {/* Bottom Tag */}
        <div className="text-center font-mono text-[11px] text-text-secondary">
          Understand → Plan → Build → Verify → Ship
        </div>
      </div>

      <ToastContainer />
    </div>
  );
}

export default AuthLayout;

