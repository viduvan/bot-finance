/**
 * CandlestickChart — Interactive financial candlestick chart
 *
 * Features:
 * - OHLCV candlestick rendering via lightweight-charts (TradingView)
 * - EMA 21 + EMA 50 overlay lines
 * - Volume histogram sub-panel
 * - Crosshair tooltip with OHLCV values
 * - Zoom/pan with mouse or touch
 * - Timeframe selector (15m / 1h / 4h)
 * - Auto-refresh every 30 seconds
 * - Lazy loading older candles when scrolling left
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import {
  createChart,
  ColorType,
  CrosshairMode,
} from 'lightweight-charts';
import type {
  IChartApi,
  ISeriesApi,
  CandlestickData,
  HistogramData,
  LineData,
  Time,
} from 'lightweight-charts';
import { marketApi, type Candle } from '../../services/api';
import './CandlestickChart.css';

// ── Types ────────────────────────────────────────────────────────

export interface Signal {
  time: number;
  type: 'BUY' | 'SELL';
  price: number;
  label?: string;
}

interface Props {
  symbol: string;
  initialTimeframe?: '15m' | '1h' | '4h';
  signals?: Signal[];
  height?: number;
  showVolume?: boolean;
  showEma?: boolean;
  autoRefreshMs?: number;
}

interface OHLCTooltip {
  open: number; high: number; low: number; close: number;
  volume: number; time: string;
  ema21?: number | null; ema50?: number | null;
}

// ── Helpers ──────────────────────────────────────────────────────

function computeEMA(data: CandlestickData[], period: number): LineData[] {
  if (data.length < period) return [];
  const k = 2 / (period + 1);
  const result: LineData[] = [];
  let ema = data.slice(0, period).reduce((s, c) => s + c.close, 0) / period;
  result.push({ time: data[period - 1].time, value: ema });
  for (let i = period; i < data.length; i++) {
    ema = data[i].close * k + ema * (1 - k);
    result.push({ time: data[i].time, value: ema });
  }
  return result;
}

function candleToChart(c: Candle): CandlestickData {
  return {
    time: (new Date(c.open_time).getTime() / 1000) as Time,
    open: parseFloat(c.open),
    high: parseFloat(c.high),
    low: parseFloat(c.low),
    close: parseFloat(c.close),
  };
}

function candleToVolume(c: Candle): HistogramData {
  const open = parseFloat(c.open);
  const close = parseFloat(c.close);
  return {
    time: (new Date(c.open_time).getTime() / 1000) as Time,
    value: parseFloat(c.volume),
    color: close >= open ? 'rgba(34,197,94,0.35)' : 'rgba(239,68,68,0.35)',
  };
}

function formatTime(ts: Time): string {
  const date = new Date((ts as number) * 1000);
  return date.toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function formatPrice(v: number): string {
  if (v >= 10000) return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (v >= 1) return v.toFixed(4);
  return v.toFixed(6);
}

// ── Component ────────────────────────────────────────────────────

const TIMEFRAMES = ['15m', '1h', '4h'] as const;

export default function CandlestickChart({
  symbol,
  initialTimeframe = '15m',
  signals = [],
  height = 420,
  showVolume = true,
  showEma = true,
  autoRefreshMs = 30_000,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const ema21Ref = useRef<ISeriesApi<'Line'> | null>(null);
  const ema50Ref = useRef<ISeriesApi<'Line'> | null>(null);
  const rawCandlesRef = useRef<CandlestickData[]>([]);
  const allCandlesRef = useRef<Candle[]>([]);
  const isLoadingMoreRef = useRef(false);
  const oldestTimeRef = useRef<string | null>(null);

  const [timeframe, setTimeframe] = useState<'15m' | '1h' | '4h'>(initialTimeframe);
  const [tooltip, setTooltip] = useState<OHLCTooltip | null>(null);
  const [candleCount, setCandleCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // ── Chart initialization ──────────────────────────────────────

  const initChart = useCallback(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'rgba(200,200,210,0.85)',
        fontFamily: "'Inter', 'Roboto', sans-serif",
        fontSize: 11,
      },
      width: container.clientWidth,
      height: height,
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.04)' },
        horzLines: { color: 'rgba(255,255,255,0.04)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(100,130,255,0.5)', width: 1, style: 1 },
        horzLine: { color: 'rgba(100,130,255,0.5)', width: 1, style: 1 },
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.08)',
        scaleMargins: { top: 0.08, bottom: showVolume ? 0.28 : 0.06 },
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.08)',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: 'rgba(34,197,94,0.7)',
      wickDownColor: 'rgba(239,68,68,0.7)',
    });

    // Volume histogram
    let volSeries: ISeriesApi<'Histogram'> | null = null;
    if (showVolume) {
      volSeries = chart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
        lastValueVisible: false,
        priceLineVisible: false,
      });
      chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.78, bottom: 0 },
      });
    }

    // EMA lines
    let ema21Series: ISeriesApi<'Line'> | null = null;
    let ema50Series: ISeriesApi<'Line'> | null = null;
    if (showEma) {
      ema21Series = chart.addLineSeries({
        color: '#f59e0b',
        lineWidth: 1,
        title: 'EMA21',
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      ema50Series = chart.addLineSeries({
        color: '#8b5cf6',
        lineWidth: 1,
        title: 'EMA50',
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }

    // Crosshair tooltip
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) return;
      const cd = param.seriesData.get(candleSeries) as CandlestickData | undefined;
      if (!cd) { setTooltip(null); return; }
      const vd = volSeries ? (param.seriesData.get(volSeries) as HistogramData | undefined) : undefined;
      const e21 = ema21Series ? (param.seriesData.get(ema21Series) as LineData | undefined) : undefined;
      const e50 = ema50Series ? (param.seriesData.get(ema50Series) as LineData | undefined) : undefined;
      setTooltip({
        open: cd.open, high: cd.high, low: cd.low, close: cd.close,
        volume: vd?.value ?? 0,
        time: formatTime(param.time),
        ema21: e21?.value ?? null,
        ema50: e50?.value ?? null,
      });
    });

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (chartRef.current) {
        chartRef.current.applyOptions({ width: container.clientWidth });
      }
    });
    ro.observe(container);

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volSeries;
    ema21Ref.current = ema21Series;
    ema50Ref.current = ema50Series;

    return () => { ro.disconnect(); };
  }, [height, showVolume, showEma]);

  // ── Data ──────────────────────────────────────────────────────

  const applyData = useCallback((candles: Candle[]) => {
    allCandlesRef.current = candles;
    const sorted = candles.map(candleToChart).sort((a, b) => (a.time as number) - (b.time as number));
    // deduplicate
    const deduped = sorted.filter((c, i, arr) => i === 0 || c.time !== arr[i-1].time);
    rawCandlesRef.current = deduped;

    candleSeriesRef.current?.setData(deduped);
    if (showVolume) {
      const volData = candles.map(candleToVolume).sort((a, b) => (a.time as number) - (b.time as number));
      const vDeduped = volData.filter((c, i, arr) => i === 0 || c.time !== arr[i-1].time);
      volumeSeriesRef.current?.setData(vDeduped);
    }
    if (showEma) {
      ema21Ref.current?.setData(computeEMA(deduped, 21));
      ema50Ref.current?.setData(computeEMA(deduped, 50));
    }
    setCandleCount(deduped.length);

    if (candles.length > 0) {
      const oldest = candles.reduce((m, c) => c.open_time < m ? c.open_time : m, candles[0].open_time);
      oldestTimeRef.current = oldest;
    }
  }, [showVolume, showEma]);

  const loadCandles = useCallback(async (tf: string) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await marketApi.getCandlesHistory(symbol, tf, 500);
      applyData(data.candles || []);
    } catch (e: unknown) {
      const apiErr = (e as { response?: { data?: { error?: { message?: string } } } });
      setError(apiErr?.response?.data?.error?.message || 'Failed to load candles');
    } finally {
      setLoading(false);
    }
  }, [symbol, applyData]);

  const loadOlderCandles = useCallback(async () => {
    if (isLoadingMoreRef.current || !oldestTimeRef.current) return;
    isLoadingMoreRef.current = true;
    setIsLoadingMore(true);
    try {
      const { data } = await marketApi.getCandlesHistory(symbol, timeframe, 500, oldestTimeRef.current);
      if (!data.candles || data.candles.length === 0) {
        isLoadingMoreRef.current = false;
        setIsLoadingMore(false);
        return;
      }
      const merged = [...data.candles, ...allCandlesRef.current];
      applyData(merged);
    } catch { /* silent */ } finally {
      isLoadingMoreRef.current = false;
      setIsLoadingMore(false);
    }
  }, [symbol, timeframe, applyData]);

  // Register scroll handler after chart is ready
  useEffect(() => {
    if (!chartRef.current) return;
    const sub = () => {
      const range = chartRef.current?.timeScale().getVisibleLogicalRange();
      if (range && range.from <= 5 && !isLoadingMoreRef.current && oldestTimeRef.current) {
        loadOlderCandles();
      }
    };
    chartRef.current.timeScale().subscribeVisibleLogicalRangeChange(sub);
    return () => { chartRef.current?.timeScale().unsubscribeVisibleLogicalRangeChange(sub); };
  }, [loadOlderCandles, timeframe]);

  // ── Effects ───────────────────────────────────────────────────

  useEffect(() => {
    const cleanup = initChart();
    return cleanup;
  }, [initChart]);

  useEffect(() => {
    rawCandlesRef.current = [];
    allCandlesRef.current = [];
    oldestTimeRef.current = null;
    loadCandles(timeframe);
  }, [symbol, timeframe, loadCandles]);

  useEffect(() => {
    if (!autoRefreshMs) return;
    const t = setInterval(() => loadCandles(timeframe), autoRefreshMs);
    return () => clearInterval(t);
  }, [timeframe, loadCandles, autoRefreshMs]);

  // Suppress signals prop warning
  void signals;

  // ── Render ────────────────────────────────────────────────────

  return (
    <div className="cc-wrapper">
      <div className="cc-header">
        <div className="cc-header-left">
          <span className="cc-symbol">{symbol}</span>
          <span className="cc-count">{candleCount.toLocaleString()} candles</span>
          {isLoadingMore && <span className="cc-loading-more">⟳ loading history…</span>}
        </div>
        <div className="cc-tf-group">
          {TIMEFRAMES.map(tf => (
            <button
              key={tf}
              id={`cc-tf-${tf}`}
              className={`cc-tf-btn ${timeframe === tf ? 'active' : ''}`}
              onClick={() => setTimeframe(tf)}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {tooltip && (
        <div className="cc-tooltip">
          <span className="cc-tooltip-time">{tooltip.time}</span>
          <span className={`cc-tooltip-close ${tooltip.close >= tooltip.open ? 'up' : 'down'}`}>
            C: {formatPrice(tooltip.close)}
          </span>
          <span className="cc-tooltip-ohlc">
            O:{formatPrice(tooltip.open)} H:{formatPrice(tooltip.high)} L:{formatPrice(tooltip.low)}
          </span>
          {tooltip.ema21 != null && <span className="cc-tooltip-ema ema21">EMA21:{formatPrice(tooltip.ema21)}</span>}
          {tooltip.ema50 != null && <span className="cc-tooltip-ema ema50">EMA50:{formatPrice(tooltip.ema50)}</span>}
          {tooltip.volume > 0 && <span className="cc-tooltip-vol">Vol:{tooltip.volume.toLocaleString(undefined, { maximumFractionDigits: 1 })}</span>}
        </div>
      )}

      <div className="cc-chart-container" style={{ height }}>
        {loading && (
          <div className="cc-overlay">
            <div className="cc-spinner" />
            <span>Loading chart…</span>
          </div>
        )}
        {error && !loading && (
          <div className="cc-overlay cc-error">
            <span>⚠️ {error}</span>
            <button className="cc-retry" onClick={() => loadCandles(timeframe)}>Retry</button>
          </div>
        )}
        <div ref={containerRef} className="cc-canvas" style={{ opacity: loading ? 0.3 : 1 }} />
      </div>

      {showEma && !loading && (
        <div className="cc-legend">
          <span className="cc-legend-item ema21-color">━ EMA 21</span>
          <span className="cc-legend-item ema50-color">━ EMA 50</span>
          <span className="cc-legend-item bull-color">■ Bullish</span>
          <span className="cc-legend-item bear-color">■ Bearish</span>
        </div>
      )}
    </div>
  );
}
