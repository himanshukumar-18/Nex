import { describe, it, expect } from 'vitest';
import { normalizeApiError, ERROR_CODES } from '@/services/errorHandler';

describe('errorHandler - normalizeApiError', () => {
  it('normalizes Django Core Backend standard error envelope', () => {
    const backendError = {
      response: {
        status: 400,
        data: {
          error: {
            code: 'INVALID_PARAMETERS',
            message: 'Invalid payload structure.',
            detail: { field: ['Required'] },
          },
        },
      },
    };

    const normalized = normalizeApiError(backendError);

    expect(normalized).toEqual({
      __normalized: true,
      code: 'INVALID_PARAMETERS',
      message: 'Invalid payload structure.',
      detail: { field: ['Required'] },
      status: 400,
      isNetworkError: false,
      isTimeout: false,
    });
  });

  it('normalizes network connection failure (no response received)', () => {
    const networkError = {
      isAxiosError: true,
      message: 'Network Error',
      response: undefined,
    };

    const normalized = normalizeApiError(networkError);

    expect(normalized.code).toBe(ERROR_CODES.NETWORK_ERROR);
    expect(normalized.isNetworkError).toBe(true);
    expect(normalized.status).toBeNull();
  });

  it('normalizes request timeout (ECONNABORTED)', () => {
    const timeoutError = {
      code: 'ECONNABORTED',
      message: 'timeout of 15000ms exceeded',
    };

    const normalized = normalizeApiError(timeoutError);

    expect(normalized.code).toBe(ERROR_CODES.TIMEOUT);
    expect(normalized.isTimeout).toBe(true);
    expect(normalized.status).toBe(408);
  });

  it('provides sensible default error codes and messages for standard HTTP status codes', () => {
    const error404 = {
      response: {
        status: 404,
        data: {},
      },
    };
    const norm404 = normalizeApiError(error404);
    expect(norm404.code).toBe(ERROR_CODES.NOT_FOUND);
    expect(norm404.status).toBe(404);

    const error429 = {
      response: {
        status: 429,
        data: {},
      },
    };
    const norm429 = normalizeApiError(error429);
    expect(norm429.code).toBe(ERROR_CODES.RATE_LIMITED);
    expect(norm429.status).toBe(429);

    const error500 = {
      response: {
        status: 500,
        data: {},
      },
    };
    const norm500 = normalizeApiError(error500);
    expect(norm500.code).toBe(ERROR_CODES.SERVER_ERROR);
    expect(norm500.status).toBe(500);
  });

  it('returns already normalized error without re-wrapping', () => {
    const initial = {
      __normalized: true,
      code: 'CUSTOM_CODE',
      message: 'Custom message',
      detail: null,
      status: 400,
      isNetworkError: false,
      isTimeout: false,
    };

    const normalized = normalizeApiError(initial);
    expect(normalized).toBe(initial);
  });
});

