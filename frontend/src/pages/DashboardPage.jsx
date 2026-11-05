import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch } from '@/app/hooks';
import { addToast } from '@/features/ui/uiSlice';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import Skeleton from '@/components/ui/Skeleton';
import EmptyState from '@/components/feedback/EmptyState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import {
  Server,
  GitBranch,
  Terminal,
  Layers,
  ArrowRight,
  RefreshCw,
  FolderGit2,
  GitPullRequest,
  ShieldCheck,
  History,
  Activity,
  CheckCircle2,
  Clock,
  AlertCircle,
  ExternalLink,
} from 'lucide-react';
import { githubApi, repositoryApi, systemApi } from '@/services';

export function DashboardPage() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const [syncStatus, setSyncStatus] = useState(null);
  const [githubStatus, setGithubStatus] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [totalRepos, setTotalRepos] = useState(0);
  const [operations, setOperations] = useState([]);
  const [totalOperations, setTotalOperations] = useState(0);
  const [systemHealth, setSystemHealth] = useState(null);

  const fetchDashboardData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const [
        ghRes,
        syncRes,
        reposRes,
        opsRes,
        sysRes,
      ] = await Promise.allSettled([
        githubApi.getGitHubStatus(),
        repositoryApi.getSyncStatus(),
        repositoryApi.getRepositories({ pageSize: 5 }),
        repositoryApi.getOperations(null, { pageSize: 5 }),
        systemApi.getReadiness().catch(() => systemApi.getLiveness()),
      ]);

      if (ghRes.status === 'fulfilled') {
        setGithubStatus(ghRes.value);
      }
      if (syncRes.status === 'fulfilled') {
        setSyncStatus(syncRes.value);
      }
      if (reposRes.status === 'fulfilled') {
        const data = reposRes.value;
        const list = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
        setRepositories(list);
        setTotalRepos(data?.count ?? list.length);
      }
      if (opsRes.status === 'fulfilled') {
        const data = opsRes.value;
        const list = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
        setOperations(list);
        setTotalOperations(data?.count ?? list.length);
      }
      if (sysRes.status === 'fulfilled') {
        setSystemHealth(sysRes.value);
      }
    } catch (err) {
      setError(err?.message || 'Failed to refresh dashboard telemetry.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData(false);
  }, [fetchDashboardData]);

  const handleManualRefresh = async () => {
    await fetchDashboardData(true);
    dispatch(
      addToast({
        type: 'info',
        title: 'TELEMETRY REFRESHED',
        message: 'Live dashboard metrics and Git status synchronized.',
      })
    );
  };

  const getRiskBadge = (level) => {
    const lvl = (level || 'LOW').toUpperCase();
    switch (lvl) {
      case 'CRITICAL':
        return <Badge variant="danger" size="sm">CRITICAL</Badge>;
      case 'HIGH':
        return <Badge variant="warning" size="sm">HIGH</Badge>;
      case 'MEDIUM':
        return <Badge variant="cyan" size="sm">MEDIUM</Badge>;
      case 'LOW':
      default:
        return <Badge variant="default" size="sm">LOW</Badge>;
    }
  };

  const getStatusBadge = (status) => {
    const st = (status || 'UNKNOWN').toUpperCase();
    switch (st) {
      case 'COMPLETED':
        return <Badge variant="success" size="sm" dot>COMPLETED</Badge>;
      case 'SIMULATED':
        return <Badge variant="cyan" size="sm" dot>SIMULATED</Badge>;
      case 'PENDING':
        return <Badge variant="warning" size="sm" dot>PENDING</Badge>;
      case 'FAILED':
        return <Badge variant="danger" size="sm" dot>FAILED</Badge>;
      default:
        return <Badge variant="outline" size="sm">{st}</Badge>;
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Breadcrumb */}
      <Breadcrumb items={[{ label: 'Dashboard' }]} />

      {/* Page Header */}
      <PageHeader
        title="SYSTEM CONTROL DASHBOARD"
        description="NEX Autonomous Intelligence for Software Engineering • Real-Time Telemetry & Status"
        badge={
          <Badge variant={systemHealth?.status === 'ok' || systemHealth?.status === 'healthy' ? 'success' : 'cyan'} dot>
            {systemHealth?.status === 'ok' || systemHealth?.status === 'healthy' ? 'GATEWAY ONLINE' : 'SYSTEM READY'}
          </Badge>
        }
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />}
              onClick={handleManualRefresh}
              disabled={loading || refreshing}
            >
              {refreshing ? 'Syncing...' : 'Refresh Metrics'}
            </Button>
            <Button
              variant="primary"
              size="sm"
              leftIcon={<FolderGit2 className="w-3.5 h-3.5" />}
              onClick={() => navigate('/projects')}
            >
              Repositories
            </Button>
          </div>
        }
      />

      {/* Engineering Philosophy Banner */}
      <div className="bg-surface-elevated border border-accent-primary/40 rounded p-5 relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded bg-accent-primary/20 border border-accent-primary flex items-center justify-center shrink-0">
              <Terminal className="w-5 h-5 text-accent-secondary" />
            </div>
            <div>
              <h2 className="text-sm font-display font-bold uppercase tracking-wider text-text-primary">
                ENGINEERING EXECUTION PIPELINE
              </h2>
              <p className="text-xs font-mono text-text-secondary mt-0.5">
                Core philosophical workflow governing all NEX autonomous software engineering agents.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {['Understand', 'Plan', 'Build', 'Verify', 'Ship'].map((step, idx) => (
              <React.Fragment key={step}>
                <span className="px-2.5 py-1 rounded bg-bg-secondary border border-border text-xs font-mono text-accent-highlight font-medium">
                  {step}
                </span>
                {idx < 4 && <ArrowRight className="w-3 h-3 text-border shrink-0" />}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>

      {/* System Infrastructure & Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Connected Repositories */}
        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-2">
          <div className="flex items-center justify-between text-text-secondary">
            <span className="text-[11px] font-mono uppercase tracking-wider">REPOSITORIES</span>
            <FolderGit2 className="w-4 h-4 text-accent-secondary" />
          </div>
          {loading ? (
            <Skeleton className="h-7 w-20" />
          ) : (
            <div className="text-xl font-display font-bold text-text-primary">
              {syncStatus?.total_repositories ?? totalRepos}
            </div>
          )}
          <div className="flex items-center gap-1.5 text-xs font-mono text-text-secondary">
            {loading ? (
              <Skeleton className="h-3.5 w-32" />
            ) : (
              <span>
                {syncStatus?.public_repositories ?? 0} PUBLIC • {syncStatus?.private_repositories ?? 0} PRIVATE
              </span>
            )}
          </div>
        </div>

        {/* Metric 2: GitHub Integration */}
        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-2">
          <div className="flex items-center justify-between text-text-secondary">
            <span className="text-[11px] font-mono uppercase tracking-wider">GITHUB APP</span>
            <GitBranch className="w-4 h-4 text-accent-primary" />
          </div>
          {loading ? (
            <Skeleton className="h-7 w-28" />
          ) : (
            <div className="text-xl font-display font-bold text-text-primary">
              {githubStatus?.connected ? 'CONNECTED' : githubStatus?.configured ? 'READY' : 'UNCONFIGURED'}
            </div>
          )}
          <div className="flex items-center gap-1.5 text-xs font-mono text-status-success">
            {loading ? (
              <Skeleton className="h-3.5 w-36" />
            ) : (
              <span className={githubStatus?.connected ? 'text-status-success' : 'text-text-secondary'}>
                {githubStatus?.installations_count ?? 0} APP INSTALLATION{(githubStatus?.installations_count === 1) ? '' : 'S'}
              </span>
            )}
          </div>
        </div>

        {/* Metric 3: Git Operations */}
        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-2">
          <div className="flex items-center justify-between text-text-secondary">
            <span className="text-[11px] font-mono uppercase tracking-wider">GIT OPERATIONS</span>
            <Terminal className="w-4 h-4 text-accent-highlight" />
          </div>
          {loading ? (
            <Skeleton className="h-7 w-20" />
          ) : (
            <div className="text-xl font-display font-bold text-text-primary">
              {totalOperations}
            </div>
          )}
          <div className="flex items-center gap-1.5 text-xs font-mono text-text-secondary">
            {loading ? (
              <Skeleton className="h-3.5 w-32" />
            ) : (
              <span>AUDIT TRAIL SYNCHRONIZED</span>
            )}
          </div>
        </div>

        {/* Metric 4: API Gateway & Health */}
        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-2">
          <div className="flex items-center justify-between text-text-secondary">
            <span className="text-[11px] font-mono uppercase tracking-wider">GATEWAY HEALTH</span>
            <Server className="w-4 h-4 text-status-success" />
          </div>
          {loading ? (
            <Skeleton className="h-7 w-24" />
          ) : (
            <div className="text-xl font-display font-bold text-text-primary">
              {systemHealth?.status === 'ok' || systemHealth?.status === 'healthy' ? 'ONLINE' : 'OPERATIONAL'}
            </div>
          )}
          <div className="flex items-center gap-1.5 text-xs font-mono text-status-success">
            {loading ? (
              <Skeleton className="h-3.5 w-28" />
            ) : (
              <>
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>DJANGO REST / PORT 8080</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Quick Navigation Shortcuts */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <button
          onClick={() => navigate('/projects')}
          className="p-3 bg-surface-elevated border border-border rounded hover:border-accent-secondary/60 transition-colors text-left flex items-center justify-between group"
        >
          <div className="flex items-center gap-2.5">
            <FolderGit2 className="w-4 h-4 text-accent-secondary group-hover:text-accent-highlight" />
            <span className="text-xs font-mono font-semibold text-text-primary">Repositories</span>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-text-secondary group-hover:text-accent-secondary" />
        </button>

        <button
          onClick={() => navigate('/approvals')}
          className="p-3 bg-surface-elevated border border-border rounded hover:border-accent-secondary/60 transition-colors text-left flex items-center justify-between group"
        >
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-4 h-4 text-status-warning group-hover:text-accent-highlight" />
            <span className="text-xs font-mono font-semibold text-text-primary">Approvals</span>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-text-secondary group-hover:text-accent-secondary" />
        </button>

        <button
          onClick={() => navigate('/history')}
          className="p-3 bg-surface-elevated border border-border rounded hover:border-accent-secondary/60 transition-colors text-left flex items-center justify-between group"
        >
          <div className="flex items-center gap-2.5">
            <History className="w-4 h-4 text-accent-highlight group-hover:text-accent-secondary" />
            <span className="text-xs font-mono font-semibold text-text-primary">Audit Log</span>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-text-secondary group-hover:text-accent-secondary" />
        </button>

        <button
          onClick={() => navigate('/settings')}
          className="p-3 bg-surface-elevated border border-border rounded hover:border-accent-secondary/60 transition-colors text-left flex items-center justify-between group"
        >
          <div className="flex items-center gap-2.5">
            <Activity className="w-4 h-4 text-status-success group-hover:text-accent-secondary" />
            <span className="text-xs font-mono font-semibold text-text-primary">Settings</span>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-text-secondary group-hover:text-accent-secondary" />
        </button>
      </div>

      {/* Main Grid: Connected Repositories & Recent Git Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Section 1: Connected Repositories */}
        <div className="bg-surface-elevated border border-border rounded p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <FolderGit2 className="w-4 h-4 text-accent-secondary" />
              <h3 className="text-sm font-display font-bold uppercase tracking-wider text-text-primary">
                CONNECTED REPOSITORIES
              </h3>
            </div>
            <Button
              variant="outline"
              size="sm"
              rightIcon={<ArrowRight className="w-3 h-3" />}
              onClick={() => navigate('/projects')}
            >
              View All
            </Button>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : repositories.length === 0 ? (
            <EmptyState
              icon={<FolderGit2 className="w-5 h-5 text-accent-secondary" />}
              title="NO REPOSITORIES CONNECTED"
              description="Connect your GitHub App installation to discover and manage repositories."
              actionLabel="Connect GitHub"
              onAction={() => navigate('/settings')}
            />
          ) : (
            <div className="divide-y divide-border">
              {repositories.map((repo) => (
                <div
                  key={repo.id}
                  onClick={() => navigate('/projects')}
                  className="py-3 flex items-center justify-between hover:bg-surface-hover/30 px-2 rounded cursor-pointer transition-colors"
                >
                  <div className="flex flex-col gap-1 min-w-0 pr-3">
                    <span className="text-xs font-mono font-semibold text-text-primary truncate">
                      {repo.full_name || repo.name}
                    </span>
                    <div className="flex items-center gap-2 text-[11px] font-mono text-text-secondary">
                      <span>branch: {repo.default_branch || 'main'}</span>
                      {repo.language && (
                        <>
                          <span>•</span>
                          <span className="text-accent-highlight">{repo.language}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant={repo.is_private ? 'outline' : 'cyan'} size="sm">
                      {repo.is_private ? 'PRIVATE' : 'PUBLIC'}
                    </Badge>
                    <Badge variant={repo.sync_status === 'active' ? 'success' : 'default'} size="sm">
                      {repo.sync_status || 'SYNCED'}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Section 2: Recent Git Operations */}
        <div className="bg-surface-elevated border border-border rounded p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-accent-highlight" />
              <h3 className="text-sm font-display font-bold uppercase tracking-wider text-text-primary">
                RECENT GIT ACTIVITY
              </h3>
            </div>
            <Button
              variant="outline"
              size="sm"
              rightIcon={<ArrowRight className="w-3 h-3" />}
              onClick={() => navigate('/history')}
            >
              Audit Log
            </Button>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : operations.length === 0 ? (
            <EmptyState
              icon={<History className="w-5 h-5 text-accent-highlight" />}
              title="NO GIT OPERATIONS YET"
              description="Safe Git operations executed through the NEX CLI or Web UI will record here."
              actionLabel="View Audit Policy"
              onAction={() => navigate('/approvals')}
            />
          ) : (
            <div className="divide-y divide-border">
              {operations.map((op) => (
                <div
                  key={op.id}
                  onClick={() => navigate('/history')}
                  className="py-3 flex items-center justify-between hover:bg-surface-hover/30 px-2 rounded cursor-pointer transition-colors"
                >
                  <div className="flex flex-col gap-1 min-w-0 pr-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-semibold text-text-primary uppercase">
                        {op.operation_type || 'OPERATION'}
                      </span>
                      {getRiskBadge(op.risk_level)}
                    </div>
                    <div className="flex items-center gap-2 text-[11px] font-mono text-text-secondary truncate">
                      <span>{op.target_branch ? `branch: ${op.target_branch}` : (op.commit_sha ? `commit: ${op.commit_sha.slice(0, 7)}` : 'repository scope')}</span>
                      {op.created_at && (
                        <>
                          <span>•</span>
                          <span className="text-text-secondary/70">
                            {new Date(op.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="shrink-0">
                    {getStatusBadge(op.status)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DashboardPage;
