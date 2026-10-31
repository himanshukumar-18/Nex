import React, { useEffect } from 'react';
import { useAppSelector, useAppDispatch } from '@/app/hooks';
import { removeToast } from '@/features/ui/uiSlice';
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';
import { cn } from '@/lib/utils';

const toastIcons = {
  success: <CheckCircle2 className="w-4 h-4 text-status-success" />,
  warning: <AlertTriangle className="w-4 h-4 text-status-warning" />,
  danger: <AlertCircle className="w-4 h-4 text-status-danger" />,
  info: <Info className="w-4 h-4 text-accent-secondary" />,
};

const toastBorders = {
  success: 'border-status-success/50',
  warning: 'border-status-warning/50',
  danger: 'border-status-danger/50',
  info: 'border-accent-secondary/50',
};

function ToastItem({ toast }) {
  const dispatch = useAppDispatch();

  useEffect(() => {
    if (toast.duration) {
      const timer = setTimeout(() => {
        dispatch(removeToast(toast.id));
      }, toast.duration);
      return () => clearTimeout(timer);
    }
  }, [toast, dispatch]);

  return (
    <div
      role="status"
      className={cn(
        'w-80 bg-surface-elevated border rounded shadow-2xl p-3 flex items-start gap-3 animate-in slide-in-from-right-5 fade-in duration-150',
        toastBorders[toast.type] || toastBorders.info
      )}
    >
      <div className="shrink-0 mt-0.5">{toastIcons[toast.type] || toastIcons.info}</div>
      <div className="flex-1 min-w-0">
        {toast.title && (
          <h4 className="text-xs font-display font-semibold text-text-primary tracking-wide">
            {toast.title}
          </h4>
        )}
        {toast.message && (
          <p className="text-xs font-mono text-text-secondary mt-0.5 leading-tight break-words">
            {toast.message}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={() => dispatch(removeToast(toast.id))}
        aria-label="Dismiss toast"
        className="text-text-secondary hover:text-white p-0.5 rounded shrink-0 transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useAppSelector((state) => state.ui.toasts);

  if (!toasts || toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-auto"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}

export default ToastContainer;

