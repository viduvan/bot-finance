import { useEffect, useState, useCallback, useRef } from 'react';
import { useAuthStore } from '../../stores/authStore';
import {
  systemApi, proposalsApi, executionApi, marketApi, featuresApi, analysisApi,
  notificationsApi, createEventsWebSocket,
  type SystemHealth, type Proposal, type PnLSummary, type Ticker, type Candle,
  type Position, type TradeResult, type AppNotification,
} from '../../services/api';
import ProposalCard from '../../components/ProposalCard/ProposalCard';
import PnLChart from '../../components/PnLChart/PnLChart';
import MarketPage from '../MarketPage/MarketPage';
import AnalysisPage from '../AnalysisPage/AnalysisPage';
import SettingsPage from '../SettingsPage/SettingsPage';
import OrdersPage from '../OrdersPage/OrdersPage';
import AuditPage from '../AuditPage/AuditPage';
import './DashboardPage.css';

type PageKey = 'dashboard' | 'proposals' | 'positions' | 'market' | 'analysis' | 'orders' | 'audit' | 'settings';

export default function DashboardPage() {
  const { logout } = useAuthStore();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [pnl, setPnl] = useState<PnLSummary | null>(null);
  const [ticker, setTicker] = useState<Ticker | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [wsConnected, setWsConnected] = useState(false);
  const [activePage, setActivePage] = useState<PageKey>('dashboard');
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT');
  const [initialLoading, setInitialLoading] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifPanel, setShowNotifPanel] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [healthRes, proposalsRes, pnlRes] = await Promise.allSettled([
        systemApi.health(), proposalsApi.active(), executionApi.pnlSummary(),
      ]);
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value.data);
      if (proposalsRes.status === 'fulfilled') setProposals(proposalsRes.value.data.proposals);
      if (pnlRes.status === 'fulfilled') setPnl(pnlRes.value.data);
    } catch { /* silent */ }
  }, []);

  const loadMarketData = useCallback(async (sym: string) => {
    try {
      const [tickerRes, candlesRes] = await Promise.allSettled([
        marketApi.ticker(sym), marketApi.getCandles(sym, '15m', 50),
      ]);
      if (tickerRes.status === 'fulfilled') setTicker(tickerRes.value.data);
      if (candlesRes.status === 'fulfilled') setCandles(candlesRes.value.data.candles || []);
    } catch { /* silent */ }
  }, []);

  const loadUnread = useCallback(async () => {
    try {
      const { data } = await notificationsApi.unreadCount();
      setUnreadCount(data.unread_count);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    async function init() {
      setInitialLoading(true);
      await Promise.all([loadData(), loadMarketData(selectedSymbol), loadUnread()]);
      setInitialLoading(false);
    }
    init();
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    const refreshTimer = setInterval(loadData, 30_000);
    const tickerTimer = setInterval(() => loadMarketData(selectedSymbol), 15_000);
    const notifTimer = setInterval(loadUnread, 60_000);

    const ws = createEventsWebSocket((event) => {
      const type = event.type as string;
      if (type === 'connected') setWsConnected(true);
      if (type === 'proposal_update' || type === 'order_filled') { loadData(); loadUnread(); }
    });
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);

    return () => { clearInterval(timer); clearInterval(refreshTimer); clearInterval(tickerTimer); clearInterval(notifTimer); ws.close(); };
  }, [loadData, loadMarketData, loadUnread, selectedSymbol]);

  const handleSymbolChange = (sym: string) => {
    setSelectedSymbol(sym);
    setTicker(null);
    setCandles([]);
    loadMarketData(sym);
  };

  const pnlValue = parseFloat(pnl?.total_net_pnl || '0');
  const pnlPositive = pnlValue >= 0;

  const PAGE_TITLES: Record<PageKey, string> = {
    dashboard: 'Overview', proposals: 'Proposals', positions: 'Positions',
    market: 'Market Depth', analysis: 'Analysis', orders: 'Orders',
    audit: 'Audit Log', settings: 'Settings',
  };

  return (
    <div className="dashboard">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <svg viewBox="0 0 32 32" fill="none"><rect width="32" height="32" rx="8" fill="url(#sg)" /><path d="M10 24L16 10L22 24" stroke="white" strokeWidth="2" strokeLinecap="round" /><path d="M12.5 19H19.5" stroke="white" strokeWidth="2" strokeLinecap="round" /><circle cx="16" cy="14.5" r="1.5" fill="white" /><defs><linearGradient id="sg" x1="0" y1="0" x2="32" y2="32"><stop stopColor="#3b82f6" /><stop offset="1" stopColor="#8b5cf6" /></linearGradient></defs></svg>
          </div>
          <span className="sidebar-brand">ACTA</span>
        </div>

        <nav className="sidebar-nav">
          <NavBtn page="dashboard" icon="grid" active={activePage} onClick={setActivePage} label="Dashboard" />
          <NavBtn page="market" icon="chart" active={activePage} onClick={setActivePage} label="Market" />
          <NavBtn page="analysis" icon="brain" active={activePage} onClick={setActivePage} label="Analysis" />
          <NavBtn page="proposals" icon="proposal" active={activePage} onClick={setActivePage} label="Proposals" badge={proposals.length || undefined} />
          <NavBtn page="positions" icon="trend" active={activePage} onClick={setActivePage} label="Positions" />
          <NavBtn page="orders" icon="order" active={activePage} onClick={setActivePage} label="Orders" />
          <div className="sidebar-divider" />
          <NavBtn page="audit" icon="audit" active={activePage} onClick={setActivePage} label="Audit Log" />
          <NavBtn page="settings" icon="settings" active={activePage} onClick={setActivePage} label="Settings" />
        </nav>

        <div className="sidebar-footer">
          <div className="ws-status">
            <span className={`status-dot ${wsConnected ? 'online' : 'offline'}`} />
            <span className="ws-label">{wsConnected ? 'Live' : 'Offline'}</span>
          </div>
          <button onClick={logout} className="btn btn-ghost sidebar-logout">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M6 14H3a1 1 0 01-1-1V3a1 1 0 011-1h3M11 11l3-3-3-3M14 8H6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="dashboard-main">
        <header className="dashboard-topbar">
          <div className="topbar-left"><h2>{PAGE_TITLES[activePage]}</h2></div>
          <div className="topbar-right">
            <SymbolSelector value={selectedSymbol} onChange={handleSymbolChange} />
            <NotifBell count={unreadCount} onClick={() => setShowNotifPanel(!showNotifPanel)} />
            <div className="topbar-status">
              <span className={`status-dot ${health?.status === 'healthy' ? 'online' : 'offline'}`} />
              <span>{health?.trading_mode || '...'}</span>
            </div>
            <div className="topbar-time">{currentTime.toLocaleTimeString()}</div>
          </div>
        </header>

        {showNotifPanel && <NotificationPanel onClose={() => { setShowNotifPanel(false); loadUnread(); }} />}

        <div className="dashboard-content page-container">
          {initialLoading ? (
            <div className="loading-state"><div className="loading-spinner" /><p>Loading market data...</p></div>
          ) : (
            <>
              {activePage === 'dashboard' && (
                <DashboardView health={health} proposals={proposals} pnl={pnl} pnlPositive={pnlPositive} pnlValue={pnlValue}
                  ticker={ticker} candles={candles} selectedSymbol={selectedSymbol}
                  onProposalAction={loadData} onMarketRefresh={() => loadMarketData(selectedSymbol)} />
              )}
              {activePage === 'market' && <MarketPage symbol={selectedSymbol} />}
              {activePage === 'analysis' && <AnalysisPage symbol={selectedSymbol} />}
              {activePage === 'proposals' && <ProposalsView proposals={proposals} onAction={loadData} symbol={selectedSymbol} />}
              {activePage === 'positions' && <PositionsView pnl={pnl} symbol={selectedSymbol} />}
              {activePage === 'orders' && <OrdersPage />}
              {activePage === 'audit' && <AuditPage />}
              {activePage === 'settings' && <SettingsPage />}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

// ── Nav Button ────────────────────────────────────────────────────

function NavBtn({ page, icon, active, onClick, label, badge }: {
  page: PageKey; icon: string; active: PageKey; onClick: (p: PageKey) => void; label: string; badge?: number;
}) {
  const icons: Record<string, JSX.Element> = {
    grid: <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" /><rect x="11" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" /><rect x="1" y="11" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" /><rect x="11" y="11" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" /></svg>,
    chart: <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2 15V7L6 10L10 4L14 8L17 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>,
    brain: <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth="1.5" /><path d="M6 9C6 7.5 7.5 6 9 6M12 9C12 10.5 10.5 12 9 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>,
    proposal: <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M4 9H14M9 4V14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /><rect x="1" y="1" width="16" height="16" rx="3" stroke="currentColor" strokeWidth="1.5" /></svg>,
    trend: <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2 14L6 8L10 11L16 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /><path d="M12 4H16V8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>,
    order: <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="2" y="3" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" /><path d="M6 7H12M6 10H10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>,
    audit: <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M4 2H14V16H4V2Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /><path d="M7 6H11M7 9H11M7 12H9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>,
    settings: <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="3" stroke="currentColor" strokeWidth="1.5" /><path d="M9 1V3M9 15V17M1 9H3M15 9H17M3.3 3.3L4.7 4.7M13.3 13.3L14.7 14.7M14.7 3.3L13.3 4.7M4.7 13.3L3.3 14.7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>,
  };

  return (
    <button onClick={() => onClick(page)} className={`sidebar-link ${active === page ? 'active' : ''}`}>
      {icons[icon]}
      {label}
      {badge !== undefined && badge > 0 && <span className="nav-badge">{badge}</span>}
    </button>
  );
}

// ── Symbol Selector ───────────────────────────────────────────────

function SymbolSelector({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="symbol-select">
      <option value="BTCUSDT">BTC/USDT</option>
      <option value="ETHUSDT">ETH/USDT</option>
      <option value="SOLUSDT">SOL/USDT</option>
      <option value="BNBUSDT">BNB/USDT</option>
    </select>
  );
}

// ── Notification Bell ─────────────────────────────────────────────

function NotifBell({ count, onClick }: { count: number; onClick: () => void }) {
  return (
    <button onClick={onClick} className="notif-bell" title="Notifications">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M13 6A4 4 0 005 6C5 10 3 12 3 12H15S13 10 13 6ZM10.4 15A1.6 1.6 0 017.6 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
      {count > 0 && <span className="notif-badge">{count > 99 ? '99+' : count}</span>}
    </button>
  );
}

// ── Notification Panel ────────────────────────────────────────────

function NotificationPanel({ onClose }: { onClose: () => void }) {
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const { data } = await notificationsApi.list(false, 20);
        setNotifications(data.notifications || []);
      } catch { /* silent */ }
      setLoading(false);
    })();
  }, []);

  const handleMarkAllRead = async () => {
    await notificationsApi.markAllRead();
    setNotifications(ns => ns.map(n => ({ ...n, is_read: true })));
    onClose();
  };

  return (
    <div className="notif-panel animate-slide-down">
      <div className="notif-panel-header">
        <h4>Notifications</h4>
        <div className="notif-panel-actions">
          <button onClick={handleMarkAllRead} className="btn btn-ghost btn-sm">Mark All Read</button>
          <button onClick={onClose} className="btn btn-ghost btn-sm">✕</button>
        </div>
      </div>
      {loading ? <p className="notif-loading">Loading...</p> : (
        notifications.length === 0 ? <p className="notif-empty">No notifications</p> : (
          <div className="notif-list">
            {notifications.map(n => (
              <div key={n.id} className={`notif-item ${n.is_read ? 'read' : 'unread'}`}>
                <div className="notif-title">{n.title}</div>
                {n.body && <div className="notif-body">{n.body}</div>}
                <div className="notif-time">{n.created_at ? new Date(n.created_at).toLocaleString() : ''}</div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}

// ── Dashboard Overview ────────────────────────────────────────────

function DashboardView({ health, proposals, pnl, pnlPositive, pnlValue, ticker, candles, selectedSymbol, onProposalAction, onMarketRefresh }: {
  health: SystemHealth | null; proposals: Proposal[]; pnl: PnLSummary | null;
  pnlPositive: boolean; pnlValue: number; ticker: Ticker | null; candles: Candle[];
  selectedSymbol: string; onProposalAction: () => void; onMarketRefresh: () => void;
}) {
  return (
    <>
      <LiveTickerBar ticker={ticker} symbol={selectedSymbol} />
      <div className="status-grid stagger">
        <KpiCard label="System" badge={health?.status || 'checking...'} badgeColor={health?.status === 'healthy' ? 'success' : 'danger'} value={`v${health?.version || '...'}`} sub={health?.environment || '...'} />
        <KpiCard label="Mode" badge={health?.trading_mode || 'PAPER'} badgeColor="warning" value="PAPER" sub="No real trades" />
        <KpiCard label="Active Proposals" badge={String(proposals.length)} badgeColor={proposals.length > 0 ? 'info' : 'success'} value={String(proposals.length)} sub="Awaiting approval" />
        <KpiCard label="Total PnL" badge={`${pnlPositive ? '+' : ''}${pnlValue.toFixed(2)}`} badgeColor={pnlPositive ? 'success' : 'danger'} value={`$${pnlValue.toFixed(2)}`} sub={`${pnl?.total_trades || 0} trades · ${pnl?.win_rate || 0}% win rate`} valueClass={pnlPositive ? 'pnl-positive' : 'pnl-negative'} />
      </div>
      <div className="section-header"><h3 className="section-title">📈 {selectedSymbol} Price Chart (15m)</h3><span className="section-badge-muted">{candles.length} candles</span></div>
      <MiniCandleChart candles={candles} />
      <AnalysisControlPanel symbol={selectedSymbol} onRefresh={() => { onProposalAction(); onMarketRefresh(); }} />
      <div className="section-header"><h3 className="section-title">Performance</h3></div>
      <PnLChart pnl={pnl} />
      {proposals.length > 0 && (
        <>
          <div className="section-header"><h3 className="section-title">🔔 Active Proposals</h3><span className="section-badge">{proposals.length} pending</span></div>
          <div className="proposals-grid">
            {proposals.map(p => <ProposalCard key={p.id} proposal={p} onAction={onProposalAction} />)}
          </div>
        </>
      )}
      {proposals.length === 0 && (
        <div className="empty-state card animate-slide-up">
          <div className="empty-icon">🤖</div><h3>No Active Proposals</h3>
          <p>Click <strong>"Run Full Analysis"</strong> above to analyze {selectedSymbol}.</p>
        </div>
      )}
    </>
  );
}

function KpiCard({ label, badge, badgeColor, value, sub, valueClass = '' }: { label: string; badge: string; badgeColor: string; value: string; sub: string; valueClass?: string }) {
  return (
    <div className="status-card animate-fade-in">
      <div className="status-card-header"><span className="status-card-label">{label}</span><span className={`badge badge-${badgeColor}`}>{badge}</span></div>
      <div className={`status-card-value ${valueClass}`}>{value}</div>
      <div className="status-card-sub">{sub}</div>
    </div>
  );
}

// ── Live Ticker Bar ───────────────────────────────────────────────

function LiveTickerBar({ ticker, symbol }: { ticker: Ticker | null; symbol: string }) {
  if (!ticker) return <div className="ticker-bar ticker-loading animate-fade-in"><div className="ticker-symbol">{symbol}</div><div className="ticker-price-loading">Loading price...</div></div>;
  const price = parseFloat(String(ticker.price));
  const changePct = parseFloat(String(ticker.price_change_pct_24h));
  const change24h = parseFloat(String(ticker.price_change_24h));
  const isUp = changePct >= 0;
  return (
    <div className="ticker-bar animate-fade-in">
      <div className="ticker-main">
        <div className="ticker-symbol">{ticker.symbol}</div>
        <div className="ticker-price">${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        <div className={`ticker-change ${isUp ? 'up' : 'down'}`}>
          <span>{isUp ? '▲' : '▼'}</span>
          <span>{isUp ? '+' : ''}{changePct.toFixed(2)}%</span>
          <span className="ticker-change-abs">({isUp ? '+' : ''}${change24h.toFixed(2)})</span>
        </div>
      </div>
      <div className="ticker-details">
        <TickerDetail label="Bid" value={`$${parseFloat(String(ticker.bid)).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
        <TickerDetail label="Ask" value={`$${parseFloat(String(ticker.ask)).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
        <TickerDetail label="Spread" value={`${parseFloat(String(ticker.spread_bps)).toFixed(1)} bps`} />
        <TickerDetail label="Vol 24h" value={formatVol(parseFloat(String(ticker.volume_24h)))} />
      </div>
    </div>
  );
}

function TickerDetail({ label, value }: { label: string; value: string }) {
  return <div className="ticker-detail-item"><span className="ticker-detail-label">{label}</span><span className="ticker-detail-value">{value}</span></div>;
}

function formatVol(v: number) { if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`; if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`; return v.toFixed(0); }

// ── Mini Candle Chart ─────────────────────────────────────────────

function MiniCandleChart({ candles }: { candles: Candle[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || candles.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr; canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width, H = rect.height;
    ctx.clearRect(0, 0, W, H);
    const prices = candles.flatMap(c => [parseFloat(String(c.high)), parseFloat(String(c.low))]);
    const minP = Math.min(...prices), maxP = Math.max(...prices);
    const range = maxP - minP || 1, pad = range * 0.05;
    const pMin = minP - pad, pMax = maxP + pad;
    const barW = Math.max(2, (W - 20) / candles.length - 1);
    const toY = (p: number) => H - 10 - ((p - pMin) / (pMax - pMin)) * (H - 20);
    ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 1;
    for (let i = 0; i < 5; i++) { const y = 10 + (i / 4) * (H - 20); ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.font = '10px monospace'; ctx.textAlign = 'right';
    for (let i = 0; i < 5; i++) { const p = pMax - (i / 4) * (pMax - pMin); const y = 10 + (i / 4) * (H - 20); ctx.fillText('$' + p.toLocaleString(undefined, { maximumFractionDigits: 0 }), W - 4, y - 3); }
    candles.forEach((c, i) => {
      const x = 10 + i * (barW + 1);
      const o = parseFloat(String(c.open)), cl = parseFloat(String(c.close)), h = parseFloat(String(c.high)), l = parseFloat(String(c.low));
      const bull = cl >= o;
      ctx.strokeStyle = bull ? '#22c55e' : '#ef4444'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x + barW / 2, toY(h)); ctx.lineTo(x + barW / 2, toY(l)); ctx.stroke();
      ctx.fillStyle = bull ? '#22c55e' : '#ef4444';
      ctx.fillRect(x, Math.min(toY(o), toY(cl)), barW, Math.max(1, Math.abs(toY(cl) - toY(o))));
    });
    if (candles.length > 0) {
      const last = parseFloat(String(candles[candles.length - 1].close));
      const ly = toY(last);
      ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 1; ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(0, ly); ctx.lineTo(W, ly); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#3b82f6'; ctx.font = 'bold 11px monospace'; ctx.textAlign = 'left';
      ctx.fillText('$' + last.toLocaleString(undefined, { minimumFractionDigits: 2 }), 10, ly - 6);
    }
  }, [candles]);
  if (candles.length === 0) return <div className="card chart-empty animate-fade-in"><div className="empty-icon">📊</div><p>No candle data yet.</p></div>;
  return <div className="card chart-container animate-fade-in"><canvas ref={canvasRef} className="candle-canvas" /></div>;
}

// ── Analysis Control Panel ────────────────────────────────────────

function AnalysisControlPanel({ symbol, onRefresh }: { symbol: string; onRefresh: () => void }) {
  const [loading, setLoading] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<{ type: string; text: string } | null>(null);
  const [analysisResult, setAnalysisResult] = useState<Record<string, unknown> | null>(null);

  const handleRunFull = async () => {
    setLoading('full'); setAnalysisResult(null);
    try {
      setStatusMsg({ type: 'info', text: `Step 1/3: Fetching candles for ${symbol}...` });
      await marketApi.fetchCandles(symbol, '15m', 100);
      setStatusMsg({ type: 'info', text: `Step 2/3: Computing indicators...` });
      await featuresApi.compute(symbol);
      setStatusMsg({ type: 'info', text: `Step 3/3: Running AI analysis (30-60s)...` });
      const { data } = await analysisApi.triggerSync(symbol);
      setAnalysisResult(data);
      setStatusMsg({ type: 'success', text: `✅ Done! Direction: ${data.final_direction} | Score: ${data.consensus_score}` });
      onRefresh();
    } catch (e: any) { setStatusMsg({ type: 'error', text: `❌ ${e.response?.data?.detail || e.message}` }); }
    finally { setLoading(null); }
  };

  const handleFetchOnly = async () => {
    setLoading('fetch');
    try {
      setStatusMsg({ type: 'info', text: `Fetching candles for ${symbol}...` });
      const { data } = await marketApi.fetchCandles(symbol, '15m', 100);
      setStatusMsg({ type: 'success', text: `✅ Stored ${data.candles_stored} candles` });
      onRefresh();
    } catch (e: any) { setStatusMsg({ type: 'error', text: `❌ ${e.response?.data?.detail || e.message}` }); }
    finally { setLoading(null); }
  };

  return (
    <div className="control-panel card animate-fade-in">
      <div className="control-panel-header">
        <div>
          <h3 className="control-panel-title"><span className="control-icon">⚡</span> AI Multi-Agent Analysis</h3>
          <p className="control-panel-desc">Fetch data → Compute indicators → Run 5 AI agents → Generate proposals</p>
        </div>
      </div>
      <div className="control-panel-actions">
        <button onClick={handleFetchOnly} disabled={!!loading} className="btn btn-ghost control-btn">
          {loading === 'fetch' ? <><span className="spinner-sm" /> Fetching...</> : <>📥 Fetch Market Data</>}
        </button>
        <button onClick={handleRunFull} disabled={!!loading} className="btn btn-primary control-btn-main">
          {loading === 'full' ? <><span className="spinner-sm" /> Running...</> : <>🚀 Run Full Analysis</>}
        </button>
      </div>
      {statusMsg && <div className={`control-status control-status-${statusMsg.type}`}>{loading && <span className="spinner-sm" />}{statusMsg.text}</div>}
      {analysisResult && <AnalysisResultCard result={analysisResult} />}
    </div>
  );
}

function AnalysisResultCard({ result }: { result: Record<string, unknown> }) {
  const direction = String(result.final_direction || 'HOLD');
  const score = Number(result.consensus_score || 0);
  const proceed = Boolean(result.proceed);
  const agents = result.agent_signals as Record<string, { direction: string; confidence: number; reasoning: string }> | undefined;
  const dirColor = direction === 'BUY' ? '#22c55e' : direction === 'SELL' ? '#ef4444' : '#94a3b8';
  return (
    <div className="analysis-result animate-slide-up">
      <div className="analysis-result-header">
        <div className="analysis-direction" style={{ color: dirColor }}>{direction === 'BUY' ? '📈' : direction === 'SELL' ? '📉' : '⏸️'} {direction}</div>
        <div className="analysis-meta">
          <span className={`badge ${proceed ? 'badge-success' : 'badge-warning'}`}>{proceed ? 'Proceed' : 'No Action'}</span>
          <span className="analysis-latency">{Number(result.latency_seconds || 0).toFixed(1)}s</span>
        </div>
      </div>
      <div className="analysis-score-bar">
        <div className="analysis-score-label">Consensus</div>
        <div className="analysis-score-track"><div className="analysis-score-fill" style={{ width: `${Math.abs(score) * 50 + 50}%`, background: dirColor }} /></div>
        <div className="analysis-score-value">{score.toFixed(2)}</div>
      </div>
      {agents && <div className="agent-signals">{Object.entries(agents).map(([name, sig]) => (
        <div key={name} className="agent-signal-item">
          <div className="agent-name">{name.replace(/_/g, ' ')}</div>
          <div className={`agent-direction ${sig.direction?.toLowerCase()}`}>{sig.direction}</div>
          <div className="agent-confidence">
            <div className="agent-conf-bar"><div className="agent-conf-fill" style={{ width: `${(sig.confidence || 0) * 100}%` }} /></div>
            <span>{((sig.confidence || 0) * 100).toFixed(0)}%</span>
          </div>
        </div>
      ))}</div>}
    </div>
  );
}

// ── Proposals View ────────────────────────────────────────────────

function ProposalsView({ proposals, onAction, symbol }: { proposals: Proposal[]; onAction: () => void; symbol: string }) {
  const [allProposals, setAllProposals] = useState<Proposal[]>([]);
  const [filter, setFilter] = useState<'active' | 'all'>('active');

  useEffect(() => {
    if (filter === 'all') {
      proposalsApi.list({ limit: 50 }).then(r => setAllProposals(r.data.proposals)).catch(() => { });
    }
  }, [filter]);

  const displayProposals = filter === 'active' ? proposals : allProposals;

  return (
    <>
      <div className="view-filters">
        <button onClick={() => setFilter('active')} className={`filter-btn ${filter === 'active' ? 'active' : ''}`}>🟢 Active ({proposals.length})</button>
        <button onClick={() => setFilter('all')} className={`filter-btn ${filter === 'all' ? 'active' : ''}`}>📋 All</button>
      </div>
      {displayProposals.length === 0 ? (
        <div className="empty-state card"><div className="empty-icon">📋</div><h3>No Proposals</h3><p>Run an analysis to generate proposals.</p></div>
      ) : (
        <div className="proposals-grid">{displayProposals.map(p => <ProposalCard key={p.id} proposal={p} onAction={onAction} expanded />)}</div>
      )}
    </>
  );
}

// ── Positions View (Enhanced) ─────────────────────────────────────

function PositionsView({ pnl, symbol }: { pnl: PnLSummary | null; symbol: string }) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<TradeResult[]>([]);
  const [tab, setTab] = useState<'summary' | 'open' | 'history'>('summary');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const [p, t] = await Promise.allSettled([
        executionApi.positions({ limit: 50 }), executionApi.trades({ limit: 50 }),
      ]);
      if (p.status === 'fulfilled') setPositions(p.value.data.positions || []);
      if (t.status === 'fulfilled') setTrades(t.value.data.trades || []);
      setLoading(false);
    })();
  }, []);

  return (
    <>
      <div className="view-filters">
        <button onClick={() => setTab('summary')} className={`filter-btn ${tab === 'summary' ? 'active' : ''}`}>📊 Summary</button>
        <button onClick={() => setTab('open')} className={`filter-btn ${tab === 'open' ? 'active' : ''}`}>🟢 Open Positions ({positions.filter(p => p.status === 'OPEN').length})</button>
        <button onClick={() => setTab('history')} className={`filter-btn ${tab === 'history' ? 'active' : ''}`}>📜 Trade History ({trades.length})</button>
      </div>

      {tab === 'summary' && (
        <div className="pnl-summary-grid stagger">
          <div className="pnl-card animate-fade-in"><div className="pnl-card-label">Total Trades</div><div className="pnl-card-value">{pnl?.total_trades ?? 0}</div></div>
          <div className="pnl-card animate-fade-in"><div className="pnl-card-label">Win Rate</div><div className="pnl-card-value">{pnl?.win_rate ?? 0}%</div></div>
          <div className="pnl-card animate-fade-in"><div className="pnl-card-label">Net PnL</div><div className={`pnl-card-value ${parseFloat(pnl?.total_net_pnl || '0') >= 0 ? 'pnl-positive' : 'pnl-negative'}`}>${parseFloat(pnl?.total_net_pnl || '0').toFixed(2)}</div></div>
          <div className="pnl-card animate-fade-in"><div className="pnl-card-label">Fees Paid</div><div className="pnl-card-value">${parseFloat(pnl?.total_fees_paid || '0').toFixed(2)}</div></div>
        </div>
      )}

      {tab === 'open' && (
        <div className="card animate-fade-in">
          {positions.filter(p => p.status === 'OPEN').length === 0 ? (
            <div className="empty-state"><div className="empty-icon">📊</div><h3>No Open Positions</h3><p>Approve and execute proposals to open positions.</p></div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Symbol</th><th>Side</th><th>Entry Price</th><th>Qty</th><th>Current</th><th>Unrealized PnL</th><th>Opened</th></tr></thead>
                <tbody>
                  {positions.filter(p => p.status === 'OPEN').map(p => (
                    <tr key={p.id}>
                      <td className="mono">{p.symbol}</td>
                      <td><span className={`badge badge-${p.side === 'BUY' ? 'success' : 'danger'}`}>{p.side}</span></td>
                      <td className="mono">${parseFloat(p.entry_price).toLocaleString()}</td>
                      <td className="mono">{p.quantity}</td>
                      <td className="mono">{p.current_price ? `$${parseFloat(p.current_price).toLocaleString()}` : '—'}</td>
                      <td className={`mono ${parseFloat(p.unrealized_pnl) >= 0 ? 'pnl-positive' : 'pnl-negative'}`}>${parseFloat(p.unrealized_pnl).toFixed(2)}</td>
                      <td className="mono">{p.opened_at ? new Date(p.opened_at).toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'history' && (
        <div className="card animate-fade-in">
          {trades.length === 0 ? (
            <div className="empty-state"><div className="empty-icon">📜</div><h3>No Trade History</h3><p>Completed trades will appear here.</p></div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>Qty</th><th>Net PnL</th><th>Return</th><th>Duration</th><th>Reason</th><th>Closed</th></tr></thead>
                <tbody>
                  {trades.map(t => (
                    <tr key={t.id}>
                      <td className="mono">{t.symbol}</td>
                      <td><span className={`badge badge-${t.side === 'BUY' ? 'success' : 'danger'}`}>{t.side}</span></td>
                      <td className="mono">${parseFloat(t.entry_price).toLocaleString()}</td>
                      <td className="mono">${parseFloat(t.exit_price).toLocaleString()}</td>
                      <td className="mono">{t.quantity}</td>
                      <td className={`mono ${parseFloat(t.net_pnl) >= 0 ? 'pnl-positive' : 'pnl-negative'}`}>${parseFloat(t.net_pnl).toFixed(2)}</td>
                      <td className="mono">{t.return_percent ? `${parseFloat(t.return_percent).toFixed(2)}%` : '—'}</td>
                      <td className="mono">{t.holding_time_seconds ? formatDuration(t.holding_time_seconds) : '—'}</td>
                      <td>{t.close_reason || '—'}</td>
                      <td className="mono">{t.closed_at ? new Date(t.closed_at).toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}
