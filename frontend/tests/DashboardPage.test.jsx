import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import DashboardPage from '@/pages/DashboardPage';
import { renderWithProviders } from './test-utils';
import { githubApi, repositoryApi, systemApi } from '@/services';

vi.mock('@/services/githubApi', () => ({
  getGitHubStatus: vi.fn(),
  default: {
    getGitHubStatus: vi.fn(),
  },
}));

vi.mock('@/services/repositoryApi', () => ({
  getSyncStatus: vi.fn(),
  getRepositories: vi.fn(),
  getOperations: vi.fn(),
  default: {
    getSyncStatus: vi.fn(),
    getRepositories: vi.fn(),
    getOperations: vi.fn(),
  },
}));

vi.mock('@/services/systemApi', () => ({
  getReadiness: vi.fn(),
  getLiveness: vi.fn(),
  default: {
    getReadiness: vi.fn(),
    getLiveness: vi.fn(),
  },
}));

describe('DashboardPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    githubApi.getGitHubStatus.mockResolvedValue({
      configured: true,
      app_slug: 'nex-bot',
      connected: true,
      installations_count: 1,
      installations: [{ id: 1, account_login: 'nex-team' }],
    });

    repositoryApi.getSyncStatus.mockResolvedValue({
      installations_count: 1,
      total_repositories: 4,
      public_repositories: 1,
      private_repositories: 3,
      last_synced_at: '2026-11-03T12:00:00Z',
    });

    repositoryApi.getRepositories.mockResolvedValue({
      count: 2,
      results: [
        {
          id: 'repo-1',
          full_name: 'nex-team/core-api',
          name: 'core-api',
          default_branch: 'main',
          language: 'Python',
          is_private: true,
          sync_status: 'active',
        },
        {
          id: 'repo-2',
          full_name: 'nex-team/frontend',
          name: 'frontend',
          default_branch: 'main',
          language: 'JavaScript',
          is_private: false,
          sync_status: 'active',
        },
      ],
    });

    repositoryApi.getOperations.mockResolvedValue({
      count: 2,
      results: [
        {
          id: 'op-1',
          operation_type: 'commit',
          target_branch: 'feat/test-runner',
          risk_level: 'HIGH',
          status: 'completed',
          created_at: '2026-11-03T12:30:00Z',
        },
        {
          id: 'op-2',
          operation_type: 'push',
          target_branch: 'main',
          risk_level: 'CRITICAL',
          status: 'simulated',
          created_at: '2026-11-03T12:35:00Z',
        },
      ],
    });

    systemApi.getReadiness.mockResolvedValue({
      status: 'ok',
      database: 'connected',
    });
  });

  it('renders page header and philosophy banner', async () => {
    renderWithProviders(<DashboardPage />);

    expect(screen.getByText(/SYSTEM CONTROL DASHBOARD/i)).toBeInTheDocument();
    expect(screen.getByText(/ENGINEERING EXECUTION PIPELINE/i)).toBeInTheDocument();
    expect(screen.getByText(/Understand/i)).toBeInTheDocument();
    expect(screen.getByText(/Ship/i)).toBeInTheDocument();
  });

  it('loads and renders live metrics and system health', async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('GATEWAY ONLINE')).toBeInTheDocument();
      expect(screen.getByText('nex-team/core-api')).toBeInTheDocument();
      expect(screen.getByText('nex-team/frontend')).toBeInTheDocument();
    });

    expect(screen.getByText(/1 PUBLIC • 3 PRIVATE/i)).toBeInTheDocument();
    expect(screen.getByText(/1 APP INSTALLATION/i)).toBeInTheDocument();
  });

  it('renders recent git operations with risk and status badges', async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('feat/test-runner', { exact: false })).toBeInTheDocument();
    });

    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
    expect(screen.getByText('SIMULATED')).toBeInTheDocument();
  });

  it('renders empty states when no repositories or operations exist', async () => {
    repositoryApi.getRepositories.mockResolvedValue({ count: 0, results: [] });
    repositoryApi.getOperations.mockResolvedValue({ count: 0, results: [] });

    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/NO REPOSITORIES CONNECTED/i)).toBeInTheDocument();
      expect(screen.getByText(/NO GIT OPERATIONS YET/i)).toBeInTheDocument();
    });
  });

  it('triggers manual refresh on button click', async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('GATEWAY ONLINE')).toBeInTheDocument();
    });

    const refreshBtn = screen.getByRole('button', { name: /Refresh Metrics/i });
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(repositoryApi.getRepositories).toHaveBeenCalledTimes(2);
    });
  });
});

