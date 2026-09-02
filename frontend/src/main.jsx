/**
 * main.jsx - React Application Entry Point
 * Razor-AI | Automated Financial Reconciliation for Razorpay
 *
 * Mounts the root <App /> component into the #root div defined in index.html.
 * React 18 concurrent mode is used for best performance.
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch() {
    try {
      sessionStorage.removeItem('razorai-product-tour');
    } catch {
      /* ignore */
    }
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24, background: '#f6f8fc', fontFamily: 'Inter, sans-serif' }}>
        <div style={{ maxWidth: 480, background: '#fff', border: '1px solid #e6ebf3', borderRadius: 16, padding: 28, boxShadow: '0 8px 32px rgba(15,23,42,0.08)' }}>
          <p style={{ marginBottom: 8, color: '#0d4fff', fontWeight: 800, letterSpacing: '0.06em', fontSize: 12 }}>RAZOR-AI</p>
          <h1 style={{ marginBottom: 8, fontSize: 22, color: '#0b3a6e' }}>The controller hit a display error</h1>
          <p style={{ marginBottom: 18, color: '#64748b', fontSize: 14 }}>{this.state.error.message}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{ border: 0, background: '#0d4fff', color: '#fff', borderRadius: 8, padding: '10px 16px', fontWeight: 700, cursor: 'pointer' }}
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
