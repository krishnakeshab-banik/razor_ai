import React from 'react';
import { useLanguage } from '../i18n/LanguageContext';

export default function LanguageToggle({ compact = false }) {
  const { locale, setLocale, t } = useLanguage();
  return (
    <div className={`lang-toggle ${compact ? 'is-compact' : ''}`} role="group" aria-label={t('lang.label')}>
      <button
        type="button"
        className={locale === 'en' ? 'active' : ''}
        onClick={() => setLocale('en')}
        aria-pressed={locale === 'en'}
      >
        EN
      </button>
      <button
        type="button"
        className={locale === 'hi' ? 'active' : ''}
        onClick={() => setLocale('hi')}
        aria-pressed={locale === 'hi'}
      >
        हिं
      </button>
    </div>
  );
}
