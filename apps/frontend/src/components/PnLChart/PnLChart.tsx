import type { PnLSummary } from '../../services/api';
import './PnLChart.css';

interface Props {
  pnl: PnLSummary | null;
}

export default function PnLChart({ pnl }: Props) {
  const totalTrades = pnl?.total_trades ?? 0;
  const winning = pnl?.winning_trades ?? 0;
  const losing = pnl?.losing_trades ?? 0;
  const winRate = pnl?.win_rate ?? 0;
  const netPnl = parseFloat(pnl?.total_net_pnl || '0');
  const fees = parseFloat(pnl?.total_fees_paid || '0');
  const pnlPositive = netPnl >= 0;

  if (totalTrades === 0) {
    return (
      <div className="pnl-chart-empty card">
        <div className="pnl-empty-icon">📈</div>
        <p>No completed trades yet — performance chart will appear here.</p>
      </div>
    );
  }

  const winPct = totalTrades > 0 ? (winning / totalTrades) * 100 : 0;
  const losePct = 100 - winPct;

  return (
    <div className="pnl-chart-card card animate-fade-in">
      <div className="pnl-chart-header">
        <h4 className="pnl-chart-title">Performance Summary</h4>
        <span className={`pnl-total ${pnlPositive ? 'positive' : 'negative'}`}>
          {pnlPositive ? '+' : ''}${netPnl.toFixed(2)}
        </span>
      </div>

      {/* Win/Loss bar */}
      <div className="win-loss-section">
        <div className="win-loss-labels">
          <span className="win-label">🟢 Won {winning}</span>
          <span className="win-rate-center">{winRate.toFixed(1)}% Win Rate</span>
          <span className="lose-label">🔴 Lost {losing}</span>
        </div>
        <div className="win-loss-bar">
          <div className="win-bar-fill" style={{ width: `${winPct}%` }} />
          <div className="lose-bar-fill" style={{ width: `${losePct}%` }} />
        </div>
      </div>

      {/* Stats row */}
      <div className="pnl-stats-row">
        <div className="pnl-stat">
          <div className="pnl-stat-label">Total Trades</div>
          <div className="pnl-stat-value">{totalTrades}</div>
        </div>
        <div className="pnl-stat">
          <div className="pnl-stat-label">Net PnL</div>
          <div className={`pnl-stat-value ${pnlPositive ? 'positive' : 'negative'}`}>
            ${netPnl.toFixed(2)}
          </div>
        </div>
        <div className="pnl-stat">
          <div className="pnl-stat-label">Gross PnL</div>
          <div className="pnl-stat-value">${parseFloat(pnl?.total_gross_pnl || '0').toFixed(2)}</div>
        </div>
        <div className="pnl-stat">
          <div className="pnl-stat-label">Fees Paid</div>
          <div className="pnl-stat-value negative">${fees.toFixed(2)}</div>
        </div>
        <div className="pnl-stat">
          <div className="pnl-stat-label">Win Rate</div>
          <div className={`pnl-stat-value ${winRate >= 50 ? 'positive' : 'negative'}`}>
            {winRate.toFixed(1)}%
          </div>
        </div>
      </div>
    </div>
  );
}
