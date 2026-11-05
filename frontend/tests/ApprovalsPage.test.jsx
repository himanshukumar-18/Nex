import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import ApprovalsPage from '@/pages/ApprovalsPage';
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

describe('ApprovalsPage Component', () => {
  const mockPendingOps = [
    {
      id: 'op-pending-1',
      operation_type: 'push',
      target_branch: 'main',
      risk_level: 'CRITICAL',
      status: 'pending',
      created_at: '2026-11-03T15:00:00Z',
      correlation_id: 'corr-12345678',
    },
  ];

  const mockAllOps = [
    {
      id: 'op-hist-1',
      operation_type: 'commit',
      target_branch: 'feat/test',
      risk_level: 'HIGH',
      status: 'completed',
      created_at: '2026-11-03T14:30:00Z',
      correlation_id: 'corr-87654321',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();

    repositoryApi.getOperations.mockImplementation((repoId, params) => {
      if (params?.status === 'pending') {
        return Promise.resolve({ count: mockPendingOps.length, results: mockPendingOps });
      }
      return Promise.resolve({ count: mockAllOps.length, results: mockAllOps });
    });
  });

  it('renders header, tabs, and pending approval badge', async () => {
    renderWithProviders(<ApprovalsPage />);

    expect(screen.getByText(/HUMAN-IN-THE-LOOP APPROVALS/i)).toBeInTheDocument();
    expect(screen.getByText('PENDING APPROVALS')).toBeInTheDocument();
    expect(screen.getByText('APPROVAL POLICY MATRIX')).toBeInTheDocument();
    expect(screen.getByText('AUDIT & VERIFICATION TRAIL')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/1 PENDING/i)).toBeInTheDocument();
      expect(screen.getByText(/CRITICAL/i)).toBeInTheDocument();
    });
  });

  it('renders empty state when no pending approvals exist', async () => {
    repositoryApi.getOperations.mockImplementation((repoId, params) => {
      if (params?.status === 'pending') {
        return Promise.resolve({ count: 0, results: [] });
      }
      return Promise.resolve({ count: 0, results: [] });
    });

    renderWithProviders(<ApprovalsPage />);

    await waitFor(() => {
      expect(screen.getByText(/NO PENDING APPROVALS/i)).toBeInTheDocument();
      expect(screen.getByText(/0 PENDING/i)).toBeInTheDocument();
    });
  });

  it('navigates to policy matrix tab and renders the 4 risk tiers', async () => {
    renderWithProviders(<ApprovalsPage />);

    const policyTab = screen.getByText('APPROVAL POLICY MATRIX');
    fireEvent.click(policyTab);

    expect(screen.getByText(/TIER 1: LOW RISK/i)).toBeInTheDocument();
    expect(screen.getByText(/TIER 2: MEDIUM RISK/i)).toBeInTheDocument();
    expect(screen.getByText(/TIER 3: HIGH RISK/i)).toBeInTheDocument();
    expect(screen.getByText(/TIER 4: CRITICAL RISK/i)).toBeInTheDocument();
  });

  it('navigates to audit trail tab and displays historical records', async () => {
    renderWithProviders(<ApprovalsPage />);

    const historyTab = screen.getByText('AUDIT & VERIFICATION TRAIL');
    fireEvent.click(historyTab);

    await waitFor(() => {
      expect(screen.getByText('feat/test')).toBeInTheDocument();
      expect(screen.getByText('HIGH')).toBeInTheDocument();
      expect(screen.getByText('COMPLETED')).toBeInTheDocument();
    });
  });
});

