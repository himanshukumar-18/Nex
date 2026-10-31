import axios from 'axios';
import { generateUUID } from '@/lib/utils';
import { normalizeApiError } from './errorHandler';

/**
 * Primary Axios client configured for NEX Django API Gateway communication.
 * The browser client communicates exclusively with the Django backend.
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Request Interceptor: Inject correlation ID and auth token if available
apiClient.interceptors.request.use(
  (config) => {
    // Generate correlation ID for request tracing if not already set
    if (!config.headers['X-Correlation-Id']) {
      config.headers['X-Correlation-Id'] = generateUUID();
    }

    return config;
  },
  (error) => {
    return Promise.reject(normalizeApiError(error));
  }
);

// Response Interceptor: Normalize all errors through the centralized errorHandler
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    const normalized = normalizeApiError(error);
    return Promise.reject(normalized);
  }
);

/**
 * Standard API service wrapper functions
 */
export const api = {
  get: (url, config) => apiClient.get(url, config),
  post: (url, data, config) => apiClient.post(url, data, config),
  put: (url, data, config) => apiClient.put(url, data, config),
  patch: (url, data, config) => apiClient.patch(url, data, config),
  delete: (url, config) => apiClient.delete(url, config),
  client: apiClient,
};

export default api;

