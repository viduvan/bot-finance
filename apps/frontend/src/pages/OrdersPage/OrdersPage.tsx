import { useEffect, useState, useCallback } from 'react';
import { ordersApi, type Order } from '../../services/api';
import './OrdersPage.css';

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await ordersApi.list({ limit: 50 });
      setOrders(data.orders || []);
    } catch { /* silent */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="page-loading"><div className="loading-spinner" /><p>Loading orders...</p></div>;

  if (orders.length === 0) {
    return (
      <div className="page-container">
        <div className="empty-state card animate-fade-in">
          <div className="empty-icon">📦</div>
          <h3>No Orders Yet</h3>
          <p>Orders will appear here after proposals are approved and executed.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="card animate-fade-in">
        <h4 className="card-title">📦 Orders ({orders.length})</h4>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th></th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Type</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Filled</th>
                <th>Avg Fill</th>
                <th>Status</th>
                <th>Env</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {orders.map(o => (
                <>
                  <tr key={o.id} onClick={() => setExpanded(expanded === o.id ? null : o.id)} className="order-row clickable">
                    <td>{expanded === o.id ? '▼' : '▶'}</td>
                    <td className="mono">{o.symbol}</td>
                    <td><span className={`badge badge-${o.side === 'BUY' ? 'success' : 'danger'}`}>{o.side}</span></td>
                    <td>{o.order_type}</td>
                    <td className="mono">{o.quantity}</td>
                    <td className="mono">{o.price ? `$${parseFloat(o.price).toLocaleString()}` : '—'}</td>
                    <td className="mono">{o.filled_quantity}</td>
                    <td className="mono">{o.average_fill_price ? `$${parseFloat(o.average_fill_price).toLocaleString()}` : '—'}</td>
                    <td><span className={`badge badge-${o.status === 'FILLED' ? 'success' : o.status === 'CANCELED' ? 'danger' : 'warning'}`}>{o.status}</span></td>
                    <td>{o.environment}</td>
                    <td className="mono">{o.created_at ? new Date(o.created_at).toLocaleString() : '—'}</td>
                  </tr>
                  {expanded === o.id && o.fills.length > 0 && (
                    <tr key={`${o.id}-fills`} className="fills-row">
                      <td colSpan={11}>
                        <div className="fills-detail">
                          <h5>Fills ({o.fills.length})</h5>
                          <div className="fills-list">
                            {o.fills.map(f => (
                              <div key={f.id} className="fill-item">
                                <span>Price: <strong>${parseFloat(f.fill_price).toLocaleString()}</strong></span>
                                <span>Qty: <strong>{f.fill_quantity}</strong></span>
                                <span>Fee: <strong>{f.fee} {f.fee_asset || ''}</strong></span>
                                <span>{f.is_maker ? 'Maker' : 'Taker'}</span>
                                <span className="mono">{f.timestamp ? new Date(f.timestamp).toLocaleTimeString() : ''}</span>
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
    </div>
  );
}
