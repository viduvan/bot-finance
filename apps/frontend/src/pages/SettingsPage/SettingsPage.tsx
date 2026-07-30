import { useEffect, useState } from 'react';
import { systemApi, type SystemConfig, type SystemStatus } from '../../services/api';
import { useT } from '../../i18n/I18nContext';
import './SettingsPage.css';

export default function SettingsPage() {
  const { t } = useT();
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [c, s] = await Promise.allSettled([systemApi.config(), systemApi.status()]);
      if (c.status === 'fulfilled') setConfig(c.value.data);
      if (s.status === 'fulfilled') setStatus(s.value.data);
      setLoading(false);
    }
    load();
  }, []);

  if (loading) return <div className="page-loading"><div className="loading-spinner" /><p>Loading settings...</p></div>;

  return (
    <div className="page-container stagger">
      {/* Service Status */}
      <div className="card animate-fade-in">
        <h4 className="card-title">🔌 Service Connectivity</h4>
        <div className="services-grid">
          {status?.services && Object.entries(status.services).map(([svc, st]) => (
            <div key={svc} className="service-item">
              <span className={`status-dot ${st === 'connected' ? 'online' : 'offline'}`} />
              <span className="service-name">{svc}</span>
              <span className={`service-status ${st === 'connected' ? 'svc-ok' : 'svc-warn'}`}>{st}</span>
            </div>
          ))}
        </div>
        <div className="service-meta">
          <span>Version: <strong>{status?.version}</strong></span>
          <span>Mode: <strong>{status?.trading_mode}</strong></span>
          <span>Status: <strong>{status?.status}</strong></span>
        </div>
      </div>

      <div className="settings-grid">
        {/* Trading Config */}
        <div className="card animate-fade-in">
          <h4 className="card-title">💹 Trading Configuration</h4>
          <div className="config-list">
            <ConfigRow label="Exchange" value={config?.trading.exchange || '—'} />
            <ConfigRow label="Market" value={config?.trading.market || '—'} />
            <ConfigRow label="Mode" value={config?.trading.mode || '—'} />
            <ConfigRow label="Symbols" value={config?.trading.symbols?.join(', ') || '—'} />
            <ConfigRow label="Order Types" value={config?.trading.allowed_order_types?.join(', ') || '—'} />
          </div>
        </div>

        {/* Risk Config */}
        <div className="card animate-fade-in">
          <h4 className="card-title">🛡️ Risk Parameters</h4>
          <div className="config-list">
            {config?.risk && Object.entries(config.risk).map(([k, v]) => (
              <ConfigRow key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
            ))}
          </div>
        </div>

        {/* Proposal Config */}
        <div className="card animate-fade-in">
          <h4 className="card-title">📋 Proposal Settings</h4>
          <div className="config-list">
            {config?.proposal && Object.entries(config.proposal).map(([k, v]) => (
              <ConfigRow key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
            ))}
          </div>
        </div>

        {/* Agent Config */}
        <div className="card animate-fade-in">
          <h4 className="card-title">⚙️ {t('set.agent')}</h4>
          <div className="config-list">
            <ConfigRow label={t('set.enabled')} value={config?.agents.enabled ? t('common.enabled') : t('common.disabled')} />
            <ConfigRow label={t('set.max_iterations')} value={String(config?.agents.max_iterations || '—')} />
            <ConfigRow label={t('set.timeout')} value={`${config?.agents.timeout_seconds || '—'}s`} />
          </div>
        </div>

        {/* LLM Config */}
        <div className="card animate-fade-in">
          <h4 className="card-title">⚙️ {t('set.llm')}</h4>
          <div className="config-list">
            <ConfigRow label={t('set.fallback_chain')} value={config?.llm.fallback_chain?.join(' → ') || '—'} />
            <ConfigRow label={t('set.timeout')} value={String(config?.llm.temperature || '—')} />
          </div>
        </div>

        {/* Integrations */}
        <div className="card animate-fade-in">
          <h4 className="card-title">🔗 Integrations</h4>
          <div className="config-list">
            <ConfigRow label="Telegram" value={config?.notifications.telegram_enabled ? '✅ Enabled' : '❌ Disabled'} />
            <ConfigRow label="Prometheus" value={config?.monitoring.prometheus_enabled ? '✅ Enabled' : '❌ Disabled'} />
            <ConfigRow label="MFA" value={config?.mfa_enabled ? '✅ Required' : '❌ Optional'} />
          </div>
        </div>
      </div>
    </div>
  );
}

function ConfigRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="config-row">
      <span className="config-label">{label}</span>
      <span className="config-value">{value}</span>
    </div>
  );
}
