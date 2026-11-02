/**
 * Standardized NEX API error representation.
 *
 * All API errors across the frontend are normalized to this shape
 * to ensure predictable presentation in UI alerts, toasts, and boundary states.
 */

export const ERROR_CODES = {
  BAD_REQUEST: 'BAD_REQUEST',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  AUTHENTICATION_ERROR: 'AUTHENTICATION_REQUIRED',
  PERMISSION_DENIED: 'PERMISSION_DENIED',
  NOT_FOUND: 'NOT_FOUND',
  CONFLICT: 'CONFLICT',
  RATE_LIMITED: 'RATE_LIMITED',
  SERVER_ERROR: 'INTERNAL_SERVER_ERROR',
  BAD_GATEWAY: 'BAD_GATEWAY',
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
  GATEWAY_TIMEOUT: 'GATEWAY_TIMEOUT',
  TIMEOUT: 'TIMEOUT_ERROR',
  NETWORK_ERROR: 'NETWORK_ERROR',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
};

/**
 * Maps an HTTP status code to a default NEX machine-readable error code.
 *
 * @param {number|null} status - The HTTP status code
 * @returns {string} Error code from ERROR_CODES
 */
export function getDefaultCodeForStatus(status) {
  switch (status) {
    case 400:
      return ERROR_CODES.BAD_REQUEST;
    case 401:
      return ERROR_CODES.AUTHENTICATION_ERROR;
    case 403:
      return ERROR_CODES.PERMISSION_DENIED;
    case 404:
      return ERROR_CODES.NOT_FOUND;
    case 409:
      return ERROR_CODES.CONFLICT;
    case 422:
      return ERROR_CODES.VALIDATION_ERROR;
    case 429:
      return ERROR_CODES.RATE_LIMITED;
    case 500:
      return ERROR_CODES.SERVER_ERROR;
    case 502:
      return ERROR_CODES.BAD_GATEWAY;
    case 503:
      return ERROR_CODES.SERVICE_UNAVAILABLE;
    case 504:
      return ERROR_CODES.GATEWAY_TIMEOUT;
    default:
      return ERROR_CODES.UNKNOWN_ERROR;
  }
}

/**
 * Returns a human-friendly message for a given HTTP status code.
 *
 * @param {number|null} status - The HTTP status code
 * @returns {string} Default human-readable message
 */
export function getDefaultMessageForStatus(status) {
  switch (status) {
    case 400:
      return 'The request was invalid or could not be processed.';
    case 401:
      return 'Authentication credentials were missing or invalid.';
    case 403:
      return 'You do not have permission to perform this action.';
    case 404:
      return 'The requested resource was not found.';
    case 409:
      return 'The resource is in a conflicting state.';
    case 422:
      return 'The provided data failed semantic validation.';
    case 429:
      return 'Rate limit exceeded. Please slow down your requests.';
    case 500:
      return 'An internal server error occurred on the NEX backend.';
    case 502:
      return 'Bad gateway. The upstream backend service failed to respond.';
    case 503:
      return 'The service is temporarily unavailable. Please try again shortly.';
    case 504:
      return 'Gateway timeout. The upstream service took too long to reply.';
    default:
      return 'An error occurred while processing your request.';
  }
}

/**
 * Normalizes an Axios error or raw exception into the standard NEX error format.
 * Matches Django Core Backend error envelopes: `{ error: "<code_string>", message: "<msg>", detail: <detail> }`
 * or `{ error: { code, message, detail } }`.
 *
 * @param {any} error - The caught error object
 * @returns {{ __normalized: boolean, code: string, message: string, detail: any, status: number|null, isNetworkError: boolean, isTimeout: boolean }}
 */
export function normalizeApiError(error) {
  // If already normalized
  if (error && error.__normalized) {
    return error;
  }

  // 1. Axios Timeout (ECONNABORTED or message contains timeout)
  if (error?.code === 'ECONNABORTED' || error?.message?.toLowerCase().includes('timeout')) {
    return {
      __normalized: true,
      code: ERROR_CODES.TIMEOUT,
      message: 'Request timed out. The server took too long to respond.',
      detail: null,
      status: 408,
      isNetworkError: false,
      isTimeout: true,
    };
  }

  // 2. Network / Offline Error (No response received)
  if (error?.isAxiosError && !error.response) {
    return {
      __normalized: true,
      code: ERROR_CODES.NETWORK_ERROR,
      message: 'Network unreachable. Please check your internet connection.',
      detail: error.message || null,
      status: null,
      isNetworkError: true,
      isTimeout: false,
    };
  }

  // 3. HTTP Response Received
  if (error?.response) {
    const status = error.response.status;
    const data = error.response.data;

    // A. Django string code envelope: { error: "validation_error", message: "...", detail: ... }
    if (data && typeof data.error === 'string') {
      const codeUpper = data.error.toUpperCase();
      return {
        __normalized: true,
        code: ERROR_CODES[codeUpper] || codeUpper || getDefaultCodeForStatus(status),
        message: data.message || getDefaultMessageForStatus(status),
        detail: data.detail !== undefined ? data.detail : null,
        status,
        isNetworkError: false,
        isTimeout: false,
      };
    }

    // B. Structured object envelope: { error: { code, message, detail } }
    if (data?.error && typeof data.error === 'object') {
      return {
        __normalized: true,
        code: data.error.code || getDefaultCodeForStatus(status),
        message: data.error.message || data.message || getDefaultMessageForStatus(status),
        detail: data.error.detail !== undefined ? data.error.detail : (data.detail || null),
        status,
        isNetworkError: false,
        isTimeout: false,
      };
    }

    // C. Django REST Framework direct detail string
    if (typeof data?.detail === 'string') {
      return {
        __normalized: true,
        code: getDefaultCodeForStatus(status),
        message: data.detail,
        detail: null,
        status,
        isNetworkError: false,
        isTimeout: false,
      };
    }

    // D. Response with top-level message
    if (typeof data?.message === 'string') {
      return {
        __normalized: true,
        code: getDefaultCodeForStatus(status),
        message: data.message,
        detail: data.detail !== undefined ? data.detail : null,
        status,
        isNetworkError: false,
        isTimeout: false,
      };
    }

    // E. Validation dictionary in data.detail or data itself (e.g., { email: ["..."] })
    if (data && typeof data === 'object') {
      return {
        __normalized: true,
        code: getDefaultCodeForStatus(status),
        message: getDefaultMessageForStatus(status),
        detail: data,
        status,
        isNetworkError: false,
        isTimeout: false,
      };
    }

    // F. Status code fallback
    return {
      __normalized: true,
      code: getDefaultCodeForStatus(status),
      message: getDefaultMessageForStatus(status),
      detail: data || null,
      status,
      isNetworkError: false,
      isTimeout: false,
    };
  }

  // 4. Generic JavaScript Error
  return {
    __normalized: true,
    code: ERROR_CODES.UNKNOWN_ERROR,
    message: error?.message || 'An unexpected client-side error occurred.',
    detail: null,
    status: null,
    isNetworkError: false,
    isTimeout: false,
  };
}

export default {
  ERROR_CODES,
  getDefaultCodeForStatus,
  getDefaultMessageForStatus,
  normalizeApiError,
};
