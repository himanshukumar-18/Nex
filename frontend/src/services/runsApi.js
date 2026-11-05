/**
 * NEX Frontend — Agent Runs API Service.
 *
 * Pre-configured service boundary communicating with Django backend for
 * autonomous agent execution workflows. Handles unmounted backend endpoints
 * gracefully (404/not implemented) during transitional development phases.
 */

import api from './api';

/**
 * Fetch paginated agent execution runs.
 *
 * @param {Object} [params]
 * @param {number} [params.page=1]
 * @param {number} [params.pageSize=20]
 * @param {string} [params.status] 'queued' | 'running' | 'completed' | 'failed'
 * @param {string} [params.repositoryId]
 * @returns {Promise<{ count: number, results: Array, next: string|null, previous: string|null, ready: boolean }>}
 */
export async function getRuns(params = {}) {
  try {
    const response = await api.get('/runs/', { params });
    const data = response.data || {};
    return {
      count: data.count ?? (Array.isArray(data) ? data.length : 0),
      results: Array.isArray(data.results) ? data.results : Array.isArray(data) ? data : [],
      next: data.next || null,
      previous: data.previous || null,
      ready: true,
    };
  } catch (error) {
    // If backend endpoint is not yet mounted (404 / 501 / 405), return clean readiness state
    if (error?.status === 404 || error?.status === 501 || error?.status === 405) {
      return {
        count: 0,
        results: [],
        next: null,
        previous: null,
        ready: false,
      };
    }
    throw error;
  }
}

/**
 * Fetch detail for a single agent execution run.
 *
 * @param {string} id - Agent Run UUID
 * @returns {Promise<Object|null>}
 */
export async function getRun(id) {
  try {
    const response = await api.get(`/runs/${id}/`);
    return response.data;
  } catch (error) {
    if (error?.status === 404 || error?.status === 501) {
      return null;
    }
    throw error;
  }
}

export const runsApi = {
  getRuns,
  getRun,
};

export default runsApi;

