import api from './api';
import {
  setFirebaseAuthenticated,
  setSynchronizingProfile,
  setAuthenticated,
  setUnauthenticated,
} from '@/features/auth/authSlice';

// Single-flight lock variables
let _activeSyncPromise = null;
let _lastSyncedUid = null;

/**
 * Synchronizes Firebase user identity and claims with the Django backend.
 * Uses a single-flight promise to prevent duplicate concurrent /me/ requests.
 *
 * @param {object|null} firebaseUser - Firebase User instance or null
 * @param {Function} [dispatch] - Optional Redux dispatch function
 * @returns {Promise<{ user: object, idToken: string }|null>}
 */
export function synchronizeSession(firebaseUser, dispatch) {
  if (!firebaseUser) {
    _activeSyncPromise = null;
    _lastSyncedUid = null;
    if (dispatch) dispatch(setUnauthenticated());
    return Promise.resolve(null);
  }

  // Reuse ongoing sync if one is already running for the exact same UID
  if (_activeSyncPromise && _lastSyncedUid === firebaseUser.uid) {
    return _activeSyncPromise;
  }

  _lastSyncedUid = firebaseUser.uid;

  _activeSyncPromise = (async () => {
    try {
      if (dispatch) {
        dispatch(
          setFirebaseAuthenticated({
            user: {
              uid: firebaseUser.uid,
              email: firebaseUser.email,
              emailVerified: firebaseUser.emailVerified,
              displayName: firebaseUser.displayName || '',
              photoURL: firebaseUser.photoURL || '',
              role: 'member',
            },
          })
        );
        dispatch(setSynchronizingProfile());
      }

      const idToken = await firebaseUser.getIdToken();

      let backendProfile = {};
      try {
        backendProfile = await authApi.getCurrentUser();
      } catch (err) {
        // If the backend specifically rejected credentials (401/403), rethrow to trigger error state
        if (err?.status === 401 || err?.status === 403) {
          throw err;
        }
        // For general transient network failures, proceed with Firebase profile
      }

      const fullUser = {
        uid: firebaseUser.uid,
        email: backendProfile.email || firebaseUser.email,
        emailVerified: backendProfile.email_verified ?? firebaseUser.emailVerified,
        displayName: backendProfile.display_name || firebaseUser.displayName || '',
        photoURL: backendProfile.avatar_url || firebaseUser.photoURL || '',
        role: backendProfile.role || 'member',
        id: backendProfile.id,
      };

      if (dispatch) {
        dispatch(setAuthenticated({ user: fullUser, idToken }));
      }

      return { user: fullUser, idToken };
    } catch (err) {
      if (dispatch) {
        dispatch(setUnauthenticated(err?.message || 'Profile synchronization failed'));
      }
      throw err;
    } finally {
      _activeSyncPromise = null;
    }
  })();

  return _activeSyncPromise;
}

/**
 * Authentication and User Identity API service.
 * Communicates with the Django Backend /api/v1/auth/ endpoints.
 */
export const authApi = {
  /**
   * Synchronizes user session single-flight.
   */
  synchronizeSession,

  /**
   * Fetches current authenticated user profile from Django.
   * @returns {Promise<{ user: object }>}
   */
  async getCurrentUser() {
    const response = await api.get('/auth/me/');
    return response.data;
  },

  /**
   * Synchronizes Firebase user claims and profile details with Django DB.
   * @param {object} [data] - Optional metadata overrides { display_name, photo_url }
   * @returns {Promise<{ user: object }>}
   */
  async syncProfile(data = {}) {
    const response = await api.post('/auth/sync/', data);
    return response.data;
  },

  /**
   * Informs backend of user sign out and revokes active server tokens if applicable.
   * @returns {Promise<{ message: string }>}
   */
  async logout() {
    _activeSyncPromise = null;
    _lastSyncedUid = null;
    const response = await api.post('/auth/logout/');
    return response.data;
  },

  /**
   * Authorizes CLI OAuth PKCE request and generates an authorization code.
   * @param {object} payload
   * @param {string} payload.client_id
   * @param {string} payload.redirect_uri
   * @param {string} payload.code_challenge
   * @param {string} payload.code_challenge_method
   * @param {string} payload.state
   * @param {string} [payload.scope]
   * @returns {Promise<{ code: string, state: string, redirect_uri: string }>}
   */
  async authorizeCli(payload) {
    const response = await api.post('/auth/cli/authorize/', payload);
    return response.data;
  },

  /**
   * Exchanges an authorization code and PKCE verifier for a CLI session token.
   * @param {object} payload
   * @param {string} payload.client_id
   * @param {string} payload.code
   * @param {string} payload.code_verifier
   * @param {string} payload.redirect_uri
   * @returns {Promise<{ access_token: string, token_type: string, expires_in: number, session_id: string }>}
   */
  async exchangeCliToken(payload) {
    const response = await api.post('/auth/cli/token/', payload);
    return response.data;
  },

  /**
   * Retrieves all active CLI sessions for the authenticated user.
   * @returns {Promise<Array<{ session_id: string, device_name: string, client_ip: string, created_at: string, last_used_at: string, is_active: boolean }>>}
   */
  async getCliSessions() {
    const response = await api.get('/auth/cli/sessions/');
    return response.data;
  },

  /**
   * Revokes a specific CLI session or token.
   * @param {string} sessionId
   * @returns {Promise<{ revoked: boolean, message: string }>}
   */
  async revokeCliSession(sessionId) {
    const response = await api.post('/auth/cli/revoke/', { session_id: sessionId });
    return response.data;
  },
};

export default authApi;
