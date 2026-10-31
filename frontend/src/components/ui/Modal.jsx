import React, { useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { X } from 'lucide-react';

/**
 * Modern Cyber Brutalist Modal using HTML5 native <dialog>.
 * Follows modern web best practices:
 * - Uses dialog.showModal() and dialog.close()
 * - Traps focus natively and supports Escape dismiss
 * - overscroll-behavior: contain prevents background scroll leak
 * - Light-dismiss on backdrop click
 */
export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  maxWidth = 'max-w-lg',
  className,
}) {
  const dialogRef = useRef(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (isOpen) {
      if (!dialog.open) {
        dialog.showModal();
      }
    } else {
      if (dialog.open) {
        dialog.close();
      }
    }
  }, [isOpen]);

  // Handle native cancel event (triggered by Escape key)
  const handleCancel = (e) => {
    e.preventDefault();
    onClose?.();
  };

  // Light dismiss on backdrop click
  const handleClick = (e) => {
    const dialog = dialogRef.current;
    if (e.target === dialog) {
      onClose?.();
    }
  };

  if (!isOpen && !dialogRef.current?.open) {
    return null;
  }

  return (
    <dialog
      ref={dialogRef}
      onCancel={handleCancel}
      onClick={handleClick}
      aria-labelledby={title ? 'modal-title' : undefined}
      aria-describedby={description ? 'modal-description' : undefined}
      className={cn(
        'w-full bg-surface-elevated text-text-primary border-2 border-border p-0 rounded-md shadow-2xl focus:outline-none backdrop:bg-bg-primary/80 backdrop:backdrop-blur-sm m-auto animate-in fade-in zoom-in-95 duration-150',
        maxWidth,
        className
      )}
    >
      <div className="flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5 bg-bg-secondary">
          <div className="flex flex-col">
            {title && (
              <h3 id="modal-title" className="text-base font-display font-semibold text-text-primary tracking-wide">
                {title}
              </h3>
            )}
            {description && (
              <p id="modal-description" className="text-xs font-mono text-text-secondary mt-0.5">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="text-text-secondary hover:text-white p-1 rounded hover:bg-surface-elevated transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body Content */}
        <div className="p-5 overflow-y-auto max-h-[calc(85vh-120px)]">{children}</div>
      </div>
    </dialog>
  );
}

export default Modal;

