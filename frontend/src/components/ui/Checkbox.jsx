import React from 'react';
import { cn } from '@/lib/utils';
import { Check } from 'lucide-react';

export const Checkbox = React.forwardRef(function Checkbox(
  {
    label,
    description,
    className,
    checked,
    id,
    disabled = false,
    onChange,
    ...props
  },
  ref
) {
  const checkboxId = id || (label ? `check-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <label
      htmlFor={checkboxId}
      className={cn(
        'inline-flex items-start gap-3 cursor-pointer select-none group',
        disabled && 'opacity-50 cursor-not-allowed pointer-events-none',
        className
      )}
    >
      <div className="relative flex items-center justify-center mt-0.5">
        <input
          ref={ref}
          id={checkboxId}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={onChange}
          className="peer sr-only"
          {...props}
        />
        <div className="w-4 h-4 rounded-sm border border-border bg-surface-elevated peer-checked:bg-accent-primary peer-checked:border-accent-primary peer-focus-visible:ring-2 peer-focus-visible:ring-accent-primary transition-all flex items-center justify-center">
          {checked && <Check className="w-3 h-3 text-white stroke-[3]" />}
        </div>
      </div>
      {(label || description) && (
        <div className="flex flex-col">
          {label && (
            <span className="text-sm font-sans text-text-primary group-hover:text-white transition-colors">
              {label}
            </span>
          )}
          {description && (
            <span className="text-xs font-mono text-text-secondary mt-0.5">{description}</span>
          )}
        </div>
      )}
    </label>
  );
});

export default Checkbox;

