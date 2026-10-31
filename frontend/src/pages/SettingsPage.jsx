import React from 'react';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Badge from '@/components/ui/Badge';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';

export function SettingsPage() {
  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb items={[{ label: 'Settings' }]} />
      <PageHeader
        title="SYSTEM & WORKSPACE SETTINGS"
        description="Configure API gateways, agent execution thresholds, model providers, and display preferences."
        badge={<Badge variant="outline">CORE v0.1</Badge>}
      />

      <div className="bg-surface-elevated border border-border rounded p-6 max-w-2xl flex flex-col gap-5">
        <h3 className="text-sm font-display font-semibold uppercase tracking-wider text-text-primary border-b border-border pb-3">
          API GATEWAY CONFIGURATION
        </h3>

        <div className="flex flex-col gap-4">
          <Input
            label="Django API Gateway URL"
            defaultValue="http://localhost:8080/api/v1"
            helperText="The browser communicates exclusively through this Django API gateway."
            disabled
          />

          <Input
            label="Internal Agent Runtime URL"
            defaultValue="http://agent-runtime:8001"
            helperText="Internal Docker network address for FastAPI service (never exposed to browser)."
            disabled
          />

          <div className="pt-2 flex justify-end">
            <Button variant="primary" size="sm" disabled>
              Save Preferences
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SettingsPage;

