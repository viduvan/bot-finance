import { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react';
import { translations, type Lang, type TranslationKey } from './translations';

// ── Context ───────────────────────────────────────────────────────

interface I18nContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: TranslationKey, fallback?: string) => string;
  toggleLang: () => void;
}

const I18nContext = createContext<I18nContextValue>({
  lang: 'vi',
  setLang: () => {},
  t: (key) => key,
  toggleLang: () => {},
});

const STORAGE_KEY = 'acta_lang';

// ── Provider ──────────────────────────────────────────────────────

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return (saved === 'en' || saved === 'vi') ? saved : 'vi'; // default Vietnamese
  });

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    localStorage.setItem(STORAGE_KEY, l);
  }, []);

  const toggleLang = useCallback(() => {
    setLang(lang === 'vi' ? 'en' : 'vi');
  }, [lang, setLang]);

  const t = useCallback((key: TranslationKey, fallback?: string): string => {
    const entry = translations[key];
    if (!entry) return fallback ?? key;
    return entry[lang] ?? entry['en'] ?? fallback ?? key;
  }, [lang]);

  // sync html lang attr for accessibility
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  return (
    <I18nContext.Provider value={{ lang, setLang, t, toggleLang }}>
      {children}
    </I18nContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────

export function useT() {
  return useContext(I18nContext);
}

// ── Language Toggle Button (reusable) ─────────────────────────────

export function LangToggle({ className = '' }: { className?: string }) {
  const { lang, toggleLang, t } = useT();
  return (
    <button
      onClick={toggleLang}
      className={`lang-toggle ${className}`}
      title={lang === 'vi' ? 'Switch to English' : 'Chuyển sang Tiếng Việt'}
      aria-label="Toggle language"
    >
      {lang === 'vi' ? '🇬🇧 EN' : '🇻🇳 VI'}
    </button>
  );
}
