import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Mic, MicOff } from 'lucide-react';
import { LIFECYCLE_STAGES } from '../tour/steps';
import { useTour } from '../tour/TourContext';
import { useApp } from '../AppContext';
import { useLanguage } from '../i18n/LanguageContext';
import { localizeTourStep } from '../i18n/tourHi';
import { speakText, stopSpeech, speechSupported } from '../i18n/speech';

const VOICE_KEY = 'razorai-tour-voice';

function readVoicePref() {
  try {
    return sessionStorage.getItem(VOICE_KEY) === '1';
  } catch {
    return false;
  }
}

function writeVoicePref(on) {
  try {
    sessionStorage.setItem(VOICE_KEY, on ? '1' : '0');
  } catch {
    /* ignore */
  }
}

function stepNarration(step, waiting, t) {
  if (waiting) return t('tour.waiting');
  return [
    step.title,
    step.body,
    step.meaning ? `${t('tour.meaning')}. ${step.meaning}` : '',
    step.action ? `${t('tour.action')}. ${step.action}` : '',
  ].filter(Boolean).join('. ');
}

const PAD = 6;
const TIP_WIDTH = 420;
const ARROW = 10;
const GAP = 14;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function placeTooltip(rect, tipHeight = 280) {
  const width = Math.min(TIP_WIDTH, window.innerWidth - 32);
  if (!rect) {
    return {
      top: Math.max(24, (window.innerHeight - tipHeight) / 2),
      left: Math.max(16, (window.innerWidth - width) / 2),
      width,
      arrowLeft: width / 2,
      side: 'bottom',
    };
  }
  const centerX = rect.left + rect.width / 2;
  const left = clamp(centerX - width / 2, 16, window.innerWidth - width - 16);
  const spaceBelow = window.innerHeight - rect.bottom;
  const spaceAbove = rect.top;
  const need = tipHeight + GAP + ARROW;
  const side = spaceBelow >= need || spaceBelow >= spaceAbove ? 'bottom' : 'top';
  const top = side === 'bottom'
    ? clamp(rect.bottom + GAP, 16, window.innerHeight - 24)
    : clamp(rect.top - tipHeight - GAP, 16, window.innerHeight - 24);
  return {
    top,
    left,
    width,
    arrowLeft: clamp(centerX - left, 22, width - 22),
    side,
  };
}

export default function ProductTour() {
  const {
    active, step, stepIndex, total, tryIt, waiting, targetReady, completed, chooser, rect,
    next, back, skip, finish, startTour, closeChooser, goDashboard, dismissComplete, canStartFromHere,
  } = useTour();
  const { dashPage, activeTab, merchantView } = useApp();
  const { t, locale } = useLanguage();
  const hereKey = activeTab === 'merchant-checkout'
    ? (merchantView || 'store')
    : (dashPage || 'home');
  const hereLabel = t(`pagesShort.${hereKey}`) || t('pagesShort.thisPage');
  const visibleStep = localizeTourStep(step, locale);
  const canSpeak = speechSupported();
  const [voiceOn, setVoiceOn] = useState(readVoicePref);

  const tipRef = useRef(null);
  const [pos, setPos] = useState(() => placeTooltip(null));

  const highlight = rect && targetReady ? {
    top: Math.max(0, rect.top - PAD),
    left: Math.max(0, rect.left - PAD),
    width: Math.max(24, rect.width + PAD * 2),
    height: Math.max(24, rect.height + PAD * 2),
  } : null;

  useLayoutEffect(() => {
    if (!active) return undefined;
    const height = tipRef.current?.offsetHeight || 280;
    const nextPos = placeTooltip(highlight, height);
    setPos((prev) => (
      prev.top === nextPos.top
      && prev.left === nextPos.left
      && prev.width === nextPos.width
      && prev.arrowLeft === nextPos.arrowLeft
      && prev.side === nextPos.side
        ? prev
        : nextPos
    ));
    return undefined;
  }, [active, highlight, stepIndex, waiting, targetReady, locale]);

  useEffect(() => {
    if (!active || !visibleStep || !voiceOn || !canSpeak) {
      stopSpeech();
      return undefined;
    }
    speakText(stepNarration(visibleStep, waiting, t), locale);
    return () => stopSpeech();
  }, [active, visibleStep?.id, stepIndex, waiting, voiceOn, locale, canSpeak, t]);

  useEffect(() => () => stopSpeech(), []);

  const toggleVoice = () => {
    setVoiceOn((prev) => {
      const nextOn = !prev;
      writeVoicePref(nextOn);
      if (!nextOn) stopSpeech();
      return nextOn;
    });
  };

  const handleSkip = () => { stopSpeech(); skip(); };
  const handleFinish = () => { stopSpeech(); finish(); };
  const handleCloseChooser = () => { stopSpeech(); closeChooser(); };
  const handleDismissComplete = () => { stopSpeech(); dismissComplete(); };

  if (chooser) {
    return (
      <div className="tour-modal-backdrop" role="dialog" aria-labelledby="tour-chooser-title">
        <div className="tour-chooser">
          <h2 id="tour-chooser-title">{t('tour.chooserTitle')}</h2>
          <p>{t('tour.chooserBody')}</p>
          <button type="button" className="tour-btn tour-btn-primary" onClick={() => startTour()}>
            {t('tour.full')}
          </button>
          {canStartFromHere && (
            <button type="button" className="tour-btn tour-btn-ghost" onClick={() => startTour({ fromCurrent: true })}>
              {t('tour.fromHere', { page: hereLabel })}
            </button>
          )}
          <button type="button" className="tour-btn tour-btn-ghost" onClick={() => startTour({ handsOn: true })}>
            {t('tour.handsOn')}
          </button>
          {canStartFromHere && (
            <button type="button" className="tour-btn tour-btn-ghost" onClick={() => startTour({ handsOn: true, fromCurrent: true })}>
              {t('tour.handsOnHere', { page: hereLabel })}
            </button>
          )}
          <button type="button" className="tour-btn tour-btn-text" onClick={handleCloseChooser}>{t('tour.cancel')}</button>
        </div>
      </div>
    );
  }

  if (completed && !active) {
    return (
      <div className="tour-modal-backdrop" role="dialog" aria-labelledby="tour-complete-title">
        <div className="tour-complete">
          <h2 id="tour-complete-title">{t('tour.completeTitle')}</h2>
          <p>{t('tour.completeBody')}</p>
          <ul className="tour-complete-list">
            {LIFECYCLE_STAGES.map((stage) => (
              <li key={stage}>{t(`lifecycle.${stage}`)}</li>
            ))}
          </ul>
          <p className="tour-complete-note">{t('tour.completeNote')}</p>
          <button type="button" className="tour-btn tour-btn-primary" onClick={goDashboard}>{t('tour.explore')}</button>
          <button type="button" className="tour-btn tour-btn-text" onClick={handleDismissComplete}>{t('tour.close')}</button>
        </div>
      </div>
    );
  }

  if (!active || !visibleStep) return null;

  const locked = Boolean(visibleStep.lockTarget);
  const progress = ((stepIndex + 1) / total) * 100;

  return (
    <div className="tour-root" aria-live="polite">
      {highlight && !locked && (
        <>
          <div className="tour-shade" style={{ top: 0, left: 0, right: 0, height: highlight.top }} />
          <div className="tour-shade" style={{ top: highlight.top, left: 0, width: highlight.left, height: highlight.height }} />
          <div className="tour-shade" style={{ top: highlight.top, left: highlight.left + highlight.width, right: 0, height: highlight.height }} />
          <div className="tour-shade" style={{ top: highlight.top + highlight.height, left: 0, right: 0, bottom: 0 }} />
        </>
      )}
      {(!highlight || locked) && <div className="tour-shade tour-shade-full" />}
      {highlight && (
        <div
          className={`tour-spotlight ${locked ? 'tour-spotlight-locked' : ''}`}
          style={{
            top: highlight.top,
            left: highlight.left,
            width: highlight.width,
            height: highlight.height,
          }}
        />
      )}

      <div
        ref={tipRef}
        className={`tour-popover tour-popover-${pos.side}`}
        style={{ top: pos.top, left: pos.left, width: pos.width }}
        role="dialog"
        aria-labelledby="tour-step-title"
      >
        <div className="tour-popover-progress" aria-hidden="true">
          <span style={{ width: `${progress}%` }} />
        </div>
        <button type="button" className="tour-popover-close" onClick={handleSkip} aria-label={t('tour.skip')}>×</button>
        <div className="tour-popover-body">
          <p className="tour-popover-kicker">{visibleStep.section}</p>
          <h3 id="tour-step-title">{visibleStep.title}</h3>
          <p>{waiting ? t('tour.waiting') : visibleStep.body}</p>
          {!waiting && visibleStep.meaning && (
            <div className="tour-callout">
              <strong>{t('tour.meaning')}</strong>
              <p>{visibleStep.meaning}</p>
            </div>
          )}
          {!waiting && visibleStep.action && (
            <div className="tour-callout tour-callout-action">
              <strong>{t('tour.action')}</strong>
              <p>{visibleStep.action}</p>
            </div>
          )}
          {!targetReady && !waiting && (
            <p className="tour-missing">{t('tour.missing')}</p>
          )}
          {tryIt && visibleStep.tryPrompt && <p className="tour-try">{visibleStep.tryPrompt}</p>}
          {visibleStep.lifecycle && (
            <ol className="tour-lifecycle" aria-label="Close loop">
              {LIFECYCLE_STAGES.map((stage) => (
                <li key={stage} className={visibleStep.lifecycle === stage ? 'is-active' : ''}>{t(`lifecycle.${stage}`)}</li>
              ))}
            </ol>
          )}
        </div>
        {canSpeak && (
          <div className="tour-voice-row">
            <button
              type="button"
              className={`tour-voice ${voiceOn ? 'is-on' : ''}`}
              onClick={toggleVoice}
              aria-pressed={voiceOn}
              title={t('tour.voiceHint')}
            >
              {voiceOn ? <Mic size={14} strokeWidth={2.25} /> : <MicOff size={14} strokeWidth={2.25} />}
              {voiceOn ? t('tour.voiceOn') : t('tour.voiceOff')}
            </button>
          </div>
        )}
        <div className="tour-popover-footer">
          <button type="button" className="tour-btn tour-btn-back" onClick={back} disabled={stepIndex === 0}>
            {t('tour.back')}
          </button>
          <span className="tour-popover-count">{t('tour.of', { current: stepIndex + 1, total })}</span>
          {stepIndex + 1 >= total ? (
            <button type="button" className="tour-btn tour-btn-next" onClick={handleFinish}>{t('tour.finish')}</button>
          ) : (
            <button type="button" className="tour-btn tour-btn-next" onClick={next}>{t('tour.next')}</button>
          )}
        </div>
        <span className="tour-popover-brand">Razor-AI</span>
        {highlight && (
          <span
            className="tour-popover-arrow"
            style={{ left: pos.arrowLeft }}
            aria-hidden="true"
          />
        )}
      </div>
    </div>
  );
}
