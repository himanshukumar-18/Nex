import React, { useState, useEffect, useCallback } from 'react';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Tabs from '@/components/ui/Tabs';
import Skeleton from '@/components/ui/Skeleton';
import EmptyState from '@/components/feedback/EmptyState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { repositoryApi } from '@/services/repositoryApi';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  RefreshCw,
  Terminal,
  Lock,
  CheckCircle2,
  Clock,
  FileCode,
  GitBranch,
} from 'lucide-react';

export function ApprovalsPage() {
  const [activeTab, setActiveTab] = useState('pending');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pendingOps, setPendingOps] = useState([]);
  const [allOps, setAllOps] = useState([]);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const [pendingRes, allRes] = await Promise.allSettled([
        repositoryApi.getOperations(null, { status: 'pending' }),
        repositoryApi.getOperations(null, { pageSize: 20 }),
      ]);

      if (pendingRes.status === 'fulfilled') {
        const data = pendingRes.value;
        const list = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
        setPendingOps(list);
      }
      if (allRes.status === 'fulfilled') {
        const data = allRes.value;
        const list = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
        setAllOps(list);
      }
    } catch {
      // Safe fallback
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData(false);
  }, [fetchData]);

  const getRiskBadge = (level) => {
    const lvl = (level || 'LOW').toUpperCase();
    switch (lvl) {
      case 'CRITICAL':
        return <Badge variant="danger" size="sm" dot>CRITICAL</Badge>;
      case 'HIGH':
        return <Badge variant="warning" size="sm" dot>HIGH</Badge>;
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

  const tabs = [
    {
      id: 'pending',
      label: 'PENDING APPROVALS',
      count: pendingOps.length,
      icon: <Clock className="w-3.5 h-3.5" />,
    },
    {
      id: 'policy',
      label: 'APPROVAL POLICY MATRIX',
      icon: <ShieldCheck className="w-3.5 h-3.5" />,
    },
    {
      id: 'history',
      label: 'AUDIT & VERIFICATION TRAIL',
      count: allOps.length,
      icon: <FileCode className="w-3.5 h-3.5" />,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb items={[{ label: 'Approvals' }]} />

      <PageHeader
        title="HUMAN-IN-THE-LOOP APPROVALS"
        description="Pending tool executions, destructive operations, Git state mutations, and pull request authorizations."
        badge={
          <Badge variant={pendingOps.length > 0 ? 'warning' : 'success'} dot>
            {pendingOps.length} PENDING
          </Badge>
        }
        actions={
          <Button
            variant="outline"
            size="sm"
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />}
            onClick={() => fetchData(true)}
            disabled={loading || refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        }
      />

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {/* Tab 1: Pending Approvals */}
      {activeTab === 'pending' && (
        <div className="flex flex-col gap-4">
          {loading ? (
            <div className="space-y-3">
              {[...Array(2)].map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : pendingOps.length === 0 ? (
            <EmptyState
              icon={<ShieldCheck className="w-6 h-6 text-status-success" />}
              title="NO PENDING APPROVALS"
              description="All autonomous operations have completed or require no manual operator confirmation at this time."
            />
          ) : (
            <div className="flex flex-col gap-3">
              <div className="p-4 bg-status-warning/10 border border-status-warning/40 rounded flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-status-warning shrink-0 mt-0.5" />
                <div className="text-xs font-mono text-text-secondary leading-relaxed">
                  <span className="text-text-primary font-semibold">Human Authorization Required:</span> The following Git operations require explicit operator confirmation before execution according to the NEX Security Policy.
                </div>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>OPERATION</TableHead>
                    <TableHead>REPOSITORY / TARGET</TableHead>
                    <TableHead>RISK LEVEL</TableHead>
                    <TableHead>STATUS</TableHead>
                    <TableHead>REQUESTED AT</TableHead>
                    <TableHead>CORRELATION ID</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingOps.map((op) => (
                    <TableRow key={op.id}>
                      <TableCell className="font-semibold text-text-primary">
                        <div className="flex items-center gap-2">
                          <Terminal className="w-3.5 h-3.5 text-accent-primary" />
                          <span className="uppercase">{op.operation_type || 'GIT OPERATION'}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-text-secondary">
                        {op.target_branch ? `branch: ${op.target_branch}` : (op.repository_full_name || 'local workspace')}
                      </TableCell>
                      <TableCell>{getRiskBadge(op.risk_level)}</TableCell>
                      <TableCell>{getStatusBadge(op.status)}</TableCell>
                      <TableCell className="text-text-secondary">
                        {op.created_at ? new Date(op.created_at).toLocaleTimeString() : 'N/A'}
                      </TableCell>
                      <TableCell className="text-text-secondary font-mono text-[11px]">
                        {op.correlation_id ? `${op.correlation_id.slice(0, 8)}...` : 'N/A'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Approval Policy Matrix */}
      {activeTab === 'policy' && (
        <div className="flex flex-col gap-6">
          <div className="bg-surface-elevated border border-border rounded p-6 flex flex-col gap-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <Lock className="w-4 h-4 text-accent-secondary" />
              <h3 className="text-sm font-display font-bold uppercase tracking-wider text-text-primary">
                NEX APPROVAL CLASSIFICATION & ENFORCEMENT
              </h3>
            </div>
            <p className="text-xs font-mono text-text-secondary leading-relaxed">
              To guarantee zero unintended destructive Git actions or remote repository pollution, NEX enforces a strict 4-tier risk classification across both the Python CLI and Web Dashboard.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div className="p-4 bg-bg-secondary border border-border rounded flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-text-primary">TIER 1: LOW RISK</span>
                  <Badge variant="default" size="sm">AUTO-APPROVED</Badge>
                </div>
                <p className="text-[11px] font-mono text-text-secondary">
                  Read-only repository inspections, diff comparisons, status checks, commit log analysis, and local pre-flight validations. Executed automatically without blocking operator workflow.
                </p>
              </div>

              <div className="p-4 bg-bg-secondary border border-border rounded flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-text-primary">TIER 2: MEDIUM RISK</span>
                  <Badge variant="cyan" size="sm">AUDIT LOGGED</Badge>
                </div>
                <p className="text-[11px] font-mono text-text-secondary">
                  Local non-destructive branch creations and staging of explicitly specified files. Recorded into the local and backend audit trail for traceability.
                </p>
              </div>

              <div className="p-4 bg-bg-secondary border border-border rounded flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-text-primary">TIER 3: HIGH RISK</span>
                  <Badge variant="warning" size="sm" dot>PROMPT REQUIRED</Badge>
                </div>
                <p className="text-[11px] font-mono text-text-secondary">
                  Creating commits, pushing to feature branches, and creating draft Pull Requests. Requires explicit interactive confirmation prompt or verified <code className="text-accent-secondary">--yes</code> eligibility.
                </p>
              </div>

              <div className="p-4 bg-bg-secondary border border-border rounded flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-text-primary">TIER 4: CRITICAL RISK</span>
                  <Badge variant="danger" size="sm" dot>STRICT MANUAL CONFIRM</Badge>
                </div>
                <p className="text-[11px] font-mono text-text-secondary">
                  Direct push to protected branches (<code className="text-accent-secondary">main</code>, <code className="text-accent-secondary">master</code>), force push, and publishing non-draft PRs. Strictly prohibited from automatic bypass; requires manual interactive confirmation with preview fingerprint validation.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: History & Audit Trail */}
      {activeTab === 'history' && (
        <div className="flex flex-col gap-4">
          {loading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : allOps.length === 0 ? (
            <EmptyState
              icon={<FileCode className="w-6 h-6 text-accent-highlight" />}
              title="NO AUDIT RECORDS FOUND"
              description="No Git operations have been recorded in this workspace."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>OPERATION</TableHead>
                  <TableHead>REPOSITORY</TableHead>
                  <TableHead>TARGET / SHA</TableHead>
                  <TableHead>RISK LEVEL</TableHead>
                  <TableHead>STATUS</TableHead>
                  <TableHead>TIMESTAMP</TableHead>
                  <TableHead>CORRELATION ID</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {allOps.map((op) => (
                  <TableRow key={op.id}>
                    <TableCell className="font-semibold text-text-primary uppercase">
                      {op.operation_type || 'OPERATION'}
                    </TableCell>
                    <TableCell className="text-text-secondary">
                      {op.repository_full_name || 'Workspace Local'}
                    </TableCell>
                    <TableCell className="text-text-secondary">
                      {op.target_branch ? (
                        <div className="flex items-center gap-1">
                          <GitBranch className="w-3 h-3 text-accent-secondary" />
                          <span>{op.target_branch}</span>
                        </div>
                      ) : op.commit_sha ? (
                        <span className="font-mono text-[11px]">{op.commit_sha.slice(0, 7)}</span>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                    <TableCell>{getRiskBadge(op.risk_level)}</TableCell>
                    <TableCell>{getStatusBadge(op.status)}</TableCell>
                    <TableCell className="text-text-secondary">
                      {op.created_at ? new Date(op.created_at).toLocaleString() : 'N/A'}
                    </TableCell>
                    <TableCell className="text-text-secondary font-mono text-[11px]">
                      {op.correlation_id ? `${op.correlation_id.slice(0, 8)}...` : 'N/A'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      )}
    </div>
  );
}

export default ApprovalsPage;
