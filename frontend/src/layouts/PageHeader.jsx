import React from 'react';
import { cn } from '@/lib/utils';

export function PageHeader({
  title,
  description,
  badge,
  actions,
  className,
}) {
  return (
    <div
      className={cn(
        'flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-border mb-6',
        className
      )}
    >
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <h1 className="text-xl sm:text-2xl font-display font-bold text-text-primary tracking-tight uppercase">
            {title}
          </h1>
          {badge}
        </div>
        {description && (
          <p className="text-xs sm:text-sm font-mono text-text-secondary leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3 shrink-0">{actions}</div>}
    </div>
  );
}

export default PageHeader;

