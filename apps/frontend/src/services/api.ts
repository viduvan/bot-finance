import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('acta_access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle 401 (token expired)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem('acta_refresh_token');
      if (refreshToken && !error.config._retry) {
        error.config._retry = true;
        try {
          const { data } = await axios.post(`${API_BASE}/api/v1/auth/refresh`, {
            refresh_token: refreshToken,
          });
          localStorage.setItem('acta_access_token', data.access_token);
          localStorage.setItem('acta_refresh_token', data.refresh_token);
          error.config.headers.Authorization = `Bearer ${data.access_token}`;
          return api(error.config);
        } catch {
          // Refresh failed, clear tokens and redirect to login
          localStorage.removeItem('acta_access_token');
          localStorage.removeItem('acta_refresh_token');
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

// ── Auth API ────────────────────────────────────────────────────

export interface LoginRequest {
  email: string;
  password: string;
  mfa_code?: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  mfa_required: boolean;
}

export interface UserInfo {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  mfa_enabled: boolean;
  created_at: string;
}

export const authApi = {
  login: (data: LoginRequest) =>
    api.post<LoginResponse>('/api/v1/auth/login', data),

  register: (data: { email: string; password: string; role?: string }) =>
    api.post<UserInfo>('/api/v1/auth/register', data),

  refresh: (refreshToken: string) =>
    api.post<LoginResponse>('/api/v1/auth/refresh', { refresh_token: refreshToken }),

  logout: () => api.post('/api/v1/auth/logout'),

  setupMfa: () =>
    api.post<{ secret: string; provisioning_uri: string }>('/api/v1/auth/mfa/setup'),
};

// ── System API ──────────────────────────────────────────────────

export interface SystemHealth {
  status: string;
  version: string;
  environment: string;
  trading_mode: string;
}

export interface SystemConfig {
  app_name: string;
  version: string;
  trading: {
    mode: string;
    symbols: string[];
  };
  risk: Record<string, number>;
  mfa_enabled: boolean;
}

export const systemApi = {
  health: () => api.get<SystemHealth>('/api/v1/system/health'),
  config: () => api.get<SystemConfig>('/api/v1/system/config'),
  status: () => api.get('/api/v1/system/status'),
};

export default api;
