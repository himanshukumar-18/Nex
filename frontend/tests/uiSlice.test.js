import { describe, it, expect } from 'vitest';
import uiReducer, {
  toggleSidebar,
  setSidebarCollapsed,
  toggleMobileMenu,
  setMobileMenuOpen,
  setActiveNav,
  setSystemNotice,
  clearSystemNotice,
  addToast,
  removeToast,
  clearToasts,
} from '@/features/ui/uiSlice';

describe('uiSlice reducers', () => {
  const initialState = {
    sidebarCollapsed: false,
    mobileMenuOpen: false,
    activeNav: 'dashboard',
    systemNotice: null,
    toasts: [],
  };

  it('handles toggleSidebar and setSidebarCollapsed', () => {
    let state = uiReducer(initialState, toggleSidebar());
    expect(state.sidebarCollapsed).toBe(true);

    state = uiReducer(state, setSidebarCollapsed(false));
    expect(state.sidebarCollapsed).toBe(false);
  });

  it('handles toggleMobileMenu and setMobileMenuOpen', () => {
    let state = uiReducer(initialState, toggleMobileMenu());
    expect(state.mobileMenuOpen).toBe(true);

    state = uiReducer(state, setMobileMenuOpen(false));
    expect(state.mobileMenuOpen).toBe(false);
  });

  it('handles setActiveNav', () => {
    const state = uiReducer(initialState, setActiveNav('runs'));
    expect(state.activeNav).toBe('runs');
  });

  it('handles systemNotice lifecycle', () => {
    const notice = {
      id: 'notice-1',
      type: 'warning',
      title: 'MAINTENANCE',
      message: 'Scheduled maintenance at midnight UTC',
      dismissible: true,
    };

    let state = uiReducer(initialState, setSystemNotice(notice));
    expect(state.systemNotice).toEqual(notice);

    state = uiReducer(state, clearSystemNotice());
    expect(state.systemNotice).toBeNull();
  });

  it('handles toasts lifecycle (add, remove, clear)', () => {
    let state = uiReducer(
      initialState,
      addToast({
        id: 'toast-1',
        type: 'success',
        title: 'BUILD PASSED',
        message: 'All verification checks completed successfully.',
      })
    );
    expect(state.toasts).toHaveLength(1);
    expect(state.toasts[0].title).toBe('BUILD PASSED');

    state = uiReducer(
      state,
      addToast({
        id: 'toast-2',
        type: 'danger',
        title: 'ERROR',
        message: 'Failed to deploy.',
      })
    );
    expect(state.toasts).toHaveLength(2);

    state = uiReducer(state, removeToast('toast-1'));
    expect(state.toasts).toHaveLength(1);
    expect(state.toasts[0].id).toBe('toast-2');

    state = uiReducer(state, clearToasts());
    expect(state.toasts).toHaveLength(0);
  });
});

