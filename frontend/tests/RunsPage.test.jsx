import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import RunsPage from '@/pages/RunsPage';
import { renderWithProviders } from './test-utils';
import { runsApi } from '@/services/runsApi';

vi.mock('@/services/runsApi', () => ({
  runsApi: {
    getRuns: vi.fn(),
    getRun: vi.fn(),
  },
  default: {
    getRuns: vi.fn(),
    getRun: vi.fn(),
  },
}));

describe('RunsPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    runsApi.getRuns.mockResolvedValue({
      count: 0,
      results: [],
      ready: false,
    });
  });

  it('renders header, workflow execution guide, and CLI commands', async () => {
    renderWithProviders(<RunsPage />);

    expect(screen.getByText(/AGENT EXECUTION RUNS/i)).toBeInTheDocument();
    expect(screen.getByText(/AUTONOMOUS WORKFLOW EXECUTION VIA CLI/i)).toBeInTheDocument();
    expect(screen.getByText(/TASK EXECUTION/i)).toBeInTheDocument();
    expect(screen.getByText(/CODE REVIEW/i)).toBeInTheDocument();
    expect(screen.getByText(/PULL REQUEST LIFECYCLE/i)).toBeInTheDocument();
    expect(screen.getByText(/nex fix/i)).toBeInTheDocument();
  });

  it('renders empty state when no agent runs are recorded', async () => {
    renderWithProviders(<RunsPage />);

    await waitFor(() => {
      expect(screen.getByText(/NO AGENT RUNS RECORDED/i)).toBeInTheDocument();
      expect(screen.getByText(/CLI DIRECT EXECUTION/i)).toBeInTheDocument();
    });
  });

  it('renders runs table when runs are returned from backend', async () => {
    runsApi.getRuns.mockResolvedValue({
      count: 1,
      results: [
        {
          id: 'run-uuid-12345678',
          task_prompt: 'Fix memory leak in rate limiter',
          status: 'completed',
          created_at: '2026-11-03T16:00:00Z',
          duration: 42,
        },
      ],
      ready: true,
    });

    renderWithProviders(<RunsPage />);

    await waitFor(() => {
      expect(screen.getByText('Fix memory leak in rate limiter')).toBeInTheDocument();
      expect(screen.getByText('COMPLETED')).toBeInTheDocument();
      expect(screen.getByText('42s')).toBeInTheDocument();
      expect(screen.getByText(/1 RUNS RECORDED/i)).toBeInTheDocument();
    });
  });
});

