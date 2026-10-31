import React from 'react';
import { cn } from '@/lib/utils';

export function Skeleton({ className, ...props }) {
  return (
    <div
      className={cn('animate-pulse bg-surface-elevated rounded border border-border/40', className)}
      {...props}
    />
  );
}

export default Skeleton;

