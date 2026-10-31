import React from 'react';
import { cn } from '@/lib/utils';
import { Terminal } from 'lucide-react';
import Button from '@/components/ui/Button';

export function EmptyState({
  icon,
  title = 'No Data Available',
  description = 'No records found matching the active criteria.',
  actionLabel,
  onAction,
  className,
}) {
  return (
    <div
      className={cn(
        'w-full flex flex-col items-center justify-center p-12 text-center border border-dashed border-border rounded bg-surface-elevated/20',
        className
      )}
    >
      <div className="w-12 h-12 rounded bg-surface-elevated border border-border flex items-center justify-center text-accent-highlight mb-4 shadow-brutal">
        {icon || <Terminal className="w-6 h-6 text-accent-primary" />}
      </div>
      <h3 className="text-sm font-display font-semibold uppercase tracking-wider text-text-primary mb-1">
        {title}
      </h3>
      <p className="text-xs font-mono text-text-secondary max-w-sm mb-6 leading-relaxed">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button variant="secondary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

export default EmptyState;

