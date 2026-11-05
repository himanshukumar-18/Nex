/**
 * NEX Frontend — Repository API Service.
 *
 * Provides typed Axios communication with Django REST Framework for
 * repository listing, metadata inspection, filtering, and manual GitHub sync.
 */

import api from './api';

/**
 * Fetch paginated list of synchronized repositories belonging to the authenticated user.
 *
 * @param {Object} [params]
 * @param {number} [params.page=1]
 * @param {number} [params.pageSize=20]
 * @param {string} [params.search]
 * @param {string} [params.visibility] 'public' | 'private'
 * @param {string} [params.language]
 * @param {boolean} [params.archived]
 * @param {string} [params.status] 'active' | 'removed' | 'all'
 * @param {number} [params.installationId]
 * @returns {Promise<{ count: number, next: string|null, previous: string|null, results: Array }>}
 */
export async function getRepositories(params = {}) {
  const queryParams = {};
  if (params.page) queryParams.page = params.page;
  if (params.pageSize) queryParams.page_size = params.pageSize;
  if (params.search) queryParams.search = params.search;
  if (params.visibility) queryParams.visibility = params.visibility;
  if (params.language) queryParams.language = params.language;
  if (params.archived !== undefined && params.archived !== '') queryParams.archived = params.archived;
  if (params.status) queryParams.status = params.status;
  if (params.installationId) queryParams.installation_id = params.installationId;

  const response = await api.get('/repositories/', { params: queryParams });
  return response.data;
}

/**
 * Fetch detailed metadata and permissions for a single repository by UUID.
 *
 * @param {string} id - Repository UUID.
 * @returns {Promise<Object>}
 */
export async function getRepository(id) {
  const response = await api.get(`/repositories/${id}/`);
  return response.data;
}

/**
 * Trigger manual synchronization of repositories from GitHub.
 *
 * @param {number|null} [installationId=null]
 * @returns {Promise<{ status: string, total: number, added: number, updated: number, removed: number, synced_at: string }>}
 */
export async function syncRepositories(installationId = null) {
  const payload = installationId ? { installation_id: installationId } : {};
  const response = await api.post('/repositories/sync/', payload);
  return response.data;
}

/**
 * Query current synchronization status and repository metrics.
 *
 * @returns {Promise<{ installations_count: number, total_repositories: number, public_repositories: number, private_repositories: number, last_synced_at: string|null }>}
 */
export async function getSyncStatus() {
  const response = await api.get('/repositories/sync/status/');
  return response.data;
}

/**
 * Fetch Git operations history (scoped to a repository or global to user).
 *
 * @param {string|null} [repositoryId=null]
 * @param {Object} [params={}]
 * @returns {Promise<Array>}
 */
export async function getOperations(repositoryId = null, params = {}) {
  const url = repositoryId
    ? `/repositories/${repositoryId}/operations/`
    : '/repositories/operations/';
  const response = await api.get(url, { params });
  return response.data;
}

/**
 * Record a Git operation to the backend.
 *
 * @param {Object} data
 * @returns {Promise<Object>}
 */
export async function recordOperation(data) {
  const response = await api.post('/repositories/operations/', data);
  return response.data;
}

/**
 * Fetch paginated list of Pull Requests for a repository.
 *
 * @param {string} repoId - Repository UUID.
 * @param {Object} [params]
 * @param {string} [params.state] 'open' | 'closed' | 'merged'
 * @param {number} [params.page=1]
 * @param {number} [params.pageSize=20]
 * @returns {Promise<{ count: number, next: string|null, previous: string|null, results: Array }>}
 */
export async function getPullRequests(repoId, params = {}) {
  const queryParams = {};
  if (params.state) queryParams.state = params.state;
  if (params.page) queryParams.page = params.page;
  if (params.pageSize) queryParams.page_size = params.pageSize;

  const response = await api.get(`/repositories/${repoId}/pulls/`, { params: queryParams });
  return response.data;
}

/**
 * Fetch single Pull Request detail.
 *
 * @param {string} repoId - Repository UUID.
 * @param {number} number - PR number.
 * @returns {Promise<Object>}
 */
export async function getPullRequest(repoId, number) {
  const response = await api.get(`/repositories/${repoId}/pulls/${number}/`);
  return response.data;
}

/**
 * Request Pull Request comparison preview and cryptographic fingerprint.
 *
 * @param {string} repoId - Repository UUID.
 * @param {Object} data - { head: string, base?: string }
 * @returns {Promise<{ preview_fingerprint: string, base: string, head: string, commits: Array, changed_files: Array, additions: number, deletions: number, has_conflicts: boolean, suggested_title: string, suggested_body: string }>}
 */
export async function previewPullRequest(repoId, data) {
  const response = await api.post(`/repositories/${repoId}/pulls/preview/`, data);
  return response.data;
}

/**
 * Publish an approved Pull Request to GitHub.
 *
 * @param {string} repoId - Repository UUID.
 * @param {Object} data - { title: string, body?: string, head: string, base: string, draft?: boolean, preview_fingerprint?: string, approved: boolean }
 * @returns {Promise<Object>}
 */
export async function createPullRequest(repoId, data) {
  const response = await api.post(`/repositories/${repoId}/pulls/`, data);
  return response.data;
}

/**
 * Synchronize Pull Request live state from GitHub API.
 *
 * @param {string} repoId - Repository UUID.
 * @param {number} number - PR number.
 * @returns {Promise<Object>}
 */
export async function syncPullRequest(repoId, number) {
  const response = await api.post(`/repositories/${repoId}/pulls/${number}/sync/`);
  return response.data;
}

export const repositoryApi = {
  getRepositories,
  getRepository,
  syncRepositories,
  getSyncStatus,
  getOperations,
  recordOperation,
  getPullRequests,
  getPullRequest,
  previewPullRequest,
  createPullRequest,
  syncPullRequest,
};

export default repositoryApi;
