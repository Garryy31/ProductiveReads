const paymentButton = document.querySelector('#razorpay-button');
let paymentCompleted = false;

function showPaymentError(message) {
  let box = document.querySelector('#payment-error');
  if (!box) {
    box = document.createElement('p');
    box.id = 'payment-error';
    box.className = 'summary-note';
    box.setAttribute('role', 'alert');
    box.style.color = '#b3402a';
    paymentButton.insertAdjacentElement('afterend', box);
  }
  box.textContent = message;
}

if (paymentButton) {
  paymentButton.addEventListener('click', async () => {
    paymentButton.disabled = true;
    paymentButton.classList.add('is-loading');
    paymentButton.dataset.originalText = paymentButton.innerHTML;
    paymentButton.innerHTML = '<span class="button-spinner" aria-hidden="true"></span> Preparing payment...';
    try {
      const orderResponse = await fetch('/create-order', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({order_id: paymentButton.dataset.localOrder}),
      });
      let order;
      try {
        order = await orderResponse.json();
      } catch (_parseError) {
        throw new Error('Your session may have expired. Please log in again and retry the payment.');
      }
      if (!order.ok) throw new Error(order.message || 'Unable to create the payment order.');
      if (paymentButton.dataset.demoMode === 'true') {
        const demoResponse = await fetch('/verify-payment', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            order_id: paymentButton.dataset.localOrder,
            razorpay_order_id: order.order_id,
            razorpay_payment_id: `demo_payment_${paymentButton.dataset.localOrder}`,
            razorpay_signature: 'demo_signature',
            demo_confirmed: 'true',
          }),
        });
        const result = await demoResponse.json();
        window.location.href = result.ok ? result.redirect : `/payment-failure/${paymentButton.dataset.localOrder}`;
        return;
      }
      const options = {
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: 'ProductiveReads',
        description: 'Self-growth and productivity books',
        order_id: order.order_id,
        handler(response) {
          paymentCompleted = true;
          fetch('/verify-payment', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({...response, order_id: paymentButton.dataset.localOrder}),
          }).then((result) => result.json()).then((result) => {
            window.location.href = result.ok ? result.redirect : `/payment-failure/${paymentButton.dataset.localOrder}`;
          }).catch(() => {
            window.location.href = `/payment-failure/${paymentButton.dataset.localOrder}`;
          });
        },
        modal: {ondismiss: () => { if (!paymentCompleted) window.location.href = `/payment-failure/${paymentButton.dataset.localOrder}`; }},
        theme: {color: '#ec7658'},
      };
      const checkout = new Razorpay(options);
      checkout.on('payment.failed', (response) => {
        console.error('Razorpay payment.failed:', response && response.error);
      });
      checkout.open();
    } catch (error) {
      console.error('Payment setup failed:', error);
      showPaymentError(error && error.message ? error.message : 'Payment could not be started. Please try again.');
      paymentButton.disabled = false;
      paymentButton.classList.remove('is-loading');
      paymentButton.innerHTML = paymentButton.dataset.originalText;
    }
  });
}
