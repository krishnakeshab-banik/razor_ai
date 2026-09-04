import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { STRINGS } from './strings';

export const LANG_KEY = 'razorai-lang';

let runtimeLocale = 'en';

export function getLocale() {
  return runtimeLocale;
}

function readSavedLang() {
  try {
    const raw = localStorage.getItem(LANG_KEY);
    return raw === 'hi' ? 'hi' : 'en';
  } catch {
    return 'en';
  }
}

const LanguageContext = createContext(null);

export function useLanguage() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error('useLanguage must be used inside LanguageProvider');
  return value;
}

function lookup(dict, key) {
  return key.split('.').reduce((node, part) => (node == null ? undefined : node[part]), dict);
}

export function LanguageProvider({ children }) {
  const [locale, setLocaleState] = useState(readSavedLang);

  useEffect(() => {
    runtimeLocale = locale;
    document.documentElement.lang = locale === 'hi' ? 'hi' : 'en';
    try {
      localStorage.setItem(LANG_KEY, locale);
    } catch {
      /* ignore quota */
    }
  }, [locale]);

  const setLocale = useCallback((next) => {
    const lang = next === 'hi' ? 'hi' : 'en';
    runtimeLocale = lang;
    setLocaleState(lang);
  }, []);

  const t = useCallback((key, vars) => {
    const dict = STRINGS[locale] || STRINGS.en;
    let text = lookup(dict, key);
    if (typeof text !== 'string') text = lookup(STRINGS.en, key);
    if (typeof text !== 'string') return key;
    if (!vars) return text;
    return text.replace(/\{(\w+)\}/g, (_, name) => (vars[name] == null ? '' : String(vars[name])));
  }, [locale]);

  const value = useMemo(() => ({ locale, setLocale, t, isHindi: locale === 'hi' }), [locale, setLocale, t]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}
