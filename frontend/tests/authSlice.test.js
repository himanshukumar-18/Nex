import { describe, it, expect } from 'vitest';
import authReducer, {
  AUTH_STATUS,
  setInitializing,
  setFirebaseAuthenticated,
  setSynchronizingProfile,
  setAuthenticated,
  setUnauthenticated,
  setCredentials,
  updateUserProfile,
  clearCredentials,
  selectCurrentUser,
  selectAuthStatus,
  selectIsAuthenticated,
  selectAuthLoading,
  selectAuthError,
  selectUserRole,
  selectIsEmailVerified,
} from '@/features/auth/authSlice';

describe('authSlice Reducer and Lifecycle State Machine', () => {
  const initialBaseState = {
    user: null,
    idToken: null,
    status: AUTH_STATUS.INITIALIZING,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  };

  it('exposes all six standard authentication lifecycle statuses', () => {
    expect(AUTH_STATUS.INITIALIZING).toBe('initializing');
    expect(AUTH_STATUS.UNAUTHENTICATED).toBe('unauthenticated');
    expect(AUTH_STATUS.FIREBASE_AUTHENTICATED).toBe('firebase_authenticated');
    expect(AUTH_STATUS.SYNCHRONIZING_PROFILE).toBe('synchronizing_profile');
    expect(AUTH_STATUS.AUTHENTICATED).toBe('authenticated');
    expect(AUTH_STATUS.ERROR).toBe('error');
  });

  it('handles setInitializing', () => {
    const unauthState = { ...initialBaseState, status: AUTH_STATUS.UNAUTHENTICATED, isLoading: false };
    const nextState = authReducer(unauthState, setInitializing());

    expect(nextState.status).toBe(AUTH_STATUS.INITIALIZING);
    expect(nextState.isLoading).toBe(true);
    expect(selectAuthLoading({ auth: nextState })).toBe(true);
  });

  it('handles setFirebaseAuthenticated and setSynchronizingProfile', () => {
    const s1 = authReducer(
      initialBaseState,
      setFirebaseAuthenticated({
        user: { uid: 'fb_1', email: 'dev@nex.dev' },
        idToken: 'tok123',
      })
    );
    expect(s1.status).toBe(AUTH_STATUS.FIREBASE_AUTHENTICATED);
    expect(s1.isLoading).toBe(true);
    expect(selectIsAuthenticated({ auth: s1 })).toBe(false);

    const s2 = authReducer(s1, setSynchronizingProfile());
    expect(s2.status).toBe(AUTH_STATUS.SYNCHRONIZING_PROFILE);
    expect(s2.isLoading).toBe(true);
    expect(selectIsAuthenticated({ auth: s2 })).toBe(false);
  });

  it('handles setAuthenticated and establishes full authenticated access', () => {
    const mockUser = {
      uid: 'fb_123',
      email: 'alex@nex.dev',
      emailVerified: true,
      role: 'developer',
      displayName: 'Alex',
    };
    const nextState = authReducer(
      initialBaseState,
      setAuthenticated({ user: mockUser, idToken: 'token_abc123' })
    );

    expect(nextState.user).toEqual(mockUser);
    expect(nextState.idToken).toBe('token_abc123');
    expect(nextState.status).toBe(AUTH_STATUS.AUTHENTICATED);
    expect(nextState.isAuthenticated).toBe(true);
    expect(nextState.isLoading).toBe(false);

    const rootState = { auth: nextState };
    expect(selectCurrentUser(rootState)).toEqual(mockUser);
    expect(selectAuthStatus(rootState)).toBe(AUTH_STATUS.AUTHENTICATED);
    expect(selectIsAuthenticated(rootState)).toBe(true);
    expect(selectAuthLoading(rootState)).toBe(false);
    expect(selectUserRole(rootState)).toBe('developer');
    expect(selectIsEmailVerified(rootState)).toBe(true);
  });

  it('handles setUnauthenticated without error on clean logout', () => {
    const populatedState = {
      user: { uid: 'fb_123', email: 'alex@nex.dev' },
      idToken: 'token_abc',
      status: AUTH_STATUS.AUTHENTICATED,
      isAuthenticated: true,
      isLoading: false,
      error: null,
    };

    const nextState = authReducer(populatedState, setUnauthenticated());
    expect(nextState.user).toBeNull();
    expect(nextState.idToken).toBeNull();
    expect(nextState.status).toBe(AUTH_STATUS.UNAUTHENTICATED);
    expect(nextState.isAuthenticated).toBe(false);
    expect(nextState.error).toBeNull();
  });

  it('handles setUnauthenticated with error on failure', () => {
    const nextState = authReducer(
      initialBaseState,
      setUnauthenticated('Authentication provider network timeout')
    );

    expect(nextState.status).toBe(AUTH_STATUS.ERROR);
    expect(nextState.isAuthenticated).toBe(false);
    expect(nextState.error).toBe('Authentication provider network timeout');
    expect(selectAuthError({ auth: nextState })).toBe('Authentication provider network timeout');
  });

  it('maintains backward compatibility with setCredentials and clearCredentials', () => {
    const mockUser = { uid: 'fb_456', email: 'legacy@nex.dev', role: 'member' };
    const state1 = authReducer(initialBaseState, setCredentials({ user: mockUser, idToken: 'tok_leg' }));
    expect(state1.isAuthenticated).toBe(true);
    expect(state1.status).toBe(AUTH_STATUS.AUTHENTICATED);

    const state2 = authReducer(state1, clearCredentials());
    expect(state2.isAuthenticated).toBe(false);
    expect(state2.status).toBe(AUTH_STATUS.UNAUTHENTICATED);
  });

  it('handles updateUserProfile partially', () => {
    const populatedState = {
      user: {
        uid: 'fb_123',
        email: 'alex@nex.dev',
        displayName: 'Alex',
        role: 'member',
      },
      idToken: 'token_abc123',
      status: AUTH_STATUS.AUTHENTICATED,
      isAuthenticated: true,
      isLoading: false,
      error: null,
    };

    const nextState = authReducer(
      populatedState,
      updateUserProfile({ displayName: 'Alex Senior', role: 'admin' })
    );

    expect(nextState.user.displayName).toBe('Alex Senior');
    expect(nextState.user.role).toBe('admin');
    expect(nextState.user.email).toBe('alex@nex.dev');
  });
});
