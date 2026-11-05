import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import SettingsPage from '@/pages/SettingsPage';
import { renderWithProviders } from './test-utils';
import { authApi } from '@/services/authApi';
import { githubApi } from '@/services';
import { resetPassword, resendVerificationEmail } from '@/services/firebase';

const mockGithubStatus = {
  configured: true,
  app_slug: 'nex-bot',
  connected: true,
  installations_count: 1,
  installations: [{ id: 101, account_login: 'nex-corp' }],
};

vi.mock('@/services/githubApi', () => {
  const apiObj = {
    getGitHubStatus: vi.fn(),
    initiateGitHubInstall: vi.fn(),
    disconnectInstallation: vi.fn(),
  };
  return {
    githubApi: apiObj,
    getGitHubStatus: apiObj.getGitHubStatus,
    initiateGitHubInstall: apiObj.initiateGitHubInstall,
    disconnectInstallation: apiObj.disconnectInstallation,
    default: apiObj,
  };
});

vi.mock('@/services/authApi', () => ({
  authApi: {
    getCliSessions: vi.fn(),
    revokeCliSession: vi.fn(),
  },
  default: {
    getCliSessions: vi.fn(),
    revokeCliSession: vi.fn(),
  },
}));

vi.mock('@/services/firebase', () => ({
  resetPassword: vi.fn(),
  resendVerificationEmail: vi.fn(),
}));

describe('SettingsPage Component', () => {
  const mockUser = {
    uid: 'firebase-user-uid-123456789',
    email: 'developer@nex.dev',
    displayName: 'Alex Rivers',
    emailVerified: false,
    role: 'developer',
  };

  const mockSessions = [
    {
      id: 'sess-uuid-001',
      device_name: 'MacBook Pro M3',
      created_at: '2026-11-01T10:00:00Z',
      last_used_at: '2026-11-03T14:00:00Z',
      expires_at: '2026-12-01T10:00:00Z',
      is_active: true,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();

    authApi.getCliSessions.mockResolvedValue(mockSessions);
    authApi.revokeCliSession.mockResolvedValue({ status: 'revoked' });
    githubApi.getGitHubStatus.mockResolvedValue(mockGithubStatus);
    resetPassword.mockResolvedValue();
    resendVerificationEmail.mockResolvedValue();
  });

  it('renders user profile details and role badge', async () => {
    renderWithProviders(<SettingsPage />, {
      preloadedState: {
        auth: {
          user: mockUser,
          isAuthenticated: true,
          isLoading: false,
        },
      },
    });

    expect(screen.getByText(/USER IDENTITY & CREDENTIALS/i)).toBeInTheDocument();
    expect(screen.getByText('Alex Rivers')).toBeInTheDocument();
    expect(screen.getByText('developer@nex.dev')).toBeInTheDocument();
    expect(screen.getByText('UNVERIFIED')).toBeInTheDocument();
    expect(screen.getByText('developer')).toBeInTheDocument();
  });

  it('triggers password reset email dispatch', async () => {
    renderWithProviders(<SettingsPage />, {
      preloadedState: {
        auth: {
          user: mockUser,
          isAuthenticated: true,
          isLoading: false,
        },
      },
    });

    const resetBtn = screen.getByRole('button', { name: /Reset Password/i });
    fireEvent.click(resetBtn);

    await waitFor(() => {
      expect(resetPassword).toHaveBeenCalledWith('developer@nex.dev');
    });
  });

  it('triggers verification email resend when email is unverified', async () => {
    renderWithProviders(<SettingsPage />, {
      preloadedState: {
        auth: {
          user: mockUser,
          isAuthenticated: true,
          isLoading: false,
        },
      },
    });

    const resendBtn = screen.getByRole('button', { name: /Resend Verification/i });
    fireEvent.click(resendBtn);

    await waitFor(() => {
      expect(resendVerificationEmail).toHaveBeenCalled();
    });
  });

  it('renders active CLI sessions and handles revocation', async () => {
    renderWithProviders(<SettingsPage />, {
      preloadedState: {
        auth: {
          user: mockUser,
          isAuthenticated: true,
          isLoading: false,
        },
      },
    });

    await waitFor(() => {
      expect(screen.getByText('MacBook Pro M3')).toBeInTheDocument();
      expect(screen.getByText(/sess-uui/i)).toBeInTheDocument();
    });

    const revokeBtn = screen.getByRole('button', { name: /Revoke/i });
    fireEvent.click(revokeBtn);

    await waitFor(() => {
      expect(authApi.revokeCliSession).toHaveBeenCalledWith('sess-uuid-001');
    });
  });

  it('displays API gateway architecture section', async () => {
    renderWithProviders(<SettingsPage />, {
      preloadedState: {
        auth: {
          user: mockUser,
          isAuthenticated: true,
          isLoading: false,
        },
      },
    });

    expect(screen.getByText(/GATEWAY ARCHITECTURE & RUNTIME/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/api\/v1/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/agent-runtime:8001/i)).toBeInTheDocument();
  });
});
