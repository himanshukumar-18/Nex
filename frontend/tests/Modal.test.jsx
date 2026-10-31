import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Modal from '@/components/ui/Modal';

describe('Modal Component', () => {
  it('renders modal content when isOpen is true', () => {
    render(
      <Modal
        isOpen={true}
        onClose={vi.fn()}
        title="TEST MODAL"
        description="Verification modal description"
      >
        <p>Modal body test message</p>
      </Modal>
    );

    expect(screen.getByText('TEST MODAL')).toBeInTheDocument();
    expect(screen.getByText('Verification modal description')).toBeInTheDocument();
    expect(screen.getByText('Modal body test message')).toBeInTheDocument();
  });

  it('calls onClose when close icon button is clicked', () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose} title="TEST MODAL">
        <p>Content</p>
      </Modal>
    );

    const closeBtn = screen.getByRole('button', { name: /Close modal/i });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});

