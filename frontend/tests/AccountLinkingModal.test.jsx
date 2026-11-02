import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { AccountLinkingModal } from '@/components/auth/AccountLinkingModal';
import * as firebaseService from '@/services/firebase';

vi.mock('@/services/firebase', () => ({
  linkWithPassword: vi.fn(),
  linkWithGoogle: vi.fn(),
  formatFirebaseAuthError: vi.fn((err) => err?.message || 'Authentication error occurred'),
}));

describe('AccountLinkingModal Component', () => {
  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();
  const mockPendingCredential = { providerId: 'github.com', signInMethod: 'github.com' };
  const mockEmail = 'octocat@github.com';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders modal content when open', () => {
    renderWithProviders(
      <AccountLinkingModal
        isOpen={true}
        onClose={mockOnClose}
        email={mockEmail}
        pendingCredential={mockPendingCredential}
        onSuccess={mockOnSuccess}
      />
    );

    expect(screen.getByText('Link Existing Account')).toBeInTheDocument();
    expect(screen.getByText(/ACCOUNT MERGE CONFIRMATION REQUIRED/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue(mockEmail)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Enter your existing account password/i)).toBeInTheDocument();
  });

  it('validates empty password submission', async () => {
    renderWithProviders(
      <AccountLinkingModal
        isOpen={true}
        onClose={mockOnClose}
        email={mockEmail}
        pendingCredential={mockPendingCredential}
        onSuccess={mockOnSuccess}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /Verify & Link/i });
    fireEvent.click(submitBtn);

    expect(screen.getByText('Please enter your account password.')).toBeInTheDocument();
    expect(firebaseService.linkWithPassword).not.toHaveBeenCalled();
  });

  it('successfully links account with password', async () => {
    firebaseService.linkWithPassword.mockResolvedValueOnce({ user: { uid: 'u123' } });

    renderWithProviders(
      <AccountLinkingModal
        isOpen={true}
        onClose={mockOnClose}
        email={mockEmail}
        pendingCredential={mockPendingCredential}
        onSuccess={mockOnSuccess}
      />
    );

    const passwordInput = screen.getByPlaceholderText(/Enter your existing account password/i);
    fireEvent.change(passwordInput, { target: { value: 'SecretPassword123!' } });

    const submitBtn = screen.getByRole('button', { name: /Verify & Link/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(firebaseService.linkWithPassword).toHaveBeenCalledWith(
        mockEmail,
        'SecretPassword123!',
        mockPendingCredential
      );
      expect(mockOnSuccess).toHaveBeenCalledTimes(1);
    });
  });

  it('handles password link failure and displays error alert', async () => {
    firebaseService.linkWithPassword.mockRejectedValueOnce(
      new Error('Invalid password provided.')
    );

    renderWithProviders(
      <AccountLinkingModal
        isOpen={true}
        onClose={mockOnClose}
        email={mockEmail}
        pendingCredential={mockPendingCredential}
        onSuccess={mockOnSuccess}
      />
    );

    const passwordInput = screen.getByPlaceholderText(/Enter your existing account password/i);
    fireEvent.change(passwordInput, { target: { value: 'WrongPassword' } });

    const submitBtn = screen.getByRole('button', { name: /Verify & Link/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Invalid password provided.')).toBeInTheDocument();
      expect(mockOnSuccess).not.toHaveBeenCalled();
    });
  });

  it('switches to Google OAuth tab and links successfully', async () => {
    firebaseService.linkWithGoogle.mockResolvedValueOnce({ user: { uid: 'u123' } });

    renderWithProviders(
      <AccountLinkingModal
        isOpen={true}
        onClose={mockOnClose}
        email={mockEmail}
        pendingCredential={mockPendingCredential}
        onSuccess={mockOnSuccess}
      />
    );

    const googleTabBtn = screen.getByRole('button', { name: /Google OAuth/i });
    fireEvent.click(googleTabBtn);

    expect(
      screen.getByText(/Authenticate with your Google account/i)
    ).toBeInTheDocument();

    const linkGoogleBtn = screen.getByRole('button', { name: /Sign In with Google to Link/i });
    fireEvent.click(linkGoogleBtn);

    await waitFor(() => {
      expect(firebaseService.linkWithGoogle).toHaveBeenCalledWith(mockPendingCredential);
      expect(mockOnSuccess).toHaveBeenCalledTimes(1);
    });
  });

  it('handles Google link failure and displays formatted error', async () => {
    firebaseService.linkWithGoogle.mockRejectedValueOnce(
      new Error('Google verification popup closed by user.')
    );

    renderWithProviders(
      <AccountLinkingModal
        isOpen={true}
        onClose={mockOnClose}
        email={mockEmail}
        pendingCredential={mockPendingCredential}
        onSuccess={mockOnSuccess}
      />
    );

    const googleTabBtn = screen.getByRole('button', { name: /Google OAuth/i });
    fireEvent.click(googleTabBtn);

    const linkGoogleBtn = screen.getByRole('button', { name: /Sign In with Google to Link/i });
    fireEvent.click(linkGoogleBtn);

    await waitFor(() => {
      expect(screen.getByText('Google verification popup closed by user.')).toBeInTheDocument();
      expect(mockOnSuccess).not.toHaveBeenCalled();
    });
  });

  it('triggers onClose when Cancel button is clicked', () => {
    renderWithProviders(
      <AccountLinkingModal
        isOpen={true}
        onClose={mockOnClose}
        email={mockEmail}
        pendingCredential={mockPendingCredential}
        onSuccess={mockOnSuccess}
      />
    );

    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancelBtn);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });
});

