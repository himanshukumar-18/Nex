/**
 * NEX Frontend — Environment Configuration and Diagnostics.
 *
 * Safe parsing and validation of Vite environment variables.
 * Sensitive values are never logged or exposed to the client console.
 */

export const env = {
  // API Gateway
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  apiTimeout: Number(import.meta.env.VITE_API_TIMEOUT) || 15000,
  appTitle: import.meta.env.VITE_APP_TITLE || 'NEX',

  // Firebase Client Config
  firebase: {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
    appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
  },

  // Environment Mode
  isDev: import.meta.env.DEV,
  isProd: import.meta.env.PROD,
  mode: import.meta.env.MODE,
};

/**
 * Validates the frontend environment configuration.
 * Returns a safe diagnostic readiness object without exposing secrets.
 *
 * @returns {{ isConfigured: boolean, missing: string[], configured: string[] }}
 */
export function validateEnvironment() {
  const required = [
    { key: 'VITE_API_BASE_URL', value: env.apiBaseUrl },
    { key: 'VITE_FIREBASE_API_KEY', value: env.firebase.apiKey },
    { key: 'VITE_FIREBASE_AUTH_DOMAIN', value: env.firebase.authDomain },
    { key: 'VITE_FIREBASE_PROJECT_ID', value: env.firebase.projectId },
    { key: 'VITE_FIREBASE_APP_ID', value: env.firebase.appId },
  ];

  const missing = [];
  const configured = [];

  for (const item of required) {
    if (!item.value || item.value.trim() === '') {
      missing.push(item.key);
    } else {
      configured.push(item.key);
    }
  }

  return {
    isConfigured: missing.length === 0,
    missing,
    configured,
  };
}

export default env;

