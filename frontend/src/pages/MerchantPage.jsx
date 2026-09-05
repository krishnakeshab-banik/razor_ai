import { useApp } from '../AppContext';
import { formatRupees, formatTimestamp } from '../lib/format';
import { api } from '../lib/api';
import { useEffect, useMemo, useState } from 'react';
import { ShoppingCart, Trash2 } from 'lucide-react';
import { useTour } from '../tour/TourContext';
import { useLanguage } from '../i18n/LanguageContext';
import LanguageToggle from '../components/LanguageToggle';

// Cosmetic store dressing only — not a live review system or product API.
const PRODUCT_RATINGS = {
  earbuds: { rating: 4.8, reviews: 214 },
  lamp: { rating: 4.6, reviews: 89 },
  notebook: { rating: 4.4, reviews: 156 },
  keyboard: { rating: 4.9, reviews: 312 },
  monitor: { rating: 4.5, reviews: 67 },
  hub: { rating: 4.3, reviews: 128 },
};

function ProductStars({ rating, reviews }) {
  const filled = Math.round(rating);
  return (
    <div className="merchant-product-rating" aria-label={`${rating} out of 5 from ${reviews} reviews`}>
      <span className="merchant-stars" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((star) => (
          <span key={star} className={star <= filled ? 'is-on' : ''}>★</span>
        ))}
      </span>
      <span className="merchant-rating-score">{rating.toFixed(1)}</span>
      <span className="merchant-rating-count">({reviews})</span>
    </div>
  );
}

export default function MerchantPage() {
  const {
    merchantView, setMerchantView, setActiveTab, goToAdmin,
    demoProducts, cart, addToCart, updateCartQty, removeCartItem,
    merchantSubtotal, merchantDiscount, merchantTax, merchantTotal,
    checkoutForm, setCheckoutForm, handleMerchantCheckout, checkoutBusy, lastPayment, handleRefundOrder,
  } = useApp();
  const { openChooser } = useTour();
  const { t } = useLanguage();

  const [orders, setOrders] = useState([]);
  const [refundingId, setRefundingId] = useState(null);
  const [storeSort, setStoreSort] = useState('featured');
  // Nav search is visual only — it does not filter the catalogue.
  const [storeSearch, setStoreSearch] = useState('');

  const catalog = useMemo(() => {
    const list = [...demoProducts];
    if (storeSort === 'price-asc') list.sort((a, b) => a.price - b.price);
    if (storeSort === 'price-desc') list.sort((a, b) => b.price - a.price);
    return list;
  }, [demoProducts, storeSort]);
  const cartQty = cart.reduce((sum, item) => sum + item.qty, 0);
  const openCart = (event) => {
    event?.preventDefault?.();
    event?.stopPropagation?.();
    setMerchantView('cart');
  };

  const loadOrders = async () => {
    try {
      const data = await api.storeOrders();
      setOrders(data.orders || []);
    } catch {
      setOrders([]);
    }
  };

  useEffect(() => {
    if (merchantView === 'orders' || merchantView === 'success') loadOrders();
  }, [merchantView, lastPayment]);

  const refund = async (order) => {
    if (!order.refundable) return;
    const preview = await handleRefundOrder(order.payment_id, order.remaining_rupees, false);
    if (!preview?.requires_confirmation) return;
    const ok = window.confirm(`${preview.message}\n\nThis updates the finance controller, cash, GST and notifications.`);
    if (!ok) return;
    setRefundingId(order.payment_id);
    try {
      await handleRefundOrder(order.payment_id, order.remaining_rupees, true);
      await loadOrders();
    } finally {
      setRefundingId(null);
    }
  };

  return (
    <div className={`merchant-shell${merchantView === 'store' && cartQty > 0 ? ' has-cart-bar' : ''}`} data-tour="marketplace-store">
      <header className="merchant-header" data-tour="store-intro">
        <div className="merchant-brand">{t('store.brand')}</div>
        <nav className="merchant-nav">
          <button className={`merchant-nav-link ${merchantView === 'store' ? 'active' : ''}`} onClick={() => setMerchantView('store')} type="button">{t('store.marketplace')}</button>
          <button className={`merchant-nav-link ${merchantView === 'orders' ? 'active' : ''}`} onClick={() => setMerchantView('orders')} type="button">{t('store.orders')}</button>
          <button className="merchant-nav-link" data-tour="store-to-controller" onClick={() => goToAdmin('home')} type="button">{t('store.admin')}</button>
          <button className="merchant-nav-link" onClick={openChooser} type="button">{t('store.tour')}</button>
        </nav>
        <label className="merchant-search">
          <span className="merchant-search-label">{t('store.search')}</span>
          <input
            type="search"
            value={storeSearch}
            onChange={(event) => setStoreSearch(event.target.value)}
            placeholder={t('store.searchPh')}
            aria-label={t('store.searchPh')}
          />
        </label>
        <div className="merchant-header-actions">
          <LanguageToggle compact />
          <button className="merchant-link-btn subtle" onClick={() => setActiveTab('overview')} type="button">{t('store.backHome')}</button>
          <button className="merchant-cart-button" data-tour="store-cart-btn" onClick={openCart} aria-label={t('store.cart')} type="button">
            <ShoppingCart className="merchant-cart-icon" strokeWidth={2} />
            <span className="merchant-cart-label">{t('store.cart')}</span>
            {cartQty > 0 ? <span className="merchant-cart-count">{cartQty}</span> : null}
          </button>
        </div>
      </header>

      {merchantView === 'store' && (
        <>
          <section className="merchant-hero">
            <div className="merchant-hero-inner">
              <h1>{t('store.heroTitle')}</h1>
              <p>{t('store.heroSub')}</p>
            </div>
          </section>
          <div className="merchant-toolbar">
            <span className="merchant-toolbar-count">{t('store.products', { count: catalog.length })}</span>
            <label className="merchant-sort">
              {t('store.sort')}
              <select value={storeSort} onChange={(event) => setStoreSort(event.target.value)}>
                <option value="featured">Catalogue order</option>
                <option value="price-asc">Price: Low to High</option>
                <option value="price-desc">Price: High to Low</option>
              </select>
            </label>
          </div>
          <section className="merchant-product-grid" data-tour="store-catalogue">
            {catalog.map((product) => {
              const rating = PRODUCT_RATINGS[product.id] || { rating: 4.5, reviews: 40 };
              const qty = cart.find((item) => item.id === product.id)?.qty || 0;
              return (
                <article className="merchant-product-card" key={product.id}>
                  <div className="merchant-product-image">
                    <img src={product.image} alt={product.name} />
                  </div>
                  <div className="merchant-product-body">
                    <h3>{product.name}</h3>
                    <ProductStars rating={rating.rating} reviews={rating.reviews} />
                    <p>{product.subtitle}</p>
                    <div className="merchant-product-footer">
                      <strong>{formatRupees(product.price)}</strong>
                      {qty > 0 ? (
                        <div className="merchant-card-stepper" data-tour="store-add" role="group" aria-label={`Quantity for ${product.name}`}>
                          <button
                            type="button"
                            aria-label={`Remove one ${product.name}`}
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              updateCartQty(product.id, -1);
                            }}
                          >
                            −
                          </button>
                          <span aria-live="polite">{qty}</span>
                          <button
                            type="button"
                            aria-label={`Add one ${product.name}`}
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              updateCartQty(product.id, 1);
                            }}
                          >
                            +
                          </button>
                        </div>
                      ) : (
                        <button
                          className="merchant-add-btn"
                          data-tour="store-add"
                          onClick={(event) => {
                            event.preventDefault();
                            event.stopPropagation();
                            addToCart(product);
                          }}
                          type="button"
                        >
                          Add
                        </button>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </section>
          {cartQty > 0 && (
            <div className="merchant-cart-bar">
              <span>{cartQty} {cartQty === 1 ? 'item' : 'items'} · {formatRupees(merchantTotal)}</span>
              <button type="button" onClick={openCart}>View cart</button>
            </div>
          )}
          <footer className="merchant-footer">
            <div className="merchant-footer-brand">© 2026 Northwind Goods · powered by Razor-AI demo checkout</div>
            <div className="merchant-footer-links">
              <span>GST invoice</span>
              <span>Razorpay UPI / card / netbanking</span>
            </div>
          </footer>
        </>
      )}

      {merchantView === 'orders' && (
        <div className="merchant-orders-shell" data-tour="store-orders">
          <section className="merchant-page-top">
            <h2>Past orders</h2>
            <p>Refunds post through the same reconciliation engine as checkout — cash, GST, exceptions and notifications update together.</p>
          </section>
          <div className="merchant-orders-list">
            {orders.length ? orders.map((order) => (
              <article className="merchant-order-card" key={order.payment_id}>
                <div>
                  <strong>{order.payment_id}</strong>
                  <small>{order.order_id || '—'} · {formatTimestamp(order.created_at)}</small>
                  <p>{(order.items || []).map((item) => item.name || item.id).filter(Boolean).join(', ') || 'Demo checkout'}</p>
                </div>
                <div className="merchant-order-money">
                  <span>Paid {formatRupees(order.amount_rupees)}</span>
                  <span>Refunded {formatRupees(order.refunded_rupees)}</span>
                  <span className={`merchant-order-status ${order.status}`}>{order.status}</span>
                </div>
                <button
                  className="merchant-refund-btn"
                  type="button"
                  disabled={!order.refundable || refundingId === order.payment_id}
                  onClick={() => refund(order)}
                >
                  {order.refundable ? (refundingId === order.payment_id ? 'Refunding…' : `Refund ${formatRupees(order.remaining_rupees)}`) : 'Fully refunded'}
                </button>
              </article>
            )) : (
              <p className="merchant-empty">No store orders yet. Complete a checkout first.</p>
            )}
          </div>
        </div>
      )}

      {merchantView === 'cart' && (
        <div className="merchant-cart-shell" data-tour="store-cart">
          <div className="merchant-cart-header-row">
            <h1 className="merchant-cart-title">Your cart</h1>
            <button className="merchant-link-btn" onClick={() => setMerchantView('store')} type="button">← Continue shopping</button>
          </div>
          <div className="merchant-cart-layout">
            <div className="merchant-cart-list">
              {cart.length ? cart.map((item) => (
                <div className="merchant-cart-item" key={item.id}>
                  <img className="merchant-thumb" src={item.image} alt={item.name} />
                  <div className="merchant-item-meta">
                    <div className="merchant-item-name">{item.name}</div>
                    <div className="merchant-item-sub">{item.subtitle}</div>
                    <div className="merchant-item-price">{formatRupees(item.price)} each</div>
                  </div>
                  <div className="merchant-cart-controls">
                    <div className="merchant-qty-stepper" role="group" aria-label={`Quantity for ${item.name}`}>
                      <button
                        type="button"
                        aria-label={`Decrease ${item.name} quantity`}
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          updateCartQty(item.id, -1);
                        }}
                      >
                        −
                      </button>
                      <span aria-live="polite">{item.qty}</span>
                      <button
                        type="button"
                        aria-label={`Increase ${item.name} quantity`}
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          updateCartQty(item.id, 1);
                        }}
                      >
                        +
                      </button>
                    </div>
                    <strong className="merchant-cart-line-total">{formatRupees(item.price * item.qty)}</strong>
                    <button
                      className="merchant-delete-btn"
                      type="button"
                      aria-label={`Remove ${item.name} from cart`}
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        removeCartItem(item.id);
                      }}
                    >
                      <Trash2 className="merchant-delete-icon" strokeWidth={2} />
                    </button>
                  </div>
                </div>
              )) : (
                <div className="merchant-empty">Your cart is empty.</div>
              )}
            </div>
            <aside className="merchant-summary-card">
              <h3>Order summary</h3>
              <div className="merchant-summary-row"><span>Subtotal ({cart.reduce((sum, item) => sum + item.qty, 0)} items)</span><strong>{formatRupees(merchantSubtotal)}</strong></div>
              <div className="merchant-summary-row"><span>Discount</span><strong>{formatRupees(merchantDiscount)}</strong></div>
              <div className="merchant-summary-row"><span>GST (18% on goods)</span><strong>{formatRupees(merchantTax)}</strong></div>
              <div className="merchant-summary-row"><span>Delivery</span><strong>Free</strong></div>
              <div className="merchant-summary-total"><span>Total</span><strong>{formatRupees(merchantTotal)}</strong></div>
              <button
                className="merchant-checkout-btn"
                onClick={() => setMerchantView('checkout')}
                type="button"
                disabled={!cart.length}
              >
                Proceed to checkout →
              </button>
              <div className="merchant-secure-badge">Razorpay Test Mode · then recon in the controller</div>
            </aside>
          </div>
        </div>
      )}

      {merchantView === 'checkout' && (
        <div className="merchant-checkout-shell">
          <div className="merchant-checkout-card" data-tour="store-checkout">
            <div className="merchant-checkout-header">
              <div className="merchant-checkout-title-wrap">
                <div>
                  <strong>Pay with Razorpay</strong>
                  <small>{cart.reduce((sum, item) => sum + item.qty, 0)} items · Test Mode checkout</small>
                </div>
              </div>
              <div className="merchant-checkout-total">{formatRupees(merchantTotal)}</div>
            </div>
            <div className="merchant-form">
              <p className="merchant-checkout-lead">
                Card, UPI, and netbanking are collected inside Razorpay’s checkout. This page only plants the settlement outcome, then opens that modal — or posts a synthetic row for judges.
              </p>
              <details className="merchant-demo-acc">
                <summary>Demo settings</summary>
                <div className="merchant-demo-box">DEMO CONTROLS — not shown to a real customer</div>
                <label className="merchant-select-row" data-tour="store-outcome">
                  Simulate settlement outcome
                  <select value={checkoutForm.aiOutcome} onChange={(event) => setCheckoutForm({ ...checkoutForm, aiOutcome: event.target.value })}>
                    <option value="clean">Clean payment</option>
                    <option value="missing_settlement">Missing settlement</option>
                    <option value="fee_miscalculation">Fee miscalculation</option>
                    <option value="tax_line_mismatch">GST line mismatch</option>
                    <option value="timing_mismatch">Timing mismatch</option>
                    <option value="duplicate_record">Duplicate record</option>
                    <option value="unaccounted_refund">Unaccounted refund</option>
                  </select>
                </label>
              </details>
              <div className="merchant-action-row">
                <button className="merchant-cancel-btn" onClick={() => setMerchantView('cart')} type="button" disabled={checkoutBusy}>Back to cart</button>
                <button
                  className="merchant-pay-btn"
                  data-tour="store-pay"
                  onClick={() => handleMerchantCheckout()}
                  type="button"
                  disabled={checkoutBusy || !cart.length}
                >
                  {checkoutBusy ? 'Opening Razorpay…' : `Pay with Razorpay ${formatRupees(merchantTotal)}`}
                </button>
              </div>
              <button
                className="merchant-synthetic-btn"
                onClick={() => handleMerchantCheckout({ synthetic: true })}
                type="button"
                disabled={checkoutBusy || !cart.length}
              >
                Plant synthetic row instead
              </button>
              <div className="merchant-secure-note">
                Test card 4111 1111 1111 1111 · or Razorpay test UPI success. Signature is verified on the server before the row is ingested.
              </div>
            </div>
          </div>
        </div>
      )}

      {merchantView === 'success' && (
        <div className="merchant-success-shell">
          <div className="merchant-success-card" data-tour="store-success">
            <p className="merchant-success-kicker">Captured</p>
            <h2>Payment captured</h2>
            <p>The charge is in the Razor-AI batch. Settlement still has to match.</p>
            <div className="merchant-success-table">
              <div><span>Amount paid</span><strong>{formatRupees(lastPayment?.amountPaid || merchantTotal)}</strong></div>
              <div><span>Payment ID</span><strong>{lastPayment?.payment_id || 'pending'}</strong></div>
              <div><span>Method</span><strong>{lastPayment?.method || checkoutForm.paymentMethod}</strong></div>
              <div><span>Engine outcome</span><strong>{lastPayment?.reconciliation_status || 'queued'}</strong></div>
            </div>
            <div className="merchant-success-note">Open Admin to see whether this row matched or became an exception.</div>
            <button className="merchant-success-btn" onClick={() => {
              goToAdmin(lastPayment?.reconciliation_status === 'exception' ? 'exceptions' : 'payments');
            }} type="button">View in Admin</button>
            <button className="merchant-link-btn" onClick={() => setMerchantView('orders')} type="button">Past orders</button>
          </div>
        </div>
      )}
    </div>
  );
}
