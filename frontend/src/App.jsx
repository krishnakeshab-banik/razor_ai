import React from 'react';
import { AppProvider, useApp } from './AppContext';
import LandingPage from './pages/LandingPage';
import HowItWorksPage from './pages/HowItWorksPage';
import RoadmapPage from './pages/RoadmapPage';
import MerchantPage from './pages/MerchantPage';
import Dashboard from './pages/Dashboard';
import ExceptionDrawer from './components/ExceptionDrawer';
import ProductTour from './components/ProductTour';
import Toasts from './components/Toasts';
import CircularNavDock from './components/ui/circular-nav-dock';
import { TourProvider } from './tour/TourContext';
import { LanguageProvider, useLanguage } from './i18n/LanguageContext';
import LanguageToggle from './components/LanguageToggle';

function Shell() {
  const { activeTab, setActiveTab, triggerToast } = useApp();
  const { t } = useLanguage();
  const marketing = activeTab !== 'dashboard' && activeTab !== 'merchant-checkout';

  React.useEffect(() => {
    const locked = activeTab === 'dashboard' || activeTab === 'merchant-checkout';
    document.documentElement.classList.toggle('app-locked', locked);
    document.body.classList.toggle('app-locked', locked);
    return () => {
      document.documentElement.classList.remove('app-locked');
      document.body.classList.remove('app-locked');
    };
  }, [activeTab]);

  return (
    <div className="app-root-container">
      {marketing && (
        <header className="header">
          <div className="container header-container">
            <button className="logo" onClick={() => setActiveTab('overview')} type="button">
              <span className="logo-accent">Razor-AI</span>
              <span className="logo-badge">{t('chrome.subtitle')}</span>
            </button>
            <nav className="nav">
              <button className={`nav-link ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')} type="button">Overview</button>
              <button className={`nav-link ${activeTab === 'how-it-works' ? 'active' : ''}`} onClick={() => setActiveTab('how-it-works')} type="button">How it works</button>
              <button className={`nav-link ${activeTab === 'roadmap' ? 'active' : ''}`} onClick={() => setActiveTab('roadmap')} type="button">Roadmap</button>
            </nav>
            <div className="header-actions">
              <LanguageToggle compact />
              <button className="btn btn-secondary-outline" type="button" onClick={() => triggerToast('Demo mode — use Get started. No login required.', 'success')}>
                Sign in
              </button>
              <button className="btn btn-primary" type="button" onClick={() => setActiveTab('dashboard')}>
                Get started
              </button>
            </div>
          </div>
        </header>
      )}

      <main>
        {activeTab === 'overview' && <LandingPage />}
        {activeTab === 'how-it-works' && <HowItWorksPage />}
        {activeTab === 'roadmap' && <RoadmapPage />}
        {activeTab === 'merchant-checkout' && <MerchantPage />}
        {activeTab === 'dashboard' && <Dashboard />}
      </main>

      {marketing && (
        <footer className="footer">
          <div className="container footer-container">
            <div className="footer-brand">
              <button className="logo" onClick={() => setActiveTab('overview')} type="button">
                <span className="logo-accent" style={{ color: '#ffffff' }}>Razor-AI</span>
              </button>
              <p>Run the books and the cash position. Match rate, auto-fixes, and an honest exception list — not a cherry-picked row.</p>
            </div>
            <div className="footer-links">
              <button onClick={() => { setActiveTab('overview'); window.scrollTo(0, 0); }} className="btn-text-only" type="button">Overview</button>
              <button onClick={() => { setActiveTab('how-it-works'); window.scrollTo(0, 0); }} className="btn-text-only" type="button">How it works</button>
              <button onClick={() => { setActiveTab('roadmap'); window.scrollTo(0, 0); }} className="btn-text-only" type="button">Roadmap</button>
            </div>
          </div>
          <div className="footer-bottom">
            <div className="container footer-bottom-container">
              <p style={{ color: '#94a3b8' }}>© 2026 Razor-AI · Razorpay Buildathon</p>
              <p style={{ color: '#64748b' }}>AI Finance Controller · synthetic Razorpay batches</p>
            </div>
          </div>
        </footer>
      )}

      {(activeTab === 'dashboard' || activeTab === 'merchant-checkout') && <CircularNavDock />}
      <ExceptionDrawer />
      <Toasts />
    </div>
  );
}

export default function App() {
  return (
    <LanguageProvider>
      <AppProvider>
        <TourProvider>
          <Shell />
          <ProductTour />
        </TourProvider>
      </AppProvider>
    </LanguageProvider>
  );
}
