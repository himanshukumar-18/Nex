import { describe, it, expect } from 'vitest';
import {
  normalizeApiError,
  ERROR_CODES,
  getDefaultCodeForStatus,
  getDefaultMessageForStatus,
} from '@/services/errorHandler';

describe('errorHandler - normalizeApiError', () => {
  it('normalizes Django backend string error envelope: { error: "authentication_required", message: "...", detail: null }', () => {
    const backendError = {
      response: {
        status: 401,
        data: {
          error: 'authentication_required',
          message: 'Authentication credentials are required.',
          detail: null,
        },
      },
    };

    const normalized = normalizeApiError(backendError);

    expect(normalized).toEqual({
      __normalized: true,
      code: ERROR_CODES.AUTHENTICATION_ERROR,
      message: 'Authentication credentials are required.',
      detail: null,
      status: 401,
      isNetworkError: false,
      isTimeout: false,
    });
  });

  it('normalizes Django Core Backend standard object error envelope', () => {
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
    expect(normalized.isTimeout).toBe(false);
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
    expect(normalized.isNetworkError).toBe(false);
    expect(normalized.status).toBe(408);
  });

  it('maps HTTP status codes to correct default error codes and messages', () => {
    const testCases = [
      { status: 400, code: ERROR_CODES.BAD_REQUEST },
      { status: 401, code: ERROR_CODES.AUTHENTICATION_ERROR },
      { status: 403, code: ERROR_CODES.PERMISSION_DENIED },
      { status: 404, code: ERROR_CODES.NOT_FOUND },
      { status: 409, code: ERROR_CODES.CONFLICT },
      { status: 422, code: ERROR_CODES.VALIDATION_ERROR },
      { status: 429, code: ERROR_CODES.RATE_LIMITED },
      { status: 500, code: ERROR_CODES.SERVER_ERROR },
      { status: 502, code: ERROR_CODES.BAD_GATEWAY },
      { status: 503, code: ERROR_CODES.SERVICE_UNAVAILABLE },
      { status: 504, code: ERROR_CODES.GATEWAY_TIMEOUT },
    ];

    testCases.forEach(({ status, code }) => {
      expect(getDefaultCodeForStatus(status)).toBe(code);
      const normalized = normalizeApiError({ response: { status, data: {} } });
      expect(normalized.code).toBe(code);
      expect(normalized.status).toBe(status);
      expect(typeof getDefaultMessageForStatus(status)).toBe('string');
    });
  });

  it('extracts top-level detail string when data.detail is present', () => {
    const error = {
      response: {
        status: 403,
        data: { detail: 'CSRF Failed: CSRF token missing.' },
      },
    };

    const normalized = normalizeApiError(error);
    expect(normalized.code).toBe(ERROR_CODES.PERMISSION_DENIED);
    expect(normalized.message).toBe('CSRF Failed: CSRF token missing.');
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

  it('normalizes generic client JavaScript error', () => {
    const generic = new Error('Client computation failed');
    const normalized = normalizeApiError(generic);

    expect(normalized.code).toBe(ERROR_CODES.UNKNOWN_ERROR);
    expect(normalized.message).toBe('Client computation failed');
    expect(normalized.status).toBeNull();
  });
});
