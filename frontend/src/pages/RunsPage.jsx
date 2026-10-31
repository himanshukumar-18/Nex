import React from 'react';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/feedback/EmptyState';
import { Cpu } from 'lucide-react';

export function RunsPage() {
  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb items={[{ label: 'Agent Runs' }]} />
      <PageHeader
        title="AGENT EXECUTION RUNS"
        description="Active and historical LangGraph agent execution cycles, task workflows, and runs."
        badge={<Badge variant="default">0 RUNNING</Badge>}
      />
      <EmptyState
        icon={<Cpu className="w-6 h-6 text-accent-primary" />}
        title="NO ACTIVE AGENT RUNS"
        description="Start an autonomous engineering workflow from the CLI or trigger an analysis run from a project."
        actionLabel="Initiate Run"
        onAction={() => alert('Agent execution initialization will be enabled in Step 9.')}
      />
    </div>
  );
}

export default RunsPage;

