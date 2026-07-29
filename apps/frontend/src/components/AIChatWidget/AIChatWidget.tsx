import { useState, useRef, useEffect } from 'react';
import { aiApi, type ChatMessage } from '../../services/api';
import { useT } from '../../i18n/I18nContext';
import './AIChatWidget.css';

interface DisplayMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  tool_calls?: { name: string; args: Record<string, unknown>; result: unknown }[];
  model?: string;
  provider?: string;
  latency_ms?: number;
  timestamp: Date;
}

const TOOL_ICONS: Record<string, string> = {
  get_ticker: '📈',
  get_positions: '💼',
  get_proposals: '📋',
  get_pnl_summary: '💰',
  get_technical_indicators: '📊',
};

const TOOL_LABELS: Record<string, string> = {
  get_ticker: 'Market Price',
  get_positions: 'Positions',
  get_proposals: 'Proposals',
  get_pnl_summary: 'P&L Summary',
  get_technical_indicators: 'Technical Indicators',
};

export default function AIChatWidget() {
  const { t } = useT();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  // Add welcome message on first open
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([{
        id: 'welcome',
        role: 'assistant',
        content: t('chat.welcome') as string,
        timestamp: new Date(),
      }]);
    }
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || loading) return;

    const userMsg: DisplayMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: msg,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      // Build history for context
      const history: ChatMessage[] = messages
        .filter(m => m.id !== 'welcome')
        .map(m => ({
          role: m.role,
          content: m.content,
        }));

      const { data } = await aiApi.chat(msg, history);

      const assistantMsg: DisplayMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.reply,
        tool_calls: data.tool_calls,
        model: data.model,
        provider: data.provider,
        latency_ms: data.latency_ms,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (e: any) {
      const errorMsg: DisplayMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: t('chat.error') as string,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    }

    setLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* Floating Toggle Button */}
      <button
        className="ai-chat-toggle"
        onClick={() => setIsOpen(!isOpen)}
        title={t('chat.title') as string}
      >
        {isOpen ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        ) : (
          <>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
              <circle cx="12" cy="10" r="1" fill="currentColor" />
              <circle cx="8" cy="10" r="1" fill="currentColor" />
              <circle cx="16" cy="10" r="1" fill="currentColor" />
            </svg>
            <span className="chat-pulse" />
          </>
        )}
      </button>

      {/* Chat Panel */}
      {isOpen && (
        <div className="ai-chat-panel">
          {/* Header */}
          <div className="ai-chat-header">
            <div className="ai-chat-header-left">
              <div className="ai-chat-avatar">🤖</div>
              <div className="ai-chat-header-info">
                <h4>{t('chat.title')}</h4>
                <span>Gemini 3.6 Flash · ACTA</span>
              </div>
            </div>
            <button className="ai-chat-close" onClick={() => setIsOpen(false)}>✕</button>
          </div>

          {/* Messages */}
          <div className="ai-chat-messages">
            {messages.map((msg) => (
              <div key={msg.id} className={`ai-msg ${msg.role}`}>
                {/* Tool Calls (shown before assistant reply) */}
                {msg.tool_calls && msg.tool_calls.length > 0 && (
                  <div className="ai-tool-calls">
                    {msg.tool_calls.map((tc, i) => (
                      <div key={i} className="ai-tool-call">
                        <span className="tool-icon">{TOOL_ICONS[tc.name] || '🔧'}</span>
                        <span className="tool-name">{TOOL_LABELS[tc.name] || tc.name}</span>
                        {tc.args && Object.keys(tc.args).length > 0 && (
                          <span className="tool-args">({Object.values(tc.args).join(', ')})</span>
                        )}
                        <span className="tool-check">✓</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Message Bubble */}
                <div className="ai-msg-bubble">
                  {msg.role === 'assistant' ? (
                    <div dangerouslySetInnerHTML={{ __html: formatMarkdown(msg.content) }} />
                  ) : (
                    msg.content
                  )}
                </div>

                {/* Meta */}
                {msg.role === 'assistant' && msg.model && (
                  <div className="ai-msg-meta">
                    {msg.model} · {msg.latency_ms ? `${(msg.latency_ms / 1000).toFixed(1)}s` : ''}
                  </div>
                )}
              </div>
            ))}

            {/* Thinking Indicator */}
            {loading && (
              <div className="ai-thinking">
                <div className="thinking-dots">
                  <span /><span /><span />
                </div>
                {t('chat.thinking')}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="ai-chat-input">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('chat.placeholder') as string}
              disabled={loading}
            />
            <button
              className="ai-send-btn"
              onClick={handleSend}
              disabled={!input.trim() || loading}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}

/** Simple markdown to HTML converter for chat messages */
function formatMarkdown(text: string): string {
  return text
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Unordered lists
    .replace(/^[-•]\s+(.+)$/gm, '<li>$1</li>')
    // Numbered lists
    .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
    // Line breaks
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
    // Wrap in paragraphs
    .replace(/^(.+)$/s, '<p>$1</p>');
}
