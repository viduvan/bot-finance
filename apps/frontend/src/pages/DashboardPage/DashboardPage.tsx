import { useEffect, useState, useCallback, useRef } from 'react';
import { useAuthStore } from '../../stores/authStore';
import {
  systemApi, proposalsApi, executionApi, marketApi, featuresApi, analysisApi,
  createEventsWebSocket,
  type SystemHealth, type Proposal, type PnLSummary, type Ticker, type Candle,
} from '../../services/api';
import ProposalCard from '../../components/ProposalCard/ProposalCard';
import PnLChart from '../../components/PnLChart/PnLChart';
import './DashboardPage.css';

// ── Main Dashboard Page ───────────────────────────────────────────

export default function DashboardPage() {
  const { logout } = useAuthStore();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [pnl, setPnl] = useState<PnLSummary | null>(null);
  const [ticker, setTicker] = useState<Ticker | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [wsConnected, setWsConnected] = useState(false);
  const [activePage, setActivePage] = useState<'dashboard' | 'proposals' | 'positions'>('dashboard');
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT');
  const [initialLoading, setInitialLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [healthRes, proposalsRes, pnlRes] = await Promise.allSettled([
        systemApi.health(),
        proposalsApi.active(),
        executionApi.pnlSummary(),
      ]);
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value.data);
      if (proposalsRes.status === 'fulfilled') setProposals(proposalsRes.value.data.proposals);
      if (pnlRes.status === 'fulfilled') setPnl(pnlRes.value.data);
    } catch { /* silent */ }
  }, []);

  const loadMarketData = useCallback(async (sym: string) => {
    try {
      const [tickerRes, candlesRes] = await Promise.allSettled([
        marketApi.ticker(sym),
        marketApi.getCandles(sym, '15m', 50),
      ]);
      if (tickerRes.status === 'fulfilled') setTicker(tickerRes.value.data);
      if (candlesRes.status === 'fulfilled') setCandles(candlesRes.value.data.candles || []);
    } catch { /* silent */ }
  }, []);

  // Initial load: system data + market data
  useEffect(() => {
    async function init() {
      setInitialLoading(true);
      await Promise.all([loadData(), loadMarketData(selectedSymbol)]);
      setInitialLoading(false);
    }
    init();

    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    const refreshTimer = setInterval(loadData, 30_000);
    const tickerTimer = setInterval(() => loadMarketData(selectedSymbol), 15_000);

    const ws = createEventsWebSocket((event) => {
      const type = event.type as string;
      if (type === 'connected') setWsConnected(true);
      if (type === 'proposal_update') loadData();
      if (type === 'order_filled') loadData();
    });
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);

    return () => {
      clearInterval(timer);
      clearInterval(refreshTimer);
      clearInterval(tickerTimer);
      ws.close();
    };
  }, [loadData, loadMarketData, selectedSymbol]);

  const handleSymbolChange = (sym: string) => {
    setSelectedSymbol(sym);
    setTicker(null);
    setCandles([]);
    loadMarketData(sym);
  };

  const pnlValue = parseFloat(pnl?.total_net_pnl || '0');
  const pnlPositive = pnlValue >= 0;

  return (
    <div className="dashboard">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <svg viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="url(#sidebar-grad)" />
              <path d="M10 24L16 10L22 24" stroke="white" strokeWidth="2" strokeLinecap="round" />
              <path d="M12.5 19H19.5" stroke="white" strokeWidth="2" strokeLinecap="round" />
              <circle cx="16" cy="14.5" r="1.5" fill="white" />
              <defs>
                <linearGradient id="sidebar-grad" x1="0" y1="0" x2="32" y2="32">
                  <stop stopColor="#3b82f6" />
                  <stop offset="1" stopColor="#8b5cf6" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <span className="sidebar-brand">ACTA</span>
        </div>

        <nav className="sidebar-nav">
          <button onClick={() => setActivePage('dashboard')} className={`sidebar-link ${activePage === 'dashboard' ? 'active' : ''}`}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" /><rect x="11" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" /><rect x="1" y="11" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" /><rect x="11" y="11" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" /></svg>
            Dashboard
          </button>
          <button onClick={() => setActivePage('proposals')} className={`sidebar-link ${activePage === 'proposals' ? 'active' : ''}`}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M4 9H14M9 4V14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /><rect x="1" y="1" width="16" height="16" rx="3" stroke="currentColor" strokeWidth="1.5" /></svg>
            Proposals
            {proposals.length > 0 && <span className="nav-badge">{proposals.length}</span>}
          </button>
          <button onClick={() => setActivePage('positions')} className={`sidebar-link ${activePage === 'positions' ? 'active' : ''}`}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2 14L6 8L10 11L16 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /><path d="M12 4H16V8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
            Positions
          </button>
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
          <div className="topbar-left">
            <h2>{activePage === 'dashboard' ? 'Overview' : activePage === 'proposals' ? 'Proposals' : 'Positions'}</h2>
          </div>
          <div className="topbar-right">
            <SymbolSelector value={selectedSymbol} onChange={handleSymbolChange} />
            <div className="topbar-status">
              <span className={`status-dot ${health?.status === 'healthy' ? 'online' : 'offline'}`} />
              <span>{health?.trading_mode || '...'}</span>
            </div>
            <div className="topbar-time">{currentTime.toLocaleTimeString()}</div>
          </div>
        </header>

        <div className="dashboard-content page-container">
          {initialLoading ? (
            <div className="loading-state">
              <div className="loading-spinner" />
              <p>Loading market data...</p>
            </div>
          ) : (
            <>
              {activePage === 'dashboard' && (
                <DashboardView
                  health={health}
                  proposals={proposals}
                  pnl={pnl}
                  pnlPositive={pnlPositive}
                  pnlValue={pnlValue}
                  ticker={ticker}
                  candles={candles}
                  selectedSymbol={selectedSymbol}
                  onProposalAction={loadData}
                  onMarketRefresh={() => loadMarketData(selectedSymbol)}
                />
              )}
              {activePage === 'proposals' && (
                <ProposalsView proposals={proposals} onAction={loadData} />
              )}
              {activePage === 'positions' && (
                <PositionsView pnl={pnl} />
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

// ── Symbol Selector ───────────────────────────────────────────────

function SymbolSelector({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="symbol-select"
    >
      <option value="BTCUSDT">BTC/USDT</option>
      <option value="ETHUSDT">ETH/USDT</option>
      <option value="SOLUSDT">SOL/USDT</option>
      <option value="BNBUSDT">BNB/USDT</option>
    </select>
  );
}

// ── Dashboard Overview ────────────────────────────────────────────

function DashboardView({ health, proposals, pnl, pnlPositive, pnlValue, ticker, candles, selectedSymbol, onProposalAction, onMarketRefresh }: {
  health: SystemHealth | null;
  proposals: Proposal[];
  pnl: PnLSummary | null;
  pnlPositive: boolean;
  pnlValue: number;
  ticker: Ticker | null;
  candles: Candle[];
  selectedSymbol: string;
  onProposalAction: () => void;
  onMarketRefresh: () => void;
}) {
  return (
    <>
      {/* Live Market Ticker Bar */}
      <LiveTickerBar ticker={ticker} symbol={selectedSymbol} />

      {/* KPI Cards */}
      <div className="status-grid stagger">
        <div className="status-card animate-fade-in">
          <div className="status-card-header">
            <span className="status-card-label">System</span>
            <span className={`badge ${health?.status === 'healthy' ? 'badge-success' : 'badge-danger'}`}>
              {health?.status || 'checking...'}
            </span>
          </div>
          <div className="status-card-value">v{health?.version || '...'}</div>
          <div className="status-card-sub">{health?.environment || '...'}</div>
        </div>

        <div className="status-card animate-fade-in">
          <div className="status-card-header">
            <span className="status-card-label">Mode</span>
            <span className="badge badge-warning">{health?.trading_mode || 'PAPER'}</span>
          </div>
          <div className="status-card-value">PAPER</div>
          <div className="status-card-sub">No real trades</div>
        </div>

        <div className="status-card animate-fade-in">
          <div className="status-card-header">
            <span className="status-card-label">Active Proposals</span>
            <span className={`badge ${proposals.length > 0 ? 'badge-info' : 'badge-success'}`}>{proposals.length}</span>
          </div>
          <div className="status-card-value">{proposals.length}</div>
          <div className="status-card-sub">Awaiting approval</div>
        </div>

        <div className="status-card animate-fade-in">
          <div className="status-card-header">
            <span className="status-card-label">Total PnL</span>
            <span className={`badge ${pnlPositive ? 'badge-success' : 'badge-danger'}`}>
              {pnlPositive ? '+' : ''}{pnlValue.toFixed(2)}
            </span>
          </div>
          <div className={`status-card-value ${pnlPositive ? 'pnl-positive' : 'pnl-negative'}`}>
            ${pnlValue.toFixed(2)}
          </div>
          <div className="status-card-sub">{pnl?.total_trades || 0} trades · {pnl?.win_rate || 0}% win rate</div>
        </div>
      </div>

      {/* Price Chart */}
      <div className="section-header">
        <h3 className="section-title">📈 {selectedSymbol} Price Chart (15m)</h3>
        <span className="section-badge-muted">{candles.length} candles</span>
      </div>
      <MiniCandleChart candles={candles} />

      {/* Analysis Control Panel */}
      <AnalysisControlPanel
        symbol={selectedSymbol}
        onRefresh={() => { onProposalAction(); onMarketRefresh(); }}
      />

      {/* PnL Chart */}
      <div className="section-header">
        <h3 className="section-title">Performance</h3>
      </div>
      <PnLChart pnl={pnl} />

      {/* Active Proposals */}
      {proposals.length > 0 && (
        <>
          <div className="section-header">
            <h3 className="section-title">🔔 Active Proposals</h3>
            <span className="section-badge">{proposals.length} pending</span>
          </div>
          <div className="proposals-grid">
            {proposals.map((p) => (
              <ProposalCard key={p.id} proposal={p} onAction={onProposalAction} />
            ))}
          </div>
        </>
      )}

      {proposals.length === 0 && (
        <div className="empty-state card animate-slide-up">
          <div className="empty-icon">🤖</div>
          <h3>No Active Proposals</h3>
          <p>Click <strong>"Run Full Analysis"</strong> above to analyze {selectedSymbol} with AI multi-agent system and generate trade proposals.</p>
        </div>
      )}
    </>
  );
}

// ── Live Ticker Bar ───────────────────────────────────────────────

function LiveTickerBar({ ticker, symbol }: { ticker: Ticker | null; symbol: string }) {
  if (!ticker) {
    return (
      <div className="ticker-bar ticker-loading animate-fade-in">
        <div className="ticker-symbol">{symbol}</div>
        <div className="ticker-price-loading">Loading price...</div>
      </div>
    );
  }

  const price = parseFloat(String(ticker.price));
  const bid = parseFloat(String(ticker.bid));
  const ask = parseFloat(String(ticker.ask));
  const spreadBps = parseFloat(String(ticker.spread_bps));
  const vol24h = parseFloat(String(ticker.volume_24h));
  const change24h = parseFloat(String(ticker.price_change_24h));
  const changePct = parseFloat(String(ticker.price_change_pct_24h));
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
        <div className="ticker-detail-item">
          <span className="ticker-detail-label">Bid</span>
          <span className="ticker-detail-value">${bid.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="ticker-detail-item">
          <span className="ticker-detail-label">Ask</span>
          <span className="ticker-detail-value">${ask.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="ticker-detail-item">
          <span className="ticker-detail-label">Spread</span>
          <span className="ticker-detail-value">{spreadBps.toFixed(1)} bps</span>
        </div>
        <div className="ticker-detail-item">
          <span className="ticker-detail-label">Vol 24h</span>
          <span className="ticker-detail-value">{vol24h > 1e6 ? (vol24h / 1e6).toFixed(1) + 'M' : vol24h.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
        </div>
      </div>
    </div>
  );
}

// ── Mini Candle Chart (Canvas-based) ──────────────────────────────

function MiniCandleChart({ candles }: { candles: Candle[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || candles.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width;
    const H = rect.height;

    // Clear
    ctx.clearRect(0, 0, W, H);

    const prices = candles.flatMap(c => [parseFloat(String(c.high)), parseFloat(String(c.low))]);
    const minP = Math.min(...prices);
    const maxP = Math.max(...prices);
    const range = maxP - minP || 1;
    const padding = range * 0.05;
    const pMin = minP - padding;
    const pMax = maxP + padding;

    const barW = Math.max(2, (W - 20) / candles.length - 1);
    const gap = 1;

    const toY = (p: number) => H - 10 - ((p - pMin) / (pMax - pMin)) * (H - 20);

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    for (let i = 0; i < 5; i++) {
      const y = 10 + (i / 4) * (H - 20);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }

    // Price labels
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.font = '10px monospace';
    ctx.textAlign = 'right';
    for (let i = 0; i < 5; i++) {
      const price = pMax - (i / 4) * (pMax - pMin);
      const y = 10 + (i / 4) * (H - 20);
      ctx.fillText('$' + price.toLocaleString(undefined, { maximumFractionDigits: 0 }), W - 4, y - 3);
    }

    // Draw candles
    candles.forEach((c, i) => {
      const x = 10 + i * (barW + gap);
      const cOpen = parseFloat(String(c.open));
      const cClose = parseFloat(String(c.close));
      const cHigh = parseFloat(String(c.high));
      const cLow = parseFloat(String(c.low));
      const oY = toY(cOpen);
      const cY = toY(cClose);
      const hY = toY(cHigh);
      const lY = toY(cLow);
      const bullish = cClose >= cOpen;

      // Wick
      ctx.strokeStyle = bullish ? '#22c55e' : '#ef4444';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x + barW / 2, hY);
      ctx.lineTo(x + barW / 2, lY);
      ctx.stroke();

      // Body
      ctx.fillStyle = bullish ? '#22c55e' : '#ef4444';
      const bodyTop = Math.min(oY, cY);
      const bodyH = Math.max(1, Math.abs(cY - oY));
      ctx.fillRect(x, bodyTop, barW, bodyH);
    });

    // Latest price line
    if (candles.length > 0) {
      const lastClose = parseFloat(String(candles[candles.length - 1].close));
      const ly = toY(lastClose);
      ctx.strokeStyle = '#3b82f6';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, ly);
      ctx.lineTo(W, ly);
      ctx.stroke();
      ctx.setLineDash([]);

      // Price label
      ctx.fillStyle = '#3b82f6';
      ctx.font = 'bold 11px monospace';
      ctx.textAlign = 'left';
      ctx.fillText('$' + lastClose.toLocaleString(undefined, { minimumFractionDigits: 2 }), 10, ly - 6);
    }
  }, [candles]);

  if (candles.length === 0) {
    return (
      <div className="card chart-empty animate-fade-in">
        <div className="empty-icon">📊</div>
        <p>No candle data yet. Click <strong>"Fetch & Analyze"</strong> below to pull market data from Binance.</p>
      </div>
    );
  }

  return (
    <div className="card chart-container animate-fade-in">
      <canvas ref={canvasRef} className="candle-canvas" />
    </div>
  );
}

// ── Multi-Agent Analysis Control Panel ────────────────────────────

function AnalysisControlPanel({ symbol, onRefresh }: { symbol: string; onRefresh: () => void }) {
  const [loading, setLoading] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);
  const [analysisResult, setAnalysisResult] = useState<Record<string, unknown> | null>(null);

  const handleRunFull = async () => {
    setLoading('full');
    setAnalysisResult(null);
    try {
      setStatusMsg({ type: 'info', text: `Step 1/3: Fetching market candles for ${symbol}...` });
      await marketApi.fetchCandles(symbol, '15m', 100);

      setStatusMsg({ type: 'info', text: `Step 2/3: Computing 125 technical indicators...` });
      await featuresApi.compute(symbol);

      setStatusMsg({ type: 'info', text: `Step 3/3: Running 5-Agent AI analysis (this may take 30-60s)...` });
      const { data } = await analysisApi.triggerSync(symbol);
      setAnalysisResult(data);
      setStatusMsg({
        type: 'success',
        text: `✅ Analysis complete! Direction: ${data.final_direction} | Consensus: ${data.consensus_score}`
      });
      onRefresh();
    } catch (e: any) {
      setStatusMsg({ type: 'error', text: `❌ ${e.response?.data?.detail || e.message}` });
    } finally {
      setLoading(null);
    }
  };

  const handleFetchOnly = async () => {
    setLoading('fetch');
    try {
      setStatusMsg({ type: 'info', text: `Fetching candles for ${symbol}...` });
      const { data } = await marketApi.fetchCandles(symbol, '15m', 100);
      setStatusMsg({ type: 'success', text: `✅ Stored ${data.candles_stored} candles for ${symbol}` });
      onRefresh();
    } catch (e: any) {
      setStatusMsg({ type: 'error', text: `❌ ${e.response?.data?.detail || e.message}` });
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="control-panel card animate-fade-in">
      <div className="control-panel-header">
        <div>
          <h3 className="control-panel-title">
            <span className="control-icon">⚡</span>
            AI Multi-Agent Analysis
          </h3>
          <p className="control-panel-desc">
            Fetch live data from Binance → Compute indicators → Run 5 AI agents → Generate trade proposals
          </p>
        </div>
      </div>

      <div className="control-panel-actions">
        <button
          onClick={handleFetchOnly}
          disabled={loading !== null}
          className="btn btn-ghost control-btn"
        >
          {loading === 'fetch' ? (
            <><span className="spinner-sm" /> Fetching...</>
          ) : (
            <>📥 Fetch Market Data</>
          )}
        </button>

        <button
          onClick={handleRunFull}
          disabled={loading !== null}
          className="btn btn-primary control-btn-main"
        >
          {loading === 'full' ? (
            <><span className="spinner-sm" /> Running Pipeline...</>
          ) : (
            <>🚀 Run Full Analysis</>
          )}
        </button>
      </div>

      {statusMsg && (
        <div className={`control-status control-status-${statusMsg.type}`}>
          {loading && <span className="spinner-sm" />}
          {statusMsg.text}
        </div>
      )}

      {analysisResult && (
        <AnalysisResultCard result={analysisResult} />
      )}
    </div>
  );
}

// ── Analysis Result Card ──────────────────────────────────────────

function AnalysisResultCard({ result }: { result: Record<string, unknown> }) {
  const direction = String(result.final_direction || 'HOLD');
  const score = Number(result.consensus_score || 0);
  const proceed = Boolean(result.proceed);
  const agents = result.agent_signals as Record<string, { direction: string; confidence: number; reasoning: string }> | undefined;
  const latency = Number(result.latency_seconds || 0);

  const dirColor = direction === 'BUY' ? '#22c55e' : direction === 'SELL' ? '#ef4444' : '#94a3b8';

  return (
    <div className="analysis-result animate-slide-up">
      <div className="analysis-result-header">
        <div className="analysis-direction" style={{ color: dirColor }}>
          {direction === 'BUY' ? '📈' : direction === 'SELL' ? '📉' : '⏸️'} {direction}
        </div>
        <div className="analysis-meta">
          <span className={`badge ${proceed ? 'badge-success' : 'badge-warning'}`}>
            {proceed ? 'Proceed' : 'No Action'}
          </span>
          <span className="analysis-latency">{latency.toFixed(1)}s</span>
        </div>
      </div>

      <div className="analysis-score-bar">
        <div className="analysis-score-label">Consensus Score</div>
        <div className="analysis-score-track">
          <div className="analysis-score-fill" style={{ width: `${Math.abs(score) * 50 + 50}%`, background: dirColor }} />
        </div>
        <div className="analysis-score-value">{score.toFixed(2)}</div>
      </div>

      {agents && (
        <div className="agent-signals">
          {Object.entries(agents).map(([name, signal]) => (
            <div key={name} className="agent-signal-item">
              <div className="agent-name">{name.replace(/_/g, ' ')}</div>
              <div className={`agent-direction ${signal.direction?.toLowerCase()}`}>
                {signal.direction}
              </div>
              <div className="agent-confidence">
                <div className="agent-conf-bar">
                  <div className="agent-conf-fill" style={{ width: `${(signal.confidence || 0) * 100}%` }} />
                </div>
                <span>{((signal.confidence || 0) * 100).toFixed(0)}%</span>
              </div>
              {signal.reasoning && (
                <div className="agent-reasoning">{signal.reasoning}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Proposals View ────────────────────────────────────────────────

function ProposalsView({ proposals, onAction }: { proposals: Proposal[]; onAction: () => void }) {
  const [filter, setFilter] = useState<string>('active');

  return (
    <>
      <div className="view-filters">
        {['active', 'all'].map((f) => (
          <button key={f} onClick={() => setFilter(f)} className={`filter-btn ${filter === f ? 'active' : ''}`}>
            {f === 'active' ? '🟢 Active' : '📋 All'}
          </button>
        ))}
      </div>
      {proposals.length === 0 ? (
        <div className="empty-state card">
          <div className="empty-icon">📋</div>
          <h3>No Proposals</h3>
          <p>Run an analysis from the Dashboard to generate trade proposals.</p>
        </div>
      ) : (
        <div className="proposals-grid">
          {proposals.map((p) => (
            <ProposalCard key={p.id} proposal={p} onAction={onAction} expanded />
          ))}
        </div>
      )}
    </>
  );
}

// ── Positions View ────────────────────────────────────────────────

function PositionsView({ pnl }: { pnl: PnLSummary | null }) {
  return (
    <>
      <div className="pnl-summary-grid stagger">
        <div className="pnl-card animate-fade-in">
          <div className="pnl-card-label">Total Trades</div>
          <div className="pnl-card-value">{pnl?.total_trades ?? 0}</div>
        </div>
        <div className="pnl-card animate-fade-in">
          <div className="pnl-card-label">Win Rate</div>
          <div className="pnl-card-value">{pnl?.win_rate ?? 0}%</div>
        </div>
        <div className="pnl-card animate-fade-in">
          <div className="pnl-card-label">Net PnL</div>
          <div className={`pnl-card-value ${parseFloat(pnl?.total_net_pnl || '0') >= 0 ? 'pnl-positive' : 'pnl-negative'}`}>
            ${parseFloat(pnl?.total_net_pnl || '0').toFixed(2)}
          </div>
        </div>
        <div className="pnl-card animate-fade-in">
          <div className="pnl-card-label">Fees Paid</div>
          <div className="pnl-card-value">${parseFloat(pnl?.total_fees_paid || '0').toFixed(2)}</div>
        </div>
      </div>
      <div className="empty-state card animate-slide-up" style={{ marginTop: '24px' }}>
        <div className="empty-icon">📊</div>
        <h3>Paper Trading Active</h3>
        <p>Open positions will appear here once proposals are approved and executed.</p>
      </div>
    </>
  );
}
