import React from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';

export const Select = React.forwardRef(function Select(
  {
    label,
    error,
    helperText,
    options = [],
    className,
    id,
    disabled = false,
    children,
    ...props
  },
  ref
) {
  const selectId = id || (label ? `select-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div className="w-full flex flex-col gap-1.5">
      {label && (
        <label
          htmlFor={selectId}
          className="text-xs font-mono font-medium text-text-secondary tracking-wider uppercase flex items-center justify-between"
        >
          <span>{label}</span>
          {props.required && <span className="text-status-danger">*</span>}
        </label>
      )}
      <div className="relative flex items-center">
        <select
          ref={ref}
          id={selectId}
          disabled={disabled}
          className={cn(
            'w-full appearance-none bg-surface-elevated text-text-primary border border-border rounded px-3 py-2 pr-9 text-sm font-sans focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
            error && 'border-status-danger focus:border-status-danger focus:ring-status-danger',
            className
          )}
          {...props}
        >
          {options.length > 0
            ? options.map((opt) => (
                <option key={opt.value} value={opt.value} className="bg-bg-secondary text-text-primary">
                  {opt.label}
                </option>
              ))
            : children}
        </select>
        <div className="absolute right-3 text-text-secondary pointer-events-none flex items-center">
          <ChevronDown className="w-4 h-4" />
        </div>
      </div>
      {error ? (
        <p className="text-xs text-status-danger font-mono mt-0.5">{error}</p>
      ) : helperText ? (
        <p className="text-xs text-text-secondary/70 font-mono mt-0.5">{helperText}</p>
      ) : null}
    </div>
  );
});

export default Select;

