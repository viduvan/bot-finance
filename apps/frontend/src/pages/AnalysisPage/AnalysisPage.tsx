import { useEffect, useState, useCallback } from 'react';
import { analysisApi, featuresApi, strategyApi, type AnalysisWorkflow, type StrategySignal } from '../../services/api';
import DataCoverage from '../../components/DataCoverage/DataCoverage';
import './AnalysisPage.css';

interface Props { symbol: string; }

export default function AnalysisPage({ symbol }: Props) {
  const [workflows, setWorkflows] = useState<AnalysisWorkflow[]>([]);
  const [features, setFeatures] = useState<Record<string, unknown> | null>(null);
  const [signal, setSignal] = useState<StrategySignal | null>(null);
  const [strategies, setStrategies] = useState<string[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState('ema_pullback');
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'history' | 'indicators' | 'strategy'>('history');

  const loadAll = useCallback(async () => {
    setLoading(true);
    const [h, f, s, sl] = await Promise.allSettled([
      analysisApi.history(symbol, 20),
      featuresApi.getLatest(symbol),
      strategyApi.signal(symbol, selectedStrategy),
      strategyApi.list(),
    ]);
    if (h.status === 'fulfilled') setWorkflows(h.value.data.workflows || []);
    if (f.status === 'fulfilled' && !f.value.data.message) setFeatures(f.value.data);
    if (s.status === 'fulfilled') setSignal(s.value.data);
    if (sl.status === 'fulfilled') setStrategies(sl.value.data.strategies || []);
    setLoading(false);
  }, [symbol, selectedStrategy]);

  useEffect(() => { loadAll(); }, [loadAll]);

  if (loading) return <div className="page-loading"><div className="loading-spinner" /><p>Loading analysis data...</p></div>;

  return (
    <div className="page-container stagger">
      {/* Data Sufficiency Banner */}
      {features && (features as Record<string, unknown>).data_sufficient === false && (
        <div className="card animate-fade-in" style={{
          background: 'rgba(234,179,8,0.08)',
          border: '1px solid rgba(234,179,8,0.25)',
          padding: '10px 16px',
        }}>
          <strong style={{ color: '#facc15' }}>⚠ Insufficient candle data</strong>
          <span style={{ color: 'rgba(200,200,210,0.7)', fontSize: '0.82rem', marginLeft: 8 }}>
            {String((features as Record<string, unknown>).data_warning || '')}
            {' '}<strong>Run Deep Backfill on Market page to improve accuracy.</strong>
          </span>
        </div>
      )}
      {features && (features as Record<string, unknown>).data_sufficient === true && (
        <div style={{ fontSize: '0.76rem', color: '#4ade80', padding: '4px 0 4px 4px' }}>
          ✅ {(features as Record<string, unknown>).candle_count_15m as number} candles — sufficient for all indicators
        </div>
      )}

      <div className="analysis-tabs">
        {(['history', 'indicators', 'strategy'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`filter-btn ${tab === t ? 'active' : ''}`}>
            {t === 'history' ? '📜 History' : t === 'indicators' ? '📊 Indicators' : '🎯 Strategy Signal'}
          </button>
        ))}
      </div>

      {tab === 'history' && <HistoryTab workflows={workflows} />}
      {tab === 'indicators' && <IndicatorsTab features={features} />}
      {tab === 'strategy' && (
        <StrategyTab
          signal={signal}
          strategies={strategies}
          selected={selectedStrategy}
          onStrategyChange={(s) => { setSelectedStrategy(s); }}
        />
      )}

      {/* Data Coverage at bottom */}
      <DataCoverage symbol={symbol} />
    </div>
  );
}

function HistoryTab({ workflows }: { workflows: AnalysisWorkflow[] }) {
  if (workflows.length === 0) {
    return <div className="empty-state card"><div className="empty-icon">📜</div><h3>No Analysis History</h3><p>Run an analysis from the Dashboard to see history here.</p></div>;
  }
  return (
    <div className="card animate-fade-in">
      <h4 className="card-title">Analysis Workflow History</h4>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Trigger</th>
              <th>Started</th>
              <th>Latency</th>
              <th>Tokens (In/Out)</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {workflows.map(w => (
              <tr key={w.id}>
                <td><span className={`badge badge-${w.status === 'COMPLETED' ? 'success' : w.status === 'FAILED' ? 'danger' : 'warning'}`}>{w.status}</span></td>
                <td>{w.trigger_type}</td>
                <td className="mono">{w.started_at ? new Date(w.started_at).toLocaleString() : '—'}</td>
                <td className="mono">{w.total_latency_ms ? `${(w.total_latency_ms / 1000).toFixed(1)}s` : '—'}</td>
                <td className="mono">{w.total_input_tokens ?? '—'} / {w.total_output_tokens ?? '—'}</td>
                <td className="text-danger truncate">{w.error_message || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function IndicatorsTab({ features }: { features: Record<string, unknown> | null }) {
  if (!features || Object.keys(features).length === 0) {
    return <div className="empty-state card"><div className="empty-icon">📊</div><h3>No Indicators</h3><p>Compute features first using "Fetch & Analyze" on the Dashboard.</p></div>;
  }

  const categories: Record<string, [string, unknown][]> = {};
  Object.entries(features).forEach(([k, v]) => {
    let cat = 'Other';
    if (k.startsWith('ema_') || k.startsWith('sma_')) cat = 'Moving Averages';
    else if (k.startsWith('rsi') || k.startsWith('stoch') || k.includes('macd')) cat = 'Oscillators';
    else if (k.startsWith('bb_') || k.startsWith('kc_')) cat = 'Bands';
    else if (k.startsWith('atr') || k.includes('volatility') || k.includes('stddev')) cat = 'Volatility';
    else if (k.includes('volume') || k.includes('obv') || k.includes('mfi') || k.includes('vwap')) cat = 'Volume';
    else if (k.startsWith('ob_') || k.includes('depth') || k.includes('bid') || k.includes('ask')) cat = 'Order Book';
    else if (k.startsWith('tf1h_') || k.startsWith('tf4h_')) cat = 'Higher Timeframes';
    else if (k.includes('trend') || k.includes('adx') || k.includes('cci')) cat = 'Trend';
    else if (k === 'open' || k === 'high' || k === 'low' || k === 'close') cat = 'Price';
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push([k, v]);
  });

  return (
    <div className="indicators-grid animate-fade-in">
      {Object.entries(categories).map(([cat, items]) => (
        <div key={cat} className="card indicator-card">
          <h4 className="card-title">{cat} <span className="badge badge-info">{items.length}</span></h4>
          <div className="indicator-list">
            {items.map(([k, v]) => (
              <div key={k} className="indicator-row">
                <span className="indicator-name">{k}</span>
                <span className="indicator-value">{formatIndicatorValue(v)}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function StrategyTab({ signal, strategies, selected, onStrategyChange }: {
  signal: StrategySignal | null; strategies: string[]; selected: string; onStrategyChange: (s: string) => void;
}) {
  return (
    <div className="card animate-fade-in">
      <div className="strategy-header">
        <h4 className="card-title">🎯 Strategy Signal</h4>
        <select value={selected} onChange={(e) => onStrategyChange(e.target.value)} className="symbol-select">
          {strategies.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
        </select>
      </div>

      {signal ? (
        <div className="strategy-content">
          <div className="strategy-signal-main">
            <div className={`strategy-direction ${signal.signal.toLowerCase()}`}>
              {signal.signal === 'LONG' ? '📈' : signal.signal === 'SHORT' ? '📉' : '⏸️'} {signal.signal}
            </div>
            <div className="strategy-stats">
              <div className="strategy-stat">
                <span className="strategy-stat-label">Score</span>
                <span className="strategy-stat-value">{signal.score}</span>
              </div>
              <div className="strategy-stat">
                <span className="strategy-stat-label">Confidence</span>
                <span className="strategy-stat-value">{(signal.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>

          {(signal.entry_zone_low || signal.stop_loss_hint || signal.take_profit_hint) && (
            <div className="strategy-levels">
              {signal.entry_zone_low && <LevelRow label="Entry Low" value={signal.entry_zone_low} color="#3b82f6" />}
              {signal.entry_zone_high && <LevelRow label="Entry High" value={signal.entry_zone_high} color="#3b82f6" />}
              {signal.stop_loss_hint && <LevelRow label="Stop Loss" value={signal.stop_loss_hint} color="#ef4444" />}
              {signal.take_profit_hint && <LevelRow label="Take Profit" value={signal.take_profit_hint} color="#22c55e" />}
            </div>
          )}

          {signal.reasons.length > 0 && (
            <div className="strategy-reasons">
              <h5>Reasons</h5>
              {signal.reasons.map((r, i) => <div key={i} className="reason-item">• {r}</div>)}
            </div>
          )}
        </div>
      ) : <p className="text-muted">No signal data. Compute features first.</p>}
    </div>
  );
}

function LevelRow({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="level-row">
      <span className="level-dot" style={{ background: color }} />
      <span className="level-label">{label}</span>
      <span className="level-value">${parseFloat(value).toLocaleString()}</span>
    </div>
  );
}

function formatIndicatorValue(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') return v.toFixed(v > 1000 ? 2 : v > 1 ? 4 : 6);
  if (typeof v === 'boolean') return v ? '✅' : '❌';
  return String(v);
}
