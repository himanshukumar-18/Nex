import React from 'react';
import { cn } from '@/lib/utils';
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';

const alertStyles = {
  info: {
    container: 'bg-accent-secondary/10 border-accent-secondary/40 text-text-primary',
    icon: <Info className="w-4 h-4 text-accent-secondary shrink-0" />,
  },
  success: {
    container: 'bg-status-success/10 border-status-success/40 text-text-primary',
    icon: <CheckCircle2 className="w-4 h-4 text-status-success shrink-0" />,
  },
  warning: {
    container: 'bg-status-warning/10 border-status-warning/40 text-text-primary',
    icon: <AlertTriangle className="w-4 h-4 text-status-warning shrink-0" />,
  },
  danger: {
    container: 'bg-status-danger/10 border-status-danger/40 text-text-primary',
    icon: <AlertCircle className="w-4 h-4 text-status-danger shrink-0" />,
  },
};

export function Alert({
  variant = 'info',
  title,
  children,
  onDismiss,
  className,
}) {
  const current = alertStyles[variant] || alertStyles.info;

  return (
    <div
      role="alert"
      className={cn(
        'w-full flex items-start gap-3 p-3.5 border rounded',
        current.container,
        className
      )}
    >
      <div className="mt-0.5">{current.icon}</div>
      <div className="flex-1 min-w-0">
        {title && (
          <h4 className="text-xs font-display font-semibold uppercase tracking-wider mb-0.5">
            {title}
          </h4>
        )}
        <div className="text-xs font-mono text-text-secondary leading-relaxed">{children}</div>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss alert"
          className="text-text-secondary hover:text-white p-0.5 rounded shrink-0 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}

export default Alert;

