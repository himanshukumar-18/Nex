import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Github, ExternalLink, ShieldCheck, CheckCircle2, AlertTriangle, Trash2, RefreshCw } from 'lucide-react';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import LoadingSpinner from '@/components/feedback/LoadingSpinner';
import Alert from '@/components/feedback/Alert';
import { githubApi } from '@/services';

export function GitHubIntegrationCard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successNotice, setSuccessNotice] = useState(null);
  const [statusData, setStatusData] = useState({
    configured: false,
    app_slug: '',
    connected: false,
    installations_count: 0,
    installations: [],
  });

  const [disconnectModalOpen, setDisconnectModalOpen] = useState(false);
  const [selectedInstallation, setSelectedInstallation] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true);
      const data = await githubApi.getGitHubStatus();
      setStatusData(data);
    } catch (err) {
      setError(err?.response?.data?.message || err?.message || 'Failed to load GitHub integration status.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    // Handle incoming URL parameters from callback redirect
    const ghParam = searchParams.get('github');
    if (ghParam === 'connected' || ghParam === 'updated') {
      const syncFailed = searchParams.get('sync') === 'failed';
      if (syncFailed) {
        setSuccessNotice('GitHub App connected, but initial repository synchronization encountered an issue. You can retry from the Repositories page.');
      } else {
        setSuccessNotice(
          ghParam === 'updated'
            ? 'GitHub App installation settings synchronized successfully.'
            : 'GitHub App successfully connected and authorized for repository operations.'
        );
      }
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('github');
      newParams.delete('installation_id');
      newParams.delete('sync');
      setSearchParams(newParams, { replace: true });
    } else if (ghParam === 'error') {
      const errCode = searchParams.get('error') || 'AUTHORIZATION_FAILED';
      setError(`GitHub App authorization error (${errCode}). Please verify configuration and try again.`);
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('github');
      newParams.delete('error');
      setSearchParams(newParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const handleConnectClick = async () => {
    try {
      setActionLoading(true);
      setError(null);
      const { install_url } = await githubApi.initiateGitHubInstall();
      if (install_url) {
        window.location.href = install_url;
      }
    } catch (err) {
      setError(err?.response?.data?.message || err?.message || 'Failed to initiate GitHub App installation.');
      setActionLoading(false);
    }
  };

  const handleOpenDisconnect = (installation) => {
    setSelectedInstallation(installation);
    setDisconnectModalOpen(true);
  };

  const handleConfirmDisconnect = async () => {
    if (!selectedInstallation) return;
    try {
      setActionLoading(true);
      await githubApi.disconnectInstallation(selectedInstallation.installation_id);
      setDisconnectModalOpen(false);
      setSelectedInstallation(null);
      setSuccessNotice('GitHub installation disconnected successfully.');
      await fetchStatus();
    } catch (err) {
      setError(err?.response?.data?.message || err?.message || 'Failed to disconnect GitHub installation.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-surface-elevated border border-border rounded p-6 max-w-2xl flex items-center justify-center min-h-[160px]">
        <LoadingSpinner message="Checking GitHub App authorization..." />
      </div>
    );
  }

  const { configured, app_slug, connected, installations } = statusData || {};

  return (
    <div className="bg-surface-elevated border border-border rounded p-6 max-w-2xl flex flex-col gap-5">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <Github className="w-5 h-5 text-accent-secondary" />
          <h3 className="text-sm font-display font-semibold uppercase tracking-wider text-text-primary">
            GITHUB APP INTEGRATION
          </h3>
        </div>
        {connected ? (
          <Badge variant="success">CONNECTED</Badge>
        ) : configured ? (
          <Badge variant="outline">NOT CONNECTED</Badge>
        ) : (
          <Badge variant="warning">CONFIG REQUIRED</Badge>
        )}
      </div>

      {successNotice && (
        <Alert variant="success" onClose={() => setSuccessNotice(null)}>
          {successNotice}
        </Alert>
      )}

      {error && (
        <Alert variant="danger" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <p className="text-xs text-text-secondary leading-relaxed">
        Connect your GitHub account or organization through the official NEX GitHub App. NEX uses
        short-lived installation access tokens with scoped, read-first repository permissions.
      </p>

      {!configured ? (
        <div className="border border-warning/30 bg-warning/5 rounded p-4 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-warning text-xs font-semibold uppercase">
            <AlertTriangle className="w-4 h-4" /> Backend Configuration Required
          </div>
          <p className="text-xs text-text-secondary">
            Set <code className="text-accent-secondary">GITHUB_APP_ID</code> and{' '}
            <code className="text-accent-secondary">GITHUB_APP_PRIVATE_KEY</code> in the backend environment to enable
            repository authorization.
          </p>
        </div>
      ) : connected ? (
        <div className="flex flex-col gap-4">
          {installations.map((inst) => (
            <div
              key={inst.id}
              className="border border-border bg-surface-subtle rounded p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
              <div className="flex items-center gap-3">
                {inst.account_avatar_url ? (
                  <img
                    src={inst.account_avatar_url}
                    alt={inst.account_login}
                    className="w-10 h-10 rounded border border-border"
                  />
                ) : (
                  <div className="w-10 h-10 rounded bg-surface border border-border flex items-center justify-center">
                    <Github className="w-5 h-5 text-text-secondary" />
                  </div>
                )}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-text-primary">{inst.account_login}</span>
                    <Badge variant="cyan">{inst.account_type}</Badge>
                  </div>
                  <div className="text-[11px] text-text-muted font-mono mt-0.5">
                    Installation ID: {inst.installation_id} • Scope: {inst.target_type}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleConnectClick}
                  disabled={actionLoading}
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-1" /> Reauthorize
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => handleOpenDisconnect(inst)}
                  disabled={actionLoading}
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1" /> Disconnect
                </Button>
              </div>
            </div>
          ))}

          <div className="pt-2 flex justify-start">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleConnectClick}
              disabled={actionLoading}
            >
              <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
              Install on Another Account
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="border border-dashed border-border rounded p-6 flex flex-col items-center justify-center text-center gap-3">
            <ShieldCheck className="w-8 h-8 text-accent-secondary" />
            <div className="text-xs text-text-secondary max-w-md">
              No repositories are currently connected. Authorize the NEX GitHub App to inspect repositories, review code changes, and prepare pull requests.
            </div>
            <Button
              variant="primary"
              onClick={handleConnectClick}
              disabled={actionLoading}
            >
              <Github className="w-4 h-4 mr-2" />
              {actionLoading ? 'Redirecting to GitHub...' : `Connect ${app_slug || 'GitHub App'}`}
            </Button>
          </div>
        </div>
      )}

      {/* Disconnect Confirmation Modal */}
      <ConfirmDialog
        isOpen={disconnectModalOpen}
        onCancel={() => {
          setDisconnectModalOpen(false);
          setSelectedInstallation(null);
        }}
        onConfirm={handleConfirmDisconnect}
        title="DISCONNECT GITHUB INSTALLATION"
        description={`Are you sure you want to disconnect GitHub account '${selectedInstallation?.account_login}'? NEX will lose repository authorization and active tokens will be revoked.`}
        confirmText="Disconnect Account"
        isDestructive
      />
    </div>
  );
}

export default GitHubIntegrationCard;

