import axios from 'axios';
import { generateUUID } from '@/lib/utils';
import { normalizeApiError } from './errorHandler';
import { getCurrentIdToken } from './firebase';
import { env } from '@/config/env';

/**
 * Safely sets a header on Axios config headers object (supports AxiosHeaders or plain object).
 */
function setHeader(headers, name, value) {
  if (!headers) return;
  if (typeof headers.set === 'function') {
    headers.set(name, value);
  } else {
    headers[name] = value;
  }
}

/**
 * Safely gets a header from Axios config headers object.
 */
function getHeader(headers, name) {
  if (!headers) return undefined;
  if (typeof headers.get === 'function') {
    return headers.get(name);
  }
  return headers[name] || headers[name.toLowerCase()];
}

/**
 * Checks whether the request URL targets the NEX backend API.
 * Prevents leaking Bearer tokens to external third-party endpoints.
 */
function isInternalApiRequest(url) {
  if (!url) return true;
  if (url.startsWith('/') || url.startsWith('api/')) return true;
  if (env.apiBaseUrl && url.startsWith(env.apiBaseUrl)) return true;
  return false;
}

// Single-flight token refresh promise to prevent stampedes on concurrent 401s
let _activeRefreshPromise = null;

function getRefreshedTokenSingleFlight() {
  if (!_activeRefreshPromise) {
    _activeRefreshPromise = Promise.resolve(getCurrentIdToken(true)).finally(() => {
      _activeRefreshPromise = null;
    });
  }
  return _activeRefreshPromise;
}

/**
 * Primary Axios client configured for NEX Django API Gateway communication.
 * The browser client communicates exclusively with the Django backend.
 */
const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: env.apiTimeout,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Request Interceptor: Inject correlation ID and auth token if available
apiClient.interceptors.request.use(
  async (config) => {
    // Generate correlation ID for end-to-end request tracing if not already set
    if (!getHeader(config.headers, 'X-Correlation-Id')) {
      setHeader(config.headers, 'X-Correlation-Id', generateUUID());
    }

    // Only attach authorization tokens to internal NEX API requests
    if (isInternalApiRequest(config.url)) {
      try {
        const token = await getCurrentIdToken();
        if (token && !getHeader(config.headers, 'Authorization')) {
          setHeader(config.headers, 'Authorization', `Bearer ${token}`);
        }
      } catch {
        // Continue unauthenticated if token retrieval fails
      }
    }

    return config;
  },
  (error) => {
    return Promise.reject(normalizeApiError(error));
  }
);

// Response Interceptor: Token refresh, idempotent transient retry, and error normalization
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error?.config;
    if (!originalRequest) {
      return Promise.reject(normalizeApiError(error));
    }

    const status = error.response ? error.response.status : null;
    const method = (originalRequest.method || 'get').toUpperCase();
    const isIdempotent = ['GET', 'HEAD', 'OPTIONS'].includes(method);
    const isLogoutRequest = (originalRequest.url || '').includes('/auth/logout');

    // 1. Token Refresh on 401 Unauthorized (Single-flight)
    // Attempt single-flight refresh of Firebase ID token and retry once
    // Never retry /auth/logout/ on 401
    if (status === 401 && !originalRequest._retryAuth && !isLogoutRequest) {
      originalRequest._retryAuth = true;
      try {
        const refreshedToken = await getRefreshedTokenSingleFlight();
        if (refreshedToken) {
          setHeader(originalRequest.headers, 'Authorization', `Bearer ${refreshedToken}`);
          return apiClient(originalRequest);
        }
      } catch {
        // Token refresh failed; proceed to error normalization
      }
    }

    // 2. Transient Network or 503 Retry (strictly idempotent methods only)
    // Non-idempotent methods (POST, PUT, PATCH, DELETE) are NEVER retried automatically
    const isTransient = !error.response || status === 503;
    if (isIdempotent && isTransient && !originalRequest._retryTransient) {
      originalRequest._retryTransient = true;
      await new Promise((resolve) => setTimeout(resolve, 300));
      return apiClient(originalRequest);
    }

    return Promise.reject(normalizeApiError(error));
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
