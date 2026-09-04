import React from 'react';
import { Maximize2 } from 'lucide-react';
import { useApp } from '../AppContext';
import { titleCaseType, formatDayLabel } from '../lib/format';
import ChatToolVisual, { captionFromAnswer } from './ChatToolVisual';
import { useLanguage } from '../i18n/LanguageContext';

function renderFormattedChatText(text, groundedIds = [], onTagClick) {
  const cleaned = String(text || '').replace(/\*\*(.*?)\*\*/g, '$1');
  if (!groundedIds || groundedIds.length === 0) {
    return <p>{cleaned}</p>;
  }
  const sortedIds = [...groundedIds].sort((a, b) => String(b).length - String(a).length);
  const parts = [];
  let cursor = 0;
  const matches = [];
  sortedIds.forEach((id) => {
    const index = cleaned.indexOf(id);
    if (index !== -1) matches.push({ id, index });
  });
  matches.sort((a, b) => a.index - b.index);
  if (!matches.length) return <p>{cleaned}</p>;
  matches.forEach((match, idx) => {
    if (match.index > cursor) {
      parts.push(<span key={`txt-${idx}`}>{cleaned.slice(cursor, match.index)}</span>);
    }
    parts.push(
      <button key={`tag-${match.id}-${idx}`} className="grounded-tag" onClick={() => onTagClick(match.id)} type="button">
        {match.id}
      </button>,
    );
    cursor = match.index + String(match.id).length;
  });
  if (cursor < cleaned.length) parts.push(<span key="txt-trail">{cleaned.slice(cursor)}</span>);
  return <p>{parts}</p>;
}

export default function ChatPanel({ variant = 'compact' }) {
  const {
    visibleChatMessages,
    chatLoading,
    chatBottomRef,
    chatInput,
    setChatInput,
    reconciliationRun,
    isConnected,
    handleSendChat,
    handleSuggestedClick,
    handleGroundedTagClick,
    handleConfirmChatAction,
    inquiryDate,
    metrics,
    setDashPage,
  } = useApp();
  const { t } = useLanguage();
  const fullView = variant === 'full';

  const batchId = metrics?.batch?.batch_id;
  const dayLabel = formatDayLabel(inquiryDate);
  const scopeLine = dayLabel
    ? t('chat.scopeDay', { day: dayLabel, batch: batchId || '—' })
    : (batchId ? t('chat.scopeBatch', { batch: batchId }) : t('chat.scopeEmpty'));
  const happenedQuestion = dayLabel
    ? t('chat.qHappenedDay', { day: dayLabel })
    : t('chat.qHappenedLatest');

  const suggestions = [
    { q: happenedQuestion, needBatch: true, label: happenedQuestion },
    { q: t('chat.qLower'), needBatch: true, label: t('chat.qLower') },
    { q: t('chat.qUnresolved'), needBatch: true, label: t('chat.qUnresolved') },
    { q: t('chat.qExceptions'), needBatch: false, label: t('chat.qExceptions') },
    { q: t('chat.qStore'), needBatch: false, label: t('chat.qStore') },
    { q: t('chat.qWhyExc'), needBatch: true, label: t('chat.qWhyExc') },
    { q: t('chat.qCash'), needBatch: true, label: t('chat.qCash') },
    { q: t('chat.qGst'), needBatch: true, label: t('chat.qGst') },
    { q: t('chat.qUnresolvedAmt'), needBatch: true, label: t('chat.qUnresolvedAmt') },
    { q: t('chat.qDelay'), needBatch: true, label: t('chat.qDelay') },
  ];

  return (
    <div className={`db-card db-chat-card ${fullView ? 'db-chat-card-full' : ''}`} data-tour={fullView ? undefined : 'settlement-qa'}>
      {fullView ? null : (
        <div className="db-card-title-row">
          <h3 className="db-card-title">{t('chat.title')}</h3>
          <button
            className="db-chat-expand"
            type="button"
            aria-label={t('chat.expand')}
            title={t('chat.expand')}
            onClick={() => setDashPage('chat')}
          >
            <Maximize2 size={16} strokeWidth={2.25} />
          </button>
        </div>
      )}
      <div className="db-chat-messages">
        {(visibleChatMessages || []).map((msg) => {
          const showVisual = fullView && msg.sender === 'bot' && !msg.isSuggested && msg.toolUsed && msg.toolPayload != null;
          return (
          <div key={msg.id} className={`db-chat-msg db-chat-${msg.sender}${showVisual ? ' db-chat-bot-visual' : ''}`}>
            {msg.isSuggested ? (
              <div>
                <p>{t('chat.intro')}</p>
                <div className="db-chat-suggestions">
                  {suggestions.map((item) => (
                    <button
                      key={item.q}
                      className="db-suggest-btn"
                      onClick={() => handleSuggestedClick(item.q)}
                      disabled={item.needBatch ? !reconciliationRun : !isConnected}
                      type="button"
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : showVisual ? (
              <>
                <p className="db-chat-caption">{captionFromAnswer(msg.text)}</p>
                <ChatToolVisual toolUsed={msg.toolUsed} payload={msg.toolPayload} />
              </>
            ) : (
              renderFormattedChatText(msg.text, msg.groundedIn, handleGroundedTagClick)
            )}
            {msg.pendingConfirmation && (
              <div className="db-chat-suggestions">
                <button className="db-suggest-btn" type="button" onClick={() => handleConfirmChatAction(true)}>{t('chat.confirm')}</button>
                <button className="db-suggest-btn" type="button" onClick={() => handleConfirmChatAction(false)}>{t('chat.cancel')}</button>
              </div>
            )}
            {msg.aiAvailable === false && (
              <p className="text-dim">{t('chat.aiDown')}</p>
            )}
          </div>
          );
        })}
        {chatLoading && <div className="db-chat-msg db-chat-bot"><p>{t('chat.thinking')}</p></div>}
        <div ref={chatBottomRef} />
      </div>
      {fullView ? null : (
        <>
          <p className="db-chat-scope">{scopeLine}</p>
          <p className="db-chat-disclaimer">{t('chat.disclaimer')}</p>
          <div className="db-chat-suggestions db-chat-chips">
            {suggestions.slice(0, 3).map((item) => (
              <button
                key={`chip-${item.q}`}
                className="db-suggest-btn"
                onClick={() => handleSuggestedClick(item.q)}
                disabled={!reconciliationRun || chatLoading}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </>
      )}
      <form className="db-chat-input-row" onSubmit={handleSendChat}>
        <input
          type="text"
          placeholder={t('chat.placeholder')}
          className="db-chat-input"
          value={chatInput}
          onChange={(event) => setChatInput(event.target.value)}
          disabled={!isConnected || chatLoading}
        />
        <button type="submit" className="db-chat-send" disabled={!isConnected || !chatInput.trim() || chatLoading}>
          {t('chat.send')}
        </button>
      </form>
    </div>
  );
}

export function ExceptionBadge({ type }) {
  const key = type || 'unclassified_discrepancy';
  return <span className={`db-issue-badge db-issue-${key}`}>{titleCaseType(key)}</span>;
}
