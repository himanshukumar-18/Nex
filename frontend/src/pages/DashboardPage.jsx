import React, { useState } from 'react';
import { useAppDispatch } from '@/app/hooks';
import { addToast } from '@/features/ui/uiSlice';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Checkbox from '@/components/ui/Checkbox';
import Modal from '@/components/ui/Modal';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import {
  Server,
  Cpu,
  Database,
  Layers,
  Sparkles,
  ArrowRight,
  Terminal,
  Code2,
  CheckCircle,
} from 'lucide-react';

export function DashboardPage() {
  const dispatch = useAppDispatch();
  const [modalOpen, setModalOpen] = useState(false);
  const [sampleInput, setSampleInput] = useState('NEX Agent Runtime v1');
  const [sampleCheck, setSampleCheck] = useState(true);

  const handleTriggerToast = (type) => {
    dispatch(
      addToast({
        type,
        title: `${type.toUpperCase()} EVENT`,
        message: `System notification dispatched at ${new Date().toLocaleTimeString()}`,
      })
    );
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Breadcrumb */}
      <Breadcrumb items={[{ label: 'Dashboard' }]} />

      {/* Page Header */}
      <PageHeader
        title="SYSTEM CONTROL DASHBOARD"
        description="NEX Autonomous Intelligence for Software Engineering • Foundation Architecture"
        badge={
          <Badge variant="cyan" dot>
            STEP 8 READY
          </Badge>
        }
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleTriggerToast('info')}
            >
              Test Toast
            </Button>
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Sparkles className="w-3.5 h-3.5" />}
              onClick={() => setModalOpen(true)}
            >
              System Modal
            </Button>
          </div>
        }
      />

      {/* Platform Philosophy Banner */}
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

      {/* System Infrastructure Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-2">
          <div className="flex items-center justify-between text-text-secondary">
            <span className="text-[11px] font-mono uppercase tracking-wider">CORE BACKEND</span>
            <Server className="w-4 h-4 text-accent-primary" />
          </div>
          <div className="text-lg font-display font-bold text-text-primary">DJANGO 5.2</div>
          <div className="flex items-center gap-1.5 text-xs font-mono text-status-success">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>PORT 8000 / 8080 API GATEWAY</span>
          </div>
        </div>

        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-2">
          <div className="flex items-center justify-between text-text-secondary">
            <span className="text-[11px] font-mono uppercase tracking-wider">AGENT RUNTIME</span>
            <Cpu className="w-4 h-4 text-accent-secondary" />
          </div>
          <div className="text-lg font-display font-bold text-text-primary">FASTAPI CORE</div>
          <div className="flex items-center gap-1.5 text-xs font-mono text-status-success">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>INTERNAL RUNTIME (PORT 8001)</span>
          </div>
        </div>

        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-2">
          <div className="flex items-center justify-between text-text-secondary">
            <span className="text-[11px] font-mono uppercase tracking-wider">CACHE & LIMITS</span>
            <Layers className="w-4 h-4 text-status-warning" />
          </div>
          <div className="text-lg font-display font-bold text-text-primary">REDIS 7.4</div>
          <div className="flex items-center gap-1.5 text-xs font-mono text-status-success">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>SLIDING-WINDOW RATE LIMITING</span>
          </div>
        </div>

        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-2">
          <div className="flex items-center justify-between text-text-secondary">
            <span className="text-[11px] font-mono uppercase tracking-wider">DATABASE ENGINE</span>
            <Database className="w-4 h-4 text-accent-highlight" />
          </div>
          <div className="text-lg font-display font-bold text-text-primary">POSTGRES 17</div>
          <div className="flex items-center gap-1.5 text-xs font-mono text-status-success">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>PGVECTOR EMBEDDINGS STORE</span>
          </div>
        </div>
      </div>

      {/* Cyber Brutalist UI Kit Showcase */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Controls Showcase */}
        <div className="bg-surface-elevated border border-border rounded p-5 flex flex-col gap-4">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Code2 className="w-4 h-4 text-accent-secondary" />
            <h3 className="text-sm font-display font-bold uppercase tracking-wider text-text-primary">
              FORM CONTROLS & INPUT SYSTEM
            </h3>
          </div>

          <div className="flex flex-col gap-4">
            <Input
              label="Agent Identifier"
              helperText="Unique identifier assigned to active agent worker."
              value={sampleInput}
              onChange={(e) => setSampleInput(e.target.value)}
            />

            <Select
              label="Target LLM Architecture"
              options={[
                { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (Default)' },
                { value: 'gemini-2.0-pro', label: 'Gemini 2.0 Pro Experimental' },
                { value: 'claude-3-7-sonnet', label: 'Claude 3.7 Sonnet' },
              ]}
              defaultValue="gemini-2.0-flash"
            />

            <Checkbox
              label="Enable Autonomous Verification Loop"
              description="Agent automatically executes test harness before emitting code diffs."
              checked={sampleCheck}
              onChange={(e) => setSampleCheck(e.target.checked)}
            />

            <div className="flex items-center gap-2 pt-2 flex-wrap">
              <Button variant="primary" size="sm">
                Primary Action
              </Button>
              <Button variant="secondary" size="sm">
                Secondary
              </Button>
              <Button variant="outline" size="sm">
                Outline
              </Button>
              <Button variant="danger" size="sm">
                Danger
              </Button>
            </div>
          </div>
        </div>

        {/* Status & Badge Matrix */}
        <div className="bg-surface-elevated border border-border rounded p-5 flex flex-col gap-4">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Layers className="w-4 h-4 text-accent-primary" />
            <h3 className="text-sm font-display font-bold uppercase tracking-wider text-text-primary">
              DESIGN SYSTEM STATUS BADGES
            </h3>
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-2">
              <Badge variant="default">DEFAULT</Badge>
              <Badge variant="accent">ACCENT</Badge>
              <Badge variant="cyan">CYAN</Badge>
              <Badge variant="success">SUCCESS</Badge>
              <Badge variant="warning">WARNING</Badge>
              <Badge variant="danger">DANGER</Badge>
              <Badge variant="outline">OUTLINE</Badge>
            </div>

            <div className="flex flex-wrap gap-2">
              <Badge variant="accent" dot>
                AGENT RUNNING
              </Badge>
              <Badge variant="success" dot>
                VERIFICATION PASSED
              </Badge>
              <Badge variant="warning" dot>
                APPROVAL REQUIRED
              </Badge>
              <Badge variant="danger" dot>
                SANDBOX TIMEOUT
              </Badge>
            </div>

            <div className="border border-border rounded p-3 bg-bg-secondary flex flex-col gap-2">
              <span className="text-[11px] font-mono text-text-secondary uppercase">
                NOTIFICATION DISPATCH TEST
              </span>
              <div className="flex items-center gap-2 flex-wrap">
                <Button variant="secondary" size="sm" onClick={() => handleTriggerToast('success')}>
                  Success Toast
                </Button>
                <Button variant="secondary" size="sm" onClick={() => handleTriggerToast('warning')}>
                  Warning Toast
                </Button>
                <Button variant="secondary" size="sm" onClick={() => handleTriggerToast('danger')}>
                  Danger Toast
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Foundation Service Status Table */}
      <div className="flex flex-col gap-3">
        <h3 className="text-sm font-display font-bold uppercase tracking-wider text-text-primary">
          SERVICE ARCHITECTURE MATRIX
        </h3>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>SERVICE COMPONENT</TableHead>
              <TableHead>RUNTIME ENVIRONMENT</TableHead>
              <TableHead>PROTOCOL & PORT</TableHead>
              <TableHead>STATUS</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell className="font-semibold text-text-primary">
                Django Core Backend
              </TableCell>
              <TableCell>Python 3.12 / Gunicorn / Nginx</TableCell>
              <TableCell>HTTP / Port 8000 & 8080</TableCell>
              <TableCell>
                <Badge variant="success" size="sm" dot>
                  ACTIVE
                </Badge>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-semibold text-text-primary">
                FastAPI Agent Runtime
              </TableCell>
              <TableCell>Python 3.12 / Uvicorn</TableCell>
              <TableCell>HTTP Internal / Port 8001</TableCell>
              <TableCell>
                <Badge variant="success" size="sm" dot>
                  ACTIVE
                </Badge>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-semibold text-text-primary">
                Redis Infrastructure
              </TableCell>
              <TableCell>Redis Alpine 7.4</TableCell>
              <TableCell>TCP / Port 6379</TableCell>
              <TableCell>
                <Badge variant="success" size="sm" dot>
                  ACTIVE
                </Badge>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-semibold text-text-primary">
                React Frontend Foundation
              </TableCell>
              <TableCell>React 18 / Vite / Tailwind</TableCell>
              <TableCell>HTTP / Port 3000</TableCell>
              <TableCell>
                <Badge variant="cyan" size="sm" dot>
                  STEP 8 FOUNDATION
                </Badge>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>

      {/* System Modal Test */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title="NEX SYSTEM FOUNDATION"
        description="HTML5 Native Dialog Component Verification"
      >
        <div className="flex flex-col gap-4">
          <p className="text-xs font-mono text-text-secondary leading-relaxed">
            This modal is rendered using HTML5 native <code className="text-accent-secondary">&lt;dialog&gt;</code>{' '}
            with native focus trapping, backdrop blur, Escape dismissal, and{' '}
            <code className="text-accent-secondary">overscroll-behavior: contain</code> to prevent background scroll leak.
          </p>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
            <Button variant="outline" size="sm" onClick={() => setModalOpen(false)}>
              Close
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setModalOpen(false);
                handleTriggerToast('success');
              }}
            >
              Confirm
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default DashboardPage;

