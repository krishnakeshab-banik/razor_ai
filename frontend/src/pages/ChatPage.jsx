import React from 'react';
import ChatPanel from '../components/ChatPanel';
import { useLanguage } from '../i18n/LanguageContext';

export default function ChatPage() {
  const { t } = useLanguage();
  return (
    <div className="db-page db-chat-page">
      <div>
        <h2 className="db-page-title">{t('chat.title')}</h2>
        <p className="db-page-sub">{t('chat.pageSub')}</p>
      </div>
      <ChatPanel variant="full" />
    </div>
  );
}
