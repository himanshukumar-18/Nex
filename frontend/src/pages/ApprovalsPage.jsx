import React from 'react';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/feedback/EmptyState';
import { ShieldCheck } from 'lucide-react';

export function ApprovalsPage() {
  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb items={[{ label: 'Approvals' }]} />
      <PageHeader
        title="HUMAN-IN-THE-LOOP APPROVALS"
        description="Pending tool executions, destructive operations, and pull-request authorizations."
        badge={<Badge variant="success">0 PENDING</Badge>}
      />
      <EmptyState
        icon={<ShieldCheck className="w-6 h-6 text-status-success" />}
        title="NO PENDING APPROVALS"
        description="All autonomous actions have completed or require no human operator confirmation at this time."
      />
    </div>
  );
}

export default ApprovalsPage;

