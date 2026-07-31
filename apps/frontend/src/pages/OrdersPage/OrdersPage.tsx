import { useEffect, useState, useCallback } from 'react';
import { ordersApi, type Order } from '../../services/api';
import { useT } from '../../i18n/I18nContext';
import './OrdersPage.css';

export default function OrdersPage() {
  const { t } = useT();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [sideFilter, setSideFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 15;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await ordersApi.list({ limit: 100 });
      setOrders(data.orders || []);
    } catch { /* silent */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = orders.filter(o => {
    const q = search.trim().toLowerCase();
    const matchSearch = !q || o.symbol.toLowerCase().includes(q);
    const matchSide = sideFilter === 'ALL' || o.side === sideFilter;
    const matchStatus = statusFilter === 'ALL' || o.status === statusFilter;
    return matchSearch && matchSide && matchStatus;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safeP = Math.min(page, totalPages);
  const paged = filtered.slice((safeP - 1) * PAGE_SIZE, safeP * PAGE_SIZE);
  const hasFilters = search || sideFilter !== 'ALL' || statusFilter !== 'ALL';

  const clearFilters = () => { setSearch(''); setSideFilter('ALL'); setStatusFilter('ALL'); setPage(1); };

  if (loading) return (
    <div className="page-loading">
      <div className="loading-spinner" />
      <p>{t('common.loading')}</p>
    </div>
  );

  return (
    <div className="page-container">
      {/* Toolbar */}
      <div className="orders-toolbar">
        <div className="search-input-wrap">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="search-icon">
            <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.3" />
            <path d="M9.5 9.5L12.5 12.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          <input
            className="search-input"
            type="text"
            placeholder="BTC, ETH..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
          {search && <button className="search-clear" onClick={() => { setSearch(''); setPage(1); }}>✕</button>}
        </div>

        <select className="filter-select" value={sideFilter} onChange={e => { setSideFilter(e.target.value); setPage(1); }}>
          <option value="ALL">— {t('ord.side')} —</option>
          <option value="BUY">📈 BUY</option>
          <option value="SELL">📉 SELL</option>
        </select>

        <select className="filter-select" value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}>
          <option value="ALL">— {t('ord.status')} —</option>
          <option value="PENDING">PENDING</option>
          <option value="OPEN">OPEN</option>
          <option value="FILLED">FILLED</option>
          <option value="PARTIALLY_FILLED">PARTIAL</option>
          <option value="CANCELED">CANCELED</option>
          <option value="REJECTED">REJECTED</option>
        </select>

        {hasFilters && (
          <button className="filter-clear-btn" onClick={clearFilters}>✕ {t('common.cancel')}</button>
        )}

        <span className="orders-count text-muted">
          {filtered.length} {filtered.length === 1 ? 'lệnh' : 'lệnh'}
        </span>

        <button className="refresh-btn" onClick={load} title={t('dash.refresh')}>🔄</button>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state card animate-fade-in">
          <div className="empty-icon">📦</div>
          <h3>{hasFilters ? 'Không có kết quả phù hợp' : t('ord.no_orders')}</h3>
          <p>{hasFilters ? 'Thử thay đổi bộ lọc.' : t('empty.orders_hint')}</p>
        </div>
      ) : (
        <>
          <div className="card animate-fade-in">
            <h4 className="card-title">📦 {t('ord.title')} ({filtered.length})</h4>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th></th>
                    <th>{t('ord.symbol')}</th>
                    <th>{t('ord.side')}</th>
                    <th>{t('ord.type')}</th>
                    <th>{t('ord.qty')}</th>
                    <th>{t('ord.price')}</th>
                    <th>{t('ord.filled')}</th>
                    <th>{t('ord.avg_fill')}</th>
                    <th>{t('ord.status')}</th>
                    <th>{t('ord.env')}</th>
                    <th>{t('ord.created')}</th>
                  </tr>
                </thead>
                <tbody>
                  {paged.map(o => (
                    <>
                      <tr key={o.id} onClick={() => setExpanded(expanded === o.id ? null : o.id)} className="order-row clickable">
                        <td>{expanded === o.id ? '▼' : '▶'}</td>
                        <td className="mono">{o.symbol}</td>
                        <td><span className={`badge badge-${o.side === 'BUY' ? 'success' : 'danger'}`}>{o.side === 'BUY' ? 'MUA' : 'BÁN'}</span></td>
                        <td>{o.order_type}</td>
                        <td className="mono">{o.quantity}</td>
                        <td className="mono">{o.price ? `$${parseFloat(o.price).toLocaleString()}` : '—'}</td>
                        <td className="mono">{o.filled_quantity}</td>
                        <td className="mono">{o.average_fill_price ? `$${parseFloat(o.average_fill_price).toLocaleString()}` : '—'}</td>
                        <td>
                          <span className={`badge badge-${o.status === 'FILLED' ? 'success' : o.status === 'CANCELED' || o.status === 'REJECTED' ? 'danger' : 'warning'}`}>
                            {o.status === 'FILLED' ? 'Đã khớp' : o.status === 'CANCELED' ? 'Đã hủy' : o.status === 'REJECTED' ? 'Từ chối' : o.status === 'OPEN' ? 'Đang mở' : o.status === 'PENDING' ? 'Chờ' : o.status}
                          </span>
                        </td>
                        <td>{o.environment === 'PAPER' ? 'Mô phỏng' : (o.environment || '—')}</td>
                        <td className="mono">{o.created_at ? new Date(o.created_at).toLocaleString('vi-VN') : '—'}</td>
                      </tr>
                      {expanded === o.id && o.fills.length > 0 && (
                        <tr key={`${o.id}-fills`} className="fills-row">
                          <td colSpan={11}>
                            <div className="fills-detail">
                              <h5>{t('ord.fills')} ({o.fills.length})</h5>
                              <div className="fills-list">
                                {o.fills.map(f => (
                                  <div key={f.id} className="fill-item">
                                    <span>{t('ord.price')}: <strong>${parseFloat(f.fill_price).toLocaleString()}</strong></span>
                                    <span>{t('ord.qty')}: <strong>{f.fill_quantity}</strong></span>
                                    <span>{t('ord.fee')}: <strong>{f.fee} {f.fee_asset || ''}</strong></span>
                                    <span>{f.is_maker ? t('ord.maker') : t('ord.taker')}</span>
                                    <span className="mono">{f.timestamp ? new Date(f.timestamp).toLocaleTimeString('vi-VN') : ''}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="pagination">
              <button className="page-btn" disabled={safeP <= 1} onClick={() => setPage(safeP - 1)}>‹ Trước</button>
              <span className="page-info">Trang {safeP} / {totalPages}</span>
              <button className="page-btn" disabled={safeP >= totalPages} onClick={() => setPage(safeP + 1)}>Sau ›</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
