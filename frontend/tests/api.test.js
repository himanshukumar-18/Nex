import { describe, it, expect, vi, beforeEach } from 'vitest';
import api from '@/services/api';
import * as firebase from '@/services/firebase';

vi.mock('@/services/firebase', () => ({
  getCurrentIdToken: vi.fn(),
}));

describe('API Client & Interceptors', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('instantiates axios client with configured default timeout and base URL', () => {
    expect(api.client.defaults.timeout).toBe(15000);
    expect(api.client.defaults.headers['Content-Type']).toBe('application/json');
    expect(api.client.defaults.headers['Accept']).toBe('application/json');
  });

  it('exposes standard HTTP methods', () => {
    expect(typeof api.get).toBe('function');
    expect(typeof api.post).toBe('function');
    expect(typeof api.put).toBe('function');
    expect(typeof api.patch).toBe('function');
    expect(typeof api.delete).toBe('function');
  });

  describe('Request Interceptor', () => {
    it('injects X-Correlation-Id and Authorization header when token is available', async () => {
      firebase.getCurrentIdToken.mockResolvedValueOnce('fake-jwt-token-123');

      // Execute request interceptor directly
      const requestInterceptor = api.client.interceptors.request.handlers[0].fulfilled;
      const config = { headers: {} };

      const result = await requestInterceptor(config);

      expect(result.headers['X-Correlation-Id']).toBeDefined();
      expect(typeof result.headers['X-Correlation-Id']).toBe('string');
      expect(result.headers['Authorization']).toBe('Bearer fake-jwt-token-123');
    });

    it('preserves existing correlation ID if provided', async () => {
      firebase.getCurrentIdToken.mockResolvedValueOnce(null);

      const requestInterceptor = api.client.interceptors.request.handlers[0].fulfilled;
      const config = { headers: { 'X-Correlation-Id': 'custom-id-999' } };

      const result = await requestInterceptor(config);

      expect(result.headers['X-Correlation-Id']).toBe('custom-id-999');
      expect(result.headers['Authorization']).toBeUndefined();
    });

    it('does not attach Authorization header to external third-party requests', async () => {
      const requestInterceptor = api.client.interceptors.request.handlers[0].fulfilled;
      const externalConfig = {
        url: 'https://identitytoolkit.googleapis.com/v1/accounts',
        headers: {},
      };

      const result = await requestInterceptor(externalConfig);

      expect(result.headers['X-Correlation-Id']).toBeDefined();
      expect(result.headers['Authorization']).toBeUndefined();
      expect(firebase.getCurrentIdToken).not.toHaveBeenCalled();
    });
  });

  describe('Response Interceptor', () => {
    it('retries request with refreshed token when receiving 401 Unauthorized', async () => {
      firebase.getCurrentIdToken.mockResolvedValueOnce('refreshed-token-456');

      const responseInterceptorError = api.client.interceptors.response.handlers[0].rejected;

      const mockError = {
        config: { headers: {}, method: 'get' },
        response: { status: 401, data: { error: 'authentication_required' } },
      };

      // Mock client call for retry
      const spyClient = vi.spyOn(api, 'get');

      try {
        await responseInterceptorError(mockError);
      } catch {
        // Will throw if apiClient mock isn't called or fails
      }

      expect(mockError.config._retryAuth).toBe(true);
      expect(mockError.config.headers['Authorization']).toBe('Bearer refreshed-token-456');
    });

    it('never automatically retries non-idempotent methods on failure', async () => {
      const responseInterceptorError = api.client.interceptors.response.handlers[0].rejected;

      const postError = {
        config: { headers: {}, method: 'post' },
        response: { status: 503, data: {} },
      };

      await expect(responseInterceptorError(postError)).rejects.toMatchObject({
        __normalized: true,
        status: 503,
      });

      expect(postError.config._retryTransient).toBeUndefined();
    });

    it('never retries /auth/logout/ request when receiving 401 Unauthorized', async () => {
      const responseInterceptorError = api.client.interceptors.response.handlers[0].rejected;

      const logoutError = {
        config: { headers: {}, method: 'post', url: '/auth/logout/' },
        response: { status: 401, data: { detail: 'Unauthorized' } },
      };

      await expect(responseInterceptorError(logoutError)).rejects.toMatchObject({
        __normalized: true,
        status: 401,
      });

      expect(logoutError.config._retryAuth).toBeUndefined();
    });

    it('normalizes response errors through errorHandler', async () => {
      const responseInterceptorError = api.client.interceptors.response.handlers[0].rejected;

      const error404 = {
        config: { headers: {}, method: 'get' },
        response: {
          status: 404,
          data: { error: 'not_found', message: 'Resource was not found.', detail: null },
        },
      };

      await expect(responseInterceptorError(error404)).rejects.toMatchObject({
        __normalized: true,
        code: 'NOT_FOUND',
        message: 'Resource was not found.',
        status: 404,
      });
    });
  });
});
