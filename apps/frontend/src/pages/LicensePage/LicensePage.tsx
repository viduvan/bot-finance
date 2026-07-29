import { useEffect, useState } from 'react';
import { systemApi } from '../../services/api';
import { useT } from '../../i18n/I18nContext';
import './LicensePage.css';

const MIT_LICENSE = `MIT License

Copyright (c) 2026 ChimSe

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.`;

const TECH_STACK = [
  { icon: '⚛️', name: 'React', desc: 'UI Framework' },
  { icon: '📘', name: 'TypeScript', desc: 'Type Safety' },
  { icon: '⚡', name: 'Vite', desc: 'Build Tool' },
  { icon: '🐍', name: 'FastAPI', desc: 'Backend API' },
  { icon: '🤖', name: 'Gemini AI', desc: 'LLM Provider' },
  { icon: '📊', name: 'Binance', desc: 'Market Data' },
  { icon: '🐘', name: 'PostgreSQL', desc: 'Database' },
  { icon: '🔴', name: 'Redis', desc: 'Cache & Queue' },
  { icon: '📈', name: 'Prometheus', desc: 'Monitoring' },
  { icon: '✈️', name: 'Telegram', desc: 'Notifications' },
  { icon: '🔐', name: 'JWT + MFA', desc: 'Security' },
  { icon: '🐳', name: 'Docker', desc: 'Deployment' },
];

interface LicenseInfo {
  app_name: string;
  version: string;
  license: string;
  copyright: string;
  gemini_model: string;
  gemini_status: string;
  fallback_chain: string[];
  rate_limits: { rpm: number; tpm: number; rpd: number };
}

export default function LicensePage() {
  const { t } = useT();
  const [info, setInfo] = useState<LicenseInfo | null>(null);
  const [config, setConfig] = useState<any>(null);
  const [testResult, setTestResult] = useState<{ status: string; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [licenseRes, configRes] = await Promise.allSettled([
          systemApi.license(),
          systemApi.config(),
        ]);
        if (licenseRes.status === 'fulfilled') setInfo(licenseRes.value.data);
        if (configRes.status === 'fulfilled') setConfig(configRes.value.data);
      } catch { /* silent */ }
    })();
  }, []);

  const handleTestGemini = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const { data } = await systemApi.aiStatus();
      setTestResult({ status: 'success', message: `✅ Connected — Model: ${data.model} | Provider: ${data.provider}` });
    } catch (e: any) {
      setTestResult({ status: 'error', message: `❌ ${e.response?.data?.detail || e.message}` });
    }
    setTesting(false);
  };

  const version = info?.version || config?.version || '0.1.0';
  const fallbackChain = info?.fallback_chain || config?.llm?.fallback_chain || ['gemini', 'openai', 'ollama'];
  const geminiModel = info?.gemini_model || 'gemini-3.6-flash';
  const geminiStatus = info?.gemini_status || 'unknown';

  return (
    <div className="page-container license-page stagger">
      {/* Hero Header */}
      <div className="license-hero animate-fade-in">
        <div className="license-hero-logo">
          <svg viewBox="0 0 32 32" fill="none">
            <path d="M10 24L16 10L22 24" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
            <path d="M12.5 19H19.5" stroke="white" strokeWidth="2" strokeLinecap="round" />
            <circle cx="16" cy="14.5" r="1.5" fill="white" />
          </svg>
        </div>
        <h1>ACTA Trading System</h1>
        <div className="license-hero-version">
          {t('lic.version')}: <strong>v{version}</strong> · {t('lic.build')}: 2026.07
        </div>
        <div className="license-hero-badges">
          <span className="license-badge mit">📄 MIT License</span>
          <span className="license-badge gemini"> {geminiModel}</span>
          <span className={`license-badge ${geminiStatus === 'connected' ? 'status-ok' : 'status-err'}`}>
            {geminiStatus === 'connected' ? '🟢' : '🔴'} Gemini {geminiStatus}
          </span>
        </div>
      </div>

      <div className="license-grid">
        {/* MIT License */}
        <div className="license-text-card license-grid-full animate-fade-in">
          <h3>📄 {t('lic.license_title')}</h3>
          <div className="license-text">{MIT_LICENSE}</div>
        </div>

        {/* Technology Stack */}
        <div className="license-text-card animate-fade-in">
          <h3>🛠️ {t('lic.tech_stack')}</h3>
          <div className="tech-stack-grid">
            {TECH_STACK.map((tech) => (
              <div key={tech.name} className="tech-item">
                <span className="tech-icon">{tech.icon}</span>
                <div className="tech-info">
                  <div className="tech-name">{tech.name}</div>
                  <div className="tech-desc">{tech.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Gemini API Info */}
        <div className="license-text-card animate-fade-in">
          <h3>🤖 {t('lic.gemini_api')}</h3>
          <div className="model-info">
            <div className="model-row">
              <span className="model-label">{t('lic.model')}</span>
              <span className="model-value">{geminiModel}</span>
            </div>
            <div className="model-row">
              <span className="model-label">{t('lic.tier')}</span>
              <span className="model-value">Free Tier</span>
            </div>
            <div className="model-row">
              <span className="model-label">{t('lic.fallback_chain')}</span>
              <span className="model-value chain">
                {fallbackChain.map((p: string, i: number) => (
                  <span key={p}>
                    {i > 0 && <span className="chain-arrow">→</span>}
                    <span className="chain-provider">{p}</span>
                  </span>
                ))}
              </span>
            </div>
          </div>

          {/* Rate Limits */}
          <div style={{ marginTop: 16 }}>
            <div className="api-status-grid">
              <div className="api-stat">
                <div className="api-stat-value">{info?.rate_limits?.rpm ?? 60}</div>
                <div className="api-stat-label">RPM</div>
                <div className="api-stat-sub">Req/Min</div>
              </div>
              <div className="api-stat">
                <div className="api-stat-value">{info?.rate_limits?.tpm ? `${(info.rate_limits.tpm / 1000).toFixed(0)}K` : '100K'}</div>
                <div className="api-stat-label">TPM</div>
                <div className="api-stat-sub">Tokens/Min</div>
              </div>
              <div className="api-stat">
                <div className="api-stat-value">{info?.rate_limits?.rpd ?? 100}</div>
                <div className="api-stat-label">RPD</div>
                <div className="api-stat-sub">Req/Day</div>
              </div>
            </div>
          </div>

          {/* Test Connection */}
          <div style={{ marginTop: 16 }}>
            <button onClick={handleTestGemini} disabled={testing} className="gemini-test-btn">
              {testing ? <><span className="spinner-sm" /> {t('common.loading')}</> : <>🔌 {t('lic.test_connection')}</>}
            </button>
            {testResult && (
              <div className={`gemini-test-result ${testResult.status}`}>{testResult.message}</div>
            )}
          </div>
        </div>

        {/* Credits */}
        <div className="license-text-card license-grid-full animate-fade-in">
          <div className="credits-section">
            <div className="credits-copyright">Copyright © 2026 ChimSe</div>
            <div>ACTA — Human-in-the-Loop Multi-Agent Crypto Trading Advisory System</div>
            <div style={{ marginTop: 8, fontSize: '0.75rem' }}>
              {t('lic.powered_by')} Google Gemini AI · Binance API · FastAPI · React
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
