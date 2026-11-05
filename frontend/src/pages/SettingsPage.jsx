import React, { useState, useEffect, useCallback } from 'react';
import { useAppSelector, useAppDispatch } from '@/app/hooks';
import { addToast } from '@/features/ui/uiSlice';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Badge from '@/components/ui/Badge';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import EmptyState from '@/components/feedback/EmptyState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import GitHubIntegrationCard from '@/components/github/GitHubIntegrationCard';
import { authApi } from '@/services/authApi';
import { resetPassword, resendVerificationEmail } from '@/services/firebase';
import { env } from '@/config/env';
import {
  User,
  Terminal,
  ShieldCheck,
  Mail,
  Key,
  Server,
  RefreshCw,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Lock,
} from 'lucide-react';

export function SettingsPage() {
  const dispatch = useAppDispatch();
  const { user } = useAppSelector((state) => state.auth);

  // CLI Sessions state
  const [sessions, setSessions] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [revokingId, setRevokingId] = useState(null);
  const [resettingPassword, setResettingPassword] = useState(false);
  const [resendingVerification, setResendingVerification] = useState(false);

  const fetchCliSessions = useCallback(async () => {
    try {
      setLoadingSessions(true);
      const data = await authApi.getCliSessions();
      setSessions(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      // Don't hard-crash if CLI sessions fail; empty list is safe
      setSessions([]);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    fetchCliSessions();
  }, [fetchCliSessions]);

  const handleRevokeSession = async (sessionId) => {
    try {
      setRevokingId(sessionId);
      await authApi.revokeCliSession(sessionId);
      dispatch(
        addToast({
          type: 'success',
          title: 'SESSION REVOKED',
          message: 'CLI authorization token has been revoked successfully.',
        })
      );
      await fetchCliSessions();
    } catch (err) {
      dispatch(
        addToast({
          type: 'danger',
          title: 'REVOCATION FAILED',
          message: err?.message || 'Failed to revoke CLI session.',
        })
      );
    } finally {
      setRevokingId(null);
    }
  };

  const handlePasswordReset = async () => {
    if (!user?.email) return;
    try {
      setResettingPassword(true);
      await resetPassword(user.email);
      dispatch(
        addToast({
          type: 'success',
          title: 'PASSWORD RESET SENT',
          message: `Password reset link delivered to ${user.email}. Check your inbox.`,
        })
      );
    } catch (err) {
      dispatch(
        addToast({
          type: 'danger',
          title: 'RESET REQUEST FAILED',
          message: err?.message || 'Failed to dispatch password reset email.',
        })
      );
    } finally {
      setResettingPassword(false);
    }
  };

  const handleResendVerification = async () => {
    try {
      setResendingVerification(true);
      await resendVerificationEmail();
      dispatch(
        addToast({
          type: 'success',
          title: 'VERIFICATION SENT',
          message: `Verification email dispatched to ${user?.email}.`,
        })
      );
    } catch (err) {
      dispatch(
        addToast({
          type: 'danger',
          title: 'DISPATCH FAILED',
          message: err?.message || 'Failed to send verification email.',
        })
      );
    } finally {
      setResendingVerification(false);
    }
  };

  const getRoleBadgeVariant = (role) => {
    const r = (role || 'member').toLowerCase();
    if (r === 'admin') return 'danger';
    if (r === 'developer' || r === 'lead') return 'accent';
    return 'cyan';
  };

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb items={[{ label: 'Settings' }]} />
      <PageHeader
        title="SYSTEM & WORKSPACE SETTINGS"
        description="Configure identity credentials, GitHub App authorizations, CLI sessions, and API architecture."
        badge={<Badge variant="outline">PRODUCTION READY</Badge>}
      />

      {/* 1. User Profile & Identity Security */}
      <div className="bg-surface-elevated border border-border rounded p-6 max-w-4xl flex flex-col gap-5">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-accent-secondary" />
            <h3 className="text-sm font-display font-semibold uppercase tracking-wider text-text-primary">
              USER IDENTITY & CREDENTIALS
            </h3>
          </div>
          <Badge variant={getRoleBadgeVariant(user?.role)} size="sm">
            {user?.role || 'DEVELOPER'}
          </Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-mono text-text-secondary uppercase">Display Name</label>
            <div className="px-3 py-2 bg-bg-secondary border border-border rounded text-xs font-mono text-text-primary">
              {user?.displayName || 'NEX Developer'}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-mono text-text-secondary uppercase">Email Address</label>
            <div className="px-3 py-2 bg-bg-secondary border border-border rounded text-xs font-mono text-text-primary flex items-center justify-between">
              <span className="truncate">{user?.email || 'unauthenticated'}</span>
              {user?.emailVerified ? (
                <Badge variant="success" size="sm" dot>VERIFIED</Badge>
              ) : (
                <Badge variant="warning" size="sm" dot>UNVERIFIED</Badge>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-2 border-t border-border">
          <div className="text-xs font-mono text-text-secondary">
            UID: <span className="text-accent-highlight">{user?.uid ? `${user.uid.slice(0, 16)}...` : 'N/A'}</span>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {!user?.emailVerified && (
              <Button
                variant="outline"
                size="sm"
                leftIcon={<Mail className="w-3.5 h-3.5" />}
                onClick={handleResendVerification}
                isLoading={resendingVerification}
              >
                Resend Verification
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              leftIcon={<Key className="w-3.5 h-3.5" />}
              onClick={handlePasswordReset}
              isLoading={resettingPassword}
            >
              Reset Password
            </Button>
          </div>
        </div>
      </div>

      {/* 2. GitHub App Integration */}
      <GitHubIntegrationCard />

      {/* 3. Active CLI Sessions Management */}
      <div className="bg-surface-elevated border border-border rounded p-6 max-w-4xl flex flex-col gap-5">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-accent-highlight" />
            <h3 className="text-sm font-display font-semibold uppercase tracking-wider text-text-primary">
              ACTIVE CLI SESSIONS
            </h3>
          </div>
          <Button
            variant="outline"
            size="sm"
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loadingSessions ? 'animate-spin' : ''}`} />}
            onClick={fetchCliSessions}
            disabled={loadingSessions}
          >
            Refresh
          </Button>
        </div>

        <p className="text-xs font-mono text-text-secondary">
          Tokens authorized through <code className="text-accent-secondary">nex auth login</code> using PKCE with local loopback. Revoking a session immediately terminates CLI access.
        </p>

        {loadingSessions ? (
          <div className="space-y-3">
            {[...Array(2)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <EmptyState
            icon={<Terminal className="w-5 h-5 text-accent-highlight" />}
            title="NO ACTIVE CLI SESSIONS"
            description="You are not signed in on any terminal workstations. Run 'nex auth login' from your terminal to establish a session."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>DEVICE / CLIENT</TableHead>
                <TableHead>SESSION ID</TableHead>
                <TableHead>LAST USED</TableHead>
                <TableHead>EXPIRES</TableHead>
                <TableHead className="text-right">ACTION</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((sess) => (
                <TableRow key={sess.id}>
                  <TableCell className="font-semibold text-text-primary">
                    <div className="flex items-center gap-2">
                      <Terminal className="w-3.5 h-3.5 text-accent-primary" />
                      <span>{sess.device_name || 'Terminal Workstation'}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-text-secondary">
                    {sess.id ? `${sess.id.slice(0, 8)}...` : 'N/A'}
                  </TableCell>
                  <TableCell className="text-text-secondary">
                    {sess.last_used_at ? new Date(sess.last_used_at).toLocaleString() : 'Just now'}
                  </TableCell>
                  <TableCell className="text-text-secondary">
                    {sess.expires_at ? new Date(sess.expires_at).toLocaleDateString() : 'N/A'}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="danger"
                      size="sm"
                      leftIcon={<Trash2 className="w-3 h-3" />}
                      onClick={() => handleRevokeSession(sess.id)}
                      isLoading={revokingId === sess.id}
                    >
                      Revoke
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* 4. API Gateway & Infrastructure Configuration (Read-Only) */}
      <div className="bg-surface-elevated border border-border rounded p-6 max-w-4xl flex flex-col gap-5">
        <div className="flex items-center gap-2 border-b border-border pb-3">
          <Server className="w-4 h-4 text-accent-secondary" />
          <h3 className="text-sm font-display font-semibold uppercase tracking-wider text-text-primary">
            GATEWAY ARCHITECTURE & RUNTIME
          </h3>
        </div>

        <div className="flex flex-col gap-4">
          <Input
            label="Django Public API Gateway"
            defaultValue={env.apiBaseUrl || 'http://localhost:8080/api/v1'}
            helperText="The browser and CLI communicate exclusively through this authenticated Django gateway."
            disabled
          />

          <Input
            label="Internal Agent Runtime URL (Isolated)"
            defaultValue="http://agent-runtime:8001"
            helperText="Internal Docker network address for FastAPI service. Never directly exposed to browsers or external networks."
            disabled
          />

          <div className="p-3 bg-bg-secondary border border-border rounded flex items-start gap-3">
            <Lock className="w-4 h-4 text-accent-highlight shrink-0 mt-0.5" />
            <div className="text-xs font-mono text-text-secondary leading-relaxed">
              <span className="text-text-primary font-semibold">Security Boundary:</span> Browser clients authenticate exclusively via Firebase ID tokens validated by Django REST Framework. Redis enforces sliding-window rate limiting (100 req/min authenticated, 20 req/min anonymous).
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SettingsPage;
