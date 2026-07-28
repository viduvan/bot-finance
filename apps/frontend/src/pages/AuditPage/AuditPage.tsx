import { useEffect, useState, useCallback } from 'react';
import { auditApi, type AuditLogEntry } from '../../services/api';
import './AuditPage.css';

const ACTION_COLORS: Record<string, string> = {
  USER_LOGIN: 'info', USER_LOGOUT: 'muted', USER_LOGIN_FAILED: 'danger',
  PROPOSAL_APPROVED: 'success', PROPOSAL_REJECTED: 'danger', PROPOSAL_CREATED: 'info',
  ORDER_FILLED: 'success', ORDER_FAILED: 'danger', ORDER_SUBMITTED: 'info',
  RISK_REJECTION: 'warning', EXECUTION_REQUESTED: 'info',
};

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { limit: 100 };
      if (actionFilter) params.action = actionFilter;
      const { data } = await auditApi.logs(params);
      setLogs(data.logs || []);
    } catch { /* silent */ }
    setLoading(false);
  }, [actionFilter]);

  useEffect(() => { load(); }, [load]);

  const uniqueActions = [...new Set(logs.map(l => l.action))].sort();

  if (loading) return <div className="page-loading"><div className="loading-spinner" /><p>Loading audit logs...</p></div>;

  return (
    <div className="page-container">
      <div className="audit-filters">
        <select value={actionFilter} onChange={e => setActionFilter(e.target.value)} className="symbol-select">
          <option value="">All Actions</option>
          {uniqueActions.map(a => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
        </select>
        <span className="text-muted">{logs.length} entries</span>
      </div>

      {logs.length === 0 ? (
        <div className="empty-state card animate-fade-in">
          <div className="empty-icon">📝</div>
          <h3>No Audit Logs</h3>
          <p>Actions will be logged here as the system operates.</p>
        </div>
      ) : (
        <div className="card animate-fade-in">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Action</th>
                  <th>Service</th>
                  <th>Resource</th>
                  <th>IP</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id}>
                    <td className="mono">{log.created_at ? new Date(log.created_at).toLocaleString() : '—'}</td>
                    <td><span className={`badge badge-${ACTION_COLORS[log.action] || 'muted'}`}>{log.action.replace(/_/g, ' ')}</span></td>
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
      )}
    </div>
  );
}
