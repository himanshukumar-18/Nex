import { describe, it, expect } from 'vitest';
import {
  formatFirebaseAuthError,
  loginWithEmail,
  registerWithEmail,
  loginWithGoogle,
  loginWithGithub,
  resetPassword,
  resendVerificationEmail,
  logoutFirebase,
  subscribeToAuthState,
  getCurrentIdToken,
  waitForAuthReady,
} from '@/services/firebase';

describe('Firebase Service & Error Normalization', () => {
  it('exposes all mandatory authentication and lifecycle methods', () => {
    expect(typeof loginWithEmail).toBe('function');
    expect(typeof registerWithEmail).toBe('function');
    expect(typeof loginWithGoogle).toBe('function');
    expect(typeof loginWithGithub).toBe('function');
    expect(typeof resetPassword).toBe('function');
    expect(typeof resendVerificationEmail).toBe('function');
    expect(typeof logoutFirebase).toBe('function');
    expect(typeof subscribeToAuthState).toBe('function');
    expect(typeof getCurrentIdToken).toBe('function');
    expect(typeof waitForAuthReady).toBe('function');
    expect(typeof formatFirebaseAuthError).toBe('function');
  });

  describe('formatFirebaseAuthError', () => {
    it('translates auth/configuration-not-found with actionable Firebase Console guidance', () => {
      const err = { code: 'auth/configuration-not-found' };
      const message = formatFirebaseAuthError(err);
      expect(message).toContain('Firebase Authentication is not initialized');
      expect(message).toContain('Build > Authentication');
      expect(message).toContain('"Get Started"');
    });

    it('translates auth/operation-not-allowed when provider is not enabled', () => {
      const err = { code: 'auth/operation-not-allowed' };
      const message = formatFirebaseAuthError(err);
      expect(message).toContain('This sign-in provider is not enabled');
      expect(message).toContain('Authentication > Sign-in method');
    });

    it('translates auth/unauthorized-domain for domain restrictions', () => {
      const err = { code: 'auth/unauthorized-domain' };
      const message = formatFirebaseAuthError(err);
      expect(message).toContain('Authorized domains');
    });

    it('translates invalid credential errors safely', () => {
      ['auth/invalid-credential', 'auth/wrong-password', 'auth/user-not-found'].forEach((code) => {
        const message = formatFirebaseAuthError({ code });
        expect(message).toContain('Invalid email address or password');
      });
    });

    it('translates duplicate account and weak password errors', () => {
      expect(formatFirebaseAuthError({ code: 'auth/email-already-in-use' })).toContain(
        'An account already exists with this email address'
      );
      expect(formatFirebaseAuthError({ code: 'auth/weak-password' })).toContain(
        'Password is too weak'
      );
    });

    it('translates popup lifecycle errors (closed by user or blocked)', () => {
      expect(formatFirebaseAuthError({ code: 'auth/popup-closed-by-user' })).toContain(
        'popup was closed'
      );
      expect(formatFirebaseAuthError({ code: 'auth/popup-blocked' })).toContain(
        'popup was blocked'
      );
    });

    it('translates account collisions and lockout errors', () => {
      expect(
        formatFirebaseAuthError({ code: 'auth/account-exists-with-different-credential' })
      ).toContain('different provider');
      expect(formatFirebaseAuthError({ code: 'auth/too-many-requests' })).toContain(
        'Access temporarily disabled'
      );
      expect(formatFirebaseAuthError({ code: 'auth/user-disabled' })).toContain(
        'account has been disabled'
      );
    });

    it('falls back to custom error message or generic string when unknown code occurs', () => {
      expect(formatFirebaseAuthError({ message: 'Custom third-party error' })).toBe(
        'Custom third-party error'
      );
      expect(formatFirebaseAuthError(null)).toBe('An unexpected authentication error occurred.');
    });
  });
});

