import React from 'react';
import { cn } from '@/lib/utils';

export function Table({ children, className }) {
  return (
    <div className="w-full overflow-x-auto border border-border rounded">
      <table className={cn('w-full text-left text-xs font-mono', className)}>
        {children}
      </table>
    </div>
  );
}

export function TableHeader({ children, className }) {
  return (
    <thead className={cn('bg-bg-secondary text-text-secondary uppercase tracking-wider border-b border-border', className)}>
      {children}
    </thead>
  );
}

export function TableBody({ children, className }) {
  return (
    <tbody className={cn('divide-y divide-border bg-surface-elevated/30', className)}>
      {children}
    </tbody>
  );
}

export function TableRow({ children, className, onClick }) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        'transition-colors hover:bg-surface-elevated/80',
        onClick && 'cursor-pointer',
        className
      )}
    >
      {children}
    </tr>
  );
}

export function TableHead({ children, className }) {
  return (
    <th className={cn('px-4 py-3 font-semibold text-text-secondary', className)}>
      {children}
    </th>
  );
}

export function TableCell({ children, className }) {
  return (
    <td className={cn('px-4 py-3 text-text-primary whitespace-nowrap', className)}>
      {children}
    </td>
  );
}

export default Table;

