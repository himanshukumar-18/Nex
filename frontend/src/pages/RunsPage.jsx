import React, { useState, useEffect, useCallback } from 'react';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import EmptyState from '@/components/feedback/EmptyState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { runsApi } from '@/services/runsApi';
import {
  Cpu,
  Terminal,
  RefreshCw,
  Clock,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Play,
  ArrowRight,
  Code2,
  FileCheck,
} from 'lucide-react';

export function RunsPage() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [runs, setRuns] = useState([]);
  const [totalRuns, setTotalRuns] = useState(0);
  const [backendReady, setBackendReady] = useState(true);

  const fetchRuns = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const res = await runsApi.getRuns();
      setRuns(res.results || []);
      setTotalRuns(res.count || 0);
      setBackendReady(res.ready !== false);
    } catch {
      setRuns([]);
      setTotalRuns(0);
      setBackendReady(false);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns(false);
  }, [fetchRuns]);

  const getStatusBadge = (status) => {
    const s = (status || 'UNKNOWN').toUpperCase();
    switch (s) {
      case 'RUNNING':
        return <Badge variant="accent" size="sm" dot>RUNNING</Badge>;
      case 'COMPLETED':
        return <Badge variant="success" size="sm" dot>COMPLETED</Badge>;
      case 'FAILED':
        return <Badge variant="danger" size="sm" dot>FAILED</Badge>;
      default:
        return <Badge variant="default" size="sm">{s}</Badge>;
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb items={[{ label: 'Agent Runs' }]} />

      <PageHeader
        title="AGENT EXECUTION RUNS"
        description="Autonomous LangGraph agent execution cycles, task workflows, and verification runs."
        badge={
          <Badge variant={backendReady ? 'accent' : 'cyan'} dot>
            {backendReady ? `${totalRuns} RUNS RECORDED` : 'CLI DIRECT EXECUTION'}
          </Badge>
        }
        actions={
          <Button
            variant="outline"
            size="sm"
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />}
            onClick={() => fetchRuns(true)}
            disabled={loading || refreshing}
          >
            {refreshing ? 'Syncing...' : 'Refresh'}
          </Button>
        }
      />

      {/* CLI Workflow Integration Guide */}
      <div className="bg-surface-elevated border border-border rounded p-5 flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-border pb-3">
          <Terminal className="w-4 h-4 text-accent-secondary" />
          <h3 className="text-sm font-display font-bold uppercase tracking-wider text-text-primary">
            AUTONOMOUS WORKFLOW EXECUTION VIA CLI
          </h3>
        </div>

        <p className="text-xs font-mono text-text-secondary leading-relaxed">
          NEX agents operate locally on developer workstations to execute the 5-stage pipeline:
          <span className="text-accent-highlight font-semibold"> Understand → Plan → Build → Verify → Ship</span>.
          Trigger autonomous agent tasks directly using the NEX CLI:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
          <div className="p-3 bg-bg-secondary border border-border rounded flex flex-col gap-2">
            <div className="flex items-center gap-2 text-text-primary">
              <Code2 className="w-4 h-4 text-accent-primary" />
              <span className="text-xs font-mono font-bold">TASK EXECUTION</span>
            </div>
            <code className="text-xs font-mono text-accent-highlight bg-surface-elevated px-2 py-1 rounded border border-border">
              nex fix &quot;&lt;task-prompt&gt;&quot;
            </code>
            <p className="text-[11px] font-mono text-text-secondary">
              Analyzes codebase, formulates multi-step plan, applies safe diffs, and runs local test suite.
            </p>
          </div>

          <div className="p-3 bg-bg-secondary border border-border rounded flex flex-col gap-2">
            <div className="flex items-center gap-2 text-text-primary">
              <FileCheck className="w-4 h-4 text-accent-secondary" />
              <span className="text-xs font-mono font-bold">CODE REVIEW</span>
            </div>
            <code className="text-xs font-mono text-accent-highlight bg-surface-elevated px-2 py-1 rounded border border-border">
              nex review
            </code>
            <p className="text-[11px] font-mono text-text-secondary">
              Inspects uncommitted changes or branch diffs for security vulnerabilities, style, and regressions.
            </p>
          </div>

          <div className="p-3 bg-bg-secondary border border-border rounded flex flex-col gap-2">
            <div className="flex items-center gap-2 text-text-primary">
              <Sparkles className="w-4 h-4 text-status-success" />
              <span className="text-xs font-mono font-bold">PULL REQUEST LIFECYCLE</span>
            </div>
            <code className="text-xs font-mono text-accent-highlight bg-surface-elevated px-2 py-1 rounded border border-border">
              nex pr --title &quot;...&quot;
            </code>
            <p className="text-[11px] font-mono text-text-secondary">
              Validates commits, compares base branch, creates cryptographic preview fingerprint, and publishes to GitHub.
            </p>
          </div>
        </div>
      </div>

      {/* Runs Table or Empty State */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <EmptyState
          icon={<Cpu className="w-6 h-6 text-accent-primary" />}
          title="NO AGENT RUNS RECORDED"
          description="Autonomous agent execution cycles will stream here as tasks are dispatched from the CLI or API Gateway."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>RUN ID</TableHead>
              <TableHead>WORKFLOW / TASK</TableHead>
              <TableHead>STATUS</TableHead>
              <TableHead>STARTED AT</TableHead>
              <TableHead className="text-right">DURATION</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((run) => (
              <TableRow key={run.id}>
                <TableCell className="font-semibold text-text-primary font-mono text-xs">
                  {run.id ? run.id.slice(0, 8) : 'N/A'}
                </TableCell>
                <TableCell className="text-text-secondary">
                  {run.task_prompt || run.workflow_name || 'Autonomous Agent Task'}
                </TableCell>
                <TableCell>{getStatusBadge(run.status)}</TableCell>
                <TableCell className="text-text-secondary">
                  {run.created_at ? new Date(run.created_at).toLocaleString() : 'N/A'}
                </TableCell>
                <TableCell className="text-right text-text-secondary font-mono">
                  {run.duration ? `${run.duration}s` : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

export default RunsPage;
