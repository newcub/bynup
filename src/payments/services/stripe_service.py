# payments/services/stripe_service.py

import stripe
from django.core.exceptions import ValidationError
from ..models import PaymentGateway, Transaction


class StripePaymentService:
    """
    Per-instance Stripe client.

    IMPORTANT: We do NOT mutate `stripe.api_key` globally. That is unsafe
    when multiple merchants are processed concurrently (one request can
    leak its API key into another request's Stripe call).
    """

    def __init__(self, payment_gateway: PaymentGateway):
        self.payment_gateway = payment_gateway
        api_key = payment_gateway.get_secret_key()
        if not api_key:
            raise ValidationError("Stripe secret key not configured")
        # Per-instance client — safe for multi-tenant concurrency.
        self.client = stripe.StripeClient(api_key)

    # ------------------------------------------------------------------
    # PaymentIntent (used to validate keys during configuration)
    # ------------------------------------------------------------------
    def create_payment_intent(self, amount, currency='usd', metadata=None):
        try:
            return self.client.payment_intents.create(params={
                'amount': int(round(float(amount) * 100)),
                'currency': currency,
                'metadata': metadata or {},
                'automatic_payment_methods': {'enabled': True},
            })
        except stripe.StripeError as e:
            raise ValidationError(f"Stripe error: {str(e)}")

    def retrieve_payment_intent(self, payment_intent_id):
        try:
            return self.client.payment_intents.retrieve(payment_intent_id)
        except stripe.StripeError as e:
            raise ValidationError(f"Stripe error: {str(e)}")

    # ------------------------------------------------------------------
    # EMBEDDED Checkout (new — keeps the customer on your domain)
    # ------------------------------------------------------------------
    def create_embedded_checkout_session(self, order, return_url):
        """
        Create a Stripe Checkout Session in EMBEDDED mode.

        The customer stays on your domain. Stripe.js mounts the checkout
        form inside a div on your page using the returned `client_secret`.
        """
        try:
            return self.client.checkout.sessions.create(params={
                'ui_mode': 'embedded',
                'line_items': [{
                    'price_data': {
                        'currency': order.currency.lower(),
                        'product_data': {
                            'name': f"Order {order.order_number}",
                        },
                        'unit_amount': int(round(float(order.total_amount) * 100)),
                    },
                    'quantity': 1,
                }],
                'mode': 'payment',
                'return_url': return_url,
                'customer_email': order.customer_email,
                'metadata': {
                    'order_number': order.order_number,
                    'page_id': str(order.page.id),
                },
            })
        except stripe.StripeError as e:
            raise ValidationError(f"Stripe error: {str(e)}")

    def retrieve_checkout_session(self, session_id):
        try:
            return self.client.checkout.sessions.retrieve(session_id)
        except stripe.StripeError as e:
            raise ValidationError(f"Stripe error: {str(e)}")

    # ------------------------------------------------------------------
    # Legacy: hosted redirect session (kept in case other code calls it)
    # ------------------------------------------------------------------
    def create_checkout_session(self, order, success_url, cancel_url):
        try:
            return self.client.checkout.sessions.create(params={
                'payment_method_types': ['card'],
                'line_items': [{
                    'price_data': {
                        'currency': order.currency.lower(),
                        'product_data': {'name': f"Order {order.order_number}"},
                        'unit_amount': int(round(float(order.total_amount) * 100)),
                    },
                    'quantity': 1,
                }],
                'mode': 'payment',
                'success_url': success_url,
                'cancel_url': cancel_url,
                'customer_email': order.customer_email,
                'metadata': {
                    'order_number': order.order_number,
                    'page_id': str(order.page.id),
                },
            })
        except stripe.StripeError as e:
            raise ValidationError(f"Stripe error: {str(e)}")

    # ------------------------------------------------------------------
    # Webhook verification (stateless)
    # ------------------------------------------------------------------
    def handle_webhook(self, payload, sig_header, webhook_secret):
        try:
            return stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError:
            raise ValidationError("Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise ValidationError("Invalid signature")

    # ------------------------------------------------------------------
    # Refunds
    # ------------------------------------------------------------------
    def refund_payment(self, payment_intent_id, amount):
        try:
            refund = self.client.refunds.create(params={
                'payment_intent': payment_intent_id,
                'amount': int(round(float(amount) * 100)),
            })
            return {
                'success': True,
                'refund_id': refund.id,
                'status': refund.status,
                'amount': amount,
            }
        except stripe.StripeError as e:
            raise ValidationError(f"Stripe refund failed: {str(e)}")


    def create_embedded_payment_intent(self, order, metadata=None):
        """
        Create a PaymentIntent for Stripe Elements.
        Returns the PaymentIntent; caller uses .client_secret on the frontend.
        """
        try:
            return self.client.payment_intents.create(params={
                'amount': int(round(float(order.total_amount) * 100)),
                'currency': order.currency.lower(),
                'automatic_payment_methods': {'enabled': True},
                'receipt_email': order.customer_email,
                'metadata': {
                    'order_number': order.order_number,
                    'page_id': str(order.page.id),
                    **(metadata or {}),
                },
            })
        except stripe.StripeError as e:
            raise ValidationError(f"Stripe error: {str(e)}")