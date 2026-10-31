import React from 'react';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/feedback/EmptyState';
import { FolderGit2 } from 'lucide-react';

export function ProjectsPage() {
  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb items={[{ label: 'Projects' }]} />
      <PageHeader
        title="PROJECTS & REPOSITORIES"
        description="Connected code repositories, dependency graphs, and codebase indexes."
        badge={<Badge variant="default">0 ACTIVE</Badge>}
      />
      <EmptyState
        icon={<FolderGit2 className="w-6 h-6 text-accent-secondary" />}
        title="NO REPOSITORIES REGISTERED"
        description="Connect a Git repository to enable automated repository understanding, indexing, and agent workflows."
        actionLabel="Register Repository"
        onAction={() => alert('Repository registration workflow will be enabled in Step 9.')}
      />
    </div>
  );
}

export default ProjectsPage;

