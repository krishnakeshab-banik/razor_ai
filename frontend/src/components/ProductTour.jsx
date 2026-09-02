import React, { useLayoutEffect, useRef, useState } from 'react';
import { useTour } from '../tour/TourContext';
import { useApp } from '../AppContext';

const PAGE_TITLES = {
  home: 'Dashboard',
  payments: 'Payments',
  reconciliation: 'Reconciliation',
  exceptions: 'Exceptions',
  cash: 'Cash',
  gst: 'GST',
  withdraw: 'Withdraw',
  audit: 'Audit logs',
  knowledge: 'Rules',
  reports: 'Reports',
  store: 'Marketplace',
};

const PAD = 6;
const TIP_WIDTH = 400;
const ARROW = 10;
const GAP = 14;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function placeTooltip(rect, tipHeight = 200) {
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
  const { dashPage, activeTab } = useApp();
  const hereLabel = activeTab === 'merchant-checkout' ? PAGE_TITLES.store : (PAGE_TITLES[dashPage] || 'this page');

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
    const height = tipRef.current?.offsetHeight || 200;
    const next = placeTooltip(highlight, height);
    setPos((prev) => (
      prev.top === next.top
      && prev.left === next.left
      && prev.width === next.width
      && prev.arrowLeft === next.arrowLeft
      && prev.side === next.side
        ? prev
        : next
    ));
    return undefined;
  }, [active, highlight, stepIndex, waiting, targetReady]);

  if (chooser) {
    return (
      <div className="tour-modal-backdrop" role="dialog" aria-labelledby="tour-chooser-title">
        <div className="tour-chooser">
          <h2 id="tour-chooser-title">Guided tour</h2>
          <p>Walk through the live Finance Controller — not a slideshow.</p>
          <button type="button" className="tour-btn tour-btn-primary" onClick={() => startTour()}>
            Full tour from Dashboard
          </button>
          {canStartFromHere && (
            <button type="button" className="tour-btn tour-btn-ghost" onClick={() => startTour({ fromCurrent: true })}>
              Start from {hereLabel}
            </button>
          )}
          <button type="button" className="tour-btn tour-btn-ghost" onClick={() => startTour({ handsOn: true })}>
            Hands-on tour (try it yourself)
          </button>
          {canStartFromHere && (
            <button type="button" className="tour-btn tour-btn-ghost" onClick={() => startTour({ handsOn: true, fromCurrent: true })}>
              Hands-on from {hereLabel}
            </button>
          )}
          <button type="button" className="tour-btn tour-btn-text" onClick={closeChooser}>Cancel</button>
        </div>
      </div>
    );
  }

  if (completed && !active) {
    return (
      <div className="tour-modal-backdrop" role="dialog" aria-labelledby="tour-complete-title">
        <div className="tour-complete">
          <h2 id="tour-complete-title">Tour complete</h2>
          <p>You have now seen the core Finance Controller workflow.</p>
          <ul className="tour-complete-list">
            <li>Monitor</li>
            <li>Reconcile</li>
            <li>Investigate</li>
            <li>Explain</li>
            <li>Resolve</li>
            <li>Audit</li>
            <li>Manage cash</li>
            <li>Withdraw</li>
            <li>Analyze finance</li>
          </ul>
          <p className="tour-complete-note">The tour did not change financial records. Try the live controls yourself.</p>
          <button type="button" className="tour-btn tour-btn-primary" onClick={goDashboard}>Explore Dashboard →</button>
          <button type="button" className="tour-btn tour-btn-text" onClick={dismissComplete}>Close</button>
        </div>
      </div>
    );
  }

  if (!active || !step) return null;

  const locked = Boolean(step.lockTarget);
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
        <button type="button" className="tour-popover-close" onClick={skip} aria-label="Skip tour">×</button>
        <div className="tour-popover-body">
          <p className="tour-popover-kicker">{step.section}</p>
          <h3 id="tour-step-title">{step.title}</h3>
          <p>{waiting ? 'Waiting for this page to load…' : step.body}</p>
          {!targetReady && !waiting && (
            <p className="tour-missing">This control is not on screen yet. Load a batch from Reconciliation, or continue.</p>
          )}
          {tryIt && step.tryPrompt && <p className="tour-try">{step.tryPrompt}</p>}
        </div>
        <div className="tour-popover-footer">
          <button type="button" className="tour-btn tour-btn-back" onClick={back} disabled={stepIndex === 0}>
            Back
          </button>
          <span className="tour-popover-count">{stepIndex + 1} of {total}</span>
          {stepIndex + 1 >= total ? (
            <button type="button" className="tour-btn tour-btn-next" onClick={finish}>Finish</button>
          ) : (
            <button type="button" className="tour-btn tour-btn-next" onClick={next}>Next</button>
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
