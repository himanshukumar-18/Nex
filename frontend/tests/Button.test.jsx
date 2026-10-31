import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Button from '@/components/ui/Button';

describe('Button Component', () => {
  it('renders button with label', () => {
    render(<Button>EXECUTE ACTION</Button>);
    expect(screen.getByRole('button', { name: /EXECUTE ACTION/i })).toBeInTheDocument();
  });

  it('handles user click events', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>CLICK ME</Button>);

    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('disables button when disabled prop is set', () => {
    const handleClick = vi.fn();
    render(
      <Button disabled onClick={handleClick}>
        DISABLED ACTION
      </Button>
    );

    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(handleClick).not.toHaveBeenCalled();
  });

  it('shows loading spinner and disables button when isLoading is true', () => {
    const handleClick = vi.fn();
    render(
      <Button isLoading onClick={handleClick}>
        SAVING
      </Button>
    );

    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    expect(button.querySelector('svg')).toBeInTheDocument();
  });

  it('applies variant styling classes correctly', () => {
    const { rerender } = render(<Button variant="danger">DELETE</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-status-danger');

    rerender(<Button variant="cyan">CYAN ACTION</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-accent-secondary');
  });
});

