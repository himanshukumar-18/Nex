import { initializeApp, getApps, getApp } from 'firebase/app';
import {
  getAuth,
  GoogleAuthProvider,
  GithubAuthProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  sendPasswordResetEmail,
  signOut,
  onIdTokenChanged,
  updateProfile,
  linkWithCredential,
  fetchSignInMethodsForEmail,
} from 'firebase/auth';
import { env } from '@/config/env';

const firebaseConfig = {
  apiKey: env.firebase.apiKey || 'AIzaSyDummyKeyForDevelopmentAndTesting00',
  authDomain: env.firebase.authDomain || 'nex-dev.firebaseapp.com',
  projectId: env.firebase.projectId || 'nex-dev',
  storageBucket: env.firebase.storageBucket || 'nex-dev.appspot.com',
  messagingSenderId: env.firebase.messagingSenderId || '123456789',
  appId: env.firebase.appId || '1:123456789:web:abcdef',
};

// Initialize Firebase App safely (singleton)
export const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();
export const auth = getAuth(app);

// Providers
export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });

export const githubProvider = new GithubAuthProvider();
githubProvider.addScope('read:user');
githubProvider.addScope('user:email');

/**
 * Authentication Methods
 */
export async function loginWithEmail(email, password) {
  return signInWithEmailAndPassword(auth, email, password);
}

export async function registerWithEmail(email, password, displayName = '') {
  const userCredential = await createUserWithEmailAndPassword(auth, email, password);
  if (displayName && userCredential.user) {
    await updateProfile(userCredential.user, { displayName });
  }
  if (userCredential.user) {
    await sendEmailVerification(userCredential.user);
  }
  return userCredential;
}

export async function loginWithGoogle() {
  return signInWithPopup(auth, googleProvider);
}

export async function loginWithGithub() {
  return signInWithPopup(auth, githubProvider);
}

export async function resetPassword(email) {
  return sendPasswordResetEmail(auth, email);
}

export async function resendVerificationEmail(user = auth.currentUser) {
  if (!user) throw new Error('No user is currently signed in.');
  return sendEmailVerification(user);
}

export async function logoutFirebase() {
  return signOut(auth);
}

let _authReadyPromise = null;

export function waitForAuthReady() {
  if (_authReadyPromise) return _authReadyPromise;

  if (auth && typeof auth.authStateReady === 'function') {
    _authReadyPromise = auth.authStateReady();
    return _authReadyPromise;
  }

  _authReadyPromise = new Promise((resolve) => {
    const unsubscribe = onAuthStateChanged(auth, () => {
      if (typeof unsubscribe === 'function') unsubscribe();
      resolve();
    });
  });
  return _authReadyPromise;
}

export function subscribeToAuthState(callback) {
  return onIdTokenChanged(auth, callback);
}

export async function getCurrentIdToken(forceRefresh = false) {
  try {
    await waitForAuthReady();
  } catch {
    // Continue if wait fails
  }
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken(forceRefresh);
}

/**
 * Account Linking and Collision Resolution Methods
 */

export function getPendingCredential(error) {
  if (!error) return null;
  if (error.code === 'auth/account-exists-with-different-credential') {
    return GithubAuthProvider.credentialFromError(error) || error.credential || null;
  }
  return null;
}

export async function getSignInMethods(email) {
  if (!email) return [];
  try {
    return await fetchSignInMethodsForEmail(auth, email);
  } catch {
    return [];
  }
}

export async function linkWithPendingCredential(user, pendingCredential) {
  if (!user || !pendingCredential) {
    throw new Error('User and pending credential are required for account linking.');
  }
  return linkWithCredential(user, pendingCredential);
}

export async function linkWithPassword(email, password, pendingCredential) {
  const userCredential = await signInWithEmailAndPassword(auth, email, password);
  if (pendingCredential && userCredential.user) {
    await linkWithCredential(userCredential.user, pendingCredential);
  }
  return userCredential;
}

export async function linkWithGoogle(pendingCredential) {
  const userCredential = await signInWithPopup(auth, googleProvider);
  if (pendingCredential && userCredential.user) {
    await linkWithCredential(userCredential.user, pendingCredential);
  }
  return userCredential;
}

/**
 * Normalizes Firebase Authentication error codes into actionable, human-readable messages.
 *
 * @param {any} error - Caught error object from Firebase Auth SDK
 * @returns {string} Human-friendly error description with troubleshooting guidance
 */
export function formatFirebaseAuthError(error) {
  if (!error) return 'An unexpected authentication error occurred.';
  const code = error.code || '';

  switch (code) {
    case 'auth/configuration-not-found':
      return 'Firebase Authentication is not initialized for this project. In the Firebase Console, navigate to Build > Authentication, click "Get Started", and enable your desired sign-in methods.';
    case 'auth/operation-not-allowed':
      return 'This sign-in provider is not enabled in the Firebase Console. Please enable it under Authentication > Sign-in method.';
    case 'auth/unauthorized-domain':
      return 'The current domain (localhost) is not authorized in Firebase. Add it under Authentication > Settings > Authorized domains.';
    case 'auth/invalid-credential':
    case 'auth/wrong-password':
    case 'auth/user-not-found':
      return 'Invalid email address or password. Please verify your credentials and try again.';
    case 'auth/email-already-in-use':
      return 'An account already exists with this email address. Please sign in or reset your password.';
    case 'auth/weak-password':
      return 'Password is too weak. Please use at least 8 characters with numbers and symbols.';
    case 'auth/popup-closed-by-user':
      return 'The sign-in popup was closed before completing authentication.';
    case 'auth/popup-blocked':
      return 'The sign-in popup was blocked by your browser. Please allow popups for this site.';
    case 'auth/account-exists-with-different-credential':
      return 'An account already exists with this email under a different provider. Please sign in using your original provider.';
    case 'auth/user-disabled':
      return 'This account has been disabled. Please contact your system administrator.';
    case 'auth/too-many-requests':
      return 'Access temporarily disabled due to multiple failed login attempts. Please wait or reset your password.';
    case 'auth/network-request-failed':
      return 'Network connection failed. Please check your internet connection.';
    default:
      return error.message || 'Authentication failed. Please try again.';
  }
}


