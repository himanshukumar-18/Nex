import React from 'react';
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { Routes, Route } from 'react-router-dom';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { renderWithProviders } from './test-utils';

describe('ProtectedRoute Component', () => {
  it('renders loading spinner when auth state is loading', () => {
    const preloadedState = {
      auth: {
        user: null,
        idToken: null,
        isAuthenticated: false,
        isLoading: true,
      },
    };

    renderWithProviders(
      <Routes>
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <div>PROTECTED WORKSPACE</div>
            </ProtectedRoute>
          }
        />
      </Routes>,
      { preloadedState, initialEntries: ['/dashboard'] }
    );

    expect(screen.getByText(/VERIFYING IDENTITY & ROLE ACCESS/i)).toBeInTheDocument();
  });

  it('redirects unauthenticated users to login route', () => {
    const preloadedState = {
      auth: {
        user: null,
        idToken: null,
        isAuthenticated: false,
        isLoading: false,
      },
    };

    renderWithProviders(
      <Routes>
        <Route path="/login" element={<div>LOGIN SCREEN</div>} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <div>PROTECTED WORKSPACE</div>
            </ProtectedRoute>
          }
        />
      </Routes>,
      { preloadedState, initialEntries: ['/dashboard'] }
    );

    expect(screen.getByText('LOGIN SCREEN')).toBeInTheDocument();
  });

  it('renders children when user is authenticated', () => {
    const preloadedState = {
      auth: {
        user: { email: 'alex@nex.dev', emailVerified: true, role: 'developer' },
        idToken: 'valid_token',
        isAuthenticated: true,
        isLoading: false,
      },
    };

    renderWithProviders(
      <Routes>
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <div>PROTECTED WORKSPACE</div>
            </ProtectedRoute>
          }
        />
      </Routes>,
      { preloadedState, initialEntries: ['/dashboard'] }
    );

    expect(screen.getByText('PROTECTED WORKSPACE')).toBeInTheDocument();
  });

  it('enforces email verification when required', () => {
    const preloadedState = {
      auth: {
        user: { email: 'unverified@nex.dev', emailVerified: false, role: 'member' },
        idToken: 'valid_token',
        isAuthenticated: true,
        isLoading: false,
      },
    };

    renderWithProviders(
      <Routes>
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute requireEmailVerified>
              <div>PROTECTED WORKSPACE</div>
            </ProtectedRoute>
          }
        />
      </Routes>,
      { preloadedState, initialEntries: ['/dashboard'] }
    );

    expect(screen.getByText(/EMAIL VERIFICATION REQUIRED/i)).toBeInTheDocument();
  });

  it('enforces role restrictions when allowedRoles is specified', () => {
    const preloadedState = {
      auth: {
        user: { email: 'member@nex.dev', emailVerified: true, role: 'member' },
        idToken: 'valid_token',
        isAuthenticated: true,
        isLoading: false,
      },
    };

    renderWithProviders(
      <Routes>
        <Route
          path="/admin"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <div>ADMIN PANEL</div>
            </ProtectedRoute>
          }
        />
      </Routes>,
      { preloadedState, initialEntries: ['/admin'] }
    );

    expect(screen.getByText(/403 — ACCESS RESTRICTED/i)).toBeInTheDocument();
  });
});

