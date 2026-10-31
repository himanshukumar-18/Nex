import React from 'react';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

const variantClasses = {
  primary:
    'bg-accent-primary text-white border border-accent-primary hover:bg-opacity-90 hover:shadow-brutal-accent active:translate-y-0.5 active:shadow-none',
  secondary:
    'bg-surface-elevated text-text-primary border border-border hover:border-accent-primary hover:bg-opacity-80 active:translate-y-0.5',
  outline:
    'bg-transparent text-text-primary border border-border hover:border-text-primary hover:bg-surface-elevated active:translate-y-0.5',
  ghost:
    'bg-transparent text-text-secondary hover:text-text-primary hover:bg-surface-elevated border border-transparent',
  danger:
    'bg-status-danger text-white border border-status-danger hover:bg-opacity-90 hover:shadow-brutal-danger active:translate-y-0.5',
  cyan:
    'bg-accent-secondary text-bg-primary font-semibold border border-accent-secondary hover:bg-opacity-90 hover:shadow-brutal-cyan active:translate-y-0.5',
};

const sizeClasses = {
  sm: 'px-2.5 py-1 text-xs font-mono',
  md: 'px-4 py-2 text-sm font-medium',
  lg: 'px-6 py-2.5 text-base font-semibold',
};

export const Button = React.forwardRef(function Button(
  {
    children,
    className,
    variant = 'primary',
    size = 'md',
    isLoading = false,
    disabled = false,
    leftIcon = null,
    rightIcon = null,
    type = 'button',
    ...props
  },
  ref
) {
  const isDisabled = disabled || isLoading;

  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded transition-all duration-150 select-none focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-primary font-display uppercase tracking-wide',
        variantClasses[variant] || variantClasses.primary,
        sizeClasses[size] || sizeClasses.md,
        isDisabled && 'opacity-50 cursor-not-allowed pointer-events-none shadow-none translate-y-0',
        className
      )}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin text-current" />
      ) : (
        leftIcon && <span className="inline-flex shrink-0">{leftIcon}</span>
      )}
      <span>{children}</span>
      {!isLoading && rightIcon && <span className="inline-flex shrink-0">{rightIcon}</span>}
    </button>
  );
});

export default Button;

