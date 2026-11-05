import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '@/layouts/PageHeader';
import Breadcrumb from '@/layouts/Breadcrumb';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/Table';
import EmptyState from '@/components/feedback/EmptyState';
import LoadingSpinner from '@/components/feedback/LoadingSpinner';
import { repositoryApi, githubApi } from '@/services';
import {
  FolderGit2,
  RefreshCw,
  Search,
  ExternalLink,
  Lock,
  Unlock,
  GitFork,
  Archive,
  GitBranch,
  Copy,
  Check,
  AlertCircle,
  Database,
  ShieldCheck,
  SlidersHorizontal,
  GitPullRequest,
  Plus,
  ArrowRight,
  GitCommit,
} from 'lucide-react';

export function ProjectsPage() {
  const navigate = useNavigate();

  // State
  const [repositories, setRepositories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [notification, setNotification] = useState(null);
  const [githubStatus, setGitHubStatus] = useState(null);
  const [syncMetrics, setSyncMetrics] = useState(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [visibilityFilter, setVisibilityFilter] = useState('all'); // 'all' | 'public' | 'private'
  const [languageFilter, setLanguageFilter] = useState('all');

  // Detail Modal & Tabs
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [modalTab, setModalTab] = useState('overview'); // 'overview' | 'operations' | 'pulls'
  const [copiedField, setCopiedField] = useState(null);
  const [repoOperations, setRepoOperations] = useState([]);
  const [operationsLoading, setOperationsLoading] = useState(false);

  // Pull Requests State
  const [pullRequests, setPullRequests] = useState([]);
  const [pullsLoading, setPullsLoading] = useState(false);
  const [syncingPrNumber, setSyncingPrNumber] = useState(null);
  const [showCreatePr, setShowCreatePr] = useState(false);

  // PR Form State
  const [newPrTitle, setNewPrTitle] = useState('');
  const [newPrBody, setNewPrBody] = useState('');
  const [newPrHead, setNewPrHead] = useState('');
  const [newPrBase, setNewPrBase] = useState('');
  const [newPrDraft, setNewPrDraft] = useState(false);
  const [prPreview, setPrPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [creatingPr, setCreatingPr] = useState(false);
  const [prError, setPrError] = useState(null);

  // Load operations and pull requests when selected repository changes
  useEffect(() => {
    if (selectedRepo?.id) {
      setModalTab('overview');
      setShowCreatePr(false);
      setPrPreview(null);
      setPrError(null);
      setNewPrTitle('');
      setNewPrBody('');
      setNewPrHead('');
      setNewPrBase(selectedRepo.default_branch || 'main');
      setNewPrDraft(false);

      // Load operations
      setOperationsLoading(true);
      repositoryApi
        .getOperations(selectedRepo.id)
        .then((data) => {
          setRepoOperations(Array.isArray(data) ? data : data.results || []);
        })
        .catch(() => setRepoOperations([]))
        .finally(() => setOperationsLoading(false));

      // Load pull requests
      setPullsLoading(true);
      repositoryApi
        .getPullRequests(selectedRepo.id)
        .then((data) => {
          setPullRequests(Array.isArray(data) ? data : data.results || []);
        })
        .catch(() => setPullRequests([]))
        .finally(() => setPullsLoading(false));
    } else {
      setRepoOperations([]);
      setPullRequests([]);
    }
  }, [selectedRepo]);

  // Load initial data
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [ghStatus, metrics, reposData] = await Promise.all([
        githubApi.getGitHubStatus().catch(() => ({ configured: false, connected: false })),
        repositoryApi.getSyncStatus().catch(() => null),
        repositoryApi.getRepositories({ page_size: 100 }).catch(() => ({ results: [] })),
      ]);

      setGitHubStatus(ghStatus);
      setSyncMetrics(metrics);
      setRepositories(reposData.results || []);
    } catch (err) {
      setError(err?.response?.data?.message || err.message || 'Failed to load repositories');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle manual sync
  const handleSync = async () => {
    try {
      setSyncing(true);
      setError(null);
      const res = await repositoryApi.syncRepositories();
      setNotification(`Synchronized ${res.total} repositories (${res.added} added, ${res.updated} updated, ${res.removed} removed).`);
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.message || err?.response?.data?.detail || 'Failed to synchronize repositories from GitHub.');
    } finally {
      setSyncing(false);
    }
  };

  // Copy helper
  const handleCopy = (text, fieldName) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  // Pull Request handlers
  const handleSyncPr = async (number) => {
    if (!selectedRepo?.id) return;
    try {
      setSyncingPrNumber(number);
      setPrError(null);
      const updated = await repositoryApi.syncPullRequest(selectedRepo.id, number);
      setPullRequests((prev) =>
        prev.map((p) => (p.number === number ? updated : p))
      );
      setNotification(`Synchronized PR #${number} live state from GitHub.`);
    } catch (err) {
      setPrError(err?.response?.data?.message || err?.message || 'Failed to sync PR');
    } finally {
      setSyncingPrNumber(null);
    }
  };

  const handlePreviewPr = async () => {
    if (!selectedRepo?.id || !newPrHead) {
      setPrError('Head branch is required to preview pull request.');
      return;
    }
    try {
      setPreviewLoading(true);
      setPrError(null);
      const preview = await repositoryApi.previewPullRequest(selectedRepo.id, {
        head: newPrHead.trim(),
        base: (newPrBase || selectedRepo.default_branch || 'main').trim(),
      });
      setPrPreview(preview);
      if (!newPrTitle && preview.suggested_title) {
        setNewPrTitle(preview.suggested_title);
      }
      if (!newPrBody && preview.suggested_body) {
        setNewPrBody(preview.suggested_body);
      }
    } catch (err) {
      setPrError(err?.response?.data?.message || err?.response?.data?.error || 'Failed to generate PR preview.');
      setPrPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleCreatePr = async (e) => {
    e?.preventDefault();
    if (!selectedRepo?.id || !newPrHead || !newPrTitle) {
      setPrError('Head branch and Title are required.');
      return;
    }
    try {
      setCreatingPr(true);
      setPrError(null);
      const payload = {
        title: newPrTitle.trim(),
        body: newPrBody,
        head: newPrHead.trim(),
        base: (newPrBase || selectedRepo.default_branch || 'main').trim(),
        draft: newPrDraft,
        preview_fingerprint: prPreview?.preview_fingerprint,
        approved: true,
      };
      const created = await repositoryApi.createPullRequest(selectedRepo.id, payload);
      setPullRequests((prev) => [created, ...prev]);
      setNotification(`Pull Request #${created.number} created successfully.`);
      setShowCreatePr(false);
      setPrPreview(null);
      setNewPrTitle('');
      setNewPrBody('');
      setNewPrHead('');
    } catch (err) {
      setPrError(err?.response?.data?.message || err?.response?.data?.detail || 'Failed to publish pull request to GitHub.');
    } finally {
      setCreatingPr(false);
    }
  };

  // Extract unique languages for filter
  const availableLanguages = useMemo(() => {
    const langs = new Set();
    repositories.forEach((repo) => {
      if (repo.language) langs.add(repo.language);
    });
    return Array.from(langs).sort();
  }, [repositories]);

  // Filtered repositories
  const filteredRepositories = useMemo(() => {
    return repositories.filter((repo) => {
      // Visibility
      if (visibilityFilter === 'public' && repo.is_private) return false;
      if (visibilityFilter === 'private' && !repo.is_private) return false;

      // Language
      if (languageFilter !== 'all' && repo.language !== languageFilter) return false;

      // Search (name, full_name, description)
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const matchName = (repo.name || '').toLowerCase().includes(query);
        const matchFullName = (repo.full_name || '').toLowerCase().includes(query);
        const matchDesc = (repo.description || '').toLowerCase().includes(query);
        if (!matchName && !matchFullName && !matchDesc) return false;
      }

      return true;
    });
  }, [repositories, visibilityFilter, languageFilter, searchQuery]);

  return (
    <div className="flex flex-col gap-6 max-w-7xl">
      <Breadcrumb items={[{ label: 'Projects & Repositories' }]} />

      <PageHeader
        title="PROJECTS & REPOSITORIES"
        description="Connected code repositories, dependency graphs, and codebase indexes."
        badge={
          <Badge variant={repositories.length > 0 ? 'accent' : 'default'} dot={repositories.length > 0}>
            {repositories.length} ACTIVE
          </Badge>
        }
        actions={
          githubStatus?.connected ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleSync}
              disabled={syncing}
              icon={<RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />}
            >
              {syncing ? 'SYNCING...' : 'SYNC GITHUB'}
            </Button>
          ) : null
        }
      />

      {/* Notification Banner */}
      {notification && (
        <div className="flex items-center justify-between p-3.5 bg-accent-primary/10 border border-accent-primary/30 rounded text-xs font-mono text-accent-highlight">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-accent-highlight shrink-0" />
            <span>{notification}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-text-secondary hover:text-text-primary uppercase tracking-wider text-[10px]"
          >
            DISMISS
          </button>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="flex items-center justify-between p-3.5 bg-status-danger/10 border border-status-danger/30 rounded text-xs font-mono text-status-danger">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-text-secondary hover:text-text-primary uppercase tracking-wider text-[10px]"
          >
            DISMISS
          </button>
        </div>
      )}

      {/* Metrics Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-1">
          <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary">
            TOTAL REPOSITORIES
          </span>
          <span className="text-xl font-display font-semibold text-text-primary">
            {syncMetrics?.total_repositories ?? repositories.length}
          </span>
        </div>
        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-1">
          <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary">
            PRIVATE CODEBASES
          </span>
          <span className="text-xl font-display font-semibold text-accent-highlight">
            {syncMetrics?.private_repositories ?? repositories.filter((r) => r.is_private).length}
          </span>
        </div>
        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-1">
          <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary">
            PUBLIC CODEBASES
          </span>
          <span className="text-xl font-display font-semibold text-accent-secondary">
            {syncMetrics?.public_repositories ?? repositories.filter((r) => !r.is_private).length}
          </span>
        </div>
        <div className="bg-surface-elevated border border-border rounded p-4 flex flex-col gap-1">
          <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary">
            LAST SYNCHRONIZATION
          </span>
          <span className="text-xs font-mono text-text-secondary mt-1 truncate">
            {syncMetrics?.last_synced_at
              ? new Date(syncMetrics.last_synced_at).toLocaleTimeString()
              : 'Never'}
          </span>
        </div>
      </div>

      {/* Filter and Action Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between bg-surface-elevated/40 border border-border rounded p-3">
        <div className="relative flex-1 max-w-md">
          <Input
            placeholder="Search repositories by name or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full text-xs"
          />
        </div>

        <div className="flex items-center gap-2">
          {/* Visibility Toggle */}
          <div className="flex items-center border border-border rounded overflow-hidden text-xs font-mono">
            <button
              onClick={() => setVisibilityFilter('all')}
              className={`px-2.5 py-1.5 transition-colors ${
                visibilityFilter === 'all'
                  ? 'bg-accent-primary text-white font-semibold'
                  : 'bg-surface-elevated text-text-secondary hover:text-text-primary'
              }`}
            >
              ALL
            </button>
            <button
              onClick={() => setVisibilityFilter('private')}
              className={`px-2.5 py-1.5 transition-colors border-l border-border ${
                visibilityFilter === 'private'
                  ? 'bg-accent-primary text-white font-semibold'
                  : 'bg-surface-elevated text-text-secondary hover:text-text-primary'
              }`}
            >
              PRIVATE
            </button>
            <button
              onClick={() => setVisibilityFilter('public')}
              className={`px-2.5 py-1.5 transition-colors border-l border-border ${
                visibilityFilter === 'public'
                  ? 'bg-accent-primary text-white font-semibold'
                  : 'bg-surface-elevated text-text-secondary hover:text-text-primary'
              }`}
            >
              PUBLIC
            </button>
          </div>

          {/* Language Dropdown */}
          {availableLanguages.length > 0 && (
            <select
              value={languageFilter}
              onChange={(e) => setLanguageFilter(e.target.value)}
              className="bg-surface-elevated border border-border rounded text-xs font-mono px-2.5 py-1.5 text-text-secondary focus:outline-none focus:border-accent-primary"
            >
              <option value="all">LANG: ALL</option>
              {availableLanguages.map((lang) => (
                <option key={lang} value={lang}>
                  {lang.toUpperCase()}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <LoadingSpinner size="lg" />
          <span className="text-xs font-mono text-text-secondary uppercase tracking-wider">
            Loading repositories from backend...
          </span>
        </div>
      ) : !githubStatus?.connected ? (
        <EmptyState
          icon={<FolderGit2 className="w-8 h-8 text-accent-secondary" />}
          title="GITHUB NOT CONNECTED"
          description="Authorize the NEX GitHub App in your Settings to automatically discover and synchronize repositories."
          actionLabel="Go to Settings"
          onAction={() => navigate('/settings')}
        />
      ) : repositories.length === 0 ? (
        <EmptyState
          icon={<FolderGit2 className="w-8 h-8 text-accent-primary" />}
          title="NO REPOSITORIES DISCOVERED"
          description="Your GitHub App is connected, but no repositories were found or synchronized yet. Trigger a sync to discover repositories."
          actionLabel={syncing ? 'SYNCING...' : 'Sync Repositories Now'}
          onAction={handleSync}
        />
      ) : filteredRepositories.length === 0 ? (
        <EmptyState
          icon={<Search className="w-8 h-8 text-text-secondary" />}
          title="NO MATCHING REPOSITORIES"
          description="No repositories matched your search query or visibility filter."
          actionLabel="Clear Filters"
          onAction={() => {
            setSearchQuery('');
            setVisibilityFilter('all');
            setLanguageFilter('all');
          }}
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>REPOSITORY</TableHead>
              <TableHead>VISIBILITY</TableHead>
              <TableHead>BRANCH</TableHead>
              <TableHead>LANGUAGE</TableHead>
              <TableHead>STATUS</TableHead>
              <TableHead className="text-right">ACTIONS</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredRepositories.map((repo) => (
              <TableRow
                key={repo.id}
                onClick={() => setSelectedRepo(repo)}
                className="hover:bg-surface-elevated cursor-pointer"
              >
                <TableCell>
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-text-primary text-xs hover:text-accent-highlight transition-colors">
                        {repo.full_name}
                      </span>
                      {repo.is_archived && (
                        <span title="Archived">
                          <Archive className="w-3 h-3 text-status-warning" />
                        </span>
                      )}
                      {repo.is_fork && (
                        <span title="Fork">
                          <GitFork className="w-3 h-3 text-text-secondary" />
                        </span>
                      )}
                    </div>
                    {repo.description && (
                      <span className="text-[11px] text-text-secondary truncate max-w-md">
                        {repo.description}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  {repo.is_private ? (
                    <Badge variant="accent" size="sm" dot>
                      PRIVATE
                    </Badge>
                  ) : (
                    <Badge variant="cyan" size="sm">
                      PUBLIC
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1.5 text-text-secondary font-mono text-[11px]">
                    <GitBranch className="w-3 h-3 text-accent-secondary" />
                    <span>{repo.default_branch || 'main'}</span>
                  </div>
                </TableCell>
                <TableCell>
                  {repo.language ? (
                    <Badge variant="default" size="sm">
                      {repo.language}
                    </Badge>
                  ) : (
                    <span className="text-[11px] text-text-secondary font-mono">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge
                    variant={repo.sync_status === 'synced' ? 'success' : 'default'}
                    size="sm"
                  >
                    {repo.sync_status.toUpperCase()}
                  </Badge>
                </TableCell>
                <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center justify-end gap-2">
                    <a
                      href={repo.html_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1 text-text-secondary hover:text-accent-secondary transition-colors"
                      title="Open in GitHub"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Repository Detail Modal */}
      {selectedRepo && (
        <Modal
          isOpen={Boolean(selectedRepo)}
          onClose={() => setSelectedRepo(null)}
          title={selectedRepo.full_name}
          description={selectedRepo.description || 'No description provided.'}
          maxWidth="max-w-3xl"
        >
          <div className="flex flex-col gap-4 text-xs font-mono">
            {/* Tab Navigation */}
            <div className="flex items-center justify-between border-b border-border pb-2.5">
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setModalTab('overview')}
                  className={`px-3 py-1.5 text-xs font-mono font-semibold rounded transition-colors ${
                    modalTab === 'overview'
                      ? 'bg-accent-secondary/15 text-accent-secondary border border-accent-secondary/40'
                      : 'text-text-secondary hover:text-text-primary'
                  }`}
                >
                  OVERVIEW
                </button>
                <button
                  type="button"
                  onClick={() => setModalTab('operations')}
                  className={`px-3 py-1.5 text-xs font-mono font-semibold rounded transition-colors flex items-center gap-1.5 ${
                    modalTab === 'operations'
                      ? 'bg-accent-secondary/15 text-accent-secondary border border-accent-secondary/40'
                      : 'text-text-secondary hover:text-text-primary'
                  }`}
                >
                  <span>OPERATIONS</span>
                  <Badge variant="outline" size="sm">
                    {repoOperations.length}
                  </Badge>
                </button>
                <button
                  type="button"
                  onClick={() => setModalTab('pulls')}
                  className={`px-3 py-1.5 text-xs font-mono font-semibold rounded transition-colors flex items-center gap-1.5 ${
                    modalTab === 'pulls'
                      ? 'bg-accent-secondary/15 text-accent-secondary border border-accent-secondary/40'
                      : 'text-text-secondary hover:text-text-primary'
                  }`}
                >
                  <span>PULL REQUESTS</span>
                  <Badge variant="cyan" size="sm">
                    {pullRequests.length}
                  </Badge>
                </button>
              </div>

              <div className="flex items-center gap-2">
                {selectedRepo.is_private ? (
                  <Badge variant="accent" size="sm">
                    PRIVATE
                  </Badge>
                ) : (
                  <Badge variant="cyan" size="sm">
                    PUBLIC
                  </Badge>
                )}
                <Badge variant="outline" size="sm">
                  BRANCH: {selectedRepo.default_branch}
                </Badge>
              </div>
            </div>

            {/* TAB 1: OVERVIEW */}
            {modalTab === 'overview' && (
              <div className="flex flex-col gap-4">

            {/* Git Clone URLs */}
            <div className="flex flex-col gap-3">
              <span className="text-[11px] uppercase tracking-wider text-text-secondary font-semibold">
                REPOSITORY CLONE URLS
              </span>

              {/* HTTPS Clone */}
              <div className="flex items-center justify-between bg-bg-secondary border border-border rounded p-2.5">
                <div className="flex flex-col gap-0.5 truncate mr-2">
                  <span className="text-[10px] text-text-secondary uppercase">HTTPS</span>
                  <span className="text-xs text-text-primary select-all truncate">
                    {selectedRepo.clone_url || `https://github.com/${selectedRepo.full_name}.git`}
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    handleCopy(
                      selectedRepo.clone_url || `https://github.com/${selectedRepo.full_name}.git`,
                      'https'
                    )
                  }
                  icon={
                    copiedField === 'https' ? (
                      <Check className="w-3.5 h-3.5 text-status-success" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )
                  }
                >
                  {copiedField === 'https' ? 'COPIED' : 'COPY'}
                </Button>
              </div>

              {/* SSH Clone */}
              <div className="flex items-center justify-between bg-bg-secondary border border-border rounded p-2.5">
                <div className="flex flex-col gap-0.5 truncate mr-2">
                  <span className="text-[10px] text-text-secondary uppercase">SSH</span>
                  <span className="text-xs text-text-primary select-all truncate">
                    {selectedRepo.ssh_url || `git@github.com:${selectedRepo.full_name}.git`}
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    handleCopy(
                      selectedRepo.ssh_url || `git@github.com:${selectedRepo.full_name}.git`,
                      'ssh'
                    )
                  }
                  icon={
                    copiedField === 'ssh' ? (
                      <Check className="w-3.5 h-3.5 text-status-success" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )
                  }
                >
                  {copiedField === 'ssh' ? 'COPIED' : 'COPY'}
                </Button>
              </div>
            </div>

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border">
              <div className="flex flex-col gap-0.5">
                <span className="text-[10px] text-text-secondary uppercase">GITHUB REPO ID</span>
                <span className="text-text-primary">{selectedRepo.github_repo_id}</span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="text-[10px] text-text-secondary uppercase">OWNER</span>
                <span className="text-text-primary">{selectedRepo.owner_login}</span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="text-[10px] text-text-secondary uppercase">INSTALLATION ID</span>
                <span className="text-text-primary">{selectedRepo.installation_id}</span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="text-[10px] text-text-secondary uppercase">LAST SYNCHRONIZED</span>
                <span className="text-text-primary">
                  {selectedRepo.last_synced_at
                    ? new Date(selectedRepo.last_synced_at).toLocaleString()
                    : 'N/A'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: OPERATIONS */}
        {modalTab === 'operations' && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-wider text-text-secondary font-semibold">
                SAFE GIT OPERATIONS HISTORY
              </span>
              <span className="text-[10px] text-text-secondary">
                {repoOperations.length} recorded
              </span>
            </div>

            {operationsLoading ? (
              <div className="flex items-center justify-center p-6">
                <LoadingSpinner size="sm" />
                <span className="ml-2 text-text-secondary text-[11px]">Loading operations...</span>
              </div>
            ) : repoOperations.length === 0 ? (
              <div className="p-4 bg-bg-secondary rounded border border-border text-center text-text-secondary text-[11px]">
                No Git operations recorded yet for this repository. Perform safe operations via NEX CLI (
                <code className="text-accent-secondary">nex git stage</code>,{' '}
                <code className="text-accent-secondary">nex git commit</code>,{' '}
                <code className="text-accent-secondary">nex git push</code>).
              </div>
            ) : (
              <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
                {repoOperations.map((op) => (
                  <div
                    key={op.id}
                    className="flex items-center justify-between p-2.5 rounded bg-bg-secondary border border-border text-[11px]"
                  >
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          op.operation_type === 'push'
                            ? 'danger'
                            : op.operation_type === 'commit'
                            ? 'cyan'
                            : op.operation_type.startsWith('branch')
                            ? 'accent'
                            : 'default'
                        }
                        size="sm"
                      >
                        {op.operation_type.toUpperCase().replace('_', ' ')}
                      </Badge>
                      <span className="text-text-primary font-mono truncate max-w-[200px]">
                        {op.target_branch ||
                          (op.commit_sha ? op.commit_sha.substring(0, 7) : '') ||
                          (op.files?.length ? `${op.files.length} file(s)` : '—')}
                      </span>
                      {op.commit_message && (
                        <span className="text-text-secondary truncate max-w-[150px]" title={op.commit_message}>
                          "{op.commit_message}"
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          op.status === 'completed'
                            ? 'success'
                            : op.status === 'simulated'
                            ? 'warning'
                            : 'default'
                        }
                        size="sm"
                      >
                        {op.status.toUpperCase()}
                      </Badge>
                      <span className="text-[10px] text-text-secondary">
                        {new Date(op.completed_at || op.created_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: PULL REQUESTS */}
        {modalTab === 'pulls' && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between pb-1">
              <div className="flex items-center gap-2">
                <GitPullRequest className="w-4 h-4 text-accent-secondary" />
                <span className="text-[11px] uppercase tracking-wider text-text-secondary font-semibold">
                  GITHUB PULL REQUESTS
                </span>
                <Badge variant="cyan" size="sm">
                  {pullRequests.length}
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                {showCreatePr ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setShowCreatePr(false);
                      setPrPreview(null);
                      setPrError(null);
                    }}
                  >
                    Cancel
                  </Button>
                ) : (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (selectedRepo?.id) {
                          setPullsLoading(true);
                          repositoryApi
                            .getPullRequests(selectedRepo.id)
                            .then((data) => setPullRequests(Array.isArray(data) ? data : data.results || []))
                            .finally(() => setPullsLoading(false));
                        }
                      }}
                      icon={<RefreshCw className={`w-3 h-3 ${pullsLoading ? 'animate-spin' : ''}`} />}
                    >
                      Refresh
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => {
                        setShowCreatePr(true);
                        setPrPreview(null);
                        setPrError(null);
                      }}
                      icon={<Plus className="w-3.5 h-3.5" />}
                    >
                      New Pull Request
                    </Button>
                  </>
                )}
              </div>
            </div>

            {prError && (
              <div className="p-2.5 bg-status-danger/10 border border-status-danger/30 rounded text-status-danger text-[11px] flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{prError}</span>
              </div>
            )}

            {/* Create Pull Request Form */}
            {showCreatePr ? (
              <form onSubmit={handleCreatePr} className="flex flex-col gap-3 p-3.5 bg-bg-secondary rounded border border-border">
                <span className="text-xs font-semibold text-text-primary uppercase tracking-wide">
                  Open Pull Request
                </span>

                {/* Branch selectors */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] uppercase text-text-secondary font-semibold">
                      Head Branch (Source) *
                    </label>
                    <Input
                      placeholder="e.g. feature/my-branch"
                      value={newPrHead}
                      onChange={(e) => setNewPrHead(e.target.value)}
                      className="font-mono text-xs"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] uppercase text-text-secondary font-semibold">
                      Base Branch (Target)
                    </label>
                    <Input
                      placeholder={selectedRepo.default_branch || 'main'}
                      value={newPrBase}
                      onChange={(e) => setNewPrBase(e.target.value)}
                      className="font-mono text-xs"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={!newPrHead || previewLoading}
                    onClick={handlePreviewPr}
                    icon={previewLoading ? <LoadingSpinner size="sm" /> : <GitBranch className="w-3.5 h-3.5" />}
                  >
                    {previewLoading ? 'Comparing...' : 'Preview Changes'}
                  </Button>
                  <span className="text-[10px] text-text-secondary">
                    Compare commits and generate cryptographic fingerprint
                  </span>
                </div>

                {/* Preview comparison banner */}
                {prPreview && (
                  <div className="p-3 bg-bg-primary rounded border border-accent-secondary/30 flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-accent-secondary uppercase">
                        Preview Comparison
                      </span>
                      <Badge
                        variant={prPreview.has_conflicts ? 'danger' : 'success'}
                        size="sm"
                      >
                        {prPreview.has_conflicts ? 'CONFLICTS' : 'CLEAN'}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 text-[11px] text-text-secondary">
                      <span>Commits: <strong className="text-text-primary">{prPreview.commits?.length || 0}</strong></span>
                      <span>
                        Changes: <strong className="text-status-success">+{prPreview.additions || 0}</strong> / <strong className="text-status-danger">-{prPreview.deletions || 0}</strong> across {prPreview.changed_files?.length || 0} file(s)
                      </span>
                    </div>
                    {prPreview.changed_files?.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-1">
                        {prPreview.changed_files.slice(0, 4).map((f) => (
                          <Badge key={f.filename} variant="default" size="sm">
                            {f.filename}
                          </Badge>
                        ))}
                        {prPreview.changed_files.length > 4 && (
                          <span className="text-[10px] text-text-secondary self-center">
                            +{prPreview.changed_files.length - 4} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* PR Title */}
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] uppercase text-text-secondary font-semibold">
                    Title *
                  </label>
                  <Input
                    placeholder="Pull request title"
                    value={newPrTitle}
                    onChange={(e) => setNewPrTitle(e.target.value)}
                    className="font-mono text-xs"
                  />
                </div>

                {/* PR Description Body */}
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] uppercase text-text-secondary font-semibold">
                    Description
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Describe your changes..."
                    value={newPrBody}
                    onChange={(e) => setNewPrBody(e.target.value)}
                    className="bg-bg-primary border border-border rounded p-2 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-secondary"
                  />
                </div>

                {/* Draft Mode Checkbox */}
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={newPrDraft}
                    onChange={(e) => setNewPrDraft(e.target.checked)}
                    className="rounded border-border text-accent-secondary focus:ring-0"
                  />
                  <span className="text-[11px] text-text-secondary">Create as Draft Pull Request</span>
                </label>

                {/* Submit Actions */}
                <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setShowCreatePr(false);
                      setPrPreview(null);
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={creatingPr || !newPrHead || !newPrTitle}
                    icon={creatingPr ? <LoadingSpinner size="sm" /> : <GitPullRequest className="w-3.5 h-3.5" />}
                  >
                    {creatingPr ? 'Publishing...' : 'Create Pull Request'}
                  </Button>
                </div>
              </form>
            ) : (
              /* PR List */
              <div>
                {pullsLoading ? (
                  <div className="flex items-center justify-center p-6">
                    <LoadingSpinner size="sm" />
                    <span className="ml-2 text-text-secondary text-[11px]">Loading pull requests...</span>
                  </div>
                ) : pullRequests.length === 0 ? (
                  <div className="p-4 bg-bg-secondary rounded border border-border text-center text-text-secondary text-[11px]">
                    No pull requests found for this repository. Create one using the button above or run{' '}
                    <code className="text-accent-secondary">nex pr</code> in your CLI.
                  </div>
                ) : (
                  <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
                    {pullRequests.map((pr) => {
                      const isDraft = pr.draft;
                      const st = (pr.state || 'open').toUpperCase();
                      const badgeVariant = isDraft
                        ? 'warning'
                        : st === 'OPEN'
                        ? 'success'
                        : st === 'MERGED'
                        ? 'accent'
                        : 'danger';

                      return (
                        <div
                          key={pr.id}
                          className="flex flex-col gap-1.5 p-3 rounded bg-bg-secondary border border-border text-[11px]"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-accent-secondary font-bold font-mono">
                                #{pr.number}
                              </span>
                              <span className="text-text-primary font-semibold truncate max-w-sm">
                                {pr.title}
                              </span>
                              <Badge variant={badgeVariant} size="sm">
                                {isDraft ? 'DRAFT' : st}
                              </Badge>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleSyncPr(pr.number)}
                                disabled={syncingPrNumber === pr.number}
                                icon={
                                  <RefreshCw
                                    className={`w-3 h-3 ${syncingPrNumber === pr.number ? 'animate-spin' : ''}`}
                                  />
                                }
                              >
                                Sync
                              </Button>
                              {pr.html_url && (
                                <a
                                  href={pr.html_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="p-1.5 text-text-secondary hover:text-accent-secondary transition-colors"
                                  title="Open on GitHub"
                                >
                                  <ExternalLink className="w-3.5 h-3.5" />
                                </a>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center gap-3 text-text-secondary text-[10px]">
                            <span className="flex items-center gap-1 font-mono">
                              <span className="text-accent-highlight">{pr.head_branch}</span>
                              <ArrowRight className="w-3 h-3" />
                              <span className="text-accent-secondary">{pr.base_branch}</span>
                            </span>
                            {pr.author_username && (
                              <span>@{pr.author_username}</span>
                            )}
                            <span>
                              {pr.additions !== undefined && pr.deletions !== undefined ? (
                                <span>
                                  <strong className="text-status-success">+{pr.additions}</strong> /{' '}
                                  <strong className="text-status-danger">-{pr.deletions}</strong> in{' '}
                                  {pr.changed_files_count || 0} file(s)
                                </span>
                              ) : null}
                            </span>
                            <span className="ml-auto">
                              {new Date(pr.github_updated_at || pr.updated_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-4 border-t border-border">
              <a
                href={selectedRepo.html_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-accent-secondary hover:text-accent-highlight text-xs font-semibold"
              >
                <span>Open in GitHub</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
              <Button variant="secondary" size="sm" onClick={() => setSelectedRepo(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

export default ProjectsPage;
