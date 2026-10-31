import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';
import { cn } from '@/lib/utils';

export function Breadcrumb({ items = [], className }) {
  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center text-xs font-mono', className)}>
      <ol className="flex items-center gap-1.5 list-none p-0 m-0 text-text-secondary">
        <li>
          <Link
            to="/"
            className="flex items-center hover:text-white transition-colors"
            aria-label="Home"
          >
            <Home className="w-3.5 h-3.5" />
          </Link>
        </li>
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <React.Fragment key={item.label || index}>
              <li className="text-border">
                <ChevronRight className="w-3.5 h-3.5" />
              </li>
              <li>
                {isLast || !item.to ? (
                  <span className="text-accent-highlight font-medium">{item.label}</span>
                ) : (
                  <Link to={item.to} className="hover:text-white transition-colors">
                    {item.label}
                  </Link>
                )}
              </li>
            </React.Fragment>
          );
        })}
      </ol>
    </nav>
  );
}

export default Breadcrumb;

