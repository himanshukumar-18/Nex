import React from 'react';
import { cn } from '@/lib/utils';

export const Textarea = React.forwardRef(function Textarea(
  {
    label,
    error,
    helperText,
    className,
    id,
    disabled = false,
    rows = 4,
    ...props
  },
  ref
) {
  const textareaId = id || (label ? `textarea-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div className="w-full flex flex-col gap-1.5">
      {label && (
        <label
          htmlFor={textareaId}
          className="text-xs font-mono font-medium text-text-secondary tracking-wider uppercase flex items-center justify-between"
        >
          <span>{label}</span>
          {props.required && <span className="text-status-danger">*</span>}
        </label>
      )}
      <textarea
        ref={ref}
        id={textareaId}
        rows={rows}
        disabled={disabled}
        className={cn(
          'w-full bg-surface-elevated text-text-primary placeholder-text-secondary/50 border border-border rounded px-3 py-2 text-sm font-sans focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed resize-y',
          error && 'border-status-danger focus:border-status-danger focus:ring-status-danger',
          className
        )}
        {...props}
      />
      {error ? (
        <p className="text-xs text-status-danger font-mono mt-0.5">{error}</p>
      ) : helperText ? (
        <p className="text-xs text-text-secondary/70 font-mono mt-0.5">{helperText}</p>
      ) : null}
    </div>
  );
});

export default Textarea;

