import React, { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';

export function Dropdown({
  trigger,
  items = [],
  align = 'right',
  className,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const alignClasses = {
    left: 'left-0 origin-top-left',
    right: 'right-0 origin-top-right',
  };

  return (
    <div ref={containerRef} className="relative inline-block text-left">
      <div onClick={() => setIsOpen((prev) => !prev)}>{trigger}</div>

      {isOpen && (
        <div
          role="menu"
          aria-orientation="vertical"
          className={cn(
            'absolute mt-1.5 min-w-[180px] bg-surface-elevated border border-border rounded shadow-xl py-1 z-50 animate-in fade-in-80 zoom-in-95 duration-100',
            alignClasses[align] || alignClasses.right,
            className
          )}
        >
          {items.map((item, index) => {
            if (item.divider) {
              return <div key={`divider-${index}`} className="my-1 border-t border-border" />;
            }

            return (
              <button
                key={item.id || item.label || index}
                role="menuitem"
                disabled={item.disabled}
                onClick={() => {
                  item.onClick?.();
                  setIsOpen(false);
                }}
                className={cn(
                  'w-full text-left px-3 py-1.5 text-xs font-mono flex items-center gap-2 transition-colors',
                  item.danger
                    ? 'text-status-danger hover:bg-status-danger/10'
                    : 'text-text-primary hover:bg-bg-secondary hover:text-accent-highlight',
                  item.disabled && 'opacity-50 cursor-not-allowed pointer-events-none'
                )}
              >
                {item.icon && <span className="w-3.5 h-3.5 shrink-0">{item.icon}</span>}
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default Dropdown;

