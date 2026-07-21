import { useState, type FormEvent } from 'react';
import { useAuthStore } from '../../stores/authStore';
import './LoginPage.css';

export default function LoginPage() {
  const { login, isLoading, error, mfaRequired, clearError } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    clearError();
    await login({ email, password, mfa_code: mfaCode || undefined });
  };

  return (
    <div className="login-page">
      {/* Background Effects */}
      <div className="login-bg">
        <div className="login-bg-grid" />
        <div className="login-bg-glow login-bg-glow-1" />
        <div className="login-bg-glow login-bg-glow-2" />
        <div className="login-bg-glow login-bg-glow-3" />
      </div>

      <div className="login-container animate-scale-in">
        {/* Logo & Title */}
        <div className="login-header">
          <div className="login-logo">
            <div className="login-logo-icon">
              <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="40" height="40" rx="10" fill="url(#logo-gradient)" />
                <path d="M12 28L20 12L28 28" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M15 22H25" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="20" cy="17" r="2" fill="white" />
                <defs>
                  <linearGradient id="logo-gradient" x1="0" y1="0" x2="40" y2="40">
                    <stop stopColor="#3b82f6" />
                    <stop offset="1" stopColor="#8b5cf6" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <h1 className="login-title">
              <span className="gradient-text">ACTA</span>
            </h1>
          </div>
          <p className="login-subtitle">Multi-Agent Crypto Trading Advisory</p>
          <div className="login-badge">
            <span className="status-dot online" />
            <span>PAPER TRADING</span>
          </div>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="login-form stagger">
          {error && (
            <div className="login-error animate-fade-in">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
                <path d="M8 5V8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                <circle cx="8" cy="11" r="0.75" fill="currentColor" />
              </svg>
              {error}
            </div>
          )}

          <div className="input-group animate-fade-in">
            <label htmlFor="email" className="input-label">Email</label>
            <input
              id="email"
              type="email"
              className="input"
              placeholder="admin@acta.local"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              autoComplete="email"
            />
          </div>

          <div className="input-group animate-fade-in">
            <label htmlFor="password" className="input-label">Password</label>
            <div className="password-wrapper">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                className="input"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={12}
                autoComplete="current-password"
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                aria-label="Toggle password visibility"
              >
                {showPassword ? '🔒' : '👁️'}
              </button>
            </div>
          </div>

          {mfaRequired && (
            <div className="input-group animate-slide-up">
              <label htmlFor="mfa" className="input-label">
                <span className="mfa-label">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="2" y="6" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
                    <path d="M4.5 6V4.5a2.5 2.5 0 015 0V6" stroke="currentColor" strokeWidth="1.2" />
                  </svg>
                  Authenticator Code
                </span>
              </label>
              <input
                id="mfa"
                type="text"
                className="input mfa-input"
                placeholder="000000"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength={6}
                pattern="\d{6}"
                autoComplete="one-time-code"
                autoFocus
              />
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary btn-lg login-submit"
            disabled={isLoading || !email || !password}
          >
            {isLoading ? (
              <>
                <div className="spinner" />
                Authenticating...
              </>
            ) : mfaRequired ? (
              'Verify & Sign In'
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="login-footer">
          <p>Agents analyze. Agents advise. <strong>Humans decide.</strong></p>
        </div>
      </div>
    </div>
  );
}
