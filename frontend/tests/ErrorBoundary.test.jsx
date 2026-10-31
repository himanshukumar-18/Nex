import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ErrorBoundary from '@/components/feedback/ErrorBoundary';

function ProblemChild({ shouldThrow }) {
  if (shouldThrow) {
    throw new Error('Test crash in child component');
  }
  return <div>Healthy Child Content</div>;
}

describe('ErrorBoundary Component', () => {
  let consoleErrorSpy;

  beforeEach(() => {
    // Suppress React boundary console.error during test
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Healthy Child Content')).toBeInTheDocument();
  });

  it('catches render error and displays cyber brutalist fallback UI', () => {
    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText(/NEX Client Runtime Exception/i)).toBeInTheDocument();
    expect(screen.getByText(/Test crash in child component/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Try Again/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reload Application/i })).toBeInTheDocument();
  });

  it('triggers onReset callback when Try Again button is clicked', () => {
    const handleReset = vi.fn();
    render(
      <ErrorBoundary onReset={handleReset}>
        <ProblemChild shouldThrow={true} />
      </ErrorBoundary>
    );

    fireEvent.click(screen.getByRole('button', { name: /Try Again/i }));
    expect(handleReset).toHaveBeenCalledTimes(1);
  });
});

