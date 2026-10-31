import React from 'react';
import { cn } from '@/lib/utils';

export function Tabs({ tabs = [], activeTab, onChange, className }) {
  return (
    <div className={cn('border-b border-border flex items-center gap-1 overflow-x-auto', className)}>
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange?.(tab.id)}
            className={cn(
              'px-4 py-2 text-xs font-mono font-medium uppercase tracking-wider border-b-2 -mb-px transition-colors flex items-center gap-2 whitespace-nowrap',
              isActive
                ? 'border-accent-primary text-accent-highlight bg-surface-elevated/40'
                : 'border-transparent text-text-secondary hover:text-text-primary hover:border-border'
            )}
          >
            {tab.icon && <span className="w-3.5 h-3.5">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span className="px-1.5 py-0.2 text-[10px] bg-bg-secondary rounded border border-border">
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export default Tabs;

