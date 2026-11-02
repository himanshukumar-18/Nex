import { describe, it, expect, vi, beforeEach } from 'vitest';
import authApi from '@/services/authApi';
import api from '@/services/api';

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe('authApi Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getCurrentUser calls GET /auth/me/ and returns data', async () => {
    const mockUser = { id: 'u-123', email: 'user@nex.dev', role: 'developer' };
    api.get.mockResolvedValueOnce({ data: mockUser });

    const result = await authApi.getCurrentUser();
    expect(api.get).toHaveBeenCalledWith('/auth/me/');
    expect(result).toEqual(mockUser);
  });

  it('syncProfile calls POST /auth/sync/ with profile payload', async () => {
    const mockResponse = { message: 'Synced successfully', user: { id: 'u-123' } };
    api.post.mockResolvedValueOnce({ data: mockResponse });

    const payload = { display_name: 'Alex Engineer', photo_url: 'https://avatar.url' };
    const result = await authApi.syncProfile(payload);

    expect(api.post).toHaveBeenCalledWith('/auth/sync/', payload);
    expect(result).toEqual(mockResponse);
  });

  it('logout calls POST /auth/logout/', async () => {
    const mockResponse = { message: 'Logged out successfully' };
    api.post.mockResolvedValueOnce({ data: mockResponse });

    const result = await authApi.logout();
    expect(api.post).toHaveBeenCalledWith('/auth/logout/');
    expect(result).toEqual(mockResponse);
  });

  it('authorizeCli calls POST /auth/cli/authorize/ with PKCE payload', async () => {
    const mockResponse = {
      authorization_code: 'code-123',
      redirect_uri: 'http://127.0.0.1:8942/callback',
      state: 'st-456',
      expires_in: 300,
    };
    api.post.mockResolvedValueOnce({ data: mockResponse });

    const payload = {
      code_challenge: 'challenge-xyz',
      code_challenge_method: 'S256',
      redirect_uri: 'http://127.0.0.1:8942/callback',
      state: 'st-456',
      device_name: 'Work-MacBook',
    };
    const result = await authApi.authorizeCli(payload);

    expect(api.post).toHaveBeenCalledWith('/auth/cli/authorize/', payload);
    expect(result).toEqual(mockResponse);
  });

  it('exchangeCliToken calls POST /auth/cli/token/ with verifier', async () => {
    const mockResponse = {
      access_token: 'cli-session-token-xyz',
      token_type: 'Bearer',
      expires_in: 2592000,
      session_id: 'sess-123',
    };
    api.post.mockResolvedValueOnce({ data: mockResponse });

    const payload = {
      code: 'code-123',
      code_verifier: 'verifier-xyz',
      redirect_uri: 'http://127.0.0.1:8942/callback',
    };
    const result = await authApi.exchangeCliToken(payload);

    expect(api.post).toHaveBeenCalledWith('/auth/cli/token/', payload);
    expect(result).toEqual(mockResponse);
  });

  it('getCliSessions calls GET /auth/cli/sessions/', async () => {
    const mockSessions = [
      { session_id: 'sess-1', device_name: 'MacBook', is_active: true },
    ];
    api.get.mockResolvedValueOnce({ data: mockSessions });

    const result = await authApi.getCliSessions();
    expect(api.get).toHaveBeenCalledWith('/auth/cli/sessions/');
    expect(result).toEqual(mockSessions);
  });

  it('revokeCliSession calls POST /auth/cli/revoke/ with sessionId', async () => {
    const mockResponse = { revoked: true, message: 'Session revoked' };
    api.post.mockResolvedValueOnce({ data: mockResponse });

    const result = await authApi.revokeCliSession('sess-1');
    expect(api.post).toHaveBeenCalledWith('/auth/cli/revoke/', { session_id: 'sess-1' });
    expect(result).toEqual(mockResponse);
  });

  describe('synchronizeSession', () => {
    it('dispatches authenticated user on successful profile synchronization', async () => {
      const mockFirebaseUser = {
        uid: 'fb_sync_1',
        email: 'engineer@nex.dev',
        emailVerified: true,
        displayName: 'Engineer',
        getIdToken: vi.fn().mockResolvedValue('jwt_sync_token'),
      };

      const mockBackendProfile = {
        id: 'u-uuid-1',
        email: 'engineer@nex.dev',
        display_name: 'Engineer Senior',
        role: 'developer',
        email_verified: true,
      };

      api.get.mockResolvedValueOnce({ data: mockBackendProfile });
      const mockDispatch = vi.fn();

      const result = await authApi.synchronizeSession(mockFirebaseUser, mockDispatch);

      expect(api.get).toHaveBeenCalledWith('/auth/me/');
      expect(result.user.role).toBe('developer');
      expect(result.user.displayName).toBe('Engineer Senior');
      expect(result.idToken).toBe('jwt_sync_token');
      expect(mockDispatch).toHaveBeenCalled();
    });

    it('reuses active in-flight sync promise for the same UID (single-flight)', async () => {
      const mockFirebaseUser = {
        uid: 'fb_sync_flight',
        email: 'flight@nex.dev',
        emailVerified: true,
        getIdToken: vi.fn().mockResolvedValue('jwt_flight_token'),
      };

      api.get.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: { role: 'member' } }), 50))
      );

      const mockDispatch = vi.fn();

      const p1 = authApi.synchronizeSession(mockFirebaseUser, mockDispatch);
      const p2 = authApi.synchronizeSession(mockFirebaseUser, mockDispatch);

      expect(p1).toBe(p2); // Exactly same promise

      await Promise.all([p1, p2]);
      expect(api.get).toHaveBeenCalledTimes(1); // Only 1 network call
    });

    it('clears credentials when firebaseUser is null', async () => {
      const mockDispatch = vi.fn();
      const result = await authApi.synchronizeSession(null, mockDispatch);
      expect(result).toBeNull();
      expect(mockDispatch).toHaveBeenCalled();
    });
  });
});

