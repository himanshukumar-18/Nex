/**
 * NEX Frontend — GitHub App Integration API Service.
 *
 * Communicates exclusively with Django backend via Axios for GitHub App
 * installation initiation, status checks, and installation revocation.
 */

import api from './api';

/**
 * Retrieve GitHub App configuration state and the user's active installations.
 *
 * @returns {Promise<{ configured: boolean, app_slug: string, connected: boolean, installations_count: number, installations: Array }>}
 */
export async function getGitHubStatus() {
  const response = await api.get('/repositories/github/status/');
  return response.data;
}

/**
 * Initiate GitHub App installation flow by requesting a signed installation URL with state.
 *
 * @returns {Promise<{ install_url: string, state: string }>}
 */
export async function initiateGitHubInstall() {
  const response = await api.post('/repositories/github/install/');
  return response.data;
}

/**
 * List active GitHub installations belonging to the authenticated user.
 *
 * @returns {Promise<Array>}
 */
export async function getInstallations() {
  const response = await api.get('/repositories/github/installations/');
  return response.data;
}

/**
 * Revoke and disconnect an authorized GitHub App installation.
 *
 * @param {number|string} installationId
 * @returns {Promise<{ status: string, installation_id: number }>}
 */
export async function disconnectInstallation(installationId) {
  const response = await api.post(`/repositories/github/installations/${installationId}/disconnect/`);
  return response.data;
}

export const githubApi = {
  getGitHubStatus,
  initiateGitHubInstall,
  getInstallations,
  disconnectInstallation,
};

export default githubApi;

