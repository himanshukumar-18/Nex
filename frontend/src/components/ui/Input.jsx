import React from 'react';
import { cn } from '@/lib/utils';

export const Input = React.forwardRef(function Input(
  {
    label,
    error,
    helperText,
    leftIcon,
    rightIcon,
    className,
    id,
    disabled = false,
    ...props
  },
  ref
) {
  const inputId = id || (label ? `input-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div className="w-full flex flex-col gap-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="text-xs font-mono font-medium text-text-secondary tracking-wider uppercase flex items-center justify-between"
        >
          <span>{label}</span>
          {props.required && <span className="text-status-danger">*</span>}
        </label>
      )}
      <div className="relative flex items-center">
        {leftIcon && (
          <div className="absolute left-3 text-text-secondary pointer-events-none flex items-center">
            {leftIcon}
          </div>
        )}
        <input
          ref={ref}
          id={inputId}
          disabled={disabled}
          className={cn(
            'w-full bg-surface-elevated text-text-primary placeholder-text-secondary/50 border border-border rounded px-3 py-2 text-sm font-sans focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
            leftIcon && 'pl-9',
            rightIcon && 'pr-9',
            error && 'border-status-danger focus:border-status-danger focus:ring-status-danger',
            className
          )}
          {...props}
        />
        {rightIcon && (
          <div className="absolute right-3 text-text-secondary pointer-events-none flex items-center">
            {rightIcon}
          </div>
        )}
      </div>
      {error ? (
        <p className="text-xs text-status-danger font-mono mt-0.5">{error}</p>
      ) : helperText ? (
        <p className="text-xs text-text-secondary/70 font-mono mt-0.5">{helperText}</p>
      ) : null}
    </div>
  );
});

export default Input;

