import { create } from 'zustand';
import { authApi, type LoginRequest, type UserInfo } from '../services/api';

interface AuthState {
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  mfaRequired: boolean;
  error: string | null;

  login: (credentials: LoginRequest) => Promise<boolean>;
  logout: () => void;
  setUser: (user: UserInfo) => void;
  clearError: () => void;
  checkAuth: () => boolean;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('acta_access_token'),
  isLoading: false,
  mfaRequired: false,
  error: null,

  login: async (credentials: LoginRequest) => {
    set({ isLoading: true, error: null, mfaRequired: false });
    try {
      const { data } = await authApi.login(credentials);

      if (data.mfa_required && !data.access_token) {
        set({ mfaRequired: true, isLoading: false });
        return false;
      }

      localStorage.setItem('acta_access_token', data.access_token);
      localStorage.setItem('acta_refresh_token', data.refresh_token);

      set({
        isAuthenticated: true,
        isLoading: false,
        mfaRequired: false,
      });
      return true;
    } catch (err: any) {
      const message = err.response?.data?.error?.message ||
        err.response?.data?.detail ||
        'Login failed';
      set({ error: message, isLoading: false });
      return false;
    }
  },

  logout: () => {
    localStorage.removeItem('acta_access_token');
    localStorage.removeItem('acta_refresh_token');
    set({
      user: null,
      isAuthenticated: false,
      mfaRequired: false,
      error: null,
    });
    authApi.logout().catch(() => { });
  },

  setUser: (user: UserInfo) => set({ user }),

  clearError: () => set({ error: null }),

  checkAuth: () => {
    const token = localStorage.getItem('acta_access_token');
    if (!token) {
      set({ isAuthenticated: false });
      return false;
    }
    return true;
  },
}));
