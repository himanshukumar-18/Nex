import api from './api';

/**
 * System and Health Probes API service.
 * Communicates with backend health endpoints (/health/, /health/ready/).
 */
export const systemApi = {
  /**
   * Performs a lightweight liveness check.
   * Confirms the Django HTTP server is responsive.
   * @returns {Promise<{ status: string }>}
   */
  async getLiveness() {
    const response = await api.get('/health/', { baseURL: '' });
    return response.data;
  },

  /**
   * Performs a readiness check.
   * Confirms Django database connectivity and critical services.
   * @returns {Promise<{ status: string, database: string }>}
   */
  async getReadiness() {
    const response = await api.get('/health/ready/', { baseURL: '' });
    return response.data;
  },
};

export default systemApi;

