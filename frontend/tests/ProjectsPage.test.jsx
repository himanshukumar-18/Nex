import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import ProjectsPage from '@/pages/ProjectsPage';
import { renderWithProviders } from './test-utils';
import { githubApi, repositoryApi } from '@/services';

vi.mock('@/services/githubApi', () => ({
  getGitHubStatus: vi.fn(),
  default: {
    getGitHubStatus: vi.fn(),
  },
}));

vi.mock('@/services/repositoryApi', () => ({
  getRepositories: vi.fn(),
  getRepository: vi.fn(),
  syncRepositories: vi.fn(),
  getSyncStatus: vi.fn(),
  getOperations: vi.fn(),
  recordOperation: vi.fn(),
  getPullRequests: vi.fn(),
  getPullRequest: vi.fn(),
  previewPullRequest: vi.fn(),
  createPullRequest: vi.fn(),
  syncPullRequest: vi.fn(),
  default: {
    getRepositories: vi.fn(),
    getRepository: vi.fn(),
    syncRepositories: vi.fn(),
    getSyncStatus: vi.fn(),
    getOperations: vi.fn(),
    recordOperation: vi.fn(),
    getPullRequests: vi.fn(),
    getPullRequest: vi.fn(),
    previewPullRequest: vi.fn(),
    createPullRequest: vi.fn(),
    syncPullRequest: vi.fn(),
  },
}));

const mockRepos = [
  {
    id: 'repo-uuid-1',
    github_repo_id: 1001,
    name: 'core-api',
    full_name: 'nex-team/core-api',
    owner_login: 'nex-team',
    description: 'Core backend engine',
    is_private: true,
    is_archived: false,
    default_branch: 'main',
    language: 'Python',
    html_url: 'https://github.com/nex-team/core-api',
    clone_url: 'https://github.com/nex-team/core-api.git',
    ssh_url: 'git@github.com:nex-team/core-api.git',
    sync_status: 'synced',
  },
  {
    id: 'repo-uuid-2',
    github_repo_id: 1002,
    name: 'dashboard-ui',
    full_name: 'nex-team/dashboard-ui',
    owner_login: 'nex-team',
    description: 'Frontend React web app',
    is_private: false,
    is_archived: false,
    default_branch: 'main',
    language: 'TypeScript',
    html_url: 'https://github.com/nex-team/dashboard-ui',
    clone_url: 'https://github.com/nex-team/dashboard-ui.git',
    ssh_url: 'git@github.com:nex-team/dashboard-ui.git',
    sync_status: 'synced',
  },
];

describe('ProjectsPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    githubApi.getGitHubStatus.mockReturnValue(new Promise(() => {}));
    repositoryApi.getRepositories.mockReturnValue(new Promise(() => {}));
    repositoryApi.getSyncStatus.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<ProjectsPage />);
    expect(screen.getByText(/Loading repositories from backend/i)).toBeInTheDocument();
  });

  it('renders GITHUB NOT CONNECTED when GitHub App is not connected', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({ connected: false });
    repositoryApi.getSyncStatus.mockResolvedValueOnce(null);
    repositoryApi.getRepositories.mockResolvedValueOnce({ results: [] });

    renderWithProviders(<ProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText('GITHUB NOT CONNECTED')).toBeInTheDocument();
    });
    expect(screen.getByText(/Authorize the NEX GitHub App in your Settings/i)).toBeInTheDocument();
    expect(screen.getByText('Go to Settings')).toBeInTheDocument();
  });

  it('renders NO REPOSITORIES DISCOVERED when connected but 0 repos exist', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({ connected: true });
    repositoryApi.getSyncStatus.mockResolvedValueOnce({ total_repositories: 0 });
    repositoryApi.getRepositories.mockResolvedValueOnce({ results: [] });

    renderWithProviders(<ProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText('NO REPOSITORIES DISCOVERED')).toBeInTheDocument();
    });
    expect(screen.getByText('Sync Repositories Now')).toBeInTheDocument();
  });

  it('renders repositories table with metrics when repositories exist', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({ connected: true });
    repositoryApi.getSyncStatus.mockResolvedValueOnce({
      total_repositories: 2,
      public_repositories: 1,
      private_repositories: 1,
      last_synced_at: '2026-11-02T12:00:00Z',
    });
    repositoryApi.getRepositories.mockResolvedValueOnce({ results: mockRepos });

    renderWithProviders(<ProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText('nex-team/core-api')).toBeInTheDocument();
      expect(screen.getByText('nex-team/dashboard-ui')).toBeInTheDocument();
    });

    // Check badges
    expect(screen.getAllByText('PRIVATE').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('PUBLIC').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();

    // Check action button
    expect(screen.getByText('SYNC GITHUB')).toBeInTheDocument();
  });

  it('filters repositories when searching', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({ connected: true });
    repositoryApi.getSyncStatus.mockResolvedValueOnce(null);
    repositoryApi.getRepositories.mockResolvedValueOnce({ results: mockRepos });

    renderWithProviders(<ProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText('nex-team/core-api')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search repositories/i);
    fireEvent.change(searchInput, { target: { value: 'dashboard' } });

    expect(screen.queryByText('nex-team/core-api')).not.toBeInTheDocument();
    expect(screen.getByText('nex-team/dashboard-ui')).toBeInTheDocument();
  });

  it('filters repositories by visibility toggle', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({ connected: true });
    repositoryApi.getSyncStatus.mockResolvedValueOnce(null);
    repositoryApi.getRepositories.mockResolvedValueOnce({ results: mockRepos });

    renderWithProviders(<ProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText('nex-team/core-api')).toBeInTheDocument();
    });

    const privateBtn = screen.getByRole('button', { name: 'PRIVATE' });
    fireEvent.click(privateBtn);

    expect(screen.getByText('nex-team/core-api')).toBeInTheDocument();
    expect(screen.queryByText('nex-team/dashboard-ui')).not.toBeInTheDocument();
  });

  it('triggers manual sync when SYNC GITHUB is clicked', async () => {
    githubApi.getGitHubStatus.mockResolvedValue({ connected: true });
    repositoryApi.getSyncStatus.mockResolvedValue(null);
    repositoryApi.getRepositories.mockResolvedValue({ results: mockRepos });
    repositoryApi.syncRepositories.mockResolvedValueOnce({
      total: 2,
      added: 0,
      updated: 2,
      removed: 0,
    });

    renderWithProviders(<ProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText('SYNC GITHUB')).toBeInTheDocument();
    });

    const syncBtn = screen.getByText('SYNC GITHUB');
    fireEvent.click(syncBtn);

    await waitFor(() => {
      expect(repositoryApi.syncRepositories).toHaveBeenCalledTimes(1);
    });
  });

  it('opens repository detail modal on row click', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({ connected: true });
    repositoryApi.getSyncStatus.mockResolvedValueOnce(null);
    repositoryApi.getRepositories.mockResolvedValueOnce({ results: mockRepos });
    repositoryApi.getOperations.mockResolvedValueOnce([]);
    repositoryApi.getPullRequests.mockResolvedValueOnce([]);

    renderWithProviders(<ProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText('nex-team/core-api')).toBeInTheDocument();
    });

    const row = screen.getByText('nex-team/core-api');
    fireEvent.click(row);

    await waitFor(() => {
      expect(screen.getByText('REPOSITORY CLONE URLS')).toBeInTheDocument();
      expect(screen.getByText('https://github.com/nex-team/core-api.git')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /operations/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /pull requests/i })).toBeInTheDocument();
    });
  });

  it('renders repository operations in modal when operations exist', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({ connected: true });
    repositoryApi.getSyncStatus.mockResolvedValueOnce(null);
    repositoryApi.getRepositories.mockResolvedValueOnce({ results: mockRepos });
    repositoryApi.getOperations.mockResolvedValueOnce([
      {
        id: 'op-1',
        operation_type: 'commit',
        status: 'completed',
        risk_level: 'high',
        commit_sha: 'a1b2c3d4e5f6',
        commit_message: 'Add auth module',
        completed_at: '2026-11-03T12:00:00Z',
      },
      {
        id: 'op-2',
        operation_type: 'push',
        status: 'completed',
        risk_level: 'critical',
        target_branch: 'main',
        completed_at: '2026-11-03T12:05:00Z',
      },
    ]);
    repositoryApi.getPullRequests.mockResolvedValueOnce([]);

    renderWithProviders(<ProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText('nex-team/core-api')).toBeInTheDocument();
    });

    const row = screen.getByText('nex-team/core-api');
    fireEvent.click(row);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /operations/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /operations/i }));

    await waitFor(() => {
      expect(screen.getByText('SAFE GIT OPERATIONS HISTORY')).toBeInTheDocument();
      expect(screen.getByText('COMMIT')).toBeInTheDocument();
      expect(screen.getByText('"Add auth module"')).toBeInTheDocument();
      expect(screen.getByText('PUSH')).toBeInTheDocument();
    });
  });

  it('renders pull requests tab and lists PRs in modal', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({ connected: true });
    repositoryApi.getSyncStatus.mockResolvedValueOnce(null);
    repositoryApi.getRepositories.mockResolvedValueOnce({ results: mockRepos });
    repositoryApi.getOperations.mockResolvedValueOnce([]);
    repositoryApi.getPullRequests.mockResolvedValueOnce([
      {
        id: 'pr-1',
        number: 42,
        title: 'Add safe git operations',
        state: 'open',
        draft: false,
        head_branch: 'feature/safe-git',
        base_branch: 'main',
        author_username: 'octocat',
        html_url: 'https://github.com/nex-team/core-api/pull/42',
        additions: 120,
        deletions: 15,
        changed_files_count: 5,
        updated_at: '2026-11-03T12:00:00Z',
      },
    ]);

    renderWithProviders(<ProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText('nex-team/core-api')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('nex-team/core-api'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /pull requests/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /pull requests/i }));

    await waitFor(() => {
      expect(screen.getByText('GITHUB PULL REQUESTS')).toBeInTheDocument();
      expect(screen.getByText('#42')).toBeInTheDocument();
      expect(screen.getByText('Add safe git operations')).toBeInTheDocument();
      expect(screen.getByText('OPEN')).toBeInTheDocument();
      expect(screen.getByText('@octocat')).toBeInTheDocument();
      expect(screen.getByText('New Pull Request')).toBeInTheDocument();
    });
  });

  it('handles in-modal pull request creation workflow with preview', async () => {
    githubApi.getGitHubStatus.mockResolvedValueOnce({ connected: true });
    repositoryApi.getSyncStatus.mockResolvedValueOnce(null);
    repositoryApi.getRepositories.mockResolvedValueOnce({ results: mockRepos });
    repositoryApi.getOperations.mockResolvedValueOnce([]);
    repositoryApi.getPullRequests.mockResolvedValueOnce([]);

    repositoryApi.previewPullRequest.mockResolvedValueOnce({
      preview_fingerprint: 'fp-12345',
      base: 'main',
      head: 'feature/pr-preview',
      commits: [{ sha: 'c1', message: 'Test commit', author: 'Dev' }],
      changed_files: [{ filename: 'src/main.py', additions: 10, deletions: 2 }],
      additions: 10,
      deletions: 2,
      has_conflicts: false,
      suggested_title: 'Implement feature pr preview',
      suggested_body: 'Automated description',
    });

    repositoryApi.createPullRequest.mockResolvedValueOnce({
      id: 'pr-created',
      number: 99,
      title: 'Implement feature pr preview',
      state: 'open',
      draft: false,
      head_branch: 'feature/pr-preview',
      base_branch: 'main',
      html_url: 'https://github.com/nex-team/core-api/pull/99',
      updated_at: '2026-11-03T12:00:00Z',
    });

    renderWithProviders(<ProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText('nex-team/core-api')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('nex-team/core-api'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /pull requests/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /pull requests/i }));

    await waitFor(() => {
      expect(screen.getByText('New Pull Request')).toBeInTheDocument();
    });

    // Click New Pull Request button
    fireEvent.click(screen.getByText('New Pull Request'));

    expect(screen.getByText('Open Pull Request')).toBeInTheDocument();

    // Fill head branch
    const headInput = screen.getByPlaceholderText('e.g. feature/my-branch');
    fireEvent.change(headInput, { target: { value: 'feature/pr-preview' } });

    // Click Preview Changes
    const previewBtn = screen.getByText('Preview Changes');
    fireEvent.click(previewBtn);

    await waitFor(() => {
      expect(repositoryApi.previewPullRequest).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/preview comparison/i)).toBeInTheDocument();
      expect(screen.getByText('CLEAN')).toBeInTheDocument();
    });

    // Verify suggested title was auto-populated
    const titleInput = screen.getByPlaceholderText('Pull request title');
    expect(titleInput.value).toBe('Implement feature pr preview');

    // Click Create Pull Request
    const submitBtn = screen.getByRole('button', { name: /create pull request/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(repositoryApi.createPullRequest).toHaveBeenCalledTimes(1);
      expect(screen.getByText('#99')).toBeInTheDocument();
    });
  });
});
