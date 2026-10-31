import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Utility function to conditionally merge Tailwind CSS classes
 * while handling conflicts cleanly.
 *
 * @param  {...any} inputs - Class names, conditionals, or objects
 * @returns {string} Merged class string
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/**
 * Generates a standard UUID v4 string for correlation IDs or unique keys.
 * Uses window.crypto.randomUUID() when available with fallback.
 *
 * @returns {string} UUID string
 */
export function generateUUID() {
  if (typeof window !== 'undefined' && window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

