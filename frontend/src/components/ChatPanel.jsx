import React from 'react';
import { useApp } from '../AppContext';
import { titleCaseType, formatDayLabel } from '../lib/format';

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

export default function ChatPanel() {
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
  } = useApp();

  const batchId = metrics?.batch?.batch_id;
  const dayLabel = formatDayLabel(inquiryDate);
  const scopeLine = dayLabel
    ? `Summary for ${dayLabel} · Batch ${batchId || '—'}`
    : (batchId ? `This batch · ${batchId}` : 'Reconcile a batch, then ask about a day or this batch.');
  const happenedQuestion = dayLabel
    ? `What happened on ${dayLabel}?`
    : 'What happened on the latest day in this batch?';

  return (
    <div className="db-card db-chat-card" data-tour="settlement-qa">
      <h3 className="db-card-title">Settlement Q&A</h3>
      <div className="db-chat-messages">
        {(visibleChatMessages || []).map((msg) => (
          <div key={msg.id} className={`db-chat-msg db-chat-${msg.sender}`}>
            {msg.isSuggested ? (
              <div>
                <p>{msg.text}</p>
                <div className="db-chat-suggestions">
                  <button className="db-suggest-btn" onClick={() => handleSuggestedClick(happenedQuestion)} disabled={!reconciliationRun} type="button">
                    {happenedQuestion}
                  </button>
                  <button className="db-suggest-btn" onClick={() => handleSuggestedClick('Why was the settlement lower?')} disabled={!reconciliationRun} type="button">
                    Why was the settlement lower?
                  </button>
                  <button className="db-suggest-btn" onClick={() => handleSuggestedClick('Show unresolved exceptions from this batch.')} disabled={!reconciliationRun} type="button">
                    Show unresolved exceptions from this batch.
                  </button>
                  <button className="db-suggest-btn" onClick={() => handleSuggestedClick('How do I use the Exceptions page?')} disabled={!isConnected} type="button">
                    How do I use Exceptions?
                  </button>
                  <button className="db-suggest-btn" onClick={() => handleSuggestedClick('How does Store checkout land in Payments?')} disabled={!isConnected} type="button">
                    How does Store checkout work?
                  </button>
                  <button className="db-suggest-btn" onClick={() => handleSuggestedClick('Why are there exceptions?')} disabled={!reconciliationRun} type="button">
                    Why are there exceptions?
                  </button>
                  <button className="db-suggest-btn" onClick={() => handleSuggestedClick('What is my cash position for the next 7 days?')} disabled={!reconciliationRun} type="button">
                    What is my 7-day cash position?
                  </button>
                  <button className="db-suggest-btn" onClick={() => handleSuggestedClick('Which GST tax lines do not match 18% of fee?')} disabled={!reconciliationRun} type="button">
                    Which GST lines are off?
                  </button>
                  <button className="db-suggest-btn" onClick={() => handleSuggestedClick('How much money is currently unresolved?')} disabled={!reconciliationRun} type="button">
                    How much is unresolved?
                  </button>
                  <button className="db-suggest-btn" onClick={() => handleSuggestedClick('What happens if tomorrow’s ₹2 lakh settlement is delayed?')} disabled={!reconciliationRun} type="button">
                    What if ₹2L is delayed?
                  </button>
                </div>
              </div>
            ) : (
              renderFormattedChatText(msg.text, msg.groundedIn, handleGroundedTagClick)
            )}
            {msg.pendingConfirmation && (
              <div className="db-chat-suggestions">
                <button className="db-suggest-btn" type="button" onClick={() => handleConfirmChatAction(true)}>Confirm</button>
                <button className="db-suggest-btn" type="button" onClick={() => handleConfirmChatAction(false)}>Cancel</button>
              </div>
            )}
            {msg.aiAvailable === false && (
              <p className="text-dim">AI investigation temporarily unavailable. Deterministic financial results remain available.</p>
            )}
          </div>
        ))}
        {chatLoading && <div className="db-chat-msg db-chat-bot"><p>Thinking…</p></div>}
        <div ref={chatBottomRef} />
      </div>
      <p className="db-chat-scope">{scopeLine}</p>
      <p className="db-chat-disclaimer">Matching, GST and cash math are deterministic. Only this panel calls Gemini. Ask about the selected day or this batch — figures come from those records.</p>
      <div className="db-chat-suggestions db-chat-chips">
        <button className="db-suggest-btn" onClick={() => handleSuggestedClick(happenedQuestion)} disabled={!reconciliationRun || chatLoading} type="button">
          {happenedQuestion}
        </button>
        <button className="db-suggest-btn" onClick={() => handleSuggestedClick('Why was the settlement lower?')} disabled={!reconciliationRun || chatLoading} type="button">
          Why was the settlement lower?
        </button>
        <button className="db-suggest-btn" onClick={() => handleSuggestedClick('Show unresolved exceptions from this batch.')} disabled={!reconciliationRun || chatLoading} type="button">
          Show unresolved exceptions from this batch.
        </button>
      </div>
      <form className="db-chat-input-row" onSubmit={handleSendChat}>
        <input
          type="text"
          placeholder="Ask about a page, payment, GST line, or cash forecast…"
          className="db-chat-input"
          value={chatInput}
          onChange={(event) => setChatInput(event.target.value)}
          disabled={!isConnected || chatLoading}
        />
        <button type="submit" className="db-chat-send" disabled={!isConnected || !chatInput.trim() || chatLoading}>
          Send
        </button>
      </form>
    </div>
  );
}

export function ExceptionBadge({ type }) {
  const key = type || 'unclassified_discrepancy';
  return <span className={`db-issue-badge db-issue-${key}`}>{titleCaseType(key)}</span>;
}
