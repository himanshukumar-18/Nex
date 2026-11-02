import { createSlice } from '@reduxjs/toolkit';

export const AUTH_STATUS = Object.freeze({
  INITIALIZING: 'initializing',
  UNAUTHENTICATED: 'unauthenticated',
  FIREBASE_AUTHENTICATED: 'firebase_authenticated',
  SYNCHRONIZING_PROFILE: 'synchronizing_profile',
  AUTHENTICATED: 'authenticated',
  ERROR: 'error',
});

const initialState = {
  user: null,
  idToken: null,
  status: AUTH_STATUS.INITIALIZING,
  isAuthenticated: false,
  isLoading: true,
  error: null,
};

export const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setInitializing: (state) => {
      state.status = AUTH_STATUS.INITIALIZING;
      state.isLoading = true;
    },
    setFirebaseAuthenticated: (state, action) => {
      state.status = AUTH_STATUS.FIREBASE_AUTHENTICATED;
      state.isLoading = true;
      if (action.payload) {
        if (action.payload.idToken) state.idToken = action.payload.idToken;
        if (action.payload.user) state.user = action.payload.user;
      }
      state.error = null;
    },
    setSynchronizingProfile: (state) => {
      state.status = AUTH_STATUS.SYNCHRONIZING_PROFILE;
      state.isLoading = true;
    },
    setAuthenticated: (state, action) => {
      const { user, idToken } = action.payload;
      state.user = user;
      state.idToken = idToken;
      state.status = AUTH_STATUS.AUTHENTICATED;
      state.isAuthenticated = true;
      state.isLoading = false;
      state.error = null;
    },
    setUnauthenticated: (state, action) => {
      const err = action.payload || null;
      state.user = null;
      state.idToken = null;
      state.status = err ? AUTH_STATUS.ERROR : AUTH_STATUS.UNAUTHENTICATED;
      state.isAuthenticated = false;
      state.isLoading = false;
      state.error = err;
    },
    // Backward-compatible actions
    setCredentials: (state, action) => {
      const { user, idToken } = action.payload;
      state.user = user;
      state.idToken = idToken;
      state.status = user ? AUTH_STATUS.AUTHENTICATED : AUTH_STATUS.UNAUTHENTICATED;
      state.isAuthenticated = !!user;
      state.isLoading = false;
      state.error = null;
    },
    updateUserProfile: (state, action) => {
      if (state.user) {
        state.user = { ...state.user, ...action.payload };
      }
    },
    clearCredentials: (state) => {
      state.user = null;
      state.idToken = null;
      state.status = AUTH_STATUS.UNAUTHENTICATED;
      state.isAuthenticated = false;
      state.isLoading = false;
      state.error = null;
    },
    setLoading: (state, action) => {
      state.isLoading = Boolean(action.payload);
    },
    setError: (state, action) => {
      state.error = action.payload || null;
      state.status = action.payload ? AUTH_STATUS.ERROR : AUTH_STATUS.UNAUTHENTICATED;
      state.isLoading = false;
    },
  },
});

export const {
  setInitializing,
  setFirebaseAuthenticated,
  setSynchronizingProfile,
  setAuthenticated,
  setUnauthenticated,
  setCredentials,
  updateUserProfile,
  clearCredentials,
  setLoading,
  setError,
} = authSlice.actions;

export const selectCurrentUser = (state) => state.auth?.user || null;
export const selectAuthStatus = (state) => {
  if (state.auth?.status) return state.auth.status;
  if (state.auth?.isAuthenticated) return AUTH_STATUS.AUTHENTICATED;
  if (state.auth?.isLoading) return AUTH_STATUS.INITIALIZING;
  return AUTH_STATUS.UNAUTHENTICATED;
};
export const selectIsAuthenticated = (state) => {
  if (!state.auth?.isAuthenticated) return false;
  const status = selectAuthStatus(state);
  return status === AUTH_STATUS.AUTHENTICATED;
};
export const selectAuthLoading = (state) => {
  if (state.auth?.isLoading) return true;
  const status = selectAuthStatus(state);
  return (
    status === AUTH_STATUS.INITIALIZING ||
    status === AUTH_STATUS.FIREBASE_AUTHENTICATED ||
    status === AUTH_STATUS.SYNCHRONIZING_PROFILE
  );
};
export const selectAuthError = (state) => state.auth?.error || null;
export const selectUserRole = (state) => state.auth?.user?.role || 'member';
export const selectIsEmailVerified = (state) => Boolean(state.auth?.user?.emailVerified);

export default authSlice.reducer;
