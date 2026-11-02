import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Mail, Lock, User, UserPlus, Github } from 'lucide-react';

import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import Alert from '@/components/feedback/Alert';
import {
  registerWithEmail,
  loginWithGoogle,
  loginWithGithub,
  formatFirebaseAuthError,
} from '@/services/firebase';
import { synchronizeSession } from '@/services/authApi';

const registerSchema = z
  .object({
    displayName: z.string().min(2, 'Display name must be at least 2 characters'),
    email: z.string().email('Please enter a valid email address'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string().min(8, 'Password confirmation is required'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

export function RegisterPage() {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const [authError, setAuthError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRegistered, setIsRegistered] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data) => {
    try {
      setAuthError(null);
      setIsSubmitting(true);
      await registerWithEmail(data.email, data.password, data.displayName);
      setIsRegistered(true);
    } catch (err) {
      setAuthError(formatFirebaseAuthError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleSignup = async () => {
    try {
      setAuthError(null);
      setIsSubmitting(true);
      const userCredential = await loginWithGoogle();
      await synchronizeSession(userCredential.user, dispatch);
      navigate('/', { replace: true });
    } catch (err) {
      setAuthError(formatFirebaseAuthError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGithubSignup = async () => {
    try {
      setAuthError(null);
      setIsSubmitting(true);
      const userCredential = await loginWithGithub();
      await synchronizeSession(userCredential.user, dispatch);
      navigate('/', { replace: true });
    } catch (err) {
      setAuthError(formatFirebaseAuthError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isRegistered) {
    return (
      <div className="flex flex-col gap-6 text-center">
        <h2 className="text-xl font-display font-bold uppercase tracking-wider text-text-primary">
          Verify Your Email
        </h2>
        <Alert variant="success" title="REGISTRATION COMPLETE">
          A verification link has been sent to your email address. Please check your inbox and verify
          your account to unlock all NEX developer capabilities.
        </Alert>
        <Link to="/login">
          <Button variant="primary" className="w-full">
            Proceed to Login
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-display font-bold uppercase tracking-wider text-text-primary">
          Create Account
        </h2>
        <p className="text-xs font-mono text-text-secondary">
          JOIN THE NEX AI SOFTWARE ENGINEERING PLATFORM
        </p>
      </div>

      {authError && (
        <Alert
          variant="danger"
          title="REGISTRATION FAILED"
          onDismiss={() => setAuthError(null)}
        >
          {authError}
        </Alert>
      )}

      {/* Social Providers */}
      <div className="grid grid-cols-2 gap-3">
        <Button
          variant="outline"
          onClick={handleGoogleSignup}
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
          onClick={handleGithubSignup}
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
          label="Full Name"
          placeholder="Ada Lovelace"
          required
          autoComplete="name"
          leftIcon={<User className="w-4 h-4" />}
          error={errors.displayName?.message}
          {...register('displayName')}
        />

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

        <Input
          label="Password"
          type="password"
          placeholder="••••••••"
          required
          autoComplete="new-password"
          leftIcon={<Lock className="w-4 h-4" />}
          error={errors.password?.message}
          {...register('password')}
        />

        <Input
          label="Confirm Password"
          type="password"
          placeholder="••••••••"
          required
          autoComplete="new-password"
          leftIcon={<Lock className="w-4 h-4" />}
          error={errors.confirmPassword?.message}
          {...register('confirmPassword')}
        />

        <Button
          type="submit"
          variant="primary"
          isLoading={isSubmitting}
          className="w-full mt-2"
          leftIcon={<UserPlus className="w-4 h-4" />}
        >
          Create Account
        </Button>
      </form>

      {/* Footer */}
      <div className="text-center text-xs font-mono text-text-secondary">
        Already have an account?{' '}
        <Link to="/login" className="text-accent-primary hover:underline font-bold">
          Sign In
        </Link>
      </div>
    </div>
  );
}

export default RegisterPage;
