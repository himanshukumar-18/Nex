import React from 'react';
import { cn } from '@/lib/utils';

const badgeVariants = {
  default: 'bg-surface-elevated text-text-secondary border-border',
  accent: 'bg-accent-primary/15 text-accent-highlight border-accent-primary/40',
  cyan: 'bg-accent-secondary/15 text-accent-secondary border-accent-secondary/40',
  success: 'bg-status-success/15 text-status-success border-status-success/40',
  warning: 'bg-status-warning/15 text-status-warning border-status-warning/40',
  danger: 'bg-status-danger/15 text-status-danger border-status-danger/40',
  outline: 'bg-transparent text-text-primary border-border',
};

const dotVariants = {
  default: 'bg-text-secondary',
  accent: 'bg-accent-primary',
  cyan: 'bg-accent-secondary',
  success: 'bg-status-success',
  warning: 'bg-status-warning',
  danger: 'bg-status-danger',
  outline: 'bg-text-primary',
};

const badgeSizes = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-0.5 text-xs',
};

export function Badge({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
  className,
  ...props
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-mono uppercase tracking-wider font-semibold border rounded-sm select-none',
        badgeVariants[variant] || badgeVariants.default,
        badgeSizes[size] || badgeSizes.md,
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn(
            'w-1.5 h-1.5 rounded-full shrink-0',
            dotVariants[variant] || dotVariants.default
          )}
        />
      )}
      <span>{children}</span>
    </span>
  );
}

export default Badge;

