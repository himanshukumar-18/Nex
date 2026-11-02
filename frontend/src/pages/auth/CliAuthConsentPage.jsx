import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { Terminal, ShieldAlert, CheckCircle2, XCircle } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import Alert from '@/components/feedback/Alert';
import { selectCurrentUser } from '@/features/auth/authSlice';
import { authApi } from '@/services/authApi';

export function CliAuthConsentPage() {
  const [searchParams] = useSearchParams();
  const user = useSelector(selectCurrentUser);

  const codeChallenge = searchParams.get('code_challenge');
  const codeChallengeMethod = searchParams.get('code_challenge_method') || 'S256';
  const redirectUri = searchParams.get('redirect_uri');
  const state = searchParams.get('state');
  const deviceName = searchParams.get('device_name') || 'Terminal Client';

  const [isApproving, setIsApproving] = useState(false);
  const [error, setError] = useState(null);
  const [authorized, setAuthorized] = useState(false);

  // Validate parameters
  const isInvalidRequest = !codeChallenge || !redirectUri || !state;

  const handleApprove = async () => {
    try {
      setIsApproving(true);
      setError(null);

      const data = await authApi.authorizeCli({
        code_challenge: codeChallenge,
        code_challenge_method: codeChallengeMethod,
        redirect_uri: redirectUri,
        state,
        device_name: deviceName,
      });

      const { authorization_code } = data;
      setAuthorized(true);

      // Redirect user's browser back to local CLI loopback listener
      const callbackUrl = `${redirectUri}?code=${encodeURIComponent(
        authorization_code
      )}&state=${encodeURIComponent(state)}`;

      setTimeout(() => {
        window.location.href = callbackUrl;
      }, 500);
    } catch (err) {
      setError(
        err.message || 'Failed to authorize CLI session. Please try again or re-run nex login.'
      );
      setIsApproving(false);
    }
  };

  const handleDeny = () => {
    if (redirectUri && state) {
      window.location.href = `${redirectUri}?error=access_denied&state=${encodeURIComponent(state)}`;
    } else {
      window.close();
    }
  };

  if (isInvalidRequest) {
    return (
      <div className="flex flex-col gap-6">
        <Alert
          variant="danger"
          title="INVALID AUTHORIZATION PARAMETERS"
          description="The authorization URL is missing required RFC 7636 PKCE parameters (code_challenge, redirect_uri, or state). Please start the login flow from your terminal using 'nex login'."
        />
      </div>
    );
  }

  if (authorized) {
    return (
      <div className="flex flex-col items-center gap-6 text-center py-4">
        <CheckCircle2 className="w-12 h-12 text-status-success animate-bounce" />
        <div className="flex flex-col gap-1">
          <h2 className="text-xl font-display font-bold uppercase tracking-wider text-text-primary">
            Terminal Authorized
          </h2>
          <p className="text-xs font-mono text-text-secondary">
            REDIRECTING CREDENTIALS TO YOUR CLI LISTENER...
          </p>
        </div>
        <p className="text-xs font-mono text-text-secondary bg-surface-elevated p-3 border border-border rounded">
          You may safely close this browser tab once your terminal confirms successful login.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3 border-b border-border pb-4">
        <div className="p-2.5 rounded bg-surface-elevated border border-accent-secondary">
          <Terminal className="w-6 h-6 text-accent-secondary" />
        </div>
        <div>
          <h2 className="text-lg font-display font-bold uppercase tracking-wider text-text-primary">
            Authorize Terminal
          </h2>
          <p className="text-xs font-mono text-text-secondary">
            NEX COMMAND-LINE INTERFACE ACCESS
          </p>
        </div>
      </div>

      {error && (
        <Alert
          variant="danger"
          title="AUTHORIZATION FAILED"
          description={error}
          onClose={() => setError(null)}
        />
      )}

      <div className="flex flex-col gap-3 bg-surface-elevated/50 p-4 border border-border rounded text-xs font-mono">
        <div className="flex justify-between border-b border-border/50 pb-2">
          <span className="text-text-secondary">ACCOUNT</span>
          <span className="text-text-primary font-bold">{user?.email}</span>
        </div>
        <div className="flex justify-between border-b border-border/50 pb-2">
          <span className="text-text-secondary">DEVICE NAME</span>
          <span className="text-accent-secondary">{deviceName}</span>
        </div>
        <div className="flex justify-between border-b border-border/50 pb-2">
          <span className="text-text-secondary">CHALLENGE METHOD</span>
          <span className="text-text-primary">S256 (RFC 7636)</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">PERMITTED SCOPES</span>
          <span className="text-accent-primary">agent:run, repo:read, repo:write</span>
        </div>
      </div>

      <div className="flex items-start gap-2.5 bg-accent-warning/10 border border-accent-warning/30 p-3 rounded text-xs text-text-secondary">
        <ShieldAlert className="w-4 h-4 text-accent-warning shrink-0 mt-0.5" />
        <p>
          Granting authorization gives the CLI session full access to interact with NEX agents and
          run approved operations on your behalf.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 mt-2">
        <Button
          variant="outline"
          onClick={handleDeny}
          disabled={isApproving}
          className="w-full flex items-center justify-center gap-2"
        >
          <XCircle className="w-4 h-4" />
          Deny
        </Button>
        <Button
          variant="primary"
          onClick={handleApprove}
          isLoading={isApproving}
          className="w-full flex items-center justify-center gap-2"
        >
          <CheckCircle2 className="w-4 h-4" />
          Authorize
        </Button>
      </div>
    </div>
  );
}

export default CliAuthConsentPage;

