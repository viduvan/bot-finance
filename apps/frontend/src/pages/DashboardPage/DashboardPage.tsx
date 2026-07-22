import { useEffect, useState, useCallback } from 'react';
import { useAuthStore } from '../../stores/authStore';
import { systemApi, proposalsApi, executionApi, createEventsWebSocket, type SystemHealth, type Proposal, type PnLSummary } from '../../services/api';
import ProposalCard from '../../components/ProposalCard/ProposalCard';
import PnLChart from '../../components/PnLChart/PnLChart';
import './DashboardPage.css';

export default function DashboardPage() {
  const { logout } = useAuthStore();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [pnl, setPnl] = useState<PnLSummary | null>(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [wsConnected, setWsConnected] = useState(false);
  const [activePage, setActivePage] = useState<'dashboard' | 'proposals' | 'positions'>('dashboard');

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

  useEffect(() => {
    loadData();
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    const refreshTimer = setInterval(loadData, 30_000);

    // WebSocket: real-time events
    const ws = createEventsWebSocket((event) => {
      const type = event.type as string;
      if (type === 'connected') setWsConnected(true);
      if (type === 'proposal_update') loadData(); // Refresh on any proposal change
      if (type === 'order_filled') loadData();
    });
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);

    return () => {
      clearInterval(timer);
      clearInterval(refreshTimer);
      ws.close();
    };
  }, [loadData]);

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
            <div className="topbar-status">
              <span className={`status-dot ${health?.status === 'healthy' ? 'online' : 'offline'}`} />
              <span>{health?.trading_mode || '...'}</span>
            </div>
            <div className="topbar-time">{currentTime.toLocaleTimeString()}</div>
          </div>
        </header>

        <div className="dashboard-content page-container">
          {activePage === 'dashboard' && (
            <DashboardView
              health={health}
              proposals={proposals}
              pnl={pnl}
              pnlPositive={pnlPositive}
              pnlValue={pnlValue}
              onProposalAction={loadData}
            />
          )}
          {activePage === 'proposals' && (
            <ProposalsView proposals={proposals} onAction={loadData} />
          )}
          {activePage === 'positions' && (
            <PositionsView pnl={pnl} />
          )}
        </div>
      </main>
    </div>
  );
}

// ── Dashboard Overview ────────────────────────────────────────────

function DashboardView({ health, proposals, pnl, pnlPositive, pnlValue, onProposalAction }: {
  health: SystemHealth | null;
  proposals: Proposal[];
  pnl: PnLSummary | null;
  pnlPositive: boolean;
  pnlValue: number;
  onProposalAction: () => void;
}) {
  return (
    <>
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
          <p>The multi-agent system is monitoring markets and will propose trades when conditions align.</p>
          <div className="phase-progress">
            {['Foundation', 'Market Data', 'Features', 'Risk Engine', 'Multi-Agent', 'Proposals', 'Paper Trading', 'Dashboard'].map((phase, i) => (
              <div key={phase} className="phase-item done">
                <span className="phase-icon">✅</span>
                <span>Phase {i}: {phase}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
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
          <p>No active trade proposals at this time.</p>
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
