import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Mail, ArrowLeft, KeyRound } from 'lucide-react';

import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import Alert from '@/components/feedback/Alert';
import { resetPassword, formatFirebaseAuthError } from '@/services/firebase';

const forgotPasswordSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
});

export function ForgotPasswordPage() {
  const [authError, setAuthError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSent, setIsSent] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(forgotPasswordSchema),
  });

  const onSubmit = async (data) => {
    try {
      setAuthError(null);
      setIsSubmitting(true);
      await resetPassword(data.email);
      setIsSent(true);
    } catch (err) {
      setAuthError(formatFirebaseAuthError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSent) {
    return (
      <div className="flex flex-col gap-6 text-center">
        <h2 className="text-xl font-display font-bold uppercase tracking-wider text-text-primary">
          Check Your Inbox
        </h2>
        <Alert variant="success" title="RESET INSTRUCTIONS DISPATCHED">
          If an account exists with that email address, password reset instructions have been
          dispatched. Click the link in the email to choose a new secure password.
        </Alert>
        <Link to="/login">
          <Button variant="outline" className="w-full flex items-center justify-center gap-2">
            <ArrowLeft className="w-4 h-4" />
            Return to Sign In
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-display font-bold uppercase tracking-wider text-text-primary">
          Password Recovery
        </h2>
        <p className="text-xs font-mono text-text-secondary">
          ENTER YOUR EMAIL TO RECEIVE SECURE RESET CREDENTIALS
        </p>
      </div>

      {authError && (
        <Alert
          variant="danger"
          title="RESET FAILED"
          onDismiss={() => setAuthError(null)}
        >
          {authError}
        </Alert>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <Input
          label="Account Email"
          type="email"
          placeholder="developer@example.com"
          required
          autoComplete="email"
          leftIcon={<Mail className="w-4 h-4" />}
          error={errors.email?.message}
          {...register('email')}
        />

        <Button
          type="submit"
          variant="primary"
          isLoading={isSubmitting}
          className="w-full mt-2"
          leftIcon={<KeyRound className="w-4 h-4" />}
        >
          Dispatch Reset Link
        </Button>
      </form>

      <div className="text-center text-xs font-mono text-text-secondary">
        Remember your password?{' '}
        <Link to="/login" className="text-accent-secondary hover:underline font-bold">
          Return to Sign In
        </Link>
      </div>
    </div>
  );
}

export default ForgotPasswordPage;
