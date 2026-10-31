import React, { useState } from 'react';
import { cn } from '@/lib/utils';

export function Tooltip({ children, content, position = 'top', className }) {
  const [isVisible, setIsVisible] = useState(false);

  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  return (
    <div
      className="relative inline-flex"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
    >
      {children}
      {isVisible && content && (
        <div
          role="tooltip"
          className={cn(
            'absolute z-50 whitespace-nowrap bg-bg-secondary text-text-primary text-xs font-mono px-2.5 py-1 border border-border rounded shadow-lg pointer-events-none animate-in fade-in-0 duration-100',
            positionClasses[position] || positionClasses.top,
            className
          )}
        >
          {content}
        </div>
      )}
    </div>
  );
}

export default Tooltip;

