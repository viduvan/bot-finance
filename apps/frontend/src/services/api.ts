import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// ── Interceptors ─────────────────────────────────────────────────

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('acta_access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) {
      const refresh = localStorage.getItem('acta_refresh_token');
      if (refresh && !err.config._retry) {
        err.config._retry = true;
        try {
          const { data } = await axios.post(`${API_BASE}/api/v1/auth/refresh`, { refresh_token: refresh });
          localStorage.setItem('acta_access_token', data.access_token);
          localStorage.setItem('acta_refresh_token', data.refresh_token);
          err.config.headers.Authorization = `Bearer ${data.access_token}`;
          return api(err.config);
        } catch {
          localStorage.removeItem('acta_access_token');
          localStorage.removeItem('acta_refresh_token');
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(err);
  }
);

// ── Auth ─────────────────────────────────────────────────────────

export interface LoginRequest { email: string; password: string; mfa_code?: string; }
export interface LoginResponse { access_token: string; refresh_token: string; token_type: string; mfa_required: boolean; }
export interface UserInfo { id: string; email: string; role: string; is_active: boolean; mfa_enabled: boolean; created_at: string; }

export const authApi = {
  login: (data: LoginRequest) => api.post<LoginResponse>('/api/v1/auth/login', data),
  register: (data: { email: string; password: string; role?: string }) => api.post<UserInfo>('/api/v1/auth/register', data),
  refresh: (token: string) => api.post<LoginResponse>('/api/v1/auth/refresh', { refresh_token: token }),
  logout: () => api.post('/api/v1/auth/logout'),
  setupMfa: () => api.post<{ secret: string; provisioning_uri: string }>('/api/v1/auth/mfa/setup'),
};

// ── System ───────────────────────────────────────────────────────

export interface SystemHealth { status: string; version: string; environment: string; trading_mode: string; }
export interface SystemConfig {
  app_name: string; version: string; environment: string;
  trading: { mode: string; exchange: string; market: string; symbols: string[]; allowed_order_types: string[]; };
  risk: Record<string, number>;
  proposal: Record<string, number | boolean>;
  agents: { enabled: boolean; max_iterations: number; timeout_seconds: number; };
  llm: { fallback_chain: string[]; temperature: number; };
  notifications: { telegram_enabled: boolean; };
  monitoring: { prometheus_enabled: boolean; };
  mfa_enabled: boolean;
}
export interface SystemStatus {
  status: string; version: string; trading_mode: string; timestamp: string;
  services: Record<string, string>;
}

export const systemApi = {
  health: () => api.get<SystemHealth>('/api/v1/system/health'),
  config: () => api.get<SystemConfig>('/api/v1/system/config'),
  status: () => api.get<SystemStatus>('/api/v1/system/status'),
};

// ── Market ───────────────────────────────────────────────────────

export interface Ticker {
  symbol: string; price: string; bid: string; ask: string;
  spread_bps: string; volume_24h: string;
  price_change_24h: string; price_change_pct_24h: string;
}

export interface Candle {
  symbol: string; timeframe: string;
  open_time: string; close_time: string;
  open: string; high: string; low: string; close: string;
  volume: string; quote_volume: string; trades_count: number;
}

export interface OrderBookLevel { price: number; quantity: number; }
export interface OrderBookData {
  symbol: string; timestamp: string;
  bids: OrderBookLevel[]; asks: OrderBookLevel[];
  last_update_id?: number;
}

export interface SymbolInfo {
  symbol: string; status: string; base_asset: string; quote_asset: string;
  base_precision: number; quote_precision: number;
  min_qty: string; max_qty: string; step_size: string;
  min_notional: string; tick_size: string;
}

export const marketApi = {
  fetchCandles: (symbol = 'BTCUSDT', timeframe = '15m', limit = 100) =>
    api.post(`/api/v1/market/candles/fetch?symbol=${symbol}&timeframe=${timeframe}&limit=${limit}`),
  getCandles: (symbol = 'BTCUSDT', timeframe = '15m', limit = 100) =>
    api.get<{ symbol: string; timeframe: string; count: number; candles: Candle[] }>(
      `/api/v1/market/candles?symbol=${symbol}&timeframe=${timeframe}&limit=${limit}`
    ),
  ticker: (symbol: string) => api.get<Ticker>(`/api/v1/market/ticker/${symbol}`),
  orderbook: (symbol: string, limit = 20) =>
    api.get<OrderBookData>(`/api/v1/market/orderbook/${symbol}?limit=${limit}`),
  snapshot: (symbol: string) => api.get(`/api/v1/market/snapshot/${symbol}`),
  refreshSnapshot: (symbol: string) => api.post(`/api/v1/market/snapshot/${symbol}/refresh`),
  quality: (symbol: string, timeframe = '15m') =>
    api.get(`/api/v1/market/quality/${symbol}?timeframe=${timeframe}`),
  backfill: (symbol: string, timeframe = '15m', hoursBack = 24) =>
    api.post(`/api/v1/market/backfill/${symbol}?timeframe=${timeframe}&hours_back=${hoursBack}`),
  exchangeInfo: (symbol: string) => api.get<SymbolInfo>(`/api/v1/market/exchange-info/${symbol}`),
  initialLoad: (symbol = 'BTCUSDT') => api.post(`/api/v1/market/candles/initial-load?symbol=${symbol}`),
};

// ── Features & Strategy ─────────────────────────────────────────

export interface StrategySignal {
  symbol: string; strategy: string; signal: string;
  score: number; confidence: number; reasons: string[];
  entry_zone_low: string | null; entry_zone_high: string | null;
  stop_loss_hint: string | null; take_profit_hint: string | null;
}

export const featuresApi = {
  compute: (symbol = 'BTCUSDT', timeframe = '15m') =>
    api.post(`/api/v1/features/${symbol}/compute?timeframe=${timeframe}`),
  getLatest: (symbol: string) => api.get(`/api/v1/features/${symbol}`),
};

export const strategyApi = {
  signal: (symbol: string, strategy = 'ema_pullback') =>
    api.get<StrategySignal>(`/api/v1/strategy/${symbol}/signal?strategy=${strategy}`),
  list: () => api.get<{ strategies: string[] }>('/api/v1/strategy/list'),
};

// ── Analysis ────────────────────────────────────────────────────

export interface AnalysisWorkflow {
  id: string; status: string; trigger_type: string;
  started_at: string | null; completed_at: string | null;
  total_latency_ms: number | null;
  total_input_tokens: number | null; total_output_tokens: number | null;
  error_message: string | null;
}

export const analysisApi = {
  triggerSync: (symbol: string) => api.post(`/api/v1/analysis/${symbol}/trigger-sync`),
  trigger: (symbol: string) => api.post(`/api/v1/analysis/${symbol}/trigger`),
  history: (symbol: string, limit = 10) =>
    api.get<{ symbol: string; count: number; workflows: AnalysisWorkflow[] }>(
      `/api/v1/analysis/${symbol}/history?limit=${limit}`
    ),
  taskStatus: (taskId: string) => api.get(`/api/v1/analysis/task/${taskId}`),
};

// ── Proposals ────────────────────────────────────────────────────

export interface Proposal {
  id: string; symbol: string; market: string;
  recommendation: string; status: string;
  current_price: string | null; suggested_price: string | null;
  suggested_quantity: string | null; suggested_order_type: string;
  stop_loss_price: string | null;
  take_profit_prices: Record<string, string> | null;
  risk_reward_ratio: string | null; estimated_fee: string | null;
  confidence: string | null;
  agent_consensus: Record<string, unknown> | null;
  supporting_reasons: string[]; risk_warnings: string[];
  critic_objections: string[]; environment: string;
  version: number; expires_at: string | null;
  created_at: string | null; updated_at: string | null;
  seconds_until_expiry: number;
}

export const proposalsApi = {
  list: (params?: { symbol?: string; status?: string; limit?: number }) =>
    api.get<{ count: number; proposals: Proposal[] }>('/api/v1/proposals', { params }),
  active: (symbol?: string) =>
    api.get<{ count: number; proposals: Proposal[] }>('/api/v1/proposals/active', { params: { symbol } }),
  get: (id: string) => api.get<Proposal>(`/api/v1/proposals/${id}`),
  issueToken: (id: string) => api.post<{ token: string; expires_in_seconds: number }>(`/api/v1/proposals/${id}/approval-token`),
  approve: (id: string, token: string, currentPrice: string) =>
    api.post(`/api/v1/proposals/${id}/approve`, { token, current_price: currentPrice }),
  reject: (id: string, reason?: string) =>
    api.post(`/api/v1/proposals/${id}/reject`, { reason: reason || '' }),
  cancel: (id: string) => api.post(`/api/v1/proposals/${id}/cancel`),
  reanalyze: (id: string) => api.post(`/api/v1/proposals/${id}/reanalyze`),
  edit: (id: string, fields: { suggested_price?: string; suggested_quantity?: string; stop_loss_price?: string }) =>
    api.patch(`/api/v1/proposals/${id}/edit`, fields),
};

// ── Execution / Positions ─────────────────────────────────────────

export interface Position {
  id: string; symbol: string; side: string;
  entry_price: string; quantity: string;
  current_price: string | null; unrealized_pnl: string;
  total_fee: string; environment: string; status: string;
  opened_at: string | null; closed_at: string | null;
}

export interface TradeResult {
  id: string; symbol: string; side: string;
  entry_price: string; exit_price: string; quantity: string;
  gross_pnl: string; total_fee: string; net_pnl: string;
  return_percent: string | null;
  holding_time_seconds: number | null;
  close_reason: string | null; environment: string;
  closed_at: string | null;
}

export interface PnLSummary {
  total_trades: number; winning_trades: number; losing_trades: number;
  win_rate: number; total_net_pnl: string; total_gross_pnl: string;
  total_fees_paid: string; environment: string;
}

export const executionApi = {
  execute: (proposalId: string, currentPrice: string) =>
    api.post(`/api/v1/execution/${proposalId}/execute`, { current_price: currentPrice }),
  positions: (params?: { symbol?: string; status?: string; limit?: number }) =>
    api.get<{ count: number; positions: Position[] }>('/api/v1/positions', { params }),
  position: (id: string) => api.get<Position>(`/api/v1/positions/${id}`),
  trades: (params?: { symbol?: string; limit?: number }) =>
    api.get<{ count: number; trades: TradeResult[] }>('/api/v1/trades', { params }),
  pnlSummary: () => api.get<PnLSummary>('/api/v1/positions/summary/pnl'),
};

// ── Orders ───────────────────────────────────────────────────────

export interface OrderFill {
  id: string; fill_price: string; fill_quantity: string;
  fee: string; fee_asset: string | null;
  is_maker: boolean | null; timestamp: string | null;
}

export interface Order {
  id: string; proposal_id: string; client_order_id: string;
  exchange_order_id: string | null; symbol: string;
  side: string; order_type: string;
  price: string | null; quantity: string;
  filled_quantity: string; average_fill_price: string | null;
  status: string; environment: string;
  submitted_at: string | null; filled_at: string | null;
  canceled_at: string | null; error_message: string | null;
  fills: OrderFill[]; created_at: string | null;
}

export const ordersApi = {
  list: (params?: { symbol?: string; status?: string; limit?: number }) =>
    api.get<{ count: number; orders: Order[] }>('/api/v1/orders', { params }),
  get: (id: string) => api.get<Order>(`/api/v1/orders/${id}`),
};

// ── Notifications ────────────────────────────────────────────────

export interface AppNotification {
  id: string; channel: string; event_type: string;
  title: string; body: string | null;
  data: Record<string, unknown> | null;
  is_read: boolean; sent_at: string | null;
  read_at: string | null; created_at: string | null;
}

export const notificationsApi = {
  list: (unreadOnly = false, limit = 30) =>
    api.get<{ count: number; notifications: AppNotification[] }>(
      `/api/v1/notifications?unread_only=${unreadOnly}&limit=${limit}`
    ),
  unreadCount: () => api.get<{ unread_count: number }>('/api/v1/notifications/unread-count'),
  markRead: (id: string) => api.post(`/api/v1/notifications/${id}/read`),
  markAllRead: () => api.post('/api/v1/notifications/read-all'),
};

// ── Audit ────────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: number; user_id: string | null; service: string;
  action: string; resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null; request_id: string | null;
  created_at: string | null;
}

export const auditApi = {
  logs: (params?: { action?: string; resource_type?: string; limit?: number }) =>
    api.get<{ count: number; logs: AuditLogEntry[] }>('/api/v1/audit/logs', { params }),
};

// ── WebSocket ─────────────────────────────────────────────────────

export function createEventsWebSocket(onMessage: (event: Record<string, unknown>) => void): WebSocket {
  const token = localStorage.getItem('acta_access_token') || '';
  const wsBase = API_BASE.replace(/^http/, 'ws');
  const ws = new WebSocket(`${wsBase}/api/v1/ws/events?token=${token}`);
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)); } catch { /* ignore */ }
  };
  return ws;
}

export function createMarketWebSocket(onMessage: (event: Record<string, unknown>) => void): WebSocket {
  const token = localStorage.getItem('acta_access_token') || '';
  const wsBase = API_BASE.replace(/^http/, 'ws');
  const ws = new WebSocket(`${wsBase}/api/v1/ws/market?token=${token}`);
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)); } catch { /* ignore */ }
  };
  return ws;
}

export const WS_BASE = API_BASE.replace(/^http/, 'ws');

export default api;
