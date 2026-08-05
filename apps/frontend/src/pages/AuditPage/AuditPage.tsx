import { useEffect, useState, useCallback } from 'react';
import { auditApi, type AuditLogEntry } from '../../services/api';
import { useT } from '../../i18n/I18nContext';
import './AuditPage.css';

const ACTION_COLORS: Record<string, string> = {
  USER_LOGIN: 'info', USER_LOGOUT: 'muted', USER_LOGIN_FAILED: 'danger',
  PROPOSAL_APPROVED: 'success', PROPOSAL_REJECTED: 'danger', PROPOSAL_CREATED: 'info',
  ORDER_FILLED: 'success', ORDER_FAILED: 'danger', ORDER_SUBMITTED: 'info',
  RISK_REJECTION: 'warning', EXECUTION_REQUESTED: 'info',
};

const ACTION_LABELS: Record<string, string> = {
  USER_LOGIN: 'Đăng nhập', USER_LOGOUT: 'Đăng xuất', USER_LOGIN_FAILED: 'Đăng nhập thất bại',
  PROPOSAL_APPROVED: 'Phê duyệt đề xuất', PROPOSAL_REJECTED: 'Từ chối đề xuất',
  PROPOSAL_CREATED: 'Tạo đề xuất', PROPOSAL_CANCELLED: 'Hủy đề xuất',
  ORDER_FILLED: 'Lệnh khớp', ORDER_FAILED: 'Lệnh thất bại', ORDER_SUBMITTED: 'Gửi lệnh',
  RISK_REJECTION: 'Từ chối rủi ro', EXECUTION_REQUESTED: 'Yêu cầu thực thi',
};

const PAGE_SIZE = 20;

export default function AuditPage() {
  const { t } = useT();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { limit: 200 };
      if (actionFilter) params.action = actionFilter;
      const { data } = await auditApi.logs(params);
      setLogs(data.logs || []);
    } catch (err) { console.error('[AuditPage] Error:', err); }
    setLoading(false);
  }, [actionFilter]);

  useEffect(() => { load(); }, [load]);

  const uniqueActions = [...new Set(logs.map(l => l.action))].sort();

  const filtered = logs.filter(log => {
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    return (
      log.action.toLowerCase().includes(q) ||
      (log.resource_type || '').toLowerCase().includes(q) ||
      (log.resource_id || '').toLowerCase().includes(q) ||
      (log.service || '').toLowerCase().includes(q) ||
      (log.ip_address || '').toLowerCase().includes(q)
    );
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safeP = Math.min(page, totalPages);
  const paged = filtered.slice((safeP - 1) * PAGE_SIZE, safeP * PAGE_SIZE);

  const hasFilters = search || actionFilter;
  const clearFilters = () => { setSearch(''); setActionFilter(''); setPage(1); };

  if (loading) return (
    <div className="page-loading">
      <div className="loading-spinner" />
      <p>{t('common.loading')}</p>
    </div>
  );

  return (
    <div className="page-container">
      {/* Toolbar */}
      <div className="audit-filters">
        <div className="search-input-wrap">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="search-icon">
            <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.3" />
            <path d="M9.5 9.5L12.5 12.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          <input
            className="search-input"
            type="text"
            placeholder={t('aud.filter_resource')}
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
          {search && <button className="search-clear" onClick={() => { setSearch(''); setPage(1); }}>✕</button>}
        </div>

        <select
          value={actionFilter}
          onChange={e => { setActionFilter(e.target.value); setPage(1); }}
          className="filter-select"
        >
          <option value="">— {t('aud.action')} —</option>
          {uniqueActions.map(a => (
            <option key={a} value={a}>{ACTION_LABELS[a] || a.replace(/_/g, ' ')}</option>
          ))}
        </select>

        {hasFilters && (
          <button className="filter-clear-btn" onClick={clearFilters}>✕ {t('common.cancel')}</button>
        )}

        <span className="text-muted">{filtered.length} {filtered.length === 1 ? 'bản ghi' : 'bản ghi'}</span>

        <button className="refresh-btn" onClick={load} title={t('dash.refresh')}>🔄</button>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state card animate-fade-in">
          <div className="empty-icon">📝</div>
          <h3>{hasFilters ? 'Không có kết quả phù hợp' : t('aud.no_logs')}</h3>
          <p>{hasFilters ? 'Thử thay đổi bộ lọc.' : 'Hành động sẽ được ghi lại ở đây khi hệ thống hoạt động.'}</p>
        </div>
      ) : (
        <>
          <div className="card animate-fade-in">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t('aud.timestamp')}</th>
                    <th>{t('aud.action')}</th>
                    <th>Dịch vụ</th>
                    <th>{t('aud.resource')}</th>
                    <th>IP</th>
                    <th>{t('aud.details')}</th>
                  </tr>
                </thead>
                <tbody>
                  {paged.map(log => (
                    <tr key={log.id}>
                      <td className="mono">{log.created_at ? new Date(log.created_at).toLocaleString('vi-VN') : '—'}</td>
                      <td>
                        <span className={`badge badge-${ACTION_COLORS[log.action] || 'muted'}`}>
                          {ACTION_LABELS[log.action] || log.action.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td>{log.service}</td>
                      <td className="mono">{log.resource_type ? `${log.resource_type}/${log.resource_id?.slice(0, 8)}` : '—'}</td>
                      <td className="mono">{log.ip_address || '—'}</td>
                      <td className="truncate">{log.details ? JSON.stringify(log.details).slice(0, 80) : '—'}</td>
                    </tr>
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
