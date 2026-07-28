import { useEffect, useState, useCallback, useRef } from 'react';
import { marketApi, type Ticker, type Candle, type OrderBookData, type SymbolInfo } from '../../services/api';
import './MarketPage.css';

interface Props { symbol: string; }

export default function MarketPage({ symbol }: Props) {
  const [ticker, setTicker] = useState<Ticker | null>(null);
  const [orderbook, setOrderbook] = useState<OrderBookData | null>(null);
  const [exchangeInfo, setExchangeInfo] = useState<SymbolInfo | null>(null);
  const [quality, setQuality] = useState<Record<string, unknown> | null>(null);
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<{ type: string; text: string } | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    const [t, ob, ei, q, s] = await Promise.allSettled([
      marketApi.ticker(symbol),
      marketApi.orderbook(symbol, 20),
      marketApi.exchangeInfo(symbol),
      marketApi.quality(symbol),
      marketApi.snapshot(symbol),
    ]);
    if (t.status === 'fulfilled') setTicker(t.value.data);
    if (ob.status === 'fulfilled') setOrderbook(ob.value.data);
    if (ei.status === 'fulfilled') setExchangeInfo(ei.value.data);
    if (q.status === 'fulfilled') setQuality(q.value.data);
    if (s.status === 'fulfilled') setSnapshot(s.value.data);
    setLoading(false);
  }, [symbol]);

  useEffect(() => { loadAll(); const t = setInterval(loadAll, 15000); return () => clearInterval(t); }, [loadAll]);

  const handleBackfill = async () => {
    setActionMsg({ type: 'info', text: 'Backfilling missing candles...' });
    try {
      const { data } = await marketApi.backfill(symbol);
      setActionMsg({ type: 'success', text: `✅ Backfill complete: ${JSON.stringify(data)}` });
    } catch (e: any) { setActionMsg({ type: 'error', text: `❌ ${e.response?.data?.detail || e.message}` }); }
  };

  const handleRefreshSnapshot = async () => {
    setActionMsg({ type: 'info', text: 'Refreshing snapshot...' });
    try {
      const { data } = await marketApi.refreshSnapshot(symbol);
      setActionMsg({ type: 'success', text: `✅ Snapshot refreshed: $${data.price}` });
      loadAll();
    } catch (e: any) { setActionMsg({ type: 'error', text: `❌ ${e.response?.data?.detail || e.message}` }); }
  };

  if (loading) return <div className="page-loading"><div className="loading-spinner" /><p>Loading market data...</p></div>;

  const price = parseFloat(String(ticker?.price || '0'));

  return (
    <div className="page-container stagger">
      {/* Ticker Summary */}
      <div className="market-ticker-summary card animate-fade-in">
        <div className="mts-left">
          <h3 className="mts-symbol">{symbol}</h3>
          <div className="mts-price">${price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
        </div>
        <div className="mts-metrics">
          <Metric label="Bid" value={`$${parseFloat(String(ticker?.bid || '0')).toLocaleString()}`} />
          <Metric label="Ask" value={`$${parseFloat(String(ticker?.ask || '0')).toLocaleString()}`} />
          <Metric label="Spread" value={`${parseFloat(String(ticker?.spread_bps || '0')).toFixed(2)} bps`} />
          <Metric label="Vol 24h" value={formatVolume(parseFloat(String(ticker?.volume_24h || '0')))} />
          <Metric label="24h Change" value={`${parseFloat(String(ticker?.price_change_pct_24h || '0')).toFixed(2)}%`}
            className={parseFloat(String(ticker?.price_change_pct_24h || '0')) >= 0 ? 'positive' : 'negative'} />
        </div>
      </div>

      <div className="market-grid">
        {/* Order Book */}
        <div className="card animate-fade-in">
          <h4 className="card-title">📊 Order Book Depth</h4>
          {orderbook ? <OrderBookDepth data={orderbook} /> : <p className="text-muted">No data</p>}
        </div>

        {/* Exchange Info */}
        <div className="card animate-fade-in">
          <h4 className="card-title">ℹ️ Exchange Info</h4>
          {exchangeInfo ? (
            <div className="info-grid">
              <InfoRow label="Base Asset" value={exchangeInfo.base_asset} />
              <InfoRow label="Quote Asset" value={exchangeInfo.quote_asset} />
              <InfoRow label="Status" value={exchangeInfo.status} />
              <InfoRow label="Min Qty" value={exchangeInfo.min_qty} />
              <InfoRow label="Max Qty" value={exchangeInfo.max_qty} />
              <InfoRow label="Step Size" value={exchangeInfo.step_size} />
              <InfoRow label="Tick Size" value={exchangeInfo.tick_size} />
              <InfoRow label="Min Notional" value={`$${exchangeInfo.min_notional}`} />
            </div>
          ) : <p className="text-muted">No data</p>}
        </div>
      </div>

      <div className="market-grid">
        {/* Data Quality */}
        <div className="card animate-fade-in">
          <h4 className="card-title">📈 Data Quality</h4>
          {quality ? (
            <div className="info-grid">
              {Object.entries(quality).map(([k, v]) => (
                <InfoRow key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
              ))}
            </div>
          ) : <p className="text-muted">No quality data</p>}
          <div className="card-actions">
            <button onClick={handleBackfill} className="btn btn-ghost btn-sm">🔄 Backfill Gaps</button>
          </div>
        </div>

        {/* Market Snapshot */}
        <div className="card animate-fade-in">
          <h4 className="card-title">📸 Market Snapshot</h4>
          {snapshot && !('message' in snapshot) ? (
            <div className="info-grid">
              {Object.entries(snapshot).slice(0, 10).map(([k, v]) => (
                <InfoRow key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'object' ? JSON.stringify(v) : String(v)} />
              ))}
            </div>
          ) : <p className="text-muted">{(snapshot as any)?.message || 'No snapshot'}</p>}
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
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width, H = rect.height;
    ctx.clearRect(0, 0, W, H);

    const bids = data.bids.slice(0, 15);
    const asks = data.asks.slice(0, 15);
    const maxQty = Math.max(...bids.map(b => b.quantity), ...asks.map(a => a.quantity), 1);

    const midY = H / 2;
    const rowH = Math.min(16, (H - 20) / Math.max(bids.length + asks.length, 1));

    // Asks (top, red)
    asks.reverse().forEach((a, i) => {
      const y = midY - (i + 1) * rowH;
      const w = (a.quantity / maxQty) * (W - 120);
      ctx.fillStyle = 'rgba(239, 68, 68, 0.2)';
      ctx.fillRect(120, y, w, rowH - 1);
      ctx.fillStyle = '#ef4444';
      ctx.font = '11px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(`$${a.price.toLocaleString()}`, 115, y + rowH - 4);
      ctx.textAlign = 'left';
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      ctx.fillText(a.quantity.toFixed(4), 125 + w, y + rowH - 4);
    });

    // Bids (bottom, green)
    bids.forEach((b, i) => {
      const y = midY + i * rowH;
      const w = (b.quantity / maxQty) * (W - 120);
      ctx.fillStyle = 'rgba(34, 197, 94, 0.2)';
      ctx.fillRect(120, y, w, rowH - 1);
      ctx.fillStyle = '#22c55e';
      ctx.font = '11px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(`$${b.price.toLocaleString()}`, 115, y + rowH - 4);
      ctx.textAlign = 'left';
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      ctx.fillText(b.quantity.toFixed(4), 125 + w, y + rowH - 4);
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
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toFixed(0);
}
