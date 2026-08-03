/**
 * DataCoverage — Widget hiển thị thống kê số lượng nến lưu trong DB
 *
 * Hiển thị cho mỗi timeframe:
 * - Số lượng nến đã lưu
 * - Khoảng thời gian phủ (coverage days)
 * - Progress bar sufficiency (đỏ/vàng/xanh)
 * - Trạng thái đủ/không đủ cho indicators
 *
 * Action:
 * - Nút "Deep Backfill" để tải thêm lịch sử nến
 */
import { useEffect, useState, useCallback } from 'react';
import { marketApi } from '../../services/api';
import './DataCoverage.css';

interface TfStats {
  count: number;
  oldest: string | null;
  newest: string | null;
  coverage_days: number | null;
  is_sufficient: boolean;
  min_required: number;
  sufficiency_pct: number;
}

interface Props {
  symbol: string;
  onBackfillComplete?: () => void;
}

export default function DataCoverage({ symbol, onBackfillComplete }: Props) {
  const [stats, setStats] = useState<Record<string, TfStats> | null>(null);
  const [loading, setLoading] = useState(true);
  const [backfilling, setBackfilling] = useState(false);
  const [backfillMsg, setBackfillMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadStats = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await marketApi.getCandleStats(symbol);
      setStats(data.timeframes);
    } catch { /* silent */ } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => { loadStats(); }, [loadStats]);

  const handleDeepBackfill = async () => {
    setBackfilling(true);
    setBackfillMsg(null);
    try {
      const { data } = await marketApi.deepBackfill(symbol);
      const results = (data as { results?: Record<string, { candles_stored?: number }> }).results || {};
      const total = Object.values(results).reduce((s, r) => s + (r.candles_stored ?? 0), 0);
      setBackfillMsg({ type: 'success', text: `✅ Deep backfill complete: ${total.toLocaleString()} candles stored` });
      await loadStats();
      onBackfillComplete?.();
    } catch (e: unknown) {
      const err = e as { code?: string; message?: string; response?: { data?: { error?: { message?: string } } } };
      // Timeout: backfill may still be running in background
      if (err?.code === 'ECONNABORTED' || err?.message?.includes('timeout') || err?.message?.includes('Network Error')) {
        setBackfillMsg({
          type: 'success',
          text: '⏳ Deep backfill started — loading data in background (check back in 2-3 minutes)',
        });
        // Poll stats after delay
        setTimeout(async () => { await loadStats(); onBackfillComplete?.(); }, 15000);
      } else {
        setBackfillMsg({
          type: 'error',
          text: `❌ ${err?.response?.data?.error?.message || err?.message || 'Backfill failed'}`,
        });
      }
    } finally {
      setBackfilling(false);
    }

  };

  const TIMEFRAMES = ['15m', '1h', '4h'];
  const TF_LABELS: Record<string, string> = { '15m': '15 min', '1h': '1 hour', '4h': '4 hour' };

  return (
    <div className="dc-wrapper">
      <div className="dc-header">
        <span className="dc-title">📊 Candle Data Coverage</span>
        <button
          id="btn-deep-backfill"
          className={`dc-backfill-btn ${backfilling ? 'loading' : ''}`}
          onClick={handleDeepBackfill}
          disabled={backfilling}
        >
          {backfilling ? '⟳ Backfilling…' : '⬇ Deep Backfill'}
        </button>
      </div>

      {backfillMsg && (
        <div className={`dc-msg dc-msg-${backfillMsg.type}`}>{backfillMsg.text}</div>
      )}

      {loading ? (
        <div className="dc-loading"><div className="dc-spinner" /><span>Loading stats…</span></div>
      ) : (
        <div className="dc-grid">
          {TIMEFRAMES.map(tf => {
            const s = stats?.[tf];
            if (!s) return (
              <div key={tf} className="dc-card dc-card-empty">
                <div className="dc-tf-label">{TF_LABELS[tf]}</div>
                <div className="dc-count">—</div>
                <div className="dc-status dc-status-warning">⚠ No data</div>
              </div>
            );

            const pct = s.sufficiency_pct;
            const statusClass = pct >= 100 ? 'ok' : pct >= 50 ? 'warning' : 'danger';

            return (
              <div key={tf} className={`dc-card dc-card-${statusClass}`}>
                <div className="dc-tf-label">{TF_LABELS[tf]}</div>
                <div className="dc-count">{s.count.toLocaleString()}</div>
                <div className="dc-subtitle">
                  {s.coverage_days != null ? `${s.coverage_days}d coverage` : 'No data'}
                  {s.oldest && ` · ${new Date(s.oldest).toLocaleDateString()}`}
                </div>

                {/* Progress bar */}
                <div className="dc-progress-track">
                  <div
                    className={`dc-progress-fill dc-progress-${statusClass}`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  />
                </div>
                <div className="dc-progress-label">
                  <span className={`dc-status-dot dc-dot-${statusClass}`} />
                  {pct >= 100
                    ? `✅ Sufficient (${s.count}/${s.min_required}+)`
                    : `⚠ ${pct}% (${s.count}/${s.min_required} needed)`}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
