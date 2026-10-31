import React from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '@/app/hooks';
import {
  toggleSidebar,
  toggleMobileMenu,
  setMobileMenuOpen,
  clearSystemNotice,
} from '@/features/ui/uiSlice';
import {
  LayoutDashboard,
  FolderGit2,
  Cpu,
  ShieldCheck,
  History,
  Settings,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  Terminal,
  Activity,
  Bell,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import ToastContainer from '@/components/feedback/Toast';
import Alert from '@/components/feedback/Alert';

const navItems = [
  { id: 'dashboard', label: 'Dashboard', to: '/', icon: LayoutDashboard },
  { id: 'projects', label: 'Projects', to: '/projects', icon: FolderGit2 },
  { id: 'runs', label: 'Agent Runs', to: '/runs', icon: Cpu },
  { id: 'approvals', label: 'Approvals', to: '/approvals', icon: ShieldCheck },
  { id: 'history', label: 'Audit Log', to: '/history', icon: History },
  { id: 'settings', label: 'Settings', to: '/settings', icon: Settings },
];

export function AppLayout() {
  const dispatch = useAppDispatch();
  const location = useLocation();
  const { sidebarCollapsed, mobileMenuOpen, systemNotice } = useAppSelector(
    (state) => state.ui
  );

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex flex-col font-sans antialiased selection:bg-accent-primary selection:text-white">
      {/* Top Header / Bar */}
      <header className="h-14 border-b border-border bg-bg-secondary sticky top-0 z-40 flex items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-4">
          {/* Mobile Menu Toggle Button */}
          <button
            type="button"
            onClick={() => dispatch(toggleMobileMenu())}
            aria-label="Toggle mobile menu"
            className="md:hidden text-text-secondary hover:text-white p-1.5 rounded hover:bg-surface-elevated transition-colors"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          {/* Platform Identity */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-surface-elevated border border-accent-primary flex items-center justify-center shadow-brutal-accent">
              <Terminal className="w-4 h-4 text-accent-secondary" />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-sm tracking-wider uppercase text-text-primary">
                NEX <span className="text-accent-secondary text-xs">CORE</span>
              </span>
              <span className="hidden sm:inline-block font-mono text-[9px] text-text-secondary tracking-widest">
                AI SOFTWARE ENGINEER
              </span>
            </div>
          </div>
        </div>

        {/* Status Indicators & Meta */}
        <div className="flex items-center gap-3 font-mono text-xs">
          <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded bg-surface-elevated border border-border">
            <Activity className="w-3.5 h-3.5 text-status-success animate-pulse" />
            <span className="text-text-secondary text-[11px]">SYS:</span>
            <span className="text-status-success text-[11px] font-semibold">ONLINE</span>
          </div>

          <button
            type="button"
            aria-label="System notifications"
            className="relative text-text-secondary hover:text-white p-1.5 rounded hover:bg-surface-elevated transition-colors"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-accent-secondary" />
          </button>
        </div>
      </header>

      {/* Main Workspace Frame */}
      <div className="flex-1 flex overflow-hidden">
        {/* Desktop Sidebar */}
        <aside
          className={cn(
            'hidden md:flex flex-col border-r border-border bg-bg-secondary transition-all duration-200 select-none z-30 shrink-0',
            sidebarCollapsed ? 'w-16' : 'w-60'
          )}
        >
          {/* Navigation Links */}
          <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.to;

              return (
                <NavLink
                  key={item.id}
                  to={item.to}
                  title={sidebarCollapsed ? item.label : undefined}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded text-xs font-mono font-medium transition-all group',
                    isActive
                      ? 'bg-surface-elevated border border-accent-primary text-accent-highlight shadow-brutal-accent'
                      : 'text-text-secondary hover:text-text-primary hover:bg-surface-elevated/50 border border-transparent'
                  )}
                >
                  <Icon
                    className={cn(
                      'w-4 h-4 shrink-0 transition-colors',
                      isActive ? 'text-accent-secondary' : 'text-text-secondary group-hover:text-text-primary'
                    )}
                  />
                  {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
                </NavLink>
              );
            })}
          </nav>

          {/* Philosophy Tagline / Footer */}
          {!sidebarCollapsed && (
            <div className="p-3 border-t border-border bg-surface-elevated/40">
              <div className="font-mono text-[10px] text-text-secondary/70 leading-relaxed uppercase">
                <span className="text-accent-secondary font-semibold">FLOW:</span> Plan → Build → Verify → Ship
              </div>
            </div>
          )}

          {/* Collapse Toggle */}
          <div className="p-2 border-t border-border flex justify-end">
            <button
              type="button"
              onClick={() => dispatch(toggleSidebar())}
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              className="w-full py-1.5 flex items-center justify-center text-text-secondary hover:text-white rounded hover:bg-surface-elevated transition-colors text-xs font-mono"
            >
              {sidebarCollapsed ? (
                <ChevronRight className="w-4 h-4" />
              ) : (
                <div className="flex items-center gap-2">
                  <ChevronLeft className="w-4 h-4" />
                  <span className="text-[11px] uppercase tracking-wider">COLLAPSE</span>
                </div>
              )}
            </button>
          </div>
        </aside>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-50 flex">
            {/* Backdrop */}
            <div
              className="fixed inset-0 bg-bg-primary/80 backdrop-blur-sm"
              onClick={() => dispatch(setMobileMenuOpen(false))}
            />

            {/* Drawer */}
            <div className="relative w-64 max-w-[80%] bg-bg-secondary border-r border-border h-full flex flex-col p-4 shadow-2xl z-10">
              <div className="flex items-center justify-between pb-4 border-b border-border mb-4">
                <span className="font-display font-bold text-sm text-text-primary uppercase">
                  NEX NAVIGATION
                </span>
                <button
                  type="button"
                  onClick={() => dispatch(setMobileMenuOpen(false))}
                  className="text-text-secondary hover:text-white p-1 rounded"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <nav className="flex-1 space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.to;

                  return (
                    <NavLink
                      key={item.id}
                      to={item.to}
                      onClick={() => dispatch(setMobileMenuOpen(false))}
                      className={cn(
                        'flex items-center gap-3 px-3 py-2.5 rounded text-xs font-mono font-medium transition-colors',
                        isActive
                          ? 'bg-surface-elevated border border-accent-primary text-accent-highlight'
                          : 'text-text-secondary hover:text-text-primary hover:bg-surface-elevated/50'
                      )}
                    >
                      <Icon className="w-4 h-4 shrink-0 text-accent-secondary" />
                      <span>{item.label}</span>
                    </NavLink>
                  );
                })}
              </nav>

              <div className="pt-4 border-t border-border">
                <p className="font-mono text-[10px] text-text-secondary">
                  Autonomous Intelligence for Software Engineering
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Central Viewport & Content Outlet */}
        <main className="flex-1 overflow-y-auto bg-bg-primary p-4 sm:p-6 lg:p-8">
          {/* Global System Notice Banner */}
          {systemNotice && (
            <div className="mb-6">
              <Alert
                variant={systemNotice.type || 'info'}
                title={systemNotice.title}
                onDismiss={systemNotice.dismissible ? () => dispatch(clearSystemNotice()) : undefined}
              >
                {systemNotice.message}
              </Alert>
            </div>
          )}

          <Outlet />
        </main>
      </div>

      {/* Global Toast Container */}
      <ToastContainer />
    </div>
  );
}

export default AppLayout;

