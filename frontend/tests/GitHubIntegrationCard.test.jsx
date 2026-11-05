import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import GitHubIntegrationCard from '@/components/github/GitHubIntegrationCard';
import { renderWithProviders } from './test-utils';
import { githubApi } from '@/services';

vi.mock('@/services/githubApi', () => ({
  getGitHubStatus: vi.fn(),
  initiateGitHubInstall: vi.fn(),
  disconnectInstallation: vi.fn(),
  default: {
    getGitHubStatus: vi.fn(),
    initiateGitHubInstall: vi.fn(),
    disconnectInstallation: vi.fn(),
  },
}));

describe('GitHubIntegrationCard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    githubApi.getGitHubStatus.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<GitHubIntegrationCard />);

    expect(screen.getByText(/Checking GitHub App authorization/i)).toBeInTheDocument();
  });

  it('renders CONFIG REQUIRED badge when backend credentials are not set', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({
      configured: false,
      app_slug: 'nex-assistant',
      connected: false,
      installations_count: 0,
      installations: [],
    });

    renderWithProviders(<GitHubIntegrationCard />);

    await waitFor(() => {
      expect(screen.getByText('CONFIG REQUIRED')).toBeInTheDocument();
    });

    expect(screen.getByText(/Backend Configuration Required/i)).toBeInTheDocument();
    expect(screen.getByText(/GITHUB_APP_ID/i)).toBeInTheDocument();
  });

  it('renders NOT CONNECTED state with connect action when configured', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({
      configured: true,
      app_slug: 'nex-assistant',
      connected: false,
      installations_count: 0,
      installations: [],
    });

    renderWithProviders(<GitHubIntegrationCard />);

    await waitFor(() => {
      expect(screen.getByText('NOT CONNECTED')).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /Connect nex-assistant/i })).toBeInTheDocument();
  });

  it('renders CONNECTED state with installation metadata', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({
      configured: true,
      app_slug: 'nex-assistant',
      connected: true,
      installations_count: 1,
      installations: [
        {
          id: 'inst-uuid-1',
          installation_id: 1234567,
          account_login: 'octocat-dev',
          account_type: 'Organization',
          account_avatar_url: 'https://example.com/avatar.png',
          target_type: 'selected',
          permissions: { contents: 'read' },
          status: 'active',
          is_active: true,
        },
      ],
    });

    renderWithProviders(<GitHubIntegrationCard />);

    await waitFor(() => {
      expect(screen.getByText('CONNECTED')).toBeInTheDocument();
    });

    expect(screen.getByText('octocat-dev')).toBeInTheDocument();
    expect(screen.getByText('Organization')).toBeInTheDocument();
    expect(screen.getByText(/Installation ID: 1234567/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Disconnect/i })).toBeInTheDocument();
  });

  it('initiates install flow on connect button click', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({
      configured: true,
      app_slug: 'nex-assistant',
      connected: false,
      installations_count: 0,
      installations: [],
    });
    githubApi.initiateGitHubInstall.mockResolvedValueOnce({
      install_url: 'https://github.com/apps/nex-assistant/installations/new?state=testStateToken',
      state: 'testStateToken',
    });

    renderWithProviders(<GitHubIntegrationCard />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Connect nex-assistant/i })).toBeInTheDocument();
    });

    const connectButton = screen.getByRole('button', { name: /Connect nex-assistant/i });
    fireEvent.click(connectButton);

    await waitFor(() => {
      expect(githubApi.initiateGitHubInstall).toHaveBeenCalledTimes(1);
    });
  });

  it('displays success notice when ?github=connected is present in URL', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({
      configured: true,
      app_slug: 'nex-assistant',
      connected: true,
      installations_count: 1,
      installations: [],
    });

    renderWithProviders(<GitHubIntegrationCard />, {
      initialEntries: ['/settings?github=connected&installation_id=12345'],
    });

    await waitFor(() => {
      expect(
        screen.getByText(/GitHub App successfully connected and authorized/i)
      ).toBeInTheDocument();
    });
  });

  it('displays updated notice when ?github=updated is present in URL', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({
      configured: true,
      app_slug: 'nex-assistant',
      connected: true,
      installations_count: 1,
      installations: [],
    });

    renderWithProviders(<GitHubIntegrationCard />, {
      initialEntries: ['/settings?github=updated&installation_id=12345'],
    });

    await waitFor(() => {
      expect(
        screen.getByText(/GitHub App installation settings synchronized successfully/i)
      ).toBeInTheDocument();
    });
  });

  it('displays error notice when ?github=error is present in URL', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({
      configured: true,
      app_slug: 'nex-assistant',
      connected: false,
      installations_count: 0,
      installations: [],
    });

    renderWithProviders(<GitHubIntegrationCard />, {
      initialEntries: ['/settings?github=error&error=UNVERIFIED_INSTALLATION'],
    });

    await waitFor(() => {
      expect(
        screen.getByText(/GitHub App authorization error \(UNVERIFIED_INSTALLATION\)/i)
      ).toBeInTheDocument();
    });
  });

  it('displays sync warning when ?github=connected&sync=failed is present in URL', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({
      configured: true,
      app_slug: 'nex-assistant',
      connected: true,
      installations_count: 1,
      installations: [],
    });

    renderWithProviders(<GitHubIntegrationCard />, {
      initialEntries: ['/settings?github=connected&installation_id=12345&sync=failed'],
    });

    await waitFor(() => {
      expect(
        screen.getByText(/initial repository synchronization encountered an issue/i)
      ).toBeInTheDocument();
    });
  });
});

