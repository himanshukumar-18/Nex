/**
 * NEX Frontend Services index.
 * Centralized export for API clients, authentication, and error normalization.
 */

export { default as api, api as apiClient } from './api';
export { default as authApi, authApi as authService } from './authApi';
export {
  default as githubApi,
  getGitHubStatus,
  initiateGitHubInstall,
  getInstallations,
  disconnectInstallation,
} from './githubApi';
export { default as repositoryApi } from './repositoryApi';
export { default as runsApi } from './runsApi';
export { default as systemApi, systemApi as systemService } from './systemApi';
export {
  ERROR_CODES,
  getDefaultCodeForStatus,
  getDefaultMessageForStatus,
  normalizeApiError,
} from './errorHandler';
export * from './firebase';

