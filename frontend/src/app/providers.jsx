import React from 'react';
import { Provider } from 'react-redux';
import { store } from './store';
import ErrorBoundary from '@/components/feedback/ErrorBoundary';

export function Providers({ children }) {
  return (
    <ErrorBoundary>
      <Provider store={store}>{children}</Provider>
    </ErrorBoundary>
  );
}

export default Providers;

