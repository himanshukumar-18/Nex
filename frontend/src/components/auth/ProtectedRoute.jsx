import React from 'react';
import { Navigate, useLocation, Outlet } from 'react-router-dom';
import { useSelector } from 'react-redux';
import {
  selectIsAuthenticated,
  selectAuthLoading,
  selectCurrentUser,
  selectAuthStatus,
  AUTH_STATUS,
} from '@/features/auth/authSlice';
import LoadingSpinner from '@/components/feedback/LoadingSpinner';
import Alert from '@/components/feedback/Alert';

export function ProtectedRoute({
  children,
  allowedRoles = null,
  requireEmailVerified = false,
}) {
  const location = useLocation();
  const isAuthenticated = useSelector(selectIsAuthenticated);
  const isLoading = useSelector(selectAuthLoading);
  const authStatus = useSelector(selectAuthStatus);
  const user = useSelector(selectCurrentUser);

  // If loading or in an active initialization/sync state, do not redirect!
  if (
    isLoading ||
    authStatus === AUTH_STATUS.INITIALIZING ||
    authStatus === AUTH_STATUS.FIREBASE_AUTHENTICATED ||
    authStatus === AUTH_STATUS.SYNCHRONIZING_PROFILE
  ) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center">
        <LoadingSpinner size="lg" message="VERIFYING IDENTITY & ROLE ACCESS..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireEmailVerified && user && !user.emailVerified) {
    return (
      <div className="min-h-screen bg-bg-primary flex flex-col items-center justify-center p-6 text-center">
        <div className="max-w-md w-full bg-surface-elevated border-2 border-accent-warning p-6 rounded shadow-2xl flex flex-col gap-4">
          <Alert variant="warning" title="EMAIL VERIFICATION REQUIRED">
            {`A verification email was sent to ${user.email}. Please verify your email before accessing protected engineering workspaces.`}
          </Alert>
          <p className="font-mono text-xs text-text-secondary">
            Once verified in your email client, refresh this page or sign in again.
          </p>
        </div>
      </div>
    );
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center p-6 text-center">
        <div className="max-w-md w-full bg-surface-elevated border-2 border-accent-danger p-6 rounded shadow-2xl flex flex-col gap-4">
          <Alert variant="danger" title="403 — ACCESS RESTRICTED">
            {`Your current role (${user.role}) lacks authorization to access this area.`}
          </Alert>
        </div>
      </div>
    );
  }

  return children ? children : <Outlet />;
}

export default ProtectedRoute;
