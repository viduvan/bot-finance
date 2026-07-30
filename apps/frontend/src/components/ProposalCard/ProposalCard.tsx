import { useState, useEffect } from 'react';
import { proposalsApi, executionApi, marketApi, systemApi, type Proposal } from '../../services/api';
import { useT } from '../../i18n/I18nContext';
import './ProposalCard.css';

interface Props {
  proposal: Proposal;
  onAction: () => void;
  expanded?: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  PENDING_REVIEW: 'info',
  RECONFIRM_REQUIRED: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
  EXPIRED: 'muted',
  CANCELLED: 'muted',
  EXECUTED: 'success',
};

const REC_COLORS: Record<string, string> = {
  BUY: 'buy',
  SELL: 'sell',
  HOLD: 'hold',
};

export default function ProposalCard({ proposal, onAction, expanded = false }: Props) {
  const { t } = useT();
  const [loading, setLoading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [tokenCountdown, setTokenCountdown] = useState<number | null>(null);
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [currentPriceInput, setCurrentPriceInput] = useState(proposal.suggested_price || '');
  const [expirationSeconds, setExpirationSeconds] = useState(600);

  // Load system config to get actual proposal expiration time
  useEffect(() => {
    systemApi.config().then(r => {
      const s = r.data.proposal?.expiration_seconds;
      if (s && typeof s === 'number' && s > 0) setExpirationSeconds(s);
    }).catch(() => {/* use default 600s */});
  }, []);

  // Auto-fill current market price from ticker when proposal is active
  useEffect(() => {
    if (!proposal.suggested_price) {
      marketApi.ticker(proposal.symbol)
        .then(r => { if (r.data?.price) setCurrentPriceInput(String(r.data.price)); })
        .catch(() => {/* keep empty */});
    }
  }, [proposal.symbol, proposal.suggested_price]);

  const statusColor = STATUS_COLORS[proposal.status] || 'muted';
  const recColor = REC_COLORS[proposal.recommendation] || 'hold';

  const timeLeft = proposal.seconds_until_expiry;
  const expiryPercent = Math.max(0, Math.min(100, (timeLeft / expirationSeconds) * 100));
  const expiryUrgent = timeLeft < 120;

  async function handleReject() {
    setLoading(true);
    setError('');
    try {
      await proposalsApi.reject(proposal.id, 'Rejected by user');
      onAction();
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Reject failed');
    } finally {
      setLoading(false);
    }
  }

  async function startApprove() {
    setLoading(true);
    setError('');
    try {
      const { data } = await proposalsApi.issueToken(proposal.id);
      setPendingToken(data.token);
      setApproving(true);
      setTokenCountdown(data.expires_in_seconds);

      // Countdown timer
      const interval = setInterval(() => {
        setTokenCountdown((prev) => {
          if (prev === null || prev <= 1) {
            clearInterval(interval);
            setPendingToken(null);
            setApproving(false);
            return null;
          }
          return prev - 1;
        });
      }, 1000);
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to issue token');
    } finally {
      setLoading(false);
    }
  }

  async function confirmApprove() {
    if (!pendingToken) return;
    setLoading(true);
    setError('');
    try {
      const res = await proposalsApi.approve(proposal.id, pendingToken, currentPriceInput);
      const status = (res.data as { status?: string })?.status;

      if (status === 'RECONFIRM_REQUIRED') {
        setError((res.data as { reason?: string })?.reason || 'Price drift — please re-confirm');
        setApproving(false);
        setPendingToken(null);
      } else if (status === 'APPROVED') {
        // Auto-execute paper trade
        try {
          await executionApi.execute(proposal.id, currentPriceInput);
        } catch { /* execute separately if needed */ }
        onAction();
      }
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Approval failed');
    } finally {
      setLoading(false);
    }
  }

  function cancelApprove() {
    setPendingToken(null);
    setApproving(false);
    setTokenCountdown(null);
  }

  const rr = parseFloat(proposal.risk_reward_ratio || '0');
  const confidence = Math.round(parseFloat(proposal.confidence || '0') * 100);
  const consensusScore = (proposal.agent_consensus as { consensus_score?: number })?.consensus_score;

  return (
    <div className={`proposal-card card ${approving ? 'approving' : ''}`}>
      {/* Header */}
      <div className="proposal-header">
        <div className="proposal-symbol">
          <span className="symbol-text">{proposal.symbol}</span>
          <span className={`rec-badge ${recColor}`}>{proposal.recommendation}</span>
        </div>
        <div className="proposal-meta">
          <span className={`badge badge-${statusColor}`}>{proposal.status.replace('_', ' ')}</span>
          <span className="proposal-env">{proposal.environment}</span>
        </div>
      </div>

      {/* Expiry Progress */}
      <div className="expiry-bar">
        <div
          className={`expiry-fill ${expiryUrgent ? 'urgent' : ''}`}
          style={{ width: `${expiryPercent}%` }}
        />
      </div>
      <div className="expiry-text">
        {timeLeft > 0 ? `${t('prop.expires')}: ${Math.floor(timeLeft / 60)}m ${timeLeft % 60}s` : '— Expired —'}
      </div>

      {/* Price Grid */}
      <div className="proposal-prices">
        <div className="price-item">
          <div className="price-label">{t('prop.entry')}</div>
          <div className="price-value">{proposal.suggested_price ? `$${parseFloat(proposal.suggested_price).toLocaleString()}` : '—'}</div>
        </div>
        <div className="price-item danger">
          <div className="price-label">{t('prop.stop_loss')}</div>
          <div className="price-value">{proposal.stop_loss_price ? `$${parseFloat(proposal.stop_loss_price).toLocaleString()}` : '—'}</div>
        </div>
        <div className="price-item success">
          <div className="price-label">{t('prop.take_profit')}</div>
          <div className="price-value">
            {proposal.take_profit_prices?.tp1 ? `$${parseFloat(proposal.take_profit_prices.tp1).toLocaleString()}` : '—'}
          </div>
        </div>
        <div className="price-item info">
          <div className="price-label">{t('prop.risk_reward')}</div>
          <div className="price-value">{rr > 0 ? `${rr.toFixed(2)}x` : '—'}</div>
        </div>
      </div>

      {/* Agent Consensus */}
      {expanded && proposal.agent_consensus && (
        <div className="consensus-section">
          <div className="consensus-header">Agent Consensus</div>
          <div className="consensus-grid">
            {Object.entries(proposal.agent_consensus as Record<string, string>).map(([k, v]) => (
              <div key={k} className="consensus-item">
                <div className="consensus-key">{k.replace(/_/g, ' ')}</div>
                <div className={`consensus-val ${typeof v === 'string' && (v.includes('BUY') || v.includes('BULL') || v === 'true') ? 'positive' : typeof v === 'string' && (v.includes('SELL') || v.includes('BEAR') || v === 'false') ? 'negative' : ''}`}>
                  {String(v)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Confidence + Score */}
      <div className="proposal-stats">
        <div className="stat-item">
          <div className="stat-label">{t('prop.confidence')}</div>
          <div className="stat-bar-wrap">
            <div className="stat-bar">
              <div className="stat-bar-fill" style={{ width: `${confidence}%` }} />
            </div>
            <span className="stat-val">{confidence}%</span>
          </div>
        </div>
        {consensusScore !== undefined && (
          <div className="stat-item">
            <div className="stat-label">{t('ana.consensus')}</div>
            <div className="stat-score">{(consensusScore as number).toFixed(1)}</div>
          </div>
        )}
      </div>

      {/* Warnings */}
      {proposal.risk_warnings.length > 0 && (
        <div className="warnings">
          {proposal.risk_warnings.slice(0, 2).map((w, i) => (
            <div key={i} className="warning-item">⚠️ {w}</div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && <div className="proposal-error">{error}</div>}

      {/* Approval Flow */}
      {proposal.status === 'PENDING_REVIEW' && !approving && (
        <div className="proposal-actions">
          <button className="btn btn-success btn-sm" onClick={startApprove} disabled={loading}>
            {loading ? <span className="spinner" /> : `✅ ${t('prop.approve')}`}
          </button>
          <button className="btn btn-danger btn-sm" onClick={handleReject} disabled={loading}>
            {loading ? <span className="spinner" /> : `❌ ${t('prop.reject')}`}
          </button>
        </div>
      )}

      {/* Token Confirmation Step */}
      {approving && pendingToken && (
        <div className="confirm-panel animate-scale-in">
          <div className="confirm-header">
            <span>{t('appr.confirm_title')}</span>
            <span className={`token-timer ${tokenCountdown && tokenCountdown < 10 ? 'urgent' : ''}`}>
              {tokenCountdown}s
            </span>
          </div>
          <div className="confirm-price-input">
            <label className="input-label">{t('appr.price_label')}</label>
            <input
              className="input"
              type="text"
              value={currentPriceInput}
              onChange={(e) => setCurrentPriceInput(e.target.value)}
              placeholder="e.g. 50000"
            />
          </div>
          <div className="confirm-warning">
            {t('appr.paper_warn')} <strong>{tokenCountdown}s</strong>.
          </div>
          <div className="proposal-actions">
            <button className="btn btn-primary btn-sm" onClick={confirmApprove} disabled={loading}>
              {loading ? <span className="spinner" /> : t('appr.confirm_exec')}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={cancelApprove} disabled={loading}>
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}

      {proposal.status === 'RECONFIRM_REQUIRED' && !approving && (
        <div className="proposal-actions">
          <div className="reconfirm-notice">{t('appr.reconfirm_notice')}</div>
          <button className="btn btn-warning btn-sm" onClick={startApprove} disabled={loading}>
            {t('appr.reconfirm_btn')}
          </button>
          <button className="btn btn-danger btn-sm" onClick={handleReject} disabled={loading}>
            ❌ {t('prop.reject')}
          </button>
        </div>
      )}
    </div>
  );
}
