import React, {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from 'react';
import { useApp } from '../AppContext';
import { firstStepIndexForPage, STORAGE_KEY, TOUR_STEPS } from './steps';

const TourContext = import.meta.hot?.data?.TourContext ?? createContext(null);
if (import.meta.hot) import.meta.hot.data.TourContext = TourContext;

export function useTour() {
  const value = useContext(TourContext);
  if (!value) throw new Error('useTour must be used inside TourProvider');
  return value;
}

function readSaved() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function waitForTarget(target, timeoutMs = 2800) {
  return new Promise((resolve) => {
    const started = Date.now();
    const tick = () => {
      const node = document.querySelector(`[data-tour="${target}"]`);
      if (node) {
        resolve(node);
        return;
      }
      if (Date.now() - started >= timeoutMs) {
        resolve(null);
        return;
      }
      window.requestAnimationFrame(tick);
    };
    tick();
  });
}

export function TourProvider({ children }) {
  const {
    activeTab, setActiveTab, dashPage, setDashPage, setMerchantView, setSidebarOpen,
    exceptions, setSelectedExcId, handleExplainDifference, reconciliationRun,
  } = useApp();

  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [tryIt, setTryIt] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [targetReady, setTargetReady] = useState(true);
  const [completed, setCompleted] = useState(false);
  const [chooser, setChooser] = useState(false);
  const [rect, setRect] = useState(null);

  const appRef = useRef({});
  appRef.current = {
    activeTab, dashPage, exceptions, reconciliationRun,
    setActiveTab, setDashPage, setMerchantView, setSidebarOpen,
    setSelectedExcId, handleExplainDifference,
  };

  const liveRef = useRef({ active: false, stepIndex: 0, tryIt: false });
  liveRef.current = { active, stepIndex, tryIt, waiting };

  const persist = useCallback((patch) => {
    const next = {
      active: liveRef.current.active,
      stepIndex: liveRef.current.stepIndex,
      tryIt: liveRef.current.tryIt,
      completed: false,
      ...patch,
    };
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* ignore quota */
    }
  }, []);

  const goToStepPage = useCallback((item) => {
    const app = appRef.current;
    app.setSidebarOpen(false);
    if (item.tab === 'merchant-checkout') {
      app.setMerchantView('store');
      app.setActiveTab('merchant-checkout');
      return;
    }
    app.setActiveTab('dashboard');
    app.setDashPage(item.page);
  }, []);

  const measure = useCallback((target) => {
    const node = document.querySelector(`[data-tour="${target}"]`);
    if (!node) {
      setRect(null);
      return null;
    }
    node.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    const box = node.getBoundingClientRect();
    setRect({
      top: box.top,
      left: box.left,
      width: box.width,
      height: box.height,
      bottom: box.bottom,
      right: box.right,
    });
    return node;
  }, []);

  const applyIndex = useCallback(async (index, direction = 1) => {
    if (index < 0) return;
    if (index >= TOUR_STEPS.length) {
      liveRef.current = { ...liveRef.current, active: false };
      setActive(false);
      setCompleted(true);
      setRect(null);
      persist({ active: false, completed: true });
      appRef.current.setActiveTab('dashboard');
      appRef.current.setDashPage('home');
      return;
    }

    const item = TOUR_STEPS[index];
    if (!item) return;
    const tryHandsOn = liveRef.current.tryIt;
    goToStepPage(item);
    setWaiting(true);
    setTargetReady(true);
    setStepIndex(index);
    liveRef.current = { ...liveRef.current, stepIndex: index, active: true, waiting: true };
    persist({ active: true, stepIndex: index });

    if (item.safeSelect && !tryHandsOn && appRef.current.exceptions?.length) {
      appRef.current.setSelectedExcId(appRef.current.exceptions[0].payment_id);
    }

    await new Promise((resolve) => window.setTimeout(resolve, 80));
    if ((item.id === 'exception-explain' || item.id === 'exception-resolve') && appRef.current.exceptions?.length) {
      appRef.current.setSelectedExcId(appRef.current.exceptions[0].payment_id);
      window.dispatchEvent(new CustomEvent('razor-open-exception-panel', {
        detail: item.id === 'exception-resolve' ? 'actions' : 'details',
      }));
    }

    await new Promise((resolve) => window.setTimeout(resolve, 60));
    const node = await waitForTarget(item.target);
    if (!node) {
      if (item.skipIfMissing) {
        await applyIndex(index + direction, direction);
        return;
      }
      setRect(null);
      setTargetReady(false);
      setWaiting(false);
      liveRef.current = { ...liveRef.current, waiting: false };
      return;
    }

    measure(item.target);
    setTargetReady(true);
    setWaiting(false);
    liveRef.current = { ...liveRef.current, waiting: false };

    if (item.id === 'exception-explain' && !tryHandsOn && appRef.current.exceptions?.length) {
      appRef.current.handleExplainDifference(appRef.current.exceptions[0].payment_id);
    }
  }, [goToStepPage, measure, persist]);

  const next = useCallback(() => applyIndex(liveRef.current.stepIndex + 1, 1), [applyIndex]);
  const back = useCallback(() => applyIndex(Math.max(0, liveRef.current.stepIndex - 1), -1), [applyIndex]);

  const finish = useCallback(() => {
    liveRef.current = { ...liveRef.current, active: false };
    setActive(false);
    setCompleted(true);
    setRect(null);
    persist({ active: false, completed: true });
    appRef.current.setActiveTab('dashboard');
    appRef.current.setDashPage('home');
  }, [persist]);

  const skip = useCallback(() => {
    liveRef.current = { ...liveRef.current, active: false };
    setActive(false);
    setCompleted(false);
    setRect(null);
    persist({ active: false, completed: false });
    appRef.current.setActiveTab('dashboard');
    appRef.current.setDashPage('guide');
  }, [persist]);

  const startTour = useCallback(async ({ handsOn = false, fromCurrent = false } = {}) => {
    setChooser(false);
    setCompleted(false);
    setTryIt(handsOn);
    setActive(true);
    const app = appRef.current;
    let start = 0;
    if (fromCurrent && app.activeTab === 'merchant-checkout') {
      start = firstStepIndexForPage('store', 'merchant-checkout');
    } else if (fromCurrent && app.dashPage && app.dashPage !== 'guide') {
      start = firstStepIndexForPage(app.dashPage, 'dashboard');
    }
    liveRef.current = { active: true, stepIndex: start, tryIt: handsOn };
    persist({ active: true, stepIndex: start, tryIt: handsOn, completed: false });
    await applyIndex(start, 1);
  }, [applyIndex, persist]);

  const openChooser = useCallback(() => setChooser(true), []);
  const closeChooser = useCallback(() => setChooser(false), []);

  const dismissComplete = useCallback(() => {
    setCompleted(false);
    persist({ active: false, completed: false });
  }, [persist]);

  const goDashboard = useCallback(() => {
    setCompleted(false);
    persist({ active: false, completed: false });
    appRef.current.setActiveTab('dashboard');
    appRef.current.setDashPage('home');
  }, [persist]);

  const restoredRef = useRef(false);
  useEffect(() => {
    if (restoredRef.current) return undefined;
    restoredRef.current = true;
    const saved = readSaved();
    if (!saved?.active || !Number.isInteger(saved.stepIndex)) return undefined;
    setTryIt(Boolean(saved.tryIt));
    setActive(true);
    setStepIndex(saved.stepIndex);
    liveRef.current = { active: true, stepIndex: saved.stepIndex, tryIt: Boolean(saved.tryIt) };
    const handle = window.setTimeout(() => applyIndex(saved.stepIndex, 1), 200);
    return () => window.clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!active) return undefined;
    const step = TOUR_STEPS[stepIndex];
    if (!step) return undefined;
    const update = () => measure(step.target);
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    const timer = window.setInterval(update, 400);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
      window.clearInterval(timer);
    };
  }, [active, measure, stepIndex]);

  useEffect(() => {
    if (!active || !tryIt) return undefined;
    const step = TOUR_STEPS[stepIndex];
    if (!step?.waitFor) return undefined;
    const onInteract = (event) => {
      if (liveRef.current.waiting) return;
      if (event.target.closest?.('.tour-popover, .tour-complete, .tour-chooser')) return;
      const hit = event.target.closest?.(`[data-tour="${step.target}"]`);
      if (!hit) return;
      next();
    };
    document.addEventListener('click', onInteract, true);
    document.addEventListener('change', onInteract, true);
    return () => {
      document.removeEventListener('click', onInteract, true);
      document.removeEventListener('change', onInteract, true);
    };
  }, [active, next, stepIndex, tryIt]);

  const step = active ? TOUR_STEPS[stepIndex] : null;
  const canStartFromHere = dashPage !== 'guide' || activeTab === 'merchant-checkout';

  const value = useMemo(() => ({
    active,
    step,
    stepIndex,
    total: TOUR_STEPS.length,
    tryIt,
    waiting,
    targetReady,
    completed,
    chooser,
    rect,
    startTour,
    next,
    back,
    skip,
    finish,
    openChooser,
    closeChooser,
    dismissComplete,
    goDashboard,
    canStartFromHere,
  }), [
    active, back, canStartFromHere, chooser, completed, dismissComplete,
    finish, goDashboard, next, openChooser, closeChooser, rect, skip, startTour, step,
    stepIndex, targetReady, tryIt, waiting,
  ]);

  return <TourContext.Provider value={value}>{children}</TourContext.Provider>;
}
