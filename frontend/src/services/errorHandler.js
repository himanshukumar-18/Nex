/**
 * Standardized NEX API error representation.
 *
 * All API errors across the frontend are normalized to this shape
 * to ensure predictable presentation in UI alerts, toasts, and boundary states.
 */

export const ERROR_CODES = {
  NETWORK_ERROR: 'NETWORK_ERROR',
  TIMEOUT: 'TIMEOUT_ERROR',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  AUTHENTICATION_ERROR: 'AUTHENTICATION_REQUIRED',
  PERMISSION_DENIED: 'PERMISSION_DENIED',
  NOT_FOUND: 'NOT_FOUND',
  RATE_LIMITED: 'RATE_LIMITED',
  SERVER_ERROR: 'INTERNAL_SERVER_ERROR',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
};

/**
 * Normalizes an Axios error or raw exception into the standard NEX error format.
 * Matches Django Core Backend error envelopes: `{ error: { code, message, detail } }`.
 *
 * @param {any} error - The caught error object
 * @returns {{ code: string, message: string, detail: any, status: number|null, isNetworkError: boolean, isTimeout: boolean }}
 */
export function normalizeApiError(error) {
  // If already normalized
  if (error && error.__normalized) {
    return error;
  }

  // 1. Axios Timeout
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

    // Check for standard NEX Django error envelope: { error: { code, message, detail } }
    if (data?.error && typeof data.error === 'object') {
      return {
        __normalized: true,
        code: data.error.code || getDefaultCodeForStatus(status),
        message: data.error.message || getDefaultMessageForStatus(status),
        detail: data.error.detail || null,
        status,
        isNetworkError: false,
        isTimeout: false,
      };
    }

    // Django REST Framework detail string or validation dict fallback
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

    // Generic response with message
    if (typeof data?.message === 'string') {
      return {
        __normalized: true,
        code: getDefaultCodeForStatus(status),
        message: data.message,
        detail: data.detail || null,
        status,
        isNetworkError: false,
        isTimeout: false,
      };
    }

    // Status code fallback
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

function getDefaultCodeForStatus(status) {
  switch (status) {
    case 400:
      return ERROR_CODES.VALIDATION_ERROR;
    case 401:
      return ERROR_CODES.AUTHENTICATION_ERROR;
    case 403:
      return ERROR_CODES.PERMISSION_DENIED;
    case 404:
      return ERROR_CODES.NOT_FOUND;
    case 429:
      return ERROR_CODES.RATE_LIMITED;
    case 500:
    case 502:
    case 503:
    case 504:
      return ERROR_CODES.SERVER_ERROR;
    default:
      return ERROR_CODES.UNKNOWN_ERROR;
  }
}

function getDefaultMessageForStatus(status) {
  switch (status) {
    case 400:
      return 'The request was invalid or could not be processed.';
    case 401:
      return 'Authentication credentials were missing or invalid.';
    case 403:
      return 'You do not have permission to perform this action.';
    case 404:
      return 'The requested resource was not found.';
    case 429:
      return 'Rate limit exceeded. Please slow down your requests.';
    case 500:
      return 'An internal server error occurred on the NEX backend.';
    case 502:
    case 503:
    case 504:
      return 'The service is temporarily unavailable. Please try again shortly.';
    default:
      return 'An error occurred while processing your request.';
  }
}

