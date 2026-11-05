import React, { useState, useEffect, useCallback } from 'react';
import { useAppDispatch } from '@/app/hooks';
import { addToast } from '@/features/ui/uiSlice';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Skeleton from '@/components/ui/Skeleton';
import EmptyState from '@/components/feedback/EmptyState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { repositoryApi } from '@/services/repositoryApi';
import {
  History,
  Terminal,
  RefreshCw,
  GitBranch,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  Filter,
} from 'lucide-react';

export function HistoryPage() {
  const dispatch = useAppDispatch();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [operations, setOperations] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedId, setCopiedId] = useState(null);

  const fetchHistory = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const params = {
        page,
        page_size: pageSize,
      };
      if (typeFilter) params.type = typeFilter;
      if (statusFilter) params.status = statusFilter;

      const data = await repositoryApi.getOperations(null, params);
      const list = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
      setOperations(list);
      setTotalCount(data?.count ?? list.length);
    } catch {
      setOperations([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, pageSize, typeFilter, statusFilter]);

  useEffect(() => {
    fetchHistory(false);
  }, [fetchHistory]);

  const handleCopy = (text, id) => {
    if (!text) return;
    navigator.clipboard?.writeText(text);
    setCopiedId(id);
    dispatch(
      addToast({
        type: 'info',
        title: 'COPIED TO CLIPBOARD',
        message: `Correlation ID ${text.slice(0, 8)}... copied.`,
      })
    );
    setTimeout(() => {
      setCopiedId(null);
    }, 2000);
  };

  const filteredOperations = operations.filter((op) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const branch = (op.target_branch || '').toLowerCase();
    const sha = (op.commit_sha || '').toLowerCase();
    const corr = (op.correlation_id || '').toLowerCase();
    const msg = (op.commit_message || '').toLowerCase();
    const type = (op.operation_type || '').toLowerCase();
    return branch.includes(q) || sha.includes(q) || corr.includes(q) || msg.includes(q) || type.includes(q);
  });

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

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb items={[{ label: 'Audit Log' }]} />

      <PageHeader
        title="IMMUTABLE AUDIT LOG"
        description="Comprehensive audit trail of Git operations, commit history, remote push verifications, and cryptographic fingerprints."
        badge={
          <Badge variant="default" dot>
            {totalCount} EVENTS RECORDED
          </Badge>
        }
        actions={
          <Button
            variant="outline"
            size="sm"
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />}
            onClick={() => fetchHistory(true)}
            disabled={loading || refreshing}
          >
            {refreshing ? 'Syncing...' : 'Refresh'}
          </Button>
        }
      />

      {/* Filter Toolbar */}
      <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-1 flex-wrap">
          <div className="w-full sm:w-64">
            <Input
              placeholder="Search branch, sha, correlation ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="w-36">
            <Select
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: '', label: 'All Operations' },
                { value: 'branch_create', label: 'Branch Create' },
                { value: 'commit', label: 'Commit' },
                { value: 'push', label: 'Push' },
                { value: 'stage', label: 'Stage' },
              ]}
            />
          </div>

          <div className="w-36">
            <Select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: '', label: 'All Statuses' },
                { value: 'completed', label: 'Completed' },
                { value: 'simulated', label: 'Simulated' },
                { value: 'pending', label: 'Pending' },
                { value: 'failed', label: 'Failed' },
              ]}
            />
          </div>
        </div>

        <div className="text-xs font-mono text-text-secondary">
          Showing {filteredOperations.length} of {totalCount} records
        </div>
      </div>

      {/* Audit Log Table */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : filteredOperations.length === 0 ? (
        <EmptyState
          icon={<History className="w-6 h-6 text-accent-highlight" />}
          title="NO AUDIT EVENTS FOUND"
          description={
            searchQuery || typeFilter || statusFilter
              ? 'No operations match your active filter criteria. Try resetting filters.'
              : 'Git operation records will appear here as developer workflows and CLI commands execute.'
          }
          actionLabel={searchQuery || typeFilter || statusFilter ? 'Reset Filters' : undefined}
          onAction={() => {
            setSearchQuery('');
            setTypeFilter('');
            setStatusFilter('');
            setPage(1);
          }}
        />
      ) : (
        <div className="flex flex-col gap-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>OPERATION</TableHead>
                <TableHead>TARGET / SHA</TableHead>
                <TableHead>DETAILS / COMMIT MSG</TableHead>
                <TableHead>RISK</TableHead>
                <TableHead>STATUS</TableHead>
                <TableHead>TIMESTAMP</TableHead>
                <TableHead className="text-right">CORRELATION ID</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredOperations.map((op) => (
                <TableRow key={op.id}>
                  <TableCell className="font-semibold text-text-primary">
                    <div className="flex items-center gap-2">
                      <Terminal className="w-3.5 h-3.5 text-accent-primary" />
                      <span className="uppercase">{op.operation_type || 'OPERATION'}</span>
                    </div>
                  </TableCell>

                  <TableCell className="text-text-secondary">
                    {op.target_branch ? (
                      <div className="flex items-center gap-1">
                        <GitBranch className="w-3 h-3 text-accent-secondary shrink-0" />
                        <span className="truncate max-w-[140px]">{op.target_branch}</span>
                      </div>
                    ) : op.commit_sha ? (
                      <span className="font-mono text-[11px] text-accent-highlight">
                        {op.commit_sha.slice(0, 7)}
                      </span>
                    ) : (
                      '—'
                    )}
                  </TableCell>

                  <TableCell className="text-text-secondary max-w-[240px]">
                    <span className="truncate block" title={op.commit_message || op.error_message || ''}>
                      {op.commit_message || (op.files && `${op.files.length} file(s) modified`) || op.error_message || '—'}
                    </span>
                  </TableCell>

                  <TableCell>{getRiskBadge(op.risk_level)}</TableCell>

                  <TableCell>{getStatusBadge(op.status)}</TableCell>

                  <TableCell className="text-text-secondary text-[11px] whitespace-nowrap">
                    {op.created_at ? new Date(op.created_at).toLocaleString() : 'N/A'}
                  </TableCell>

                  <TableCell className="text-right">
                    {op.correlation_id ? (
                      <button
                        onClick={() => handleCopy(op.correlation_id, op.id)}
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-bg-secondary border border-border text-[10px] font-mono text-text-secondary hover:text-text-primary hover:border-accent-secondary transition-colors"
                        title="Click to copy correlation ID"
                      >
                        {copiedId === op.id ? (
                          <Check className="w-3 h-3 text-status-success" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                        <span>{op.correlation_id.slice(0, 8)}...</span>
                      </button>
                    ) : (
                      <span className="text-text-secondary font-mono text-[11px]">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between p-3 bg-surface-elevated border border-border rounded">
              <span className="text-xs font-mono text-text-secondary">
                Page {page} of {totalPages}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<ChevronLeft className="w-3.5 h-3.5" />}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1 || loading}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages || loading}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default HistoryPage;
