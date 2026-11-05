import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import HistoryPage from '@/pages/HistoryPage';
import { renderWithProviders } from './test-utils';
import { repositoryApi } from '@/services/repositoryApi';

vi.mock('@/services/repositoryApi', () => ({
  repositoryApi: {
    getOperations: vi.fn(),
  },
  default: {
    getOperations: vi.fn(),
  },
}));

describe('HistoryPage Component', () => {
  const mockOperations = [
    {
      id: 'op-001',
      operation_type: 'commit',
      target_branch: 'feat/audit-log',
      commit_sha: 'a1b2c3d4e5f6',
      commit_message: 'feat(audit): implement immutable audit logging',
      risk_level: 'HIGH',
      status: 'completed',
      correlation_id: 'corr-uuid-12345678',
      created_at: '2026-11-03T15:30:00Z',
    },
    {
      id: 'op-002',
      operation_type: 'push',
      target_branch: 'main',
      commit_sha: null,
      commit_message: null,
      risk_level: 'CRITICAL',
      status: 'simulated',
      correlation_id: 'corr-uuid-87654321',
      created_at: '2026-11-03T15:35:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    repositoryApi.getOperations.mockResolvedValue({
      count: 2,
      results: mockOperations,
    });
  });

  it('renders header, event count badge, and table data', async () => {
    renderWithProviders(<HistoryPage />);

    expect(screen.getByText(/IMMUTABLE AUDIT LOG/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/2 EVENTS RECORDED/i)).toBeInTheDocument();
      expect(screen.getByText('feat/audit-log')).toBeInTheDocument();
      expect(screen.getByText(/implement immutable audit logging/i)).toBeInTheDocument();
      expect(screen.getByText('HIGH')).toBeInTheDocument();
      expect(screen.getByText('COMPLETED')).toBeInTheDocument();
      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
      expect(screen.getByText('SIMULATED')).toBeInTheDocument();
    });
  });

  it('filters operations based on search query', async () => {
    renderWithProviders(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('feat/audit-log')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search branch, sha, correlation ID.../i);
    fireEvent.change(searchInput, { target: { value: 'main' } });

    expect(screen.queryByText('feat/audit-log')).not.toBeInTheDocument();
    expect(screen.getByText('main')).toBeInTheDocument();
  });

  it('renders empty state when no matching records found', async () => {
    repositoryApi.getOperations.mockResolvedValue({ count: 0, results: [] });

    renderWithProviders(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByText(/NO AUDIT EVENTS FOUND/i)).toBeInTheDocument();
    });
  });

  it('copies correlation ID to clipboard on button click', async () => {
    // Mock clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(),
      },
    });

    renderWithProviders(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getAllByText(/corr-uui/i).length).toBeGreaterThan(0);
    });

    const copyBtn = screen.getAllByTitle(/Click to copy correlation ID/i)[0];
    fireEvent.click(copyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('corr-uuid-12345678');
  });
});
