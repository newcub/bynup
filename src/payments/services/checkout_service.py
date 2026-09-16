# import stripe
# from django.conf import settings
# from django.core.exceptions import ValidationError
# from django.urls import reverse
# from ..models import Order, OrderItem, Transaction, PaymentGateway
# import uuid
# import json

# class CheckoutService:
#     def __init__(self, page, gateway):
#         self.page = page
#         self.gateway = gateway
#         self.setup_payment_gateway()

#     def setup_payment_gateway(self):
#         """Setup the specific payment gateway"""
#         if self.gateway.gateway_type == 'stripe':
#             self.setup_stripe()
#         elif self.gateway.gateway_type == 'paypal':
#             self.setup_paypal()
#         # Add other gateways here
    
#     def setup_stripe(self):
#         """Configure Stripe with user's API keys"""
#         api_key = self.gateway.get_secret_key()
#         if not api_key:
#             raise ValidationError("Stripe secret key not configured")
        
#         import stripe
#         stripe.api_key = api_key
#         self.stripe = stripe
    
#     def setup_paypal(self):
#         """Configure PayPal - placeholder for future implementation"""
#         # PayPal integration would go here
#         pass
    
#     def create_checkout(self, order_data, customer_info, request):
#         """Create checkout based on gateway type"""
#         if self.gateway.gateway_type == 'stripe':
#             return self.create_stripe_checkout(order_data, customer_info, request)
#         elif self.gateway.gateway_type == 'paypal':
#             return self.create_paypal_checkout(order_data, customer_info, request)
#         else:
#             raise ValidationError(f"Payment gateway {self.gateway.gateway_type} not implemented")
    
#     def create_stripe_checkout(self, order_data, customer_info, request):
#         """Create Stripe checkout session"""
#         try:
#             # Determine checkout type and create order
#             if order_data.get('checkout_type') == 'instant':
#                 order = self.create_order_from_product(order_data.get('product', {}), customer_info)
#                 line_items = self.get_stripe_line_items_from_product(order_data.get('product', {}))
#             else:  # cart checkout
#                 order = self.create_order_from_cart(order_data.get('cart', {}), customer_info)
#                 line_items = self.get_stripe_line_items_from_cart(order_data.get('cart', {}))
            
#             success_url = request.build_absolute_uri(
#                 reverse('payments:checkout_success', args=[self.page.subdomain])
#             ) + f'?session_id={{CHECKOUT_SESSION_ID}}'
            
#             cancel_url = request.build_absolute_uri(
#                 reverse('payments:checkout_cancel', args=[self.page.subdomain])
#             )
            
#             session = self.stripe.checkout.Session.create(
#                 payment_method_types=['card'],
#                 line_items=line_items,
#                 mode='payment',
#                 success_url=success_url,
#                 cancel_url=cancel_url,
#                 customer_email=customer_info.get('email'),
#                 metadata={
#                     'order_number': order.order_number,
#                     'page_id': str(self.page.id),
#                     'checkout_type': order_data.get('checkout_type', 'instant')
#                 }
#             )
            
#             # Create transaction record
#             Transaction.objects.create(
#                 order=order,
#                 payment_gateway=self.gateway,
#                 gateway_payment_intent_id=session.payment_intent or session.id,
#                 gateway_transaction_id=session.id,
#                 amount=order.total_amount,
#                 status='pending',
#                 gateway_response={'session_id': session.id, 'status': 'created'}
#             )
            
#             return {
#                 'session_id': session.id,
#                 'public_key': self.gateway.get_public_key(),
#                 'order_number': order.order_number,
#                 'gateway': 'stripe'
#             }
            
#         except Exception as e:
#             raise ValidationError(f"Stripe checkout creation failed: {str(e)}")    
  

# payments/services/checkout_service.py
import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from ..models import Order, OrderItem, Transaction, PaymentGateway
from builder.models import Product
from .tax_service import TaxService
import uuid
import json

from payments.services import tax_service
from payments.utils import check_and_deduct_stock

class CheckoutService:
    def __init__(self, page, gateway=None):
        """
        Initialize CheckoutService.
        Supports both single gateway (page only) and multi-gateway (page + gateway) usage.
        """
        self.page = page
        
        # Handle both initialization styles
        if gateway:
            self.gateway = gateway
        else:
            # Fallback to Stripe gateway for backward compatibility
            self.gateway = self.get_stripe_gateway()
        
        self.setup_payment_gateway()

    # In your checkout service when creating order


    def calculate_order_tax(self, order_data, customer_info):
        """Calculate tax for order"""
        items = []
        for item in order_data.get('items', []):
            items.append({
                'product_id': item.get('product_id'),
                'title': item.get('title'),
                'price': item.get('price'),
                'quantity': item.get('quantity'),
                'tax_class_id': item.get('tax_class_id')
            })
        
        tax_service = TaxService(self.page)
        tax_result = tax_service.calculate_tax(
            items=items,
            customer_data=customer_info,
            shipping_cost=order_data.get('shipping_amount', 0)
        )
        
        return tax_result
    
    def get_stripe_gateway(self):
        """Get active Stripe gateway for the page (for backward compatibility)"""
        gateway = self.page.payment_gateways.filter(
            gateway_type='stripe',
            is_active=True
        ).first()
        
        if not gateway:
            raise ValidationError("Stripe payment gateway not configured or active")
        
        return gateway
    
    def setup_payment_gateway(self):
        """Setup the specific payment gateway"""
        if self.gateway.gateway_type == 'stripe':
            self.setup_stripe()
        elif self.gateway.gateway_type == 'paypal':
            from .paypal_service import PayPalService
            self.paypal_service = PayPalService(self.gateway)
        elif self.gateway.gateway_type == 'razorpay':  # ADD THIS
            from .razorpay_service import RazorpayService
            self.razorpay_service = RazorpayService(self.gateway)
        elif self.gateway.gateway_type == 'fincra':  # ADD THIS
            from .fincra_service import FincraService
            self.fincra_service = FincraService(self.gateway)
        elif self.gateway.gateway_type == 'cryptomus':  # ADD THIS
            from .cryptomus_service import CryptomusService
            self.cryptomus_service = CryptomusService(self.gateway)
        elif self.gateway.gateway_type == 'pay_on_delivery':
            from .pod_service import PayOnDeliveryService
            self.pod_service = PayOnDeliveryService(self.gateway)
        elif self.gateway.gateway_type == 'social_media':
            from .social_media_service import SocialMediaService  # FIX: Import inside the condition
            self.social_media_service = SocialMediaService(self.gateway)
        else:
            raise ValidationError(f"Payment gateway {self.gateway.gateway_type} not implemented") 
           
    def setup_stripe(self):
        """Configure Stripe with the merchant's keys (per-instance client)."""
        from .stripe_service import StripePaymentService
        self.stripe_service = StripePaymentService(self.gateway)

    def _recompute_order_totals(self, order):
        """
        Recompute the order's totals from the DB product prices.
        Prevents client-side price tampering.
        """
        from decimal import Decimal, InvalidOperation
        from builder.models import Product

        def _to_decimal(value):
            """Safely coerce anything (float, int, Decimal, str, None) to Decimal."""
            if value is None:
                return Decimal('0.00')
            if isinstance(value, Decimal):
                return value
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError, TypeError):
                return Decimal('0.00')

        subtotal = Decimal('0.00')

        for item in order.items.all():
            db_price = None
            if item.product_id:
                try:
                    product = Product.objects.get(id=item.product_id)
                    db_price = _to_decimal(getattr(product, 'price', item.product_price))
                except (Product.DoesNotExist, Exception):
                    db_price = None

            effective_price = db_price if db_price is not None else _to_decimal(item.product_price)

            item.product_price = effective_price
            item.total_price = (effective_price * _to_decimal(item.quantity)).quantize(Decimal('0.01'))
            item.save(update_fields=['product_price', 'total_price'])

            subtotal += item.total_price

        tax = _to_decimal(order.tax_amount)
        shipping = _to_decimal(order.shipping_amount)

        order.subtotal = subtotal
        order.total_amount = (subtotal + tax + shipping).quantize(Decimal('0.01'))
        order.save(update_fields=['subtotal', 'total_amount'])

        return order
    # def setup_paypal(self):
    #     """Configure PayPal - placeholder for future implementation"""
    #      # PayPal integration would go here
    #     pass
    
    # def create_checkout(self, order_data, customer_info, request):
    #     """Main checkout method - routes to specific gateway"""
    #     if self.gateway.gateway_type == 'stripe':
    #         return self.create_stripe_checkout(order_data, customer_info, request)
    #     else:
    #         raise ValidationError(f"Payment gateway {self.gateway.gateway_type} not implemented")

    def create_checkout(self, order_data, customer_info, request):
        """Main checkout method - routes to specific gateway"""
        if self.gateway.gateway_type == 'stripe':
            return self.create_stripe_checkout(order_data, customer_info, request)
        elif self.gateway.gateway_type == 'paypal':
            return self.create_paypal_checkout(order_data, customer_info, request)
        elif self.gateway.gateway_type == 'razorpay':  # ADD THIS
            return self.create_razorpay_checkout(order_data, customer_info, request)
        elif self.gateway.gateway_type == 'fincra':  # ADD THIS
            return self.create_fincra_checkout(order_data, customer_info, request)
        elif self.gateway.gateway_type == 'cryptomus':  # ADD THIS
            return self.create_cryptomus_checkout(order_data, customer_info, request)
        elif self.gateway.gateway_type == 'pay_on_delivery':
            return self.create_pod_checkout(order_data, customer_info, request)
        elif self.gateway.gateway_type == 'social_media':  # ADD THIS
            return self.create_social_media_checkout(order_data, customer_info, request)
        else:
            raise ValidationError(f"Payment gateway {self.gateway.gateway_type} not implemented")


    # ADD THIS NEW METHOD
    def create_social_media_checkout(self, order_data, customer_info, request):
        """Create social media checkout"""
         # Extract shipping info from order_data (same level as customer)
        shipping_cost = order_data.get('shipping_cost', 0)
        shipping_rate = order_data.get('shipping_rate', {})
        
        # Add shipping to customer_info so it gets saved with order
        customer_info['shipping_cost'] = shipping_cost
        customer_info['shipping_method'] = shipping_rate.get('name', 'Standard Shipping')
        customer_info['delivery_estimate'] = shipping_rate.get('delivery_estimate', '')
        
        print(f'📦 Shipping data added to customer_info: cost={shipping_cost}, method={customer_info["shipping_method"]}')
        try:
            from .social_media_service import SocialMediaService
            social_service = SocialMediaService(self.gateway)
            
            result = social_service.create_social_media_order(order_data, customer_info, request)
            
            # Store order number in session for success page
            request.session['last_order_number'] = result['order_number']
            request.session['payment_method'] = 'social_media'
            request.session['social_media_messages'] = result['platform_messages']
            
            return result
            
        except Exception as e:
            raise ValidationError(f"Social media checkout failed: {str(e)}")
    
        
    #POD checkout
    def create_pod_checkout(self, order_data, customer_info, request):
        """Create Pay on Delivery checkout"""
        try:

            # Debug: Print the data types
            print(f"Order data type: {type(order_data)}")
            print(f"Order data: {order_data}")
            
            # Check each field that might be causing tuple issues
            if 'order_number' in order_data:
                print(f"Order number type: {type(order_data['order_number'])}")
                print(f"Order number value: {order_data['order_number']}")
            
            if 'items' in order_data:
                print(f"Items type: {type(order_data['items'])}")
                for item in order_data['items']:
                    print(f"Item: {item}")
            
            result = self.pod_service.create_pod_order(order_data, customer_info, request)
            
            # Store order number in session for success page
            request.session['last_order_number'] = result['order_number']
            request.session['payment_method'] = 'pay_on_delivery'
            
            return result
            
        except Exception as e:
            raise ValidationError(f"Pay on Delivery checkout failed: {str(e)}")
            

        # ADD NEW METHOD for Cryptomus checkout:
    def create_cryptomus_checkout(self, order_data, customer_info, request):
        """Create Cryptomus cryptocurrency checkout"""
        try:
            # First create order in our database
            if order_data.get('checkout_type') == 'instant':
                order = self.create_order_from_product(order_data.get('product', {}), customer_info)
            else:  # cart checkout
                order = self.create_order_from_cart(order_data.get('cart', {}), customer_info, order_data)
            # Create Cryptomus checkout data
            checkout_data = self.cryptomus_service.create_checkout_data(order_data, customer_info, request)
            
            # Create transaction record
            Transaction.objects.create(
                order=order,
                payment_gateway=self.gateway,
                gateway_transaction_id=checkout_data['payment_uuid'],
                amount=order.total_amount,
                currency='USD',  # We'll convert to crypto amount
                status='pending',
                gateway_response=checkout_data,
                metadata={
                    'crypto_amount': checkout_data['amount'],
                    'crypto_currency': checkout_data['currency'],
                    'crypto_address': checkout_data['address'],
                    'crypto_network': checkout_data['network'],
                    'payment_url': checkout_data['payment_url']
                }
            )
            
            return {
                'payment_url': checkout_data['payment_url'],
                'payment_id': checkout_data['payment_id'],
                'payment_uuid': checkout_data['payment_uuid'],
                'crypto_amount': checkout_data['amount'],
                'crypto_currency': checkout_data['currency'],
                'crypto_address': checkout_data['address'],
                'crypto_network': checkout_data['network'],
                'qr_code': checkout_data.get('qr_code'),
                'expired_at': checkout_data.get('expired_at'),
                'order_number': order.order_number,
                'gateway': 'cryptomus',
                'redirect_type': 'link',
                'is_crypto': True
            }
            
        except Exception as e:
            raise ValidationError(f"Cryptomus checkout creation failed: {str(e)}")
        
    #  Fincra checkout:
    def create_fincra_checkout(self, order_data, customer_info, request):
        """Create Fincra checkout"""
        try:
            # First create order in our database
            if order_data.get('checkout_type') == 'instant':
                order = self.create_order_from_product(order_data.get('product', {}), customer_info)
            else:  # cart checkout
                order = self.create_order_from_cart(order_data.get('cart', {}), customer_info)
            
            # Create Fincra checkout data
            checkout_data = self.fincra_service.create_checkout_data(order_data, customer_info, request)
            
            # Create transaction record
            Transaction.objects.create(
                order=order,
                payment_gateway=self.gateway,
                gateway_transaction_id=checkout_data['reference'],
                amount=order.total_amount,
                currency='NGN',  # Fincra primarily uses NGN
                status='pending',
                gateway_response=checkout_data
            )
            
            return {
                'payment_link': checkout_data['payment_link'],
                'reference': checkout_data['reference'],
                'order_number': order.order_number,
                'gateway': 'fincra',
                'redirect_type': 'link'  # Fincra uses payment links
            }
            
        except Exception as e:
            raise ValidationError(f"Fincra checkout creation failed: {str(e)}")
        
    #  Razorpay checkout:
    def create_razorpay_checkout(self, order_data, customer_info, request):
        """Create Razorpay checkout"""
        try:
            # First create order in our database
            if order_data.get('checkout_type') == 'instant':
                order = self.create_order_from_product(order_data.get('product', {}), customer_info)
            else:  # cart checkout
                order = self.create_order_from_cart(order_data.get('cart', {}), customer_info)
            
            # Create Razorpay checkout data
            checkout_data = self.razorpay_service.create_checkout_data(order_data, customer_info, request)
            
            # Create transaction record
            Transaction.objects.create(
                order=order,
                payment_gateway=self.gateway,
                gateway_transaction_id=checkout_data['order_id'],
                amount=order.total_amount,
                currency='INR',  # Razorpay primarily uses INR
                status='pending',
                gateway_response=checkout_data
            )
            
            return {
                'order_id': checkout_data['order_id'],
                'razorpay_data': checkout_data,
                'order_number': order.order_number,
                'gateway': 'razorpay'
            }
            
        except Exception as e:
            raise ValidationError(f"Razorpay checkout creation failed: {str(e)}")
        
    def create_paypal_checkout(self, order_data, customer_info, request):
        """Create PayPal checkout"""
        try:
            # First create the order in our database
            if order_data.get('checkout_type') == 'instant':
                order = self.create_order_from_product(order_data.get('product', {}), customer_info)
            else:  # cart checkout
                order = self.create_order_from_cart(order_data.get('cart', {}), customer_info)
            
            # Create PayPal order
            paypal_result = self.paypal_service.create_order(order_data, customer_info, request)
            
            # Create transaction record
            Transaction.objects.create(
                order=order,
                payment_gateway=self.gateway,
                gateway_transaction_id=paypal_result['order_id'],
                amount=order.total_amount,
                status='pending',
                gateway_response=paypal_result
            )
            
            return {
                'order_id': paypal_result['order_id'],
                'approval_url': paypal_result['approval_url'],   # kept as fallback
                'client_id': self.gateway.get_paypal_client_id(), # public — safe for frontend
                'order_number': order.order_number,
                'mode': 'inline',                                 # tells frontend to use SDK
                'gateway': 'paypal'
            }            
        except Exception as e:
            raise ValidationError(f"PayPal checkout creation failed: {str(e)}")
    
    def create_stripe_checkout(self, order_data, customer_info, request):
        """Create a PaymentIntent for embedded Elements checkout."""
        try:
            checkout_type = order_data.get('checkout_type', 'instant')

            if checkout_type == 'instant':
                order = self.create_order_from_product(
                    order_data.get('product', {}), customer_info
                )
            else:
                order = self.create_order_from_cart(
                    order_data.get('cart', {}), customer_info, order_data
                )

            self._recompute_order_totals(order)

            intent = self.stripe_service.create_embedded_payment_intent(
                order,
                metadata={'checkout_type': checkout_type},
            )

            Transaction.objects.create(
                order=order,
                payment_gateway=self.gateway,
                gateway_payment_intent_id=intent.id,
                gateway_transaction_id=intent.id,
                amount=order.total_amount,
                currency=order.currency,
                status='pending',
                gateway_response={'intent_id': intent.id, 'status': intent.status},
            )

            return {
                'client_secret': intent.client_secret,
                'publishable_key': self.gateway.get_public_key(),
                'order_number': order.order_number,
                'amount': float(order.total_amount),
                'currency': order.currency.lower(),
                'gateway': 'stripe',
                'mode': 'elements',
            }
        except Exception as e:
            raise ValidationError(f"Stripe checkout creation failed: {str(e)}")
        
    # Helper methods remain the same...
    def create_order_from_product(self, product_data, customer_info):
        """Create order from single product"""
         # Get product ID - try both 'id' and 'product_id'
        product_id = product_data.get('id') or product_data.get('product_id')
        payment_gateway = self.gateway.gateway_type

        print(f'payment_gateway  is {payment_gateway}')
        print(f'Product  is {product_data}')

        print(f'Product ID is {product_id}')
        
        print(f'Customer info  is {customer_info}')
        
        quantity = product_data.get('quantity', 1)
        
        # ONE LINE - Validates AND deducts stock
        success, error = check_and_deduct_stock(self.page, [{'product_id': product_id, 'quantity': quantity}])
        if not success:
            raise ValidationError(error)
    
        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        # Calculate tax first
        tax_service = TaxService(self.page)
        items_for_tax = []
        for item in product_data.get('items', []):
            print(f'Product ID in tax is is {item.get("product_id")}')
            items_for_tax.append({
                'product_id': item.get('product_id'),
                'title': item.get('title'),
                'price': item.get('price'),
                'quantity': item.get('quantity'),
                'tax_class_id': item.get('tax_class_id')
            })
        
        tax_result = tax_service.calculate_tax(
            items=items_for_tax,
            customer_data=customer_info,
            shipping_cost=customer_info.get('shipping_cost', 0)
        )
        subtotal=product_data['price'] * product_data.get('quantity', 1)
        tax_amount=tax_result['tax_total']

        shipping_method = customer_info.get('shipping_method', 'Standard Shipping')
        delivery_estimate = customer_info.get('delivery_estimate', '')
        shipping_amount =customer_info.get('shipping_cost', 0)
        total_amount = subtotal + tax_amount + shipping_amount
        print(f"Country iso {customer_info}")
        order = Order.objects.create(
            page=self.page,
            order_number=order_number,
            customer_email=customer_info.get('email', ''),
            customer_name=customer_info.get('name', ''),
            phone=customer_info.get('phone', ''),
            customer_address=customer_info.get('delivery_address'),
            customer_city=customer_info.get('city'),
            customer_state=customer_info.get('state'),
            customer_zip=customer_info.get('zip'),
            customer_country=customer_info.get('country_name'),
            country_iso=customer_info.get('country', ''),
            delivery_address=customer_info.get('delivery_address'),
            delivery_state=customer_info.get('delivery_state'),
            delivery_city = customer_info.get('delivery_city'),
            delivery_zip=customer_info.get('delivery_zip'),
            delivery_country=customer_info.get('country'),
            delivery_notes=customer_info.get('delivery_notes'),
            vid=product_data.get('vid', ''),
            
            subtotal=subtotal,
            tax_amount=tax_amount,
            shipping_amount=shipping_amount,
            total_amount=total_amount,

            payment_method=payment_gateway,
        )
        # Get product for additional details
        product = None
        try:
            product = Product.objects.get(id=product_data.get('product_id'))
        except Product.DoesNotExist:
            pass
        OrderItem.objects.create(
            order=order,
            product_variant=product_data.get('cj_vid', ''),
            product_id=product_id,
            vid = product_data.get('cj_vid', ''),
            product_title=product_data['title'],
            product_price=product_data['price'],
            quantity=product_data.get('quantity', 1),
            total_price=total_amount,

            # NEW: Include variant data
            selected_color=product_data.get('selected_color', ''),
            selected_size=product_data.get('selected_size', ''),
            # product_variant=f"{product_data.get('selected_color', '')} {product_data.get('selected_size', '')}".strip(),
            product_sku=product_data.get('sku', product.sku if product else ''),
            product_image=product_data.get('image_url', product.main_image.url if product and product.main_image else '')
        )

        # Save tax transaction for auditing
        tax_service.save_tax_transaction(order, tax_result)

        try:
            from .email_service import EmailService 
            EmailService.send_order_confirmation(order)
            # Notify the Store Owner
            EmailService.send_admin_order_notification(order)
        except Exception as e:
            
            print(f"Notification error: {e}")
        
        return order
    
    
    def create_order_from_cart(self, cart_data, customer_info, order_data=None):
        """Create order from cart data"""

         # Get product ID - try both 'id' and 'product_id'
    # Build items list for stock validation - handle all possible key names
        items = []
        for item in cart_data.get('items', []):
            # Try all possible keys for product ID
            product_id = (item.get('product_id') or 
                        item.get('id') or 
                        item.get('product'))
            quantity = item.get('quantity', 1)
            items.append({'product_id': product_id, 'quantity': quantity})
        
        # ONE LINE - Validates AND deducts stock
        success, error = check_and_deduct_stock(self.page, items)
        if not success:
            raise ValidationError(error)
        
        payment_gateway = self.gateway.gateway_type
    
        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        
        # Get shipping info from order_data if provided
        shipping_method = customer_info.get('shipping_method', 'Standard Shipping')
        delivery_estimate = customer_info.get('delivery_estimate', '')
        shipping_amount = customer_info.get('shipping_cost', 0)
        
        if order_data:
            shipping_cost = order_data.get('shipping_cost', 0)
            shipping_rate = order_data.get('shipping_rate', {})
            shipping_method = shipping_rate.get('name', 'Standard Shipping')
            delivery_estimate = shipping_rate.get('delivery_estimate', '')
            shipping_amount = shipping_cost
        
        # FIXED: Use delivery_estimate, not shipping_delivery_estimate
        print(f'💾 Saving order with shipping: cost={shipping_amount}, method={shipping_method}')
        print(f"Shipping data received: amount={shipping_amount}, method={shipping_method}, estimate={delivery_estimate}")
        
        tax_service = TaxService(self.page)
        items_for_tax = []
        for item in cart_data.get('items', []):
            items_for_tax.append({
                'product_id': item.get('product_id'),
                'title': item.get('title'),
                'price': item.get('price'),
                'quantity': item.get('quantity'),
                'tax_class_id': item.get('tax_class_id')
            })

        
        tax_result = tax_service.calculate_tax(
            items=items_for_tax,
            customer_data=customer_info,
            shipping_cost=cart_data.get('shipping_amount', 0)
        )
        
        # Get country ISO from the 'country' field
        country_iso = customer_info.get('country', '')
        
        # If country_iso is empty, try country_name as fallback
        if not country_iso:
            country_iso = customer_info.get('country_iso', '')
        
        # If still empty, use a default
        if not country_iso:
            country_iso = 'US'  # Default to US
        
        print(f"Country ISO being saved: {country_iso}")
        
        order = Order.objects.create(
            page=self.page,
            order_number=order_number,
            customer_email=customer_info.get('email', ''),
            customer_name=customer_info.get('name', ''),
            phone=customer_info.get('phone', ''),
            customer_address=customer_info.get('delivery_address', ''),
            customer_city=customer_info.get('city', ''),
            customer_state=customer_info.get('state', ''),
            customer_zip=customer_info.get('zip', ''),
            customer_country=customer_info.get('country_name', ''),
            country_iso=country_iso,
            delivery_address=customer_info.get('delivery_address', ''),
            delivery_state=customer_info.get('delivery_state', ''),
            delivery_city=customer_info.get('delivery_city', ''),
            delivery_zip=customer_info.get('delivery_zip', ''),
            delivery_country=customer_info.get('country_name', ''),
            delivery_notes=customer_info.get('delivery_notes', ''),
            vid=cart_data.get('vid', ''),
            
            # Shipping information 
            shipping_method=shipping_method,
            shipping_delivery_estimate=delivery_estimate,  # FIXED: Use delivery_estimate here
            
            subtotal=cart_data.get('subtotal', 0),
            tax_amount=tax_result['tax_total'],
            shipping_amount=shipping_amount,
            total_amount=cart_data.get('total_amount', 0),

            payment_method=payment_gateway,

        )
        
        for item in cart_data.get('items', []):
            # Get product details for additional fields
            product = None
            try:
                product = Product.objects.get(id=item.get('product_id'))
            except Product.DoesNotExist:
                pass
            
            OrderItem.objects.create(
                order=order,
                product_id=item.get('id', ''),
                vid=item.get('cj_vid', ''),
                product_description=item.get('description', ''),
                product_title=item.get('title', ''),
                product_price=item.get('price', 0),
                quantity=item.get('quantity', 1),
                total_price=item.get('total_price', 0),
                selected_color=item.get('selected_color', ''),
                selected_size=item.get('selected_size', ''),
                product_variant=f"{item.get('selected_color', '')} {item.get('selected_size', '')}".strip(),
                product_sku=item.get('sku', product.sku if product else ''),
                product_image=item.get('image_url', product.main_image.url if product and product.main_image else '')
            )

        # Save tax transaction for auditing
        tax_service.save_tax_transaction(order, tax_result)
        
        try:
            from .email_service import EmailService
            EmailService.send_order_confirmation(order)
            # Notify the Store Owner
            EmailService.send_admin_order_notification(order)
        except Exception as e:
            print(f"Notification error: {e}")

        return order
    
    def get_stripe_line_items_from_product(self, product_data):
        return [{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': product_data['title'],
                    'description': product_data.get('description', ''),
                },
                'unit_amount': int(product_data['price'] * 100),
            },
            'quantity': product_data.get('quantity', 1),
        }]
    
    def get_stripe_line_items_from_cart(self, cart_data):
        line_items = []
        for item in cart_data.get('items', []):
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': item['title'],
                        'description': item.get('description', ''),
                    },
                    'unit_amount': int(item['price'] * 100),
                },
                'quantity': item.get('quantity', 1),
            })
        return line_items



