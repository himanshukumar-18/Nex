import React from 'react';
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import NotFoundPage from '@/pages/NotFoundPage';

describe('NotFoundPage Component', () => {
  it('renders 404 error code and guidance message', () => {
    renderWithProviders(<NotFoundPage />);

    expect(screen.getByText(/ERROR 404 • ROUTE_NOT_FOUND/i)).toBeInTheDocument();
    expect(screen.getByText(/RESOURCE NOT LOCATED/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Return to Workspace/i })
    ).toBeInTheDocument();
  });
});

