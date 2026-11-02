import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import CliAuthConsentPage from '@/pages/auth/CliAuthConsentPage';
import { renderWithProviders } from './test-utils';
import { authApi } from '@/services/authApi';

vi.mock('@/services/authApi', () => ({
  authApi: {
    authorizeCli: vi.fn(),
  },
  default: {
    authorizeCli: vi.fn(),
  },
}));

describe('CliAuthConsentPage Component', () => {
  it('renders error notice when PKCE parameters are missing', () => {
    renderWithProviders(<CliAuthConsentPage />, {
      initialEntries: ['/auth/cli'],
    });

    expect(screen.getByText(/INVALID AUTHORIZATION PARAMETERS/i)).toBeInTheDocument();
  });

  it('renders consent prompt with device name and scopes when params are present', () => {
    const preloadedState = {
      auth: {
        user: { email: 'developer@nex.dev', role: 'developer' },
        isAuthenticated: true,
        isLoading: false,
      },
    };

    const qs = '?code_challenge=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk&redirect_uri=http://127.0.0.1:8942/callback&state=xyzState123&device_name=Alex-MacBook';

    renderWithProviders(<CliAuthConsentPage />, {
      preloadedState,
      initialEntries: [`/auth/cli${qs}`],
    });

    expect(screen.getByText('Authorize Terminal')).toBeInTheDocument();
    expect(screen.getByText('Alex-MacBook')).toBeInTheDocument();
    expect(screen.getByText('developer@nex.dev')).toBeInTheDocument();
    expect(screen.getByText('S256 (RFC 7636)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Authorize/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Deny/i })).toBeInTheDocument();
  });

  it('submits authorization and displays success state', async () => {
    const preloadedState = {
      auth: {
        user: { email: 'developer@nex.dev', role: 'developer' },
        isAuthenticated: true,
        isLoading: false,
      },
    };

    authApi.authorizeCli.mockResolvedValueOnce({
      authorization_code: 'auth_code_secret_xyz',
      redirect_uri: 'http://127.0.0.1:8942/callback',
      state: 'xyzState123',
    });

    const qs = '?code_challenge=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk&redirect_uri=http://127.0.0.1:8942/callback&state=xyzState123&device_name=Alex-MacBook';

    renderWithProviders(<CliAuthConsentPage />, {
      preloadedState,
      initialEntries: [`/auth/cli${qs}`],
    });

    const approveButton = screen.getByRole('button', { name: /Authorize/i });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(authApi.authorizeCli).toHaveBeenCalledWith({
        code_challenge: 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk',
        code_challenge_method: 'S256',
        redirect_uri: 'http://127.0.0.1:8942/callback',
        state: 'xyzState123',
        device_name: 'Alex-MacBook',
      });
      expect(screen.getByText(/Terminal Authorized/i)).toBeInTheDocument();
    });
  });
});

