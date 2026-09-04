const CHECKOUT_SRC = 'https://checkout.razorpay.com/v1/checkout.js';

export function loadRazorpayScript() {
  if (typeof window !== 'undefined' && window.Razorpay) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${CHECKOUT_SRC}"]`);
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('Could not load Razorpay Checkout')), { once: true });
      return;
    }
    const script = document.createElement('script');
    script.src = CHECKOUT_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Could not load Razorpay Checkout'));
    document.body.appendChild(script);
  });
}

export function openRazorpayCheckout(options) {
  return new Promise((resolve, reject) => {
    if (!window.Razorpay) {
      reject(new Error('Razorpay Checkout is not available'));
      return;
    }
    const rzp = new window.Razorpay({
      ...options,
      handler: (response) => resolve(response),
      modal: {
        ...(options.modal || {}),
        ondismiss: () => reject(new Error('Checkout cancelled')),
      },
    });
    rzp.on('payment.failed', (event) => {
      const description = event?.error?.description || 'Razorpay payment failed';
      reject(new Error(description));
    });
    rzp.open();
  });
}
