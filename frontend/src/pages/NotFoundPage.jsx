import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowLeft } from 'lucide-react';
import Button from '@/components/ui/Button';

export function NotFoundPage() {
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex items-center justify-center p-6 bg-grid-pattern">
      <div className="w-full max-w-lg bg-surface-elevated border-2 border-border p-8 rounded shadow-2xl flex flex-col items-center text-center gap-5">
        <div className="w-14 h-14 rounded bg-status-danger/10 border border-status-danger/40 flex items-center justify-center text-status-danger">
          <AlertTriangle className="w-7 h-7" />
        </div>

        <div className="flex flex-col gap-1">
          <span className="font-mono text-xs text-status-danger uppercase tracking-widest">
            ERROR 404 • ROUTE_NOT_FOUND
          </span>
          <h1 className="font-display font-bold text-2xl uppercase tracking-wider text-text-primary">
            RESOURCE NOT LOCATED
          </h1>
          <p className="font-mono text-xs text-text-secondary mt-1 max-w-md">
            The requested workspace endpoint does not exist or has been relocated within the NEX architecture.
          </p>
        </div>

        <div className="pt-2">
          <Link to="/">
            <Button
              variant="primary"
              size="sm"
              leftIcon={<ArrowLeft className="w-4 h-4" />}
            >
              Return to Workspace
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default NotFoundPage;

