import React from 'react';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

export function LoadingSpinner({
  size = 'md',
  message = 'Loading NEX System...',
  className,
}) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-10 h-10',
  };

  return (
    <div className={cn('flex flex-col items-center justify-center gap-3 p-6 text-text-secondary', className)}>
      <Loader2 className={cn('animate-spin text-accent-primary', sizeClasses[size] || sizeClasses.md)} />
      {message && <p className="text-xs font-mono tracking-wider uppercase text-text-secondary">{message}</p>}
    </div>
  );
}

export default LoadingSpinner;

