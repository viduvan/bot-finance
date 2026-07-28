import { useEffect, useState, useCallback, useRef, Component, ReactNode } from 'react';
import { marketApi, type Ticker, type Candle, type OrderBookData, type SymbolInfo } from '../../services/api';
import './MarketPage.css';

interface Props { symbol: string; }

// ── Error Boundary ────────────────────────────────────────────────

interface EBState { hasError: boolean; error?: string; }
class ErrorBoundary extends Component<{ children: ReactNode; label?: string }, EBState> {
  constructor(props: { children: ReactNode; label?: string }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error): EBState {
    return { hasError: true, error: error.message };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="error-panel">
          <span className="error-icon">⚠️</span>
          <div>
            <strong>{this.props.label || 'Component'} error</strong>
            <p className="error-detail">{this.state.error}</p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function MarketPage({ symbol }: Props) {
  const [ticker, setTicker] = useState<Ticker | null>(null);
  const [orderbook, setOrderbook] = useState<OrderBookData | null>(null);
  const [exchangeInfo, setExchangeInfo] = useState<Record<string, unknown> | null>(null);
  const [quality, setQuality] = useState<Record<string, unknown> | null>(null);
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<{ type: string; text: string } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const loadAll = useCallback(async () => {
    setLoading(true);
    const newErrors: Record<string, string> = {};

    const [t, ob, ei, q, s] = await Promise.allSettled([
      marketApi.ticker(symbol),
      marketApi.orderbook(symbol, 20),
      marketApi.exchangeInfo(symbol),
      marketApi.quality(symbol),
      marketApi.snapshot(symbol),
    ]);

    if (t.status === 'fulfilled') setTicker(t.value.data);
    else newErrors.ticker = (t.reason as any)?.response?.data?.error?.message || 'Ticker unavailable';

    if (ob.status === 'fulfilled') {
      const data = ob.value.data;
      // Normalize: price & quantity may be strings from API — convert to numbers
      setOrderbook({
        ...data,
        bids: (data.bids || []).map(b => ({ price: parseFloat(String(b.price)), quantity: parseFloat(String(b.quantity)) })),
        asks: (data.asks || []).map(a => ({ price: parseFloat(String(a.price)), quantity: parseFloat(String(a.quantity)) })),
      });
    } else newErrors.orderbook = (ob.reason as any)?.response?.data?.error?.message || 'OrderBook unavailable';

    if (ei.status === 'fulfilled') setExchangeInfo(ei.value.data as unknown as Record<string, unknown>);
    else newErrors.exchangeInfo = (ei.reason as any)?.response?.data?.error?.message || 'Exchange info unavailable';

    if (q.status === 'fulfilled') setQuality(q.value.data);
    else newErrors.quality = (q.reason as any)?.response?.data?.error?.message || 'Quality data unavailable';

    if (s.status === 'fulfilled') setSnapshot(s.value.data);
    else newErrors.snapshot = (s.reason as any)?.response?.data?.error?.message || 'Snapshot unavailable';

    setErrors(newErrors);
    setLoading(false);
  }, [symbol]);

  useEffect(() => {
    loadAll();
    const t = setInterval(loadAll, 15000);
    return () => clearInterval(t);
  }, [loadAll]);

  const handleBackfill = async () => {
    setActionMsg({ type: 'info', text: 'Backfilling missing candles...' });
    try {
      const { data } = await marketApi.backfill(symbol);
      setActionMsg({ type: 'success', text: `✅ Backfill complete: ${data.candles_backfilled ?? 0} candles added` });
    } catch (e: any) {
      setActionMsg({ type: 'error', text: `❌ ${e.response?.data?.error?.message || e.message}` });
    }
  };

  const handleRefreshSnapshot = async () => {
    setActionMsg({ type: 'info', text: 'Refreshing snapshot...' });
    try {
      const { data } = await marketApi.refreshSnapshot(symbol);
      setActionMsg({ type: 'success', text: `✅ Snapshot refreshed: $${data.price}` });
      loadAll();
    } catch (e: any) {
      setActionMsg({ type: 'error', text: `❌ ${e.response?.data?.error?.message || e.message}` });
    }
  };

  if (loading) return (
    <div className="page-loading">
      <div className="loading-spinner" />
      <p>Loading market data...</p>
    </div>
  );

  const price = parseFloat(String(ticker?.price || '0'));

  return (
    <div className="page-container stagger">
      {/* Ticker Summary */}
      <div className="market-ticker-summary card animate-fade-in">
        <div className="mts-left">
          <h3 className="mts-symbol">{symbol}</h3>
          {errors.ticker ? (
            <div className="error-inline">⚠️ {errors.ticker}</div>
          ) : (
            <div className="mts-price">${price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
          )}
        </div>
        <div className="mts-metrics">
          <Metric label="Bid" value={ticker ? `$${parseFloat(String(ticker.bid || '0')).toLocaleString()}` : '—'} />
          <Metric label="Ask" value={ticker ? `$${parseFloat(String(ticker.ask || '0')).toLocaleString()}` : '—'} />
          <Metric label="Spread" value={ticker ? `${parseFloat(String(ticker.spread_bps || '0')).toFixed(2)} bps` : '—'} />
          <Metric label="Vol 24h" value={ticker ? formatVolume(parseFloat(String(ticker.volume_24h || '0'))) : '—'} />
          <Metric
            label="24h Change"
            value={ticker ? `${parseFloat(String(ticker.price_change_pct_24h || '0')).toFixed(2)}%` : '—'}
            className={ticker && parseFloat(String(ticker.price_change_pct_24h || '0')) >= 0 ? 'positive' : 'negative'}
          />
        </div>
      </div>

      <div className="market-grid">
        {/* Order Book */}
        <div className="card animate-fade-in">
          <h4 className="card-title">📊 Order Book Depth</h4>
          {errors.orderbook ? (
            <div className="error-panel"><span className="error-icon">⚠️</span><p>{errors.orderbook}</p></div>
          ) : orderbook ? (
            <ErrorBoundary label="OrderBook">
              <OrderBookDepth data={orderbook} />
            </ErrorBoundary>
          ) : (
            <p className="text-muted">No orderbook data</p>
          )}
        </div>

        {/* Exchange Info */}
        <div className="card animate-fade-in">
          <h4 className="card-title">ℹ️ Exchange Info</h4>
          {errors.exchangeInfo ? (
            <div className="error-panel"><span className="error-icon">⚠️</span><p>{errors.exchangeInfo}</p></div>
          ) : exchangeInfo ? (
            <div className="info-grid">
              <InfoRow label="Base Asset" value={String(exchangeInfo.base_asset || '—')} />
              <InfoRow label="Quote Asset" value={String(exchangeInfo.quote_asset || '—')} />
              <InfoRow label="Status" value={String(exchangeInfo.status || '—')} />
              <InfoRow label="Price Precision" value={String(exchangeInfo.price_precision ?? '—')} />
              <InfoRow label="Qty Precision" value={String(exchangeInfo.quantity_precision ?? '—')} />
              <InfoRow label="Min Qty" value={String(exchangeInfo.min_quantity || exchangeInfo.min_qty || '—')} />
              <InfoRow label="Max Qty" value={String(exchangeInfo.max_quantity || exchangeInfo.max_qty || '—')} />
              <InfoRow label="Step Size" value={String(exchangeInfo.step_size || '—')} />
              <InfoRow label="Tick Size" value={String(exchangeInfo.tick_size || '—')} />
              <InfoRow label="Min Notional" value={exchangeInfo.min_notional ? `$${exchangeInfo.min_notional}` : '—'} />
            </div>
          ) : (
            <p className="text-muted">No exchange info</p>
          )}
        </div>
      </div>

      <div className="market-grid">
        {/* Data Quality */}
        <div className="card animate-fade-in">
          <h4 className="card-title">📈 Data Quality</h4>
          {errors.quality ? (
            <div className="error-panel"><span className="error-icon">⚠️</span><p>{errors.quality}</p></div>
          ) : quality ? (
            <div className="info-grid">
              <InfoRow label="Symbol" value={String(quality.symbol || symbol)} />
              <InfoRow label="Timeframe" value={String(quality.timeframe || '—')} />
              <InfoRow label="Is Healthy" value={quality.is_healthy ? '✅ Yes' : '⚠️ No'} />
              <InfoRow label="Total Candles" value={String(quality.total || '—')} />
              <InfoRow label="Gap Count" value={String(quality.gap_count ?? '0')} />
              {quality.staleness && typeof quality.staleness === 'object' && (
                <>
                  <InfoRow label="Is Stale" value={(quality.staleness as any).is_stale ? '⚠️ Yes' : '✅ No'} />
                  <InfoRow label="Last Update" value={(quality.staleness as any).last_update ? new Date((quality.staleness as any).last_update).toLocaleString() : '—'} />
                </>
              )}
            </div>
          ) : (
            <p className="text-muted">No quality data</p>
          )}
          <div className="card-actions">
            <button onClick={handleBackfill} className="btn btn-ghost btn-sm">🔄 Backfill Gaps</button>
          </div>
        </div>

        {/* Market Snapshot */}
        <div className="card animate-fade-in">
          <h4 className="card-title">📸 Market Snapshot</h4>
          {errors.snapshot ? (
            <div className="error-panel"><span className="error-icon">⚠️</span><p>{errors.snapshot}</p></div>
          ) : snapshot && !('message' in snapshot) ? (
            <div className="info-grid">
              <InfoRow label="Price" value={snapshot.last_price ? `$${parseFloat(String(snapshot.last_price)).toLocaleString()}` : '—'} />
              <InfoRow label="Best Bid" value={snapshot.best_bid ? `$${parseFloat(String(snapshot.best_bid)).toLocaleString()}` : '—'} />
              <InfoRow label="Best Ask" value={snapshot.best_ask ? `$${parseFloat(String(snapshot.best_ask)).toLocaleString()}` : '—'} />
              <InfoRow label="Spread" value={snapshot.spread_bps ? `${parseFloat(String(snapshot.spread_bps)).toFixed(2)} bps` : '—'} />
              <InfoRow label="Volume 24h" value={snapshot.volume_24h ? formatVolume(parseFloat(String(snapshot.volume_24h))) : '—'} />
              <InfoRow label="Is Stale" value={snapshot.is_stale ? '⚠️ Stale' : '✅ Fresh'} />
              <InfoRow label="Timestamp" value={snapshot.timestamp ? new Date(String(snapshot.timestamp)).toLocaleString() : '—'} />
              <InfoRow label="Source" value={String(snapshot.source || '—')} />
            </div>
          ) : (
            <div>
              <p className="text-muted">{snapshot ? String((snapshot as any).message) : 'No snapshot yet'}</p>
              <p className="text-muted" style={{ fontSize: '0.75rem', marginTop: 4 }}>Click "Refresh Snapshot" to generate one</p>
            </div>
          )}
          <div className="card-actions">
            <button onClick={handleRefreshSnapshot} className="btn btn-ghost btn-sm">🔄 Refresh Snapshot</button>
          </div>
        </div>
      </div>

      {actionMsg && (
        <div className={`control-status control-status-${actionMsg.type} animate-fade-in`}>
          {actionMsg.text}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div className="mts-metric">
      <span className="mts-metric-label">{label}</span>
      <span className={`mts-metric-value ${className}`}>{value}</span>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-row">
      <span className="info-label">{label}</span>
      <span className="info-value">{value}</span>
    </div>
  );
}

function OrderBookDepth({ data }: { data: OrderBookData }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    if (!rect.width) return;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width, H = rect.height;
    ctx.clearRect(0, 0, W, H);

    const bids = (data.bids || []).slice(0, 15);
    const asks = (data.asks || []).slice(0, 15);
    if (bids.length === 0 && asks.length === 0) return;

    const allQty = [...bids.map(b => Number(b.quantity)), ...asks.map(a => Number(a.quantity))];
    const maxQty = Math.max(...allQty, 1);
    const midY = H / 2;
    const rowH = Math.min(16, (H - 20) / Math.max(bids.length + asks.length, 1));
    const labelWidth = 100;

    // Asks (top, red) — reverse so closest ask is at midpoint
    [...asks].reverse().forEach((a, i) => {
      const y = midY - (i + 1) * rowH;
      const qty = Number(a.quantity);
      const w = (qty / maxQty) * (W - labelWidth - 10);
      ctx.fillStyle = 'rgba(239, 68, 68, 0.2)';
      ctx.fillRect(labelWidth, y, w, rowH - 1);
      ctx.fillStyle = '#ef4444';
      ctx.font = '11px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(`$${Number(a.price).toLocaleString()}`, labelWidth - 4, y + rowH - 4);
      ctx.textAlign = 'left';
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.fillText(qty.toFixed(4), labelWidth + w + 4, y + rowH - 4);
    });

    // Bids (bottom, green)
    bids.forEach((b, i) => {
      const y = midY + i * rowH;
      const qty = Number(b.quantity);
      const w = (qty / maxQty) * (W - labelWidth - 10);
      ctx.fillStyle = 'rgba(34, 197, 94, 0.2)';
      ctx.fillRect(labelWidth, y, w, rowH - 1);
      ctx.fillStyle = '#22c55e';
      ctx.font = '11px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(`$${Number(b.price).toLocaleString()}`, labelWidth - 4, y + rowH - 4);
      ctx.textAlign = 'left';
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.fillText(qty.toFixed(4), labelWidth + w + 4, y + rowH - 4);
    });

    // Midpoint line
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.5)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(W, midY);
    ctx.stroke();
    ctx.setLineDash([]);
  }, [data]);

  return <canvas ref={canvasRef} className="orderbook-canvas" />;
}

function formatVolume(v: number): string {
  if (isNaN(v)) return '—';
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toFixed(0);
}
