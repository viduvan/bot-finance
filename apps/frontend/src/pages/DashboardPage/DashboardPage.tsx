import { useEffect, useState } from 'react';
import { useAuthStore } from '../../stores/authStore';
import { systemApi, type SystemHealth } from '../../services/api';
import './DashboardPage.css';

export default function DashboardPage() {
  const { logout } = useAuthStore();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    systemApi.health().then(({ data }) => setHealth(data)).catch(() => { });
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

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
          <a href="#" className="sidebar-link active">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="11" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="1" y="11" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="11" y="11" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/></svg>
            Dashboard
          </a>
          <a href="#" className="sidebar-link">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2 14L6 6L10 10L16 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Market
          </a>
          <a href="#" className="sidebar-link">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M4 9H14M9 4V14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><rect x="1" y="1" width="16" height="16" rx="3" stroke="currentColor" strokeWidth="1.5"/></svg>
            Proposals
          </a>
          <a href="#" className="sidebar-link">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2 14L6 8L10 11L16 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M12 4H16V8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Analytics
          </a>
          <a href="#" className="sidebar-link">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="3" stroke="currentColor" strokeWidth="1.5"/><path d="M9 1V3M9 15V17M1 9H3M15 9H17M3.3 3.3L4.7 4.7M13.3 13.3L14.7 14.7M3.3 14.7L4.7 13.3M13.3 4.7L14.7 3.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            Settings
          </a>
        </nav>

        <div className="sidebar-footer">
          <button onClick={logout} className="btn btn-ghost sidebar-logout">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M6 14H3a1 1 0 01-1-1V3a1 1 0 011-1h3M11 11l3-3-3-3M14 8H6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="dashboard-main">
        {/* Top Bar */}
        <header className="dashboard-topbar">
          <div className="topbar-left">
            <h2>Dashboard</h2>
          </div>
          <div className="topbar-right">
            <div className="topbar-status">
              <span className={`status-dot ${health?.status === 'healthy' ? 'online' : 'offline'}`} />
              <span>{health?.trading_mode || '...'}</span>
            </div>
            <div className="topbar-time">{currentTime.toLocaleTimeString()}</div>
          </div>
        </header>

        {/* Content Area */}
        <div className="dashboard-content page-container">
          {/* Status Cards */}
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
                <span className="status-card-label">Trading Mode</span>
                <span className="badge badge-warning">{health?.trading_mode || '...'}</span>
              </div>
              <div className="status-card-value">PAPER</div>
              <div className="status-card-sub">No real trades</div>
            </div>

            <div className="status-card animate-fade-in">
              <div className="status-card-header">
                <span className="status-card-label">Active Proposals</span>
                <span className="badge badge-info">0</span>
              </div>
              <div className="status-card-value">0</div>
              <div className="status-card-sub">Awaiting approval</div>
            </div>

            <div className="status-card animate-fade-in">
              <div className="status-card-header">
                <span className="status-card-label">Daily PnL</span>
                <span className="badge badge-success">$0.00</span>
              </div>
              <div className="status-card-value pnl-positive">$0.00</div>
              <div className="status-card-sub">0 trades today</div>
            </div>
          </div>

          {/* Welcome Message */}
          <div className="welcome-card card animate-slide-up">
            <div className="welcome-icon">🚀</div>
            <h3>Welcome to ACTA</h3>
            <p>Your trading advisory system is ready. Phase 0 foundation is complete.</p>
            <div className="welcome-steps">
              <div className="welcome-step done">
                <span className="welcome-step-icon">✅</span>
                <span>Backend API running</span>
              </div>
              <div className="welcome-step done">
                <span className="welcome-step-icon">✅</span>
                <span>Authentication configured</span>
              </div>
              <div className="welcome-step pending">
                <span className="welcome-step-icon">⏳</span>
                <span>Connect Binance API keys</span>
              </div>
              <div className="welcome-step pending">
                <span className="welcome-step-icon">⏳</span>
                <span>Configure Ollama LLM</span>
              </div>
              <div className="welcome-step pending">
                <span className="welcome-step-icon">⏳</span>
                <span>Run first analysis</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
