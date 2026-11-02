import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Mail, Lock, LogIn, Github } from 'lucide-react';

import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import Alert from '@/components/feedback/Alert';
import { AccountLinkingModal } from '@/components/auth/AccountLinkingModal';
import {
  auth,
  loginWithEmail,
  loginWithGoogle,
  loginWithGithub,
  formatFirebaseAuthError,
  getPendingCredential,
} from '@/services/firebase';
import { synchronizeSession } from '@/services/authApi';
import {
  selectIsAuthenticated,
  selectAuthLoading,
} from '@/features/auth/authSlice';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
});

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch();

  const isAuthenticated = useSelector(selectIsAuthenticated);
  const isAuthLoading = useSelector(selectAuthLoading);

  const [authError, setAuthError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [linkingState, setLinkingState] = useState({
    isOpen: false,
    email: '',
    pendingCredential: null,
  });

  const from = location.state?.from?.pathname || '/';

  // If already authenticated and not loading, redirect to target immediately
  useEffect(() => {
    if (isAuthenticated && !isAuthLoading) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, isAuthLoading, navigate, from]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data) => {
    try {
      setAuthError(null);
      setIsSubmitting(true);
      const userCredential = await loginWithEmail(data.email, data.password);
      await synchronizeSession(userCredential.user, dispatch);
      navigate(from, { replace: true });
    } catch (err) {
      setAuthError(formatFirebaseAuthError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleLogin = async () => {
    try {
      setAuthError(null);
      setIsSubmitting(true);
      const userCredential = await loginWithGoogle();
      await synchronizeSession(userCredential.user, dispatch);
      navigate(from, { replace: true });
    } catch (err) {
      if (err?.code === 'auth/account-exists-with-different-credential') {
        const pendingCred = getPendingCredential(err);
        const email = err.customData?.email || '';
        setLinkingState({
          isOpen: true,
          email,
          pendingCredential: pendingCred,
        });
        return;
      }
      setAuthError(formatFirebaseAuthError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGithubLogin = async () => {
    try {
      setAuthError(null);
      setIsSubmitting(true);
      const userCredential = await loginWithGithub();
      await synchronizeSession(userCredential.user, dispatch);
      navigate(from, { replace: true });
    } catch (err) {
      if (err?.code === 'auth/account-exists-with-different-credential') {
        const pendingCred = getPendingCredential(err);
        const email = err.customData?.email || '';
        setLinkingState({
          isOpen: true,
          email,
          pendingCredential: pendingCred,
        });
        return;
      }
      setAuthError(formatFirebaseAuthError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-display font-bold uppercase tracking-wider text-text-primary">
          Sign In
        </h2>
        <p className="text-xs font-mono text-text-secondary">
          ACCESS THE SECURE NEX AGENT CONTROL CENTER
        </p>
      </div>

      {authError && (
        <Alert
          variant="danger"
          title="AUTHENTICATION FAILED"
          onDismiss={() => setAuthError(null)}
        >
          {authError}
        </Alert>
      )}

      {/* Social Providers */}
      <div className="grid grid-cols-2 gap-3">
        <Button
          variant="outline"
          onClick={handleGoogleLogin}
          isLoading={isSubmitting}
          className="w-full flex items-center justify-center gap-2 text-xs"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="currentColor"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="currentColor"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="currentColor"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          Google
        </Button>
        <Button
          variant="outline"
          onClick={handleGithubLogin}
          isLoading={isSubmitting}
          className="w-full flex items-center justify-center gap-2 text-xs"
        >
          <Github className="w-4 h-4" />
          GitHub
        </Button>
      </div>

      <div className="relative flex items-center justify-center">
        <div className="border-t border-border w-full"></div>
        <span className="bg-surface-elevated px-3 text-[10px] font-mono text-text-secondary uppercase">
          OR EMAIL & PASSWORD
        </span>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <Input
          label="Email Address"
          type="email"
          placeholder="developer@example.com"
          required
          autoComplete="email"
          leftIcon={<Mail className="w-4 h-4" />}
          error={errors.email?.message}
          {...register('email')}
        />

        <div className="flex flex-col gap-1">
          <Input
            label="Password"
            type="password"
            placeholder="••••••••"
            required
            autoComplete="current-password"
            leftIcon={<Lock className="w-4 h-4" />}
            error={errors.password?.message}
            {...register('password')}
          />
          <div className="flex justify-end">
            <Link
              to="/forgot-password"
              className="text-xs font-mono text-accent-secondary hover:underline"
            >
              Forgot Password?
            </Link>
          </div>
        </div>

        <Button
          type="submit"
          variant="primary"
          isLoading={isSubmitting}
          className="w-full mt-2"
          leftIcon={<LogIn className="w-4 h-4" />}
        >
          Authenticate
        </Button>
      </form>

      {/* Footer */}
      <div className="text-center text-xs font-mono text-text-secondary">
        Don&apos;t have an account?{' '}
        <Link to="/register" className="text-accent-primary hover:underline font-bold">
          Register
        </Link>
      </div>

      {/* Account Linking Modal for Provider Collisions */}
      <AccountLinkingModal
        isOpen={linkingState.isOpen}
        onClose={() => setLinkingState({ isOpen: false, email: '', pendingCredential: null })}
        email={linkingState.email}
        pendingCredential={linkingState.pendingCredential}
        onSuccess={async () => {
          setLinkingState({ isOpen: false, email: '', pendingCredential: null });
          try {
            if (auth.currentUser) {
              await synchronizeSession(auth.currentUser, dispatch);
            }
            navigate(from, { replace: true });
          } catch (err) {
            setAuthError(formatFirebaseAuthError(err));
          }
        }}
      />
    </div>
  );
}

export default LoginPage;
