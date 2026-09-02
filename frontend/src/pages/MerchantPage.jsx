import { useApp } from '../AppContext';
import { formatRupees } from '../lib/format';
import { api } from '../lib/api';
import { useEffect, useState } from 'react';
import { useTour } from '../tour/TourContext';

const METHODS = ['UPI', 'Card', 'Netbanking'];

export default function MerchantPage() {
  const {
    merchantView, setMerchantView, setActiveTab, setDashPage,
    demoProducts, cart, addToCart, updateCartQty, removeCartItem,
    merchantSubtotal, merchantDiscount, merchantTax, merchantTotal,
    checkoutForm, setCheckoutForm, handleMerchantCheckout, lastPayment, handleRefundOrder,
  } = useApp();
  const { openChooser } = useTour();

  const method = checkoutForm.paymentMethod;
  const [orders, setOrders] = useState([]);
  const [refundingId, setRefundingId] = useState(null);

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
    <div className="merchant-shell" data-tour="marketplace-store">
      <header className="merchant-header">
        <div className="merchant-brand">Northwind Goods · demo store</div>
        <nav className="merchant-nav">
          <button className="merchant-nav-link" onClick={() => setActiveTab('overview')} type="button">Home</button>
          <button className={`merchant-nav-link ${merchantView === 'store' ? 'active' : ''}`} onClick={() => setMerchantView('store')} type="button">Marketplace</button>
          <button className={`merchant-nav-link ${merchantView === 'orders' ? 'active' : ''}`} onClick={() => setMerchantView('orders')} type="button">Past orders</button>
          <button className="merchant-nav-link" onClick={() => setActiveTab('dashboard')} type="button">Controller</button>
          <button className="merchant-nav-link" onClick={openChooser} type="button">Tour</button>
        </nav>
        <div className="merchant-header-actions">
          <button className="merchant-link-btn subtle" onClick={() => setActiveTab('overview')} type="button">Back to home</button>
          <button className="merchant-cart-button" onClick={() => setMerchantView('cart')} aria-label="Open cart" type="button">
            🛒{cart.length ? <span className="merchant-cart-count">{cart.reduce((sum, item) => sum + item.qty, 0)}</span> : null}
          </button>
        </div>
      </header>

      {merchantView === 'store' && (
        <>
          <section className="merchant-page-top">
            <h2>Shop the catalogue</h2>
            <p>Simulated Razorpay checkout — each payment lands in the finance controller with a chosen exception outcome.</p>
          </section>
          <section className="merchant-product-grid">
            {demoProducts.map((product) => (
              <article className="merchant-product-card" key={product.id}>
                <div className="merchant-product-image">
                  <img src={product.image} alt={product.name} />
                </div>
                <div className="merchant-product-body">
                  <h3>{product.name}</h3>
                  <p>{product.subtitle}</p>
                  <div className="merchant-product-footer">
                    <strong>{formatRupees(product.price)}</strong>
                    <div className="merchant-product-qty-wrap">
                      <button className="merchant-product-qty-btn" onClick={() => updateCartQty(product.id, -1)} disabled={!cart.some((item) => item.id === product.id)} type="button">−</button>
                      <span className="merchant-product-qty-value">{cart.find((item) => item.id === product.id)?.qty || 0}</span>
                      <button className="merchant-product-qty-btn" onClick={() => addToCart(product)} type="button">+</button>
                    </div>
                    <button className="merchant-add-btn" onClick={() => addToCart(product)} type="button">Add to cart</button>
                  </div>
                </div>
              </article>
            ))}
          </section>
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
        <div className="merchant-orders-shell">
          <section className="merchant-page-top">
            <h2>Past orders</h2>
            <p>Refunds post through the same reconciliation engine as checkout — cash, GST, exceptions and notifications update together.</p>
          </section>
          <div className="merchant-orders-list">
            {orders.length ? orders.map((order) => (
              <article className="merchant-order-card" key={order.payment_id}>
                <div>
                  <strong>{order.payment_id}</strong>
                  <small>{order.order_id || '—'} · {order.created_at ? new Date(order.created_at).toLocaleString('en-IN') : ''}</small>
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
        <div className="merchant-cart-shell">
          <div className="merchant-cart-header-row">
            <div className="merchant-brand-small">Northwind Goods</div>
            <button className="merchant-link-btn" onClick={() => setMerchantView('store')} type="button">← Continue shopping</button>
          </div>
          <h1 className="merchant-cart-title">Your cart</h1>
          <div className="merchant-cart-layout">
            <div className="merchant-cart-list">
              {cart.length ? cart.map((item) => (
                <div className="merchant-cart-item" key={item.id}>
                  <img className="merchant-thumb" src={item.image} alt={item.name} />
                  <div className="merchant-item-meta">
                    <div className="merchant-item-name">{item.name}</div>
                    <div className="merchant-item-sub">{item.subtitle}</div>
                    <div className="merchant-item-price">{formatRupees(item.price)}</div>
                  </div>
                  <div className="merchant-qty-wrap">
                    <button onClick={() => updateCartQty(item.id, -1)} type="button">-</button>
                    <span>{item.qty}</span>
                    <button onClick={() => updateCartQty(item.id, 1)} type="button">+</button>
                    <button className="merchant-delete-btn" onClick={() => removeCartItem(item.id)} type="button">🗑</button>
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
              <button className="merchant-checkout-btn" onClick={() => setMerchantView('checkout')} type="button">Proceed to checkout →</button>
              <div className="merchant-secure-badge">Razorpay-style checkout · demo only</div>
            </aside>
          </div>
        </div>
      )}

      {merchantView === 'checkout' && (
        <div className="merchant-checkout-shell">
          <div className="merchant-checkout-card">
            <div className="merchant-checkout-header">
              <div className="merchant-checkout-title-wrap">
                <div>
                  <strong>Razorpay Checkout</strong>
                  <small>{cart.reduce((sum, item) => sum + item.qty, 0)} items · demo</small>
                </div>
              </div>
              <div className="merchant-checkout-total">{formatRupees(merchantTotal)}</div>
            </div>
            <div className="merchant-payment-methods">
              {METHODS.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={`merchant-payment-method ${method === item ? 'active' : ''}`}
                  onClick={() => setCheckoutForm({ ...checkoutForm, paymentMethod: item })}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="merchant-form">
              <div className="merchant-billing-grid">
                <label>Full name
                  <input value={checkoutForm.name} onChange={(event) => setCheckoutForm({ ...checkoutForm, name: event.target.value })} placeholder="Name on the account" />
                </label>
                <label>Email
                  <input type="email" value={checkoutForm.email} onChange={(event) => setCheckoutForm({ ...checkoutForm, email: event.target.value })} placeholder="you@merchant.in" />
                </label>
              </div>
              <div className="merchant-billing-grid">
                <label>Phone
                  <input type="tel" value={checkoutForm.phone} onChange={(event) => setCheckoutForm({ ...checkoutForm, phone: event.target.value })} placeholder="+91 98765 43210" />
                </label>
                <label>City
                  <input value={checkoutForm.city} onChange={(event) => setCheckoutForm({ ...checkoutForm, city: event.target.value })} placeholder="Bengaluru" />
                </label>
              </div>
              <label>Billing address
                <input value={checkoutForm.address} onChange={(event) => setCheckoutForm({ ...checkoutForm, address: event.target.value })} placeholder="House number, street, locality" />
              </label>
              {method === 'UPI' && (
                <label>UPI ID
                  <input value={checkoutForm.cardNumber} onChange={(event) => setCheckoutForm({ ...checkoutForm, cardNumber: event.target.value })} placeholder="merchant@okaxis" />
                </label>
              )}
              {method === 'Card' && (
                <>
                  <label>Card number
                    <input value={checkoutForm.cardNumber} onChange={(event) => setCheckoutForm({ ...checkoutForm, cardNumber: event.target.value })} placeholder="4111 1111 1111 1111" />
                  </label>
                  <div className="merchant-row-two">
                    <label>Expiry
                      <input value={checkoutForm.expiry} onChange={(event) => setCheckoutForm({ ...checkoutForm, expiry: event.target.value })} placeholder="MM/YY" />
                    </label>
                    <label>CVV
                      <input value={checkoutForm.cvc} onChange={(event) => setCheckoutForm({ ...checkoutForm, cvc: event.target.value })} placeholder="•••" />
                    </label>
                  </div>
                </>
              )}
              {method === 'Netbanking' && (
                <label>Bank
                  <input value={checkoutForm.cardNumber} onChange={(event) => setCheckoutForm({ ...checkoutForm, cardNumber: event.target.value })} placeholder="HDFC / ICICI / SBI" />
                </label>
              )}
              <label className="merchant-check-row">
                <input type="checkbox" checked={checkoutForm.saveCard} onChange={() => setCheckoutForm({ ...checkoutForm, saveCard: !checkoutForm.saveCard })} />
                Save this method for the demo session
              </label>
              <div className="merchant-demo-box">DEMO CONTROLS — not shown to a real customer</div>
              <label className="merchant-select-row">
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
              <div className="merchant-action-row">
                <button className="merchant-cancel-btn" onClick={() => setMerchantView('cart')} type="button">Cancel</button>
                <button className="merchant-pay-btn" onClick={handleMerchantCheckout} type="button">Pay {formatRupees(merchantTotal)}</button>
              </div>
              <div className="merchant-secure-note">Demo capture · then recon in the controller</div>
            </div>
          </div>
        </div>
      )}

      {merchantView === 'success' && (
        <div className="merchant-success-shell">
          <div className="merchant-success-card">
            <p className="merchant-success-kicker">Captured</p>
            <h2>Payment captured</h2>
            <p>The charge is in the Razor-AI batch. Settlement still has to match.</p>
            <div className="merchant-success-table">
              <div><span>Amount paid</span><strong>{formatRupees(lastPayment?.amountPaid || merchantTotal)}</strong></div>
              <div><span>Payment ID</span><strong>{lastPayment?.payment_id || 'pending'}</strong></div>
              <div><span>Method</span><strong>{lastPayment?.method || checkoutForm.paymentMethod}</strong></div>
              <div><span>Engine outcome</span><strong>{lastPayment?.reconciliation_status || 'queued'}</strong></div>
            </div>
            <div className="merchant-success-note">Open the controller to see whether this row matched or became an exception.</div>
            <button className="merchant-success-btn" onClick={() => {
              setActiveTab('dashboard');
              setDashPage(lastPayment?.reconciliation_status === 'exception' ? 'exceptions' : 'payments');
            }} type="button">View in Razor-AI</button>
            <button className="merchant-link-btn" onClick={() => setMerchantView('orders')} type="button">Past orders</button>
          </div>
        </div>
      )}
    </div>
  );
}
