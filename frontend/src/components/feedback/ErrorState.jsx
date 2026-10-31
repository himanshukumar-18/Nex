import React from 'react';
import { cn } from '@/lib/utils';
import { AlertCircle, RefreshCw } from 'lucide-react';
import Button from '@/components/ui/Button';

export function ErrorState({
  title = 'Service Error',
  message = 'Failed to load data from the NEX backend service.',
  errorCode,
  onRetry,
  className,
}) {
  return (
    <div
      className={cn(
        'w-full flex flex-col items-center justify-center p-8 text-center border border-status-danger/40 bg-status-danger/5 rounded',
        className
      )}
    >
      <div className="w-10 h-10 rounded bg-status-danger/10 border border-status-danger/40 flex items-center justify-center text-status-danger mb-3">
        <AlertCircle className="w-5 h-5" />
      </div>
      <h3 className="text-sm font-display font-semibold uppercase tracking-wider text-text-primary mb-1">
        {title}
      </h3>
      <p className="text-xs font-mono text-text-secondary max-w-md mb-2">{message}</p>
      {errorCode && (
        <span className="text-[10px] font-mono text-status-danger uppercase px-2 py-0.5 bg-status-danger/10 border border-status-danger/30 rounded mb-4">
          CODE: {errorCode}
        </span>
      )}
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          onClick={onRetry}
        >
          Retry Request
        </Button>
      )}
    </div>
  );
}

export default ErrorState;

