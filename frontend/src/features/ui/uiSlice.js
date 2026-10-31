import { createSlice } from '@reduxjs/toolkit';

// Retrieve saved sidebar preference if available
const getInitialSidebarState = () => {
  if (typeof window !== 'undefined' && window.localStorage) {
    const saved = window.localStorage.getItem('nex_sidebar_collapsed');
    return saved === 'true';
  }
  return false;
};

const initialState = {
  sidebarCollapsed: getInitialSidebarState(),
  mobileMenuOpen: false,
  activeNav: 'dashboard',
  systemNotice: null,
  toasts: [],
};

export const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    toggleSidebar: (state) => {
      state.sidebarCollapsed = !state.sidebarCollapsed;
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem('nex_sidebar_collapsed', String(state.sidebarCollapsed));
      }
    },
    setSidebarCollapsed: (state, action) => {
      state.sidebarCollapsed = action.payload;
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem('nex_sidebar_collapsed', String(state.sidebarCollapsed));
      }
    },
    toggleMobileMenu: (state) => {
      state.mobileMenuOpen = !state.mobileMenuOpen;
    },
    setMobileMenuOpen: (state, action) => {
      state.mobileMenuOpen = action.payload;
    },
    setActiveNav: (state, action) => {
      state.activeNav = action.payload;
    },
    setSystemNotice: (state, action) => {
      state.systemNotice = action.payload;
    },
    clearSystemNotice: (state) => {
      state.systemNotice = null;
    },
    addToast: (state, action) => {
      const id = action.payload.id || Date.now().toString();
      state.toasts.push({
        id,
        type: action.payload.type || 'info', // 'info' | 'success' | 'warning' | 'danger'
        title: action.payload.title || '',
        message: action.payload.message || '',
        duration: action.payload.duration || 5000,
      });
    },
    removeToast: (state, action) => {
      state.toasts = state.toasts.filter((t) => t.id !== action.payload);
    },
    clearToasts: (state) => {
      state.toasts = [];
    },
  },
});

export const {
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
} = uiSlice.actions;

export default uiSlice.reducer;

