import React, { useState } from 'react';
import { Lock, LogIn, AlertTriangle, ShieldCheck } from 'lucide-react';

import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import Alert from '@/components/feedback/Alert';
import {
  linkWithPassword,
  linkWithGoogle,
  formatFirebaseAuthError,
} from '@/services/firebase';

export function AccountLinkingModal({
  isOpen,
  onClose,
  email,
  pendingCredential,
  onSuccess,
}) {
  const [method, setMethod] = useState('password'); // 'password' | 'google'
  const [password, setPassword] = useState('');
  const [isLinking, setIsLinking] = useState(false);
  const [linkError, setLinkError] = useState(null);

  const handlePasswordLink = async (e) => {
    e.preventDefault();
    if (!password) {
      setLinkError('Please enter your account password.');
      return;
    }

    try {
      setIsLinking(true);
      setLinkError(null);
      await linkWithPassword(email, password, pendingCredential);
      setPassword('');
      onSuccess?.();
    } catch (err) {
      setLinkError(formatFirebaseAuthError(err));
    } finally {
      setIsLinking(false);
    }
  };

  const handleGoogleLink = async () => {
    try {
      setIsLinking(true);
      setLinkError(null);
      await linkWithGoogle(pendingCredential);
      onSuccess?.();
    } catch (err) {
      setLinkError(formatFirebaseAuthError(err));
    } finally {
      setIsLinking(false);
    }
  };

  const handleClose = () => {
    setPassword('');
    setLinkError(null);
    onClose?.();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Link Existing Account"
      description="VERIFY IDENTITY TO CONNECT GITHUB"
      maxWidth="max-w-md"
    >
      <div className="flex flex-col gap-5 pt-2">
        <Alert
          variant="warning"
          title="ACCOUNT MERGE CONFIRMATION REQUIRED"
        >
          {`An account already exists for ${email || 'this email'}. To prevent account hijacking, verify ownership using your existing sign-in method before linking GitHub.`}
        </Alert>

        {linkError && (
          <Alert
            variant="danger"
            title="VERIFICATION FAILED"
            onDismiss={() => setLinkError(null)}
          >
            {linkError}
          </Alert>
        )}

        {/* Tab switch between Password and Google */}
        <div className="flex border border-border-default rounded overflow-hidden">
          <button
            type="button"
            onClick={() => {
              setMethod('password');
              setLinkError(null);
            }}
            className={`flex-1 py-2 text-xs font-mono font-bold uppercase tracking-wider transition-colors ${
              method === 'password'
                ? 'bg-accent-primary text-white'
                : 'bg-surface-elevated text-text-secondary hover:text-text-primary'
            }`}
          >
            Password
          </button>
          <button
            type="button"
            onClick={() => {
              setMethod('google');
              setLinkError(null);
            }}
            className={`flex-1 py-2 text-xs font-mono font-bold uppercase tracking-wider transition-colors ${
              method === 'google'
                ? 'bg-accent-primary text-white'
                : 'bg-surface-elevated text-text-secondary hover:text-text-primary'
            }`}
          >
            Google OAuth
          </button>
        </div>

        {method === 'password' ? (
          <form onSubmit={handlePasswordLink} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-mono text-text-secondary uppercase">
                Account Email
              </label>
              <input
                type="text"
                value={email}
                disabled
                className="w-full bg-surface-base border border-border-default px-3 py-2 text-sm font-mono text-text-muted cursor-not-allowed rounded"
              />
            </div>

            <Input
              label="Password"
              type="password"
              placeholder="Enter your existing account password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              leftIcon={<Lock className="w-4 h-4 text-text-secondary" />}
              autoFocus
            />

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                disabled={isLinking}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                isLoading={isLinking}
                className="flex items-center gap-2"
              >
                <ShieldCheck className="w-4 h-4" />
                Verify & Link
              </Button>
            </div>
          </form>
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-xs font-mono text-text-secondary leading-relaxed">
              Authenticate with your Google account ({email}) to cryptographically confirm ownership and link your GitHub credentials.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                disabled={isLinking}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="cyan"
                onClick={handleGoogleLink}
                isLoading={isLinking}
                className="flex items-center gap-2"
              >
                <LogIn className="w-4 h-4" />
                Sign In with Google to Link
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

export default AccountLinkingModal;
