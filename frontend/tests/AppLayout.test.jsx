import React from 'react';
import { describe, it, expect } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import AppLayout from '@/layouts/AppLayout';

describe('AppLayout Component', () => {
  it('renders top bar brand and navigation links', () => {
    renderWithProviders(<AppLayout />);

    expect(screen.getByText('NEX')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Projects')).toBeInTheDocument();
    expect(screen.getByText('Agent Runs')).toBeInTheDocument();
    expect(screen.getByText('Approvals')).toBeInTheDocument();
    expect(screen.getByText('Audit Log')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders system online status indicator', () => {
    renderWithProviders(<AppLayout />);
    expect(screen.getByText('ONLINE')).toBeInTheDocument();
  });

  it('displays system notice when present in state', () => {
    renderWithProviders(<AppLayout />, {
      preloadedState: {
        ui: {
          sidebarCollapsed: false,
          mobileMenuOpen: false,
          activeNav: 'dashboard',
          systemNotice: {
            id: 'n-1',
            type: 'warning',
            title: 'MAINTENANCE ADVISORY',
            message: 'Database backup in progress.',
            dismissible: true,
          },
          toasts: [],
        },
      },
    });

    expect(screen.getByText('MAINTENANCE ADVISORY')).toBeInTheDocument();
    expect(screen.getByText('Database backup in progress.')).toBeInTheDocument();
  });

  it('toggles mobile menu drawer when mobile button is clicked', () => {
    renderWithProviders(<AppLayout />);

    const toggleBtn = screen.getByRole('button', { name: /Toggle mobile menu/i });
    fireEvent.click(toggleBtn);

    expect(screen.getByText('NEX NAVIGATION')).toBeInTheDocument();
  });
});

