import React, { useEffect } from 'react';
import { Provider, useDispatch } from 'react-redux';
import { store } from './store';
import ErrorBoundary from '@/components/feedback/ErrorBoundary';
import { subscribeToAuthState } from '@/services/firebase';
import { synchronizeSession } from '@/services/authApi';

function AuthInitializer({ children }) {
  const dispatch = useDispatch();

  useEffect(() => {
    const unsubscribe = subscribeToAuthState((firebaseUser) => {
      synchronizeSession(firebaseUser, dispatch).catch(() => {
        // Handled within synchronizeSession via dispatch(setUnauthenticated(...))
      });
    });

    return () => {
      if (typeof unsubscribe === 'function') {
        unsubscribe();
      }
    };
  }, [dispatch]);

  return children;
}

export function Providers({ children }) {
  return (
    <ErrorBoundary>
      <Provider store={store}>
        <AuthInitializer>{children}</AuthInitializer>
      </Provider>
    </ErrorBoundary>
  );
}

export default Providers;
