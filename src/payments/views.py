from asyncio.log import logger
from decimal import Decimal
from django.urls import reverse
from xml.dom import ValidationErr
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .services.fincra_service import FincraService
from .services.cryptomus_service import CryptomusService
from .models import PaymentGateway
# Add this import with your other imports
from .models import TaxTransaction
from django.utils import timezone 
from django.db.models import Avg, Sum, Count, Max, Min, StdDev, Variance, Q, F
from django.conf import settings
import json
import uuid
# Add these imports at the top of payments/views.py
from urllib.parse import quote
import re

from builder.models import PublishedPage
from .models import PaymentGateway, Order, OrderItem, Transaction
from .services.stripe_service import StripePaymentService
import razorpay
from .services.razorpay_service import RazorpayService
from payments.decorators import *

@login_required
@login_required
def manage_payment_gateways(request, subdomain):
    """Manage payment gateways for a published page"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    payment_gateways = page.payment_gateways.all()
    
    
    # Get or create Stripe gateway for the template
    stripe_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='stripe',
        defaults={
            'is_active': False,
            'is_test_mode': True,
        }
    )
    paypal_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='paypal',
        defaults={
            'is_active': False,
            'is_test_mode': True,
        }
    )


    pod_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='pay_on_delivery',
        defaults={
            'is_active': False,  # Default active
            'is_test_mode': False,
            'pod_minimum_amount': 0,
            'pod_maximum_amount': 500,
            'pod_requires_confirmation': True,
        }
    )

    
    social_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='social_media',
        defaults={
            'is_active': False,  # Default active
            'is_test_mode': False,
        }
    )
    
    
    # Calculate statistics
    active_gateways_count = payment_gateways.filter(is_active=True).count()
    test_mode_gateways_count = payment_gateways.filter(is_test_mode=True).count()
    live_mode_gateways_count = payment_gateways.filter(is_test_mode=False).count()
    
    return render(request, 'payments/manage_gateways.html', {
        'page': page,
        'payment_gateways': payment_gateways,
        'stripe_gateway': stripe_gateway,
        'paypal_gateway':paypal_gateway,
        'pod_gateway': pod_gateway,  
        'social_gateway':social_gateway,
        'active_gateways_count': active_gateways_count,
        'test_mode_gateways_count': test_mode_gateways_count,
        'live_mode_gateways_count': live_mode_gateways_count,
    })

@login_required
def configure_stripe_gateway(request, subdomain):
    """Configure Stripe payment gateway"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create Stripe gateway
    stripe_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='stripe',
        defaults={
            'is_active': False,
            'is_test_mode': True,
        }
    )
    
    if request.method == 'POST':
        stripe_gateway.test_public_key = request.POST.get('test_public_key', '').strip()
        stripe_gateway.test_secret_key = request.POST.get('test_secret_key', '').strip()
        stripe_gateway.live_public_key = request.POST.get('live_public_key', '').strip()
        stripe_gateway.live_secret_key = request.POST.get('live_secret_key', '').strip()
        stripe_gateway.webhook_secret = request.POST.get('webhook_secret', '').strip()
        stripe_gateway.is_test_mode = request.POST.get('is_test_mode') == 'on'
        stripe_gateway.is_active = request.POST.get('is_active') == 'on'
        
        # Validate Stripe configuration
        try:
            if stripe_gateway.is_active:
                service = StripePaymentService(stripe_gateway)
                # Test connection by creating a test intent
                service.create_payment_intent(1.00)  # $1 test
                
            stripe_gateway.save()
            messages.success(request, 'Stripe configuration saved successfully!')
            return redirect('payments:manage_gateways', subdomain=subdomain)
            
        except Exception as e:
            messages.error(request, f'Stripe configuration error: {str(e)}')
    
    return render(request, 'payments/configure_stripe.html', {
        'page': page,
        'stripe_gateway': stripe_gateway,
    })

# @csrf_exempt
# def create_checkout_session(request, subdomain):
#     """Create Stripe checkout session"""
#     if request.method == 'POST':
#         try:
#             page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
#             data = json.loads(request.body)
            
#             # Get active Stripe gateway
#             stripe_gateway = page.payment_gateways.filter(
#                 gateway_type='stripe', 
#                 is_active=True
#             ).first()
            
#             if not stripe_gateway:
#                 return JsonResponse({'error': 'Stripe payment gateway not configured'}, status=400)
            
#             # Create order
#             order = create_order_from_cart(page, data)
            
#             # Create Stripe checkout session
#             service = StripePaymentService(stripe_gateway)
            
#             success_url = f"{request.build_absolute_uri('/')}payments/checkout-success/{subdomain}/?session_id={{CHECKOUT_SESSION_ID}}"
#             cancel_url = f"{request.build_absolute_uri('/')}payments/checkout-cancel/{subdomain}/?session_id={{CHECKOUT_SESSION_ID}}"
            
#             session = service.create_checkout_session(order, success_url, cancel_url)
            
#             return JsonResponse({
#                 'sessionId': session.id,
#                 'publicKey': stripe_gateway.test_public_key if stripe_gateway.is_test_mode else stripe_gateway.live_public_key
#             })
            
#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=400)
    
#     return JsonResponse({'error': 'Invalid request method'}, status=405)



@csrf_exempt
def create_checkout_session(request, subdomain):
    """Create Stripe checkout session"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
            data = json.loads(request.body)
            
            # Get active Stripe gateway
            stripe_gateway = page.payment_gateways.filter(
                gateway_type='stripe',
                is_active=True
            ).first()
            
            if not stripe_gateway:
                return JsonResponse({'error': 'Stripe payment gateway not configured'}, status=400)
            
            # Add customer information to cart data
            customer_info = data.get('customer', {})
            cart_data = data.get('cart', {})
            
            # Merge customer info into cart data
            cart_data.update({
                'customer_email': customer_info.get('email', ''),
                'customer_name': customer_info.get('name', ''),
                'customer_phone': customer_info.get('phone', ''),
                'customer_address': customer_info.get('address', ''),
                'customer_city': customer_info.get('city', ''),
                'customer_state': customer_info.get('state', ''),
                'customer_zip': customer_info.get('zip', ''),
                'customer_country': customer_info.get('country_name', ''),
                'country_iso': customer_info.get('country_iso', ''),
                'payment_method': 'stripe',
                'ip_address': get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'referrer': request.META.get('HTTP_REFERER', ''),
            })
            
            # Create order
            order = create_order_from_cart(page, cart_data)
            
            # Create Stripe checkout session
            service = StripePaymentService(stripe_gateway)
            
            success_url = f"{request.build_absolute_uri('/')}payments/checkout-success/{subdomain}/?session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{request.build_absolute_uri('/')}payments/checkout-cancel/{subdomain}/?session_id={{CHECKOUT_SESSION_ID}}"
            
            session = service.create_checkout_session(order, success_url, cancel_url)
            
            return JsonResponse({
                'sessionId': session.id,
                'publicKey': stripe_gateway.test_public_key if stripe_gateway.is_test_mode else stripe_gateway.live_public_key
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def create_order_from_cart(page, cart_data):
    """Create order from cart data"""
    # This function expects page and cart_data
    # Make sure it handles both instant and cart checkout types
    
    order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    # Check if it's instant checkout (has product)
    if cart_data.get('checkout_type') == 'instant' and cart_data.get('product'):
        product = cart_data.get('product')
        customer_info = cart_data.get('customer', {})
        
        order = Order.objects.create(
            page=page,
            order_number=order_number,
            customer_email=customer_info.get('email', ''),
            customer_name=customer_info.get('name', ''),
            phone=customer_info.get('phone', ''),
            customer_address=customer_info.get('address', ''),
            customer_city=customer_info.get('city', ''),
            customer_state=customer_info.get('state', ''),
            customer_zip=customer_info.get('zip', ''),
            customer_country=customer_info.get('country', 'US'),
            country_iso=customer_info.get('country_iso', ''),
            delivery_address=customer_info.get('delivery_address', customer_info.get('address', '')),
            delivery_city=customer_info.get('delivery_city', customer_info.get('city', '')),
            delivery_state=customer_info.get('delivery_state', customer_info.get('state', '')),
            delivery_zip=customer_info.get('delivery_zip', customer_info.get('zip', '')),
            delivery_country=customer_info.get('country', 'US'),
            delivery_notes=customer_info.get('delivery_notes', ''),
            subtotal=cart_data.get('subtotal', product.get('price', 0) * product.get('quantity', 1)),
            tax_amount=cart_data.get('tax_amount', 0),
            shipping_amount=cart_data.get('shipping_amount', 0),
            total_amount=cart_data.get('total_amount', product.get('price', 0) * product.get('quantity', 1)),
            payment_method=cart_data.get('payment_method', 'social_media'),
            vid=product.get('cj_vid', ''),
        )
        
        # Create order item
        OrderItem.objects.create(
            order=order,
            product_id=product.get('id', ''),
            vid=product.get('cj_vid', ''),
            product_title=product.get('title', 'Product'),
            product_description=product.get('description', ''),
            product_price=product.get('price', 0),
            quantity=product.get('quantity', 1),
            total_price=product.get('total_price', product.get('price', 0) * product.get('quantity', 1)),
            selected_color=product.get('selected_color', ''),
            selected_size=product.get('selected_size', ''),
            product_variant=f"{product.get('selected_color', '')} {product.get('selected_size', '')}".strip(),
        )
        
    else:
        # Cart checkout
        customer_info = cart_data.get('customer', {})
        
        order = Order.objects.create(
            page=page,
            order_number=order_number,
            customer_email=customer_info.get('email', ''),
            customer_name=customer_info.get('name', ''),
            phone=customer_info.get('phone', ''),
            customer_address=customer_info.get('address', ''),
            customer_city=customer_info.get('city', ''),
            customer_state=customer_info.get('state', ''),
            customer_zip=customer_info.get('zip', ''),
            customer_country=customer_info.get('country', 'US'),
            country_iso=customer_info.get('country_iso', ''),
            delivery_address=customer_info.get('delivery_address', customer_info.get('address', '')),
            delivery_city=customer_info.get('delivery_city', customer_info.get('city', '')),
            delivery_state=customer_info.get('delivery_state', customer_info.get('state', '')),
            delivery_zip=customer_info.get('delivery_zip', customer_info.get('zip', '')),
            delivery_country=customer_info.get('country', 'US'),
            delivery_notes=customer_info.get('delivery_notes', ''),
            subtotal=cart_data.get('subtotal', 0),
            tax_amount=cart_data.get('tax_amount', 0),
            shipping_amount=cart_data.get('shipping_amount', 0),
            total_amount=cart_data.get('total_amount', 0),
            payment_method=cart_data.get('payment_method', 'social_media'),
            vid=cart_data.get('vid', ''),
        )
        
        # Create order items from cart
        for item in cart_data.get('items', []):
            OrderItem.objects.create(
                order=order,
                product_id=item.get('id', ''),
                vid=item.get('cj_vid', ''),
                product_title=item.get('title', 'Product'),
                product_description=item.get('description', ''),
                product_price=item.get('price', 0),
                quantity=item.get('quantity', 1),
                total_price=item.get('total_price', item.get('price', 0) * item.get('quantity', 1)),
                selected_color=item.get('selected_color', ''),
                selected_size=item.get('selected_size', ''),
                product_variant=f"{item.get('selected_color', '')} {item.get('selected_size', '')}".strip(),
                product_sku=item.get('sku', ''),
                product_image=item.get('image_url', ''),
            )
    
    return order


@csrf_exempt
def stripe_webhook(request, subdomain):
    """Handle Stripe webhooks (embedded checkout + payment intents)"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    stripe_gateway = get_object_or_404(PaymentGateway, page=page, gateway_type='stripe')

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        service = StripePaymentService(stripe_gateway)
        event = service.handle_webhook(
            payload, sig_header, stripe_gateway.webhook_secret
        )
    except Exception as e:
        return HttpResponse(str(e), status=400)

    etype = event['type']
    obj = event['data']['object']

    if etype == 'checkout.session.completed':
        # Embedded Checkout fires this
        handle_checkout_session_completed(obj)
    elif etype == 'payment_intent.succeeded':
        handle_payment_success(event)
    elif etype == 'payment_intent.payment_failed':
        handle_payment_failure(event)

    return HttpResponse(status=200)


def handle_checkout_session_completed(session):
    """Handle embedded Checkout completion."""
    session_id = session.get('id')
    order_number = (session.get('metadata') or {}).get('order_number')

    tx = Transaction.objects.filter(gateway_transaction_id=session_id).first()
    if not tx and order_number:
        order = Order.objects.filter(order_number=order_number).first()
        if order:
            tx = order.transactions.first()

    if not tx:
        return

    tx.status = 'success'
    tx.gateway_response = session
    tx.processed_at = timezone.now()
    tx.save(update_fields=['status', 'gateway_response', 'processed_at'])

    order = tx.order
    if order.status != 'completed':
        # --- TRIGGER CJ FULFILLMENT ---
        try:
            from builder.services.cj_fulfillment_service import fulfill_cj_order
            fulfill_cj_order(order)
        except Exception as e:
            print(f"CJ fulfillment error: {e}")

        order.status = 'completed'
        order.paid_at = timezone.now()
        order.save(update_fields=['status', 'paid_at'])


def handle_payment_success(event):
    """Handle successful payment_intent (kept for backup path)."""
    payment_intent = event['data']['object']

    try:
        transaction = Transaction.objects.get(
            gateway_payment_intent_id=payment_intent['id']
        )
        transaction.status = 'success'
        transaction.gateway_response = payment_intent
        transaction.processed_at = timezone.now()
        transaction.save(update_fields=['status', 'gateway_response', 'processed_at'])

        order = transaction.order
        if order.status != 'completed':
            # --- TRIGGER CJ FULFILLMENT ---
            try:
                from builder.services.cj_fulfillment_service import fulfill_cj_order
                fulfill_cj_order(order)
            except Exception as e:
                print(f"CJ fulfillment error: {e}")

            order.status = 'completed'
            order.paid_at = timezone.now()
            order.save(update_fields=['status', 'paid_at'])

    except Transaction.DoesNotExist:
        pass


def handle_payment_failure(event):
    """Handle payment_intent.payment_failed."""
    payment_intent = event['data']['object']
    tx = Transaction.objects.filter(
        gateway_payment_intent_id=payment_intent['id']
    ).first()
    if not tx:
        return
    tx.status = 'failed'
    tx.gateway_response = payment_intent
    tx.processed_at = timezone.now()
    tx.save(update_fields=['status', 'gateway_response', 'processed_at'])

    
# def checkout_success(request, subdomain):
#     """Checkout success page"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain)
#     session_id = request.GET.get('session_id')
    
#     return render(request, 'payments/checkout_success.html', {
#         'page': page,
#         'session_id': session_id,
#     })

def checkout_success(request, subdomain):
    """Checkout success page with CJ fulfillment"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    session_id = request.GET.get('session_id')
    
    # Try to find the order from the session or transaction
    order = None
    order_number = request.session.get('last_order_number', '')
    
    if order_number:
        try:
            order = Order.objects.get(
                order_number=order_number,
                page=page,
                status='pending'  # Orders start as pending before payment confirmation
            )
        except Order.DoesNotExist:
            pass
    
    # If no order found from session, try to find by transaction
    if not order and session_id:
        try:
            transaction = Transaction.objects.get(
                gateway_transaction_id=session_id,
                payment_gateway__page=page
            )
            order = transaction.order
        except Transaction.DoesNotExist:
            pass
    
    # ========== CJ FULFILLMENT LOGIC ==========
    if order and order.can_fulfill_cj():
        print(f"✅ Order {order.order_number} eligible for CJ fulfillment")
        
        from builder.services.cj_service import CJManager
        from builder.models import CJSettings
        import logging
        logger = logging.getLogger(__name__)
        
        # Get CJ settings for this specific page/store
        account = CJSettings.objects.filter(page=page).first()
        
        if account and account.access_token:
            try:
                manager = CJManager(token=account.access_token)
                
                # Call fulfillment (order is still in 'pending' state)
                success = manager.fulfill_cj_order_corrected(order)
                
                if success:
                    messages.success(request, f"CJ order #{order.cj_order_id} created successfully!")
                    print(f"✅ CJ order created: {order.cj_order_id}")
                else:
                    messages.error(request, "Failed to create CJ order. Please check CJ dashboard.")
                    
            except Exception as e:
                logger.error(f"CJ fulfillment error for order {order.order_number}: {str(e)}")
                messages.error(request, f"CJ fulfillment error: {str(e)}")
        else:
            messages.warning(request, "CJ integration not configured or token missing.")
            
    elif order:
        # Order exists but not eligible for CJ
        if order.is_cj_fulfilled:
            messages.info(request, f"Order already fulfilled via CJ (#{order.cj_order_id})")
        elif not order.all_items_have_vid:
            cj_count = order.cj_items_count
            manual_count = order.manual_items_count
            if cj_count > 0 and manual_count > 0:
                messages.warning(request, 
                    f"Order contains {cj_count} CJ item(s) and {manual_count} manual item(s). "
                    f"CJ fulfillment skipped for mixed orders."
                )
            else:
                messages.info(request, "No CJ items in order. Manual fulfillment required.")
    
    return render(request, 'payments/checkout_success.html', {
        'page': page,
        'session_id': session_id,
        'order': order,
        'order_number': order.order_number if order else None
    })

def checkout_cancel(request, subdomain):
    """Checkout cancel page"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    
    return render(request, 'payments/checkout_cancel.html', {
        'page': page,
    })




from .services.checkout_service import CheckoutService
from django.views.decorators.csrf import csrf_exempt
import json

# def payment_selection(request, subdomain):
#     """Payment method selection page"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
#     # Get available payment gateways
#     available_gateways = page.payment_gateways.filter(is_active=True)
    
#     # Get order data from session or request
#     order_data = request.session.get('pending_order', {})
    
#     context = {
#         'page': page,
#         'available_gateways': available_gateways,
#         'order_data': order_data,
#     }
    
#     return render(request, 'payments/payment_selection.html', context)

# payments/views.py - Update the payment_selection view

def payment_selection(request, subdomain):
    """Payment method selection page with Pay Via Chat integration"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
    # Get available payment gateways
    available_gateways = page.payment_gateways.filter(is_active=True)
    
    # Get order data from session
    order_data = request.session.get('pending_order', {})
    customer_info = request.session.get('customer_info', {})
    
    # Merge customer info into order data
    if customer_info:
        order_data['customer'] = customer_info
    
    # ========== GET SOCIAL MEDIA PLATFORMS ==========
    social_gateway = page.payment_gateways.filter(
        gateway_type='social_media',
        is_active=True
    ).first()
    
    platform_messages = {}
    platform_count = 0
    
    if social_gateway:
        # Get enabled platforms
        platforms = social_gateway.social_media_platforms or []
        
        # Get order for message prefill
        order_number = request.session.get('last_order_number', '')
        order = None
        if order_number:
            try:
                order = Order.objects.get(order_number=order_number, page=page)
            except Order.DoesNotExist:
                pass
        
        # Build order message
        order_message = build_order_message(order, order_data, customer_info)
        
        # Encode message for URL
        encoded_message = quote(order_message)
        
        for platform in platforms:
            platform_key = platform.lower()
            
            if platform_key == 'whatsapp':
                phone = social_gateway.whatsapp_number or ''
                if phone:
                    # Clean phone number (remove non-digits)
                    phone = re.sub(r'\D', '', phone)
                    if phone:
                        platform_messages['whatsapp'] = {
                            'icon': 'fab fa-whatsapp',
                            'display_name': 'WhatsApp',
                            'username': phone,
                            'business_name': social_gateway.whatsapp_business_name or page.brand_name,
                            'link': f"https://wa.me/{phone}?text={encoded_message}"
                        }
                        platform_count += 1
                        
            elif platform_key == 'facebook':
                page_id = social_gateway.facebook_page_id or ''
                if page_id:
                    platform_messages['facebook'] = {
                        'icon': 'fab fa-facebook-messenger',
                        'display_name': 'Messenger',
                        'username': social_gateway.facebook_username or page_id,
                        'business_name': social_gateway.whatsapp_business_name or page.brand_name,
                        'link': f"https://m.me/{page_id}?ref=order_{order_number}"
                    }
                    platform_count += 1
                    
            elif platform_key == 'instagram':
                username = social_gateway.instagram_username or ''
                if username:
                    platform_messages['instagram'] = {
                        'icon': 'fab fa-instagram',
                        'display_name': 'Instagram',
                        'username': username,
                        'business_name': social_gateway.whatsapp_business_name or page.brand_name,
                        'link': f"https://www.instagram.com/{username}/"
                    }
                    platform_count += 1
                    
            elif platform_key == 'telegram':
                username = social_gateway.telegram_username or ''
                if username:
                    # Remove @ if present
                    username = username.lstrip('@')
                    platform_messages['telegram'] = {
                        'icon': 'fab fa-telegram',
                        'display_name': 'Telegram',
                        'username': username,
                        'business_name': social_gateway.whatsapp_business_name or page.brand_name,
                        'link': f"https://t.me/{username}"
                    }
                    platform_count += 1
                    
            elif platform_key == 'x':
                username = social_gateway.x_username or ''
                if username:
                    username = username.lstrip('@')
                    platform_messages['x'] = {
                        'icon': 'fab fa-x-twitter',
                        'display_name': 'X.com',
                        'username': username,
                        'business_name': social_gateway.whatsapp_business_name or page.brand_name,
                        'link': f"https://twitter.com/{username}"
                    }
                    platform_count += 1
    
    context = {
        'page': page,
        'available_gateways': available_gateways,
        'order_data': order_data,
        'platform_messages': platform_messages,
        'platform_count': platform_count,
        'customer_info': customer_info,
    }
    
    return render(request, 'payments/payment_selection.html', context)


def build_order_message(order, order_data, customer_info):
    """Build prefilled order message for chat platforms"""
    message = "Hello! I would like to place an order.\n\n"
    
    if order:
        message += f"📦 Order #: {order.order_number}\n"
        message += f"👤 Customer: {order.customer_name}\n"
        message += f"📧 Email: {order.customer_email}\n"
        message += f"📱 Phone: {order.phone}\n\n"
        
        message += "🛍️ Order Items:\n"
        for item in order.items.all():
            variant = ""
            if item.selected_color:
                variant += f" Color: {item.selected_color}"
            if item.selected_size:
                variant += f" Size: {item.selected_size}"
            message += f"  • {item.quantity}x {item.product_title}{variant} - ${item.total_price}\n"
        
        message += f"\n💰 Total: ${order.total_amount}\n"
        message += f"📍 Delivery: {order.delivery_address or order.customer_address}\n"
        if order.delivery_city or order.customer_city:
            message += f"📍 City: {order.delivery_city or order.customer_city}\n"
        if order.delivery_state or order.customer_state:
            message += f"📍 State: {order.delivery_state or order.customer_state}\n"
        
    else:
        # Fallback from order_data
        if order_data.get('checkout_type') == 'instant':
            product = order_data.get('product', {})
            message += f"🛍️ Product: {product.get('title', 'Product')}\n"
            message += f"💰 Price: ${product.get('price', 0)}\n"
        else:
            cart = order_data.get('cart', {})
            message += "🛍️ Items:\n"
            for item in cart.get('items', []):
                message += f"  • {item.get('quantity', 1)}x {item.get('title', 'Product')} - ${item.get('price', 0)}\n"
            message += f"\n💰 Total: ${cart.get('total_amount', 0)}\n"
        
        if customer_info:
            message += f"\n👤 Customer: {customer_info.get('name', '')}\n"
            message += f"📧 Email: {customer_info.get('email', '')}\n"
            message += f"📱 Phone: {customer_info.get('phone', '')}\n"
            message += f"📍 Address: {customer_info.get('address', '')}\n"
    
    return message






@csrf_exempt
def process_payment_selection(request, subdomain):
    """Process payment method selection and create checkout"""
    if request.method == 'POST':
        try:
            import json
            import logging
            logger = logging.getLogger(__name__)
            
            # Log the raw request
            logger.info(f"Payment request for subdomain: {subdomain}")
            logger.info(f"Request body: {request.body}")
            
            page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
            data = json.loads(request.body)
            
            logger.info(f"Parsed data: {data}")
            
            payment_method = data.get('payment_method')
            order_data = data.get('order_data', {})
            
            logger.info(f"Payment method: {payment_method}")
            logger.info(f"Order data: {order_data}")
            
            if not payment_method:
                logger.warning("No payment method provided")
                return JsonResponse({'error': 'Please select a payment method'}, status=400)
            
            # Get customer info from session if not in order_data
            if 'customer' not in order_data:
                customer_info = request.session.get('customer_info', {})
                if customer_info:
                    logger.info(f"Customer info from session: {customer_info}")
                    order_data['customer'] = customer_info
                else:
                    logger.warning("No customer information found")
                    return JsonResponse({'error': 'Customer information is required'}, status=400)

             # Store shipping data in order_data for the checkout service
            # This is critical - make sure shipping_cost and shipping_rate are passed
            if 'shipping_cost' not in order_data:
                order_data['shipping_cost'] = 0
            if 'shipping_rate' not in order_data:
                order_data['shipping_rate'] = {}
            
            print(f"Shipping data in order_data: cost={order_data.get('shipping_cost')}, rate={order_data.get('shipping_rate')}")

             # Store in session for success page
            request.session['last_order_customer'] = order_data['customer']
            request.session['last_shipping_cost'] = order_data.get('shipping_cost', 0)
            request.session['last_shipping_method'] = order_data.get('shipping_rate', {}).get('name', 'Standard Shipping')
            request.session['last_shipping_estimate'] = order_data.get('shipping_rate', {}).get('delivery_estimate', '3-7 days')
            
            # Get the selected payment gateway
            gateway = page.payment_gateways.filter(
                gateway_type=payment_method,
                is_active=True
            ).first()
            
            if not gateway:
                logger.warning(f"Payment gateway {payment_method} not found or inactive")
                return JsonResponse({'error': f'{payment_method} payment is not available'}, status=400)
            
            logger.info(f"Found gateway: {gateway.gateway_type} (ID: {gateway.id})")
            
            # Process based on checkout type
            checkout_type = order_data.get('checkout_type', 'instant')
            logger.info(f"Checkout type: {checkout_type}")
            
            if checkout_type == 'instant':
                result = process_instant_payment(page, gateway, order_data, request)
            elif checkout_type == 'cart':
                result = process_cart_payment(page, gateway, order_data, request)
            else:
                logger.warning(f"Invalid checkout type: {checkout_type}")
                return JsonResponse({'error': 'Invalid checkout type'}, status=400)
            
            # Clear session data after successful order
            if 'pending_order' in request.session:
                del request.session['pending_order']
            if 'customer_info' in request.session:
                del request.session['customer_info']
            
            logger.info(f"Payment successful, result: {result}")
            return JsonResponse(result)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Payment processing error: {str(e)}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)



# payments/views.py - Ensure these functions are correct
def process_instant_payment(page, gateway, order_data, request):
    """Process instant payment"""
    from .services.checkout_service import CheckoutService
    print(f"Instant order data is {order_data}")
    # CORRECT: Pass both page and gateway
    checkout_service = CheckoutService(page=page, gateway=gateway)
    print("101010101010101010101010101010101010110101001010")
    result = checkout_service.create_checkout(
        order_data,  # Pass the full order_data
        order_data.get('customer', {}),
        request
    )
    print("1313131313131313131313131313131313131331313113131311")
    print(f"Instant payment result is {result}")
    return result

def process_cart_payment(page, gateway, order_data, request):
    """Process cart payment"""
    from .services.checkout_service import CheckoutService
    
    # CORRECT: Pass both page and gateway
    checkout_service = CheckoutService(page=page, gateway=gateway)
    result = checkout_service.create_checkout(
        order_data,  # Pass the full order_data
        order_data.get('customer', {}),
        request
    )
    return result

@csrf_exempt
def create_instant_checkout(request, subdomain):
    """Handle instant checkout from Buy Now buttons"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
            data = json.loads(request.body)
            
            # Extract product and customer data
            product_data = data.get('product', {})
            customer_info = data.get('customer', {})
            
            # Validate required fields
            if not product_data.get('title') or not product_data.get('price'):
                return JsonResponse({'error': 'Product title and price are required'}, status=400)
            
            # Create checkout
            checkout_service = CheckoutService(page)
            result = checkout_service.create_instant_checkout(product_data, customer_info, request)
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def create_cart_checkout(request, subdomain):
    """Handle checkout from shopping cart"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
            data = json.loads(request.body)
            
            # Extract cart and customer data
            cart_data = data.get('cart', {})
            customer_info = data.get('customer', {})
            
            # Validate cart has items
            if not cart_data.get('items'):
                return JsonResponse({'error': 'Cart is empty'}, status=400)
            
            # Create checkout
            checkout_service = CheckoutService(page)
            result = checkout_service.create_cart_checkout(cart_data, customer_info, request)
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def get_checkout_status(request, subdomain, order_number):
    """Get checkout status for a specific order"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        order = get_object_or_404(Order, order_number=order_number, page=page)
        
        return JsonResponse({
            'order_number': order.order_number,
            'status': order.status,
            'total_amount': str(order.total_amount),
            'created_at': order.created_at.isoformat(),
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    




# paypal

# @csrf_exempt
# def paypal_success(request, subdomain):
#     """Handle successful PayPal payment"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain)
#     token = request.GET.get('token')
    
#     if not token:
#         return render(request, 'payments/paypal_error.html', {
#             'page': page,
#             'error': 'No payment token provided'
#         })
    
#     try:
#         # Find transaction by PayPal order ID
#         transaction = Transaction.objects.get(
#             gateway_transaction_id=token,
#             payment_gateway__page=page,
#             status='pending'
#         )
        
#         # Capture the payment
#         from .services.paypal_service import PayPalService
#         paypal_service = PayPalService(transaction.payment_gateway)
#         capture_result = paypal_service.capture_order(token)
        
#         if capture_result.get('status') == 'COMPLETED':
#             # Update transaction status
#             transaction.status = 'success'
#             transaction.gateway_response = capture_result
#             transaction.processed_at = timezone.now()
#             transaction.save()
            
#             # Update order status
#             order = transaction.order
#             order.status = 'completed'
#             order.paid_at = timezone.now()
#             order.save()
            
#             return render(request, 'payments/checkout_success.html', {
#                 'page': page,
#                 'order_number': order.order_number
#             })
#         else:
#             raise ValidationError("Payment not completed")
            
#     except Exception as e:
#         return render(request, 'payments/paypal_error.html', {
#             'page': page,
#             'error': str(e)
#         })


# ============================================================
# PayPal inline API endpoints (for the native buttons on checkout)
# ============================================================

@csrf_exempt
def paypal_create_order_api(request, subdomain):
    """
    Called by the frontend when the user selects PayPal.
    Creates a PayPal order server-side and returns:
      - client_id (public, for the PayPal JS SDK)
      - order_id  (the PayPal order identifier)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
        data = json.loads(request.body)
        order_data = data.get('order_data', {})

        # Get active PayPal gateway
        gateway = page.payment_gateways.filter(
            gateway_type='paypal', is_active=True
        ).first()
        if not gateway:
            return JsonResponse({'error': 'PayPal is not available'}, status=400)

        # Build order + PayPal order using the existing CheckoutService
        from .services.checkout_service import CheckoutService
        service = CheckoutService(page=page, gateway=gateway)
        result = service.create_checkout(
            order_data,
            order_data.get('customer', {}),
            request,
        )

        return JsonResponse({
            'success': True,
            'client_id': result.get('client_id'),
            'order_id': result.get('order_id'),
            'order_number': result.get('order_number'),
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
def paypal_capture_order_api(request, subdomain):
    """
    Called by the frontend after the user approves the payment in PayPal.
    Captures the order and marks the transaction/order as paid.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        data = json.loads(request.body)
        paypal_order_id = data.get('order_id')
        payer_id = data.get('payer_id')

        if not paypal_order_id:
            return JsonResponse({'success': False, 'error': 'Missing order_id'}, status=400)

        # Find the pending transaction by PayPal order id
        transaction = Transaction.objects.filter(
            gateway_transaction_id=paypal_order_id,
            payment_gateway__page=page,
            status='pending',
        ).first()

        if not transaction:
            return JsonResponse({
                'success': False,
                'error': 'Transaction not found or already processed'
            }, status=404)

        # Capture via PayPal
        from .services.paypal_service import PayPalService
        paypal_service = PayPalService(transaction.payment_gateway)
        capture_result = paypal_service.capture_order(paypal_order_id)

        if capture_result.get('status') != 'COMPLETED':
            return JsonResponse({
                'success': False,
                'error': f"PayPal capture status: {capture_result.get('status')}"
            }, status=400)

        # Idempotent update
        transaction.status = 'success'
        transaction.gateway_response = capture_result
        transaction.processed_at = timezone.now()
        transaction.save(update_fields=['status', 'gateway_response', 'processed_at'])

        order = transaction.order
        if order.status != 'completed':
            # CJ fulfillment (same as your other success handlers)
            try:
                from builder.services.cj_service import CJManager
                from builder.models import CJSettings
                account = CJSettings.objects.filter(page=page).first()
                if account and account.access_token:
                    CJManager(token=account.access_token).fulfill_cj_order_corrected(order)
            except Exception as e:
                print(f"CJ fulfillment error: {e}")

            order.status = 'completed'
            order.paid_at = timezone.now()
            order.save(update_fields=['status', 'paid_at'])

        return JsonResponse({
            'success': True,
            'order_number': order.order_number,
            'paypal_order_id': paypal_order_id,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
@csrf_exempt
def paypal_success(request, subdomain):
    """Handle successful PayPal payment with CJ fulfillment"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    token = request.GET.get('token')
    
    if not token:
        return render(request, 'payments/paypal_error.html', {
            'page': page,
            'error': 'No payment token provided'
        })
    
    try:
        # Find transaction by PayPal order ID
        transaction = Transaction.objects.get(
            gateway_transaction_id=token,
            payment_gateway__page=page,
            status='pending'
        )
        
        # Capture the payment
        from .services.paypal_service import PayPalService
        paypal_service = PayPalService(transaction.payment_gateway)
        capture_result = paypal_service.capture_order(token)
        
        if capture_result.get('status') == 'COMPLETED':
            # Update transaction status
            transaction.status = 'success'
            transaction.gateway_response = capture_result
            transaction.processed_at = timezone.now()
            transaction.save()
            
            # Get the order
            order = transaction.order
            
            # ========== CJ FULFILLMENT (BEFORE status change) ==========
            if order and order.can_fulfill_cj():
                print(f"✅ Order {order.order_number} eligible for CJ fulfillment")
                
                from builder.services.cj_service import CJManager
                from builder.models import CJSettings
                
                # Get CJ settings for this specific page/store
                account = CJSettings.objects.filter(page=page).first()
                
                if account and account.access_token:
                    try:
                        manager = CJManager(token=account.access_token)
                        
                        # Call fulfillment (order is still in 'pending' state)
                        success = manager.fulfill_cj_order_corrected(order)
                        
                        if success:
                            messages.success(request, f"CJ order #{order.cj_order_id} created successfully!")
                            print(f"✅ CJ order created: {order.cj_order_id}")
                        else:
                            messages.error(request, "Failed to create CJ order. Please check CJ dashboard.")
                            
                    except Exception as e:
                        logger.error(f"CJ fulfillment error for order {order.order_number}: {str(e)}")
                        messages.error(request, f"CJ fulfillment error: {str(e)}")
                else:
                    messages.warning(request, "CJ integration not configured or token missing.")
                    
            elif order:
                # Order exists but not eligible for CJ
                if order.is_cj_fulfilled:
                    messages.info(request, f"Order already fulfilled via CJ (#{order.cj_order_id})")
                elif not order.all_items_have_vid:
                    cj_count = order.cj_items_count
                    manual_count = order.manual_items_count
                    if cj_count > 0 and manual_count > 0:
                        messages.warning(request, 
                            f"Order contains {cj_count} CJ item(s) and {manual_count} manual item(s). "
                            f"CJ fulfillment skipped for mixed orders."
                        )
                    else:
                        messages.info(request, "No CJ items in order. Manual fulfillment required.")
            
            # NOW update order status to completed (after CJ fulfillment)
            order.status = 'completed'
            order.paid_at = timezone.now()
            order.save()
            
            return render(request, 'payments/checkout_success.html', {
                'page': page,
                'order_number': order.order_number
            })
        else:
            raise ValidationError("Payment not completed")
            
    except Exception as e:
        return render(request, 'payments/paypal_error.html', {
            'page': page,
            'error': str(e)
        })

def paypal_cancel(request, subdomain):
    """Handle cancelled PayPal payment"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    return render(request, 'payments/checkout_cancel.html', {
        'page': page,
        'message': 'PayPal payment was cancelled'
    })

@csrf_exempt
def paypal_webhook(request, subdomain):
    """Handle PayPal webhooks"""
    # PayPal webhook implementation would go here
    # For now, we'll use the redirect approach
    return HttpResponse(status=200)


@login_required
def configure_paypal_gateway(request, subdomain):
    """Configure PayPal payment gateway"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create PayPal gateway
    paypal_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='paypal',
        defaults={
            'is_active': False,
            'is_test_mode': True,
        }
    )
    
    if request.method == 'POST':
        paypal_gateway.paypal_client_id = request.POST.get('paypal_client_id', '').strip()
        paypal_gateway.paypal_client_secret = request.POST.get('paypal_client_secret', '').strip()
        paypal_gateway.paypal_live_client_id = request.POST.get('paypal_live_client_id', '').strip()
        paypal_gateway.paypal_live_client_secret = request.POST.get('paypal_live_client_secret', '').strip()
        paypal_gateway.is_test_mode = request.POST.get('is_test_mode') == 'on'
        paypal_gateway.is_active = request.POST.get('is_active') == 'on'
        
        # Validate PayPal configuration
        try:
            if paypal_gateway.is_active:
                from .services.paypal_service import PayPalService
                service = PayPalService(paypal_gateway)
                # Test connection by getting access token
                
            paypal_gateway.save()
            messages.success(request, 'PayPal configuration saved successfully!')
            return redirect('payments:manage_gateways', subdomain=subdomain)
            
        except Exception as e:
            messages.error(request, f'PayPal configuration error: {str(e)}')
    
    return render(request, 'payments/configure_paypal.html', {
        'page': page,
        'paypal_gateway': paypal_gateway,
    })



# @login_required
# def manage_payment_gateways(request, subdomain):
#     """Manage payment gateways for a published page"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
#     payment_gateways = page.payment_gateways.all()
    
#     # Get or create gateways for the template
#     stripe_gateway, created = PaymentGateway.objects.get_or_create(
#         page=page,
#         gateway_type='stripe',
#         defaults={
#             'is_active': False,
#             'is_test_mode': True,
#         }
#     )
    
#     paypal_gateway, created = PaymentGateway.objects.get_or_create(
#         page=page,
#         gateway_type='paypal',
#         defaults={
#             'is_active': False,
#             'is_test_mode': True,
#         }
#     )
    
#     # Calculate statistics
#     active_gateways_count = payment_gateways.filter(is_active=True).count()
#     test_mode_gateways_count = payment_gateways.filter(is_test_mode=True).count()
#     live_mode_gateways_count = payment_gateways.filter(is_test_mode=False).count()
    
#     return render(request, 'payments/manage_gateways.html', {
#         'page': page,
#         'payment_gateways': payment_gateways,
#         'stripe_gateway': stripe_gateway,
#         'paypal_gateway': paypal_gateway,
#         'active_gateways_count': active_gateways_count,
#         'test_mode_gateways_count': test_mode_gateways_count,
#         'live_mode_gateways_count': live_mode_gateways_count,
#     })



@csrf_exempt
@login_required
def test_paypal_connection(request, subdomain):
    """Test PayPal connection with provided credentials"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            client_id = data.get('client_id')
            client_secret = data.get('client_secret')
            is_test_mode = data.get('is_test_mode', True)
            
            if not client_id or not client_secret:
                return JsonResponse({'success': False, 'error': 'Client ID and Secret are required'})
            
            # Test PayPal authentication
            import requests
            import base64
            
            base_url = "https://api-m.sandbox.paypal.com" if is_test_mode else "https://api-m.paypal.com"
            
            auth_string = f"{client_id}:{client_secret}"
            auth_bytes = auth_string.encode('ascii')
            base64_auth = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                'Authorization': f'Basic {base64_auth}',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            data = 'grant_type=client_credentials'
            
            response = requests.post(
                f'{base_url}/v1/oauth2/token',
                headers=headers,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                return JsonResponse({'success': True, 'message': 'PayPal connection successful'})
            else:
                error_text = response.json().get('error_description', 'Authentication failed')
                return JsonResponse({'success': False, 'error': error_text})
                
        except requests.exceptions.Timeout:
            return JsonResponse({'success': False, 'error': 'Connection timeout'})
        except requests.exceptions.ConnectionError:
            return JsonResponse({'success': False, 'error': 'Network connection error'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})



# Razorpay views

# Add Razorpay configuration view
@login_required
def configure_razorpay_gateway(request, subdomain):
    """Configure Razorpay payment gateway"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create Razorpay gateway
    razorpay_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='razorpay',
        defaults={
            'is_active': False,
            'is_test_mode': True,
        }
    )
    
    if request.method == 'POST':
        razorpay_gateway.razorpay_key_id = request.POST.get('razorpay_key_id', '').strip()
        razorpay_gateway.razorpay_key_secret = request.POST.get('razorpay_key_secret', '').strip()
        razorpay_gateway.razorpay_webhook_secret = request.POST.get('razorpay_webhook_secret', '').strip()
        razorpay_gateway.is_test_mode = request.POST.get('is_test_mode') == 'on'
        razorpay_gateway.is_active = request.POST.get('is_active') == 'on'
        
        # Validate Razorpay configuration
        try:
            if razorpay_gateway.is_active and razorpay_gateway.razorpay_key_id and razorpay_gateway.razorpay_key_secret:
                # Test connection by creating a test client
                client = razorpay.Client(auth=(
                    razorpay_gateway.razorpay_key_id,
                    razorpay_gateway.razorpay_key_secret
                ))
                # Test API call
                client.order.all({'count': 1})
                
            razorpay_gateway.save()
            messages.success(request, 'Razorpay configuration saved successfully!')
            return redirect('payments:manage_gateways', subdomain=subdomain)
            
        except Exception as e:
            messages.error(request, f'Razorpay configuration error: {str(e)}')
    
    return render(request, 'payments/configure_razorpay.html', {
        'page': page,
        'razorpay_gateway': razorpay_gateway,
    })

# Add Razorpay webhook handler
@csrf_exempt
def razorpay_webhook(request, subdomain):
    """Handle Razorpay webhooks"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    razorpay_gateway = get_object_or_404(PaymentGateway, page=page, gateway_type='razorpay')
    
    payload = request.body.decode('utf-8')
    signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
    
    try:
        service = RazorpayService(razorpay_gateway)
        
        # Verify webhook signature
        if not service.verify_webhook_signature(payload, signature):
            return HttpResponse('Invalid signature', status=400)
        
        data = json.loads(payload)
        event = data.get('event', '')
        
        # Handle payment captured event
        if event == 'payment.captured':
            payment_data = data.get('payload', {}).get('payment', {}).get('entity', {})
            
            # Find transaction
            transaction = Transaction.objects.filter(
                gateway_transaction_id=payment_data.get('order_id'),
                payment_gateway=razorpay_gateway
            ).first()
            
            if transaction:
                transaction.status = 'success'
                transaction.gateway_response = payment_data
                transaction.gateway_transaction_id = payment_data.get('id')
                transaction.processed_at = timezone.now()
                transaction.save()
                
                # Update order
                order = transaction.order
                order.status = 'completed'
                order.paid_at = timezone.now()
                order.save()
        
        elif event == 'payment.failed':
            payment_data = data.get('payload', {}).get('payment', {}).get('entity', {})
            
            transaction = Transaction.objects.filter(
                gateway_transaction_id=payment_data.get('order_id'),
                payment_gateway=razorpay_gateway
            ).first()
            
            if transaction:
                transaction.status = 'failed'
                transaction.gateway_response = payment_data
                transaction.save()
        
        return HttpResponse(status=200)
        
    except Exception as e:
        return HttpResponse(str(e), status=400)

# Add Razorpay payment verification
@csrf_exempt
def verify_razorpay_payment(request, subdomain):
    """Verify Razorpay payment on frontend callback"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            razorpay_order_id = data.get('razorpay_order_id')
            razorpay_payment_id = data.get('razorpay_payment_id')
            razorpay_signature = data.get('razorpay_signature')
            
            page = get_object_or_404(PublishedPage, subdomain=subdomain)
            razorpay_gateway = get_object_or_404(PaymentGateway, page=page, gateway_type='razorpay')
            
            service = RazorpayService(razorpay_gateway)
            
            # Verify signature
            if service.verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
                # Update transaction
                transaction = Transaction.objects.filter(
                    gateway_transaction_id=razorpay_order_id,
                    payment_gateway=razorpay_gateway
                ).first()
                
                if transaction:
                    transaction.status = 'success'
                    transaction.gateway_transaction_id = razorpay_payment_id
                    transaction.processed_at = timezone.now()
                    transaction.save()
                    
                    # Update order
                    order = transaction.order
                    order.status = 'completed'
                    order.paid_at = timezone.now()
                    order.save()
                    
                    return JsonResponse({
                        'success': True,
                        'order_number': order.order_number,
                        'message': 'Payment verified successfully'
                    })
            
            return JsonResponse({'success': False, 'error': 'Payment verification failed'}, status=400)
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)






# Add Fincra configuration view
@login_required
def configure_fincra_gateway(request, subdomain):
    """Configure Fincra payment gateway"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create Fincra gateway
    fincra_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='fincra',
        defaults={
            'is_active': False,
            'is_test_mode': True,
        }
    )
    
    if request.method == 'POST':
        fincra_gateway.fincra_api_key = request.POST.get('fincra_api_key', '').strip()
        fincra_gateway.fincra_secret_key = request.POST.get('fincra_secret_key', '').strip()
        fincra_gateway.fincra_business_id = request.POST.get('fincra_business_id', '').strip()
        fincra_gateway.fincra_subaccount_id = request.POST.get('fincra_subaccount_id', '').strip()
        fincra_gateway.is_test_mode = request.POST.get('is_test_mode') == 'on'
        fincra_gateway.is_active = request.POST.get('is_active') == 'on'
        
        # Validate Fincra configuration
        try:
            if fincra_gateway.is_active and all([
                fincra_gateway.fincra_api_key,
                fincra_gateway.fincra_secret_key,
                fincra_gateway.fincra_business_id
            ]):
                # Test connection by making a simple API call
                service = FincraService(fincra_gateway)
                # Try to get business info
                response = requests.get(
                    f"{service.base_url}/businesses/{fincra_gateway.fincra_business_id}",
                    headers=service.headers,
                    timeout=10
                )
                
                if response.status_code != 200:
                    raise ValidationError("Fincra connection test failed")
                
            fincra_gateway.save()
            messages.success(request, 'Fincra configuration saved successfully!')
            return redirect('payments:manage_gateways', subdomain=subdomain)
            
        except Exception as e:
            messages.error(request, f'Fincra configuration error: {str(e)}')
    
    return render(request, 'payments/configure_fincra.html', {
        'page': page,
        'fincra_gateway': fincra_gateway,
    })

# Add Fincra callback handler (for redirect after payment)
def fincra_callback(request, subdomain):
    """Handle Fincra payment callback"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    
    reference = request.GET.get('reference')
    status = request.GET.get('status')
    
    if reference:
        try:
            # Find transaction
            transaction = Transaction.objects.filter(
                gateway_transaction_id=reference,
                payment_gateway__page=page,
                payment_gateway__gateway_type='fincra'
            ).first()
            
            if transaction:
                # Verify payment status with Fincra
                fincra_gateway = transaction.payment_gateway
                service = FincraService(fincra_gateway)
                verification = service.verify_payment(reference)
                
                if verification['success'] and verification['status'] == 'successful':
                    transaction.status = 'success'
                    transaction.gateway_response = verification
                    transaction.processed_at = timezone.now()
                    transaction.save()
                    
                    # Update order
                    order = transaction.order
                    order.status = 'completed'
                    order.paid_at = timezone.now()
                    order.save()
                    
                    return render(request, 'payments/checkout_success.html', {
                        'page': page,
                        'order_number': order.order_number
                    })
                else:
                    # Payment failed or pending
                    return render(request, 'payments/checkout_cancel.html', {
                        'page': page,
                        'message': 'Payment not completed'
                    })
        
        except Exception as e:
            print(f"Fincra callback error: {e}")
    
    # Default fallback
    return render(request, 'payments/checkout_cancel.html', {
        'page': page,
        'message': 'Payment processing error'
    })

# Add Fincra webhook handler
@csrf_exempt
def fincra_webhook(request, subdomain):
    """Handle Fincra webhooks"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    fincra_gateway = get_object_or_404(PaymentGateway, page=page, gateway_type='fincra')
    
    payload = request.body.decode('utf-8')
    signature = request.META.get('HTTP_X_FINCRA_SIGNATURE', '')
    
    try:
        service = FincraService(fincra_gateway)
        
        # Verify webhook signature
        if not service.verify_webhook_signature(payload, signature):
            return HttpResponse('Invalid signature', status=400)
        
        data = json.loads(payload)
        event_type = data.get('event')
        
        # Handle different event types
        if event_type == 'payment.success':
            payment_data = data.get('data', {})
            reference = payment_data.get('reference')
            
            # Find transaction
            transaction = Transaction.objects.filter(
                gateway_transaction_id=reference,
                payment_gateway=fincra_gateway
            ).first()
            
            if transaction:
                transaction.status = 'success'
                transaction.gateway_response = payment_data
                transaction.processed_at = timezone.now()
                transaction.save()
                
                # Update order
                order = transaction.order
                order.status = 'completed'
                order.paid_at = timezone.now()
                order.save()
        
        elif event_type == 'payment.failed':
            payment_data = data.get('data', {})
            reference = payment_data.get('reference')
            
            transaction = Transaction.objects.filter(
                gateway_transaction_id=reference,
                payment_gateway=fincra_gateway
            ).first()
            
            if transaction:
                transaction.status = 'failed'
                transaction.gateway_response = payment_data
                transaction.save()
        
        return HttpResponse(status=200)
        
    except Exception as e:
        return HttpResponse(str(e), status=400)

# Add Fincra payment verification endpoint
@csrf_exempt
def verify_fincra_payment(request, subdomain):
    """Verify Fincra payment status"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            reference = data.get('reference')
            
            page = get_object_or_404(PublishedPage, subdomain=subdomain)
            fincra_gateway = get_object_or_404(PaymentGateway, page=page, gateway_type='fincra')
            
            service = FincraService(fincra_gateway)
            verification = service.verify_payment(reference)
            
            if verification['success']:
                # Update transaction if found
                transaction = Transaction.objects.filter(
                    gateway_transaction_id=reference,
                    payment_gateway=fincra_gateway
                ).first()
                
                if transaction:
                    if verification['status'] == 'successful':
                        transaction.status = 'success'
                        transaction.processed_at = timezone.now()
                        transaction.save()
                        
                        order = transaction.order
                        order.status = 'completed'
                        order.paid_at = timezone.now()
                        order.save()
                    
                    elif verification['status'] == 'failed':
                        transaction.status = 'failed'
                        transaction.save()
                
                return JsonResponse({
                    'success': True,
                    'status': verification['status'],
                    'reference': reference,
                    'data': verification
                })
            
            return JsonResponse({'success': False, 'error': 'Payment verification failed'}, status=400)
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)






# Add Cryptomus configuration view
@login_required
def configure_cryptomus_gateway(request, subdomain):
    """Configure Cryptomus payment gateway"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create Cryptomus gateway
    cryptomus_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='cryptomus',
        defaults={
            'is_active': False,
            'is_test_mode': True,
        }
    )
    
    if request.method == 'POST':
        cryptomus_gateway.cryptomus_api_key = request.POST.get('cryptomus_api_key', '').strip()
        cryptomus_gateway.cryptomus_merchant_uuid = request.POST.get('cryptomus_merchant_uuid', '').strip()
        cryptomus_gateway.cryptomus_webhook_secret = request.POST.get('cryptomus_webhook_secret', '').strip()
        cryptomus_gateway.is_active = request.POST.get('is_active') == 'on'
        
        # Cryptomus doesn't have test mode in traditional sense
        # You can use test API keys for testing
        
        # Validate Cryptomus configuration
        try:
            if cryptomus_gateway.is_active and all([
                cryptomus_gateway.cryptomus_api_key,
                cryptomus_gateway.cryptomus_merchant_uuid
            ]):
                # Test connection by getting balance
                service = CryptomusService(cryptomus_gateway)
                balance_result = service.get_balance()
                
                if not balance_result['success']:
                    raise ValidationError("Cryptomus connection test failed")
                
            cryptomus_gateway.save()
            messages.success(request, 'Cryptomus configuration saved successfully!')
            return redirect('payments:manage_gateways', subdomain=subdomain)
            
        except Exception as e:
            messages.error(request, f'Cryptomus configuration error: {str(e)}')
    
    return render(request, 'payments/configure_cryptomus.html', {
        'page': page,
        'cryptomus_gateway': cryptomus_gateway,
    })

# Add Cryptomus callback handler
def cryptomus_callback(request, subdomain):
    """Handle Cryptomus payment callback/return"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    
    payment_uuid = request.GET.get('uuid')
    status = request.GET.get('status')
    
    if payment_uuid:
        try:
            # Find transaction
            transaction = Transaction.objects.filter(
                gateway_transaction_id=payment_uuid,
                payment_gateway__page=page,
                payment_gateway__gateway_type='cryptomus'
            ).first()
            
            if transaction:
                # Get updated payment info
                cryptomus_gateway = transaction.payment_gateway
                service = CryptomusService(cryptomus_gateway)
                payment_info = service.get_payment_info(payment_uuid)
                
                if payment_info['success']:
                    if payment_info['status'] == 'paid':
                        transaction.status = 'success'
                        transaction.processed_at = timezone.now()
                        transaction.save()
                        
                        # Update order
                        order = transaction.order
                        order.status = 'completed'
                        order.paid_at = timezone.now()
                        order.save()
                        
                        return render(request, 'payments/checkout_success.html', {
                            'page': page,
                            'order_number': order.order_number,
                            'is_crypto': True
                        })
                    elif payment_info['status'] == 'pending':
                        return render(request, 'payments/cryptomus_pending.html', {
                            'page': page,
                            'payment_uuid': payment_uuid,
                            'order_number': transaction.order.order_number
                        })
                    else:
                        return render(request, 'payments/checkout_cancel.html', {
                            'page': page,
                            'message': f'Payment status: {payment_info["status"]}'
                        })
        
        except Exception as e:
            print(f"Cryptomus callback error: {e}")
    
    return render(request, 'payments/checkout_cancel.html', {
        'page': page,
        'message': 'Cryptomus payment processing error'
    })

# Add Cryptomus webhook handler
@csrf_exempt
def cryptomus_webhook(request, subdomain):
    """Handle Cryptomus webhooks"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    cryptomus_gateway = get_object_or_404(PaymentGateway, page=page, gateway_type='cryptomus')
    
    try:
        # Get raw body and signature
        payload = request.body.decode('utf-8')
        payload_dict = json.loads(payload) if payload else {}
        signature = request.META.get('HTTP_SIGN', '')
        
        service = CryptomusService(cryptomus_gateway)
        
        # Verify webhook signature
        if not service.verify_webhook_signature(payload_dict, signature):
            return HttpResponse('Invalid signature', status=400)
        
        # Process webhook data
        payment_data = payload_dict
        payment_uuid = payment_data.get('uuid')
        order_id = payment_data.get('order_id')
        status = payment_data.get('status')
        
        if payment_uuid:
            # Find transaction
            transaction = Transaction.objects.filter(
                gateway_transaction_id=payment_uuid,
                payment_gateway=cryptomus_gateway
            ).first()
            
            if transaction:
                if status == 'paid':
                    transaction.status = 'success'
                    transaction.gateway_response = payment_data
                    transaction.processed_at = timezone.now()
                    transaction.save()
                    
                    # Update order
                    order = transaction.order
                    order.status = 'completed'
                    order.paid_at = timezone.now()
                    order.save()
                    
                elif status == 'expired':
                    transaction.status = 'cancelled'
                    transaction.gateway_response = payment_data
                    transaction.save()
        
        return HttpResponse(status=200)
        
    except Exception as e:
        return HttpResponse(str(e), status=400)

# Add Cryptomus payment status check
@csrf_exempt
def check_cryptomus_payment(request, subdomain, payment_uuid):
    """Check Cryptomus payment status"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        cryptomus_gateway = get_object_or_404(PaymentGateway, page=page, gateway_type='cryptomus')
        
        service = CryptomusService(cryptomus_gateway)
        payment_info = service.get_payment_info(payment_uuid)
        
        if payment_info['success']:
            # Update transaction if found
            transaction = Transaction.objects.filter(
                gateway_transaction_id=payment_uuid,
                payment_gateway=cryptomus_gateway
            ).first()
            
            if transaction:
                if payment_info['status'] == 'paid':
                    transaction.status = 'success'
                    transaction.processed_at = timezone.now()
                    transaction.save()
                    
                    order = transaction.order
                    order.status = 'completed'
                    order.paid_at = timezone.now()
                    order.save()
                
                elif payment_info['status'] == 'expired':
                    transaction.status = 'cancelled'
                    transaction.save()
            
            return JsonResponse({
                'success': True,
                'status': payment_info['status'],
                'payment_uuid': payment_uuid,
                'is_final': payment_info.get('is_final', False),
                'paid_amount': payment_info.get('paid_amount'),
                'data': payment_info
            })
        
        return JsonResponse({'success': False, 'error': 'Payment check failed'}, status=400)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    


# Add new view for POD configuration
@login_required
def configure_pod_gateway(request, subdomain):
    """Configure Pay on Delivery gateway"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create POD gateway
    pod_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='pay_on_delivery',
        defaults={
            'is_active': False,  # Default active
            'is_test_mode': False,
            'pod_minimum_amount': 0,
            'pod_maximum_amount': 500,
            'pod_requires_confirmation': True,
        }
    )
    
    if request.method == 'POST':
        pod_gateway.is_active = request.POST.get('is_active') == 'on'
        pod_gateway.pod_minimum_amount = Decimal(request.POST.get('pod_minimum_amount', 0))
        pod_gateway.pod_maximum_amount = Decimal(request.POST.get('pod_maximum_amount', 500))
        pod_gateway.pod_instructions = request.POST.get('pod_instructions', '')
        pod_gateway.pod_requires_confirmation = request.POST.get('pod_requires_confirmation') == 'on'
        
        # Parse JSON for available zones
        zones_text = request.POST.get('pod_available_zones', '')
        print(f'Available Zones are: {zones_text}')
        if zones_text:
            pod_gateway.pod_available_zones = [zone.strip() for zone in zones_text.split(',')]

        else:
            pod_gateway.pod_available_zones = None
        
        pod_gateway.save()
        messages.success(request, 'Pay on Delivery configuration saved successfully!')
        return redirect('payments:manage_gateways', subdomain=subdomain)
    
    return render(request, 'payments/configure_pod.html', {
        'page': page,
        'pod_gateway': pod_gateway,
    })

# Add view for POD success page
# def pod_success(request, subdomain):
#     """Pay on Delivery success page"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain)
#     order_number = request.session.get('last_order_number', '')
    
#     try:
#         order = get_object_or_404(Order,
#             order_number=order_number,
#             page=page,
#             status='pending_pod'
#         )
#     except Order.DoesNotExist:
#         order = None

#     # Get POD gateway for instructions
#     pod_gateway = page.payment_gateways.filter(
#         gateway_type='pay_on_delivery',
#         is_active=True
#     ).first()
    
#     # --- NEW: TRIGGER CJ FULFILLMENT ---
#     from builder.services.cj_service import CJManager
#     from builder.models import CJSettings
#     # fulfill_cj_order(order)
#     for item in order.items.all():
#         print("========================================================================================================================")
#         print("========================================================================================================================")
#         print("========================================================================================================================")
#         print("========================================================================================================================")
#         print("========================================================================================================================")
#         print("========================================================================================================================")
#         print("========================================================================================================================")
#         print("========================================================================================================================")

#         print(f'Item VID is {item.vid}')
#         print("========================================================================================================================")

#         if item.vid:
#             account = CJSettings.objects.first() 
#             manager = CJManager(token=account.access_token) 
#             manager.fulfill_cj_order(order)
#             # manager.sync_product_color_size(item.product)
#     return render(request, 'payments/pod_success.html', {
#         'page': page,
#         'order': order,
#         'order_number': order_number,
#         'pod_gateway': pod_gateway,
#     })

def pod_success(request, subdomain):
    """Pay on Delivery success page"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain)
    order_number = request.session.get('last_order_number', '')
    
    try:
        order = get_object_or_404(Order,
            order_number=order_number,
            page=page,
            status='pending_pod'
        )
    except Order.DoesNotExist:
        order = None
    
    # Get POD gateway for instructions
    pod_gateway = page.payment_gateways.filter(
        gateway_type='pay_on_delivery',
        is_active=True
    ).first()
    
    # ========== CJ FULFILLMENT LOGIC ==========
    if order and order.can_fulfill_cj():
        print(f"✅ Order {order.order_number} eligible for CJ fulfillment")
        
        from builder.services.cj_service import CJManager
        from builder.models import CJSettings
        
        # Get CJ settings for this specific page/store
        account = CJSettings.objects.filter(page=page).first()
        
        if account and account.access_token:
            try:
                manager = CJManager(token=account.access_token)
                
                # Call fulfillment (using the corrected method from previous answer)
                success = manager.fulfill_cj_order_corrected(order)
                
                if success:
                    messages.success(request, f"CJ order #{order.cj_order_id} created successfully!")
                    print(f"✅ CJ order created: {order.cj_order_id}")
                else:
                    messages.error(request, "Failed to create CJ order. Please check CJ dashboard.")
                    
            except Exception as e:
                logger.error(f"CJ fulfillment error for order {order_number}: {str(e)}")
                messages.error(request, f"CJ fulfillment error: {str(e)}")
        else:
            messages.warning(request, "CJ integration not configured or token missing.")
    elif order:
        # Order exists but not eligible for CJ
        if order.is_cj_fulfilled:
            messages.info(request, f"Order already fulfilled via CJ (#{order.cj_order_id})")
        elif not order.all_items_have_vid:
            cj_count = order.cj_items_count
            manual_count = order.manual_items_count
            if cj_count > 0 and manual_count > 0:
                messages.warning(request, 
                    f"Order contains {cj_count} CJ item(s) and {manual_count} manual item(s). "
                    f"CJ fulfillment skipped for mixed orders."
                )
            else:
                messages.info(request, "No CJ items in order. Manual fulfillment required.")
    
    return render(request, 'payments/pod_success.html', {
        'page': page,
        'order': order,
        'order_number': order_number,
        'pod_gateway': pod_gateway,
    })


# Add admin view for managing POD orders
@login_required
def manage_pod_orders(request, subdomain):
    """Manage Pay on Delivery orders (admin)"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get POD gateway
    pod_gateway = get_object_or_404(
        PaymentGateway, 
        page=page, 
        gateway_type='pay_on_delivery',
        is_active=True
    )
    
    # Get pending POD transactions
    pending_transactions = Transaction.objects.filter(
        payment_gateway=pod_gateway,
        status='pending'
    ).select_related('order').order_by('-created_at')
    
    # Get completed POD transactions
    completed_transactions = Transaction.objects.filter(
        payment_gateway=pod_gateway,
        status='success'
    ).select_related('order').order_by('-processed_at')[:50]
    
    return render(request, 'payments/manage_pod_orders.html', {
        'page': page,
        'pod_gateway': pod_gateway,
        'pending_transactions': pending_transactions,
        'completed_transactions': completed_transactions,
    })

# Add AJAX view for confirming POD payment
@csrf_exempt
@login_required
def confirm_pod_payment(request, subdomain, transaction_id):
    """Confirm POD payment was received"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            pod_gateway = get_object_or_404(PaymentGateway, page=page, gateway_type='pay_on_delivery')
            
            from .services.pod_service import PayOnDeliveryService
            pod_service = PayOnDeliveryService(pod_gateway)
            
            data = json.loads(request.body)
            result = pod_service.confirm_payment_received(
                transaction_id, 
                request.user
            )
            
            return JsonResponse(result)
            
        except ValidationErr as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

# Add AJAX view for cancelling POD order
@csrf_exempt
@login_required
def cancel_pod_order(request, subdomain, transaction_id):
    """Cancel POD order"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            pod_gateway = get_object_or_404(PaymentGateway, page=page, gateway_type='pay_on_delivery')
            
            data = json.loads(request.body)
            reason = data.get('reason', 'Cancelled by admin')
            
            from .services.pod_service import PayOnDeliveryService
            pod_service = PayOnDeliveryService(pod_gateway)
            
            result = pod_service.cancel_pod_order(transaction_id, reason)
            
            return JsonResponse(result)
            
        except ValidationErr as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


from django.http import JsonResponse
import json

@csrf_exempt
def get_pod_info(request, subdomain):
    """Get Pay on Delivery gateway information for frontend"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
        
        # Get POD gateway
        pod_gateway = page.payment_gateways.filter(
            gateway_type='pay_on_delivery',
            is_active=True
        ).first()
        
        if not pod_gateway:
            return JsonResponse({
                'error': 'Pay on Delivery is not available',
                'available': False
            }, status=404)
        
        return JsonResponse({
            'available': True,
            'pod_minimum_amount': float(pod_gateway.pod_minimum_amount),
            'pod_maximum_amount': float(pod_gateway.pod_maximum_amount),
            'pod_available_zones': pod_gateway.pod_available_zones or [],
            'pod_instructions': pod_gateway.pod_instructions or '',
            'pod_requires_confirmation': pod_gateway.pod_requires_confirmation,
            'is_active': pod_gateway.is_active
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



# Add these imports at the top
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncMonth, TruncDay
from datetime import datetime, timedelta
import csv
from django.http import HttpResponse

# Order List View
@login_required
def order_list(request, subdomain):
    """List all orders for a store"""
    page_obj = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    payment_status_filter = request.GET.get('payment_status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('q', '')
    
    # Start with all orders for this page
    orders = page_obj.orders.all().select_related('page').prefetch_related('items')
    
    # Apply filters
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if payment_status_filter:
        orders = orders.filter(payment_status=payment_status_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            orders = orders.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            orders = orders.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(customer_email__icontains=search_query) |
            Q(customer_phone__icontains=search_query)
        )
    
    # Get statistics
    total_orders = page_obj.orders.count()
    total_revenue = page_obj.orders.filter(status='completed').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Status counts
    status_counts = page_obj.orders.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Pagination
    paginator = Paginator(orders, 25)  # 25 orders per page
    page_number = request.GET.get('page', 1)
    
    try:
        orders_page = paginator.page(page_number)
    except PageNotAnInteger:
        orders_page = paginator.page(1)
    except EmptyPage:
        orders_page = paginator.page(paginator.num_pages)
    
    context = {
        'page': page_obj,
        'orders': orders_page,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'status_counts': status_counts,
        'status_filter': status_filter,
        'payment_status_filter': payment_status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'status_choices': Order.ORDER_STATUS,
        'payment_status_choices': Order._meta.get_field('payment_status').choices,
    }
    
    return render(request, 'payments/order_list.html', context)

# Order Detail View
@login_required
def order_detail(request, subdomain, order_id):
    """View order details"""
    page_obj = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    order = get_object_or_404(Order, id=order_id, page=page_obj)

    print(f"Oder is {order}")
    
    # Get related transactions
    transactions = order.transactions.all().order_by('-created_at')
    print(f"Transactions are {transactions}")
    # Get order timeline from status history
    timeline = order.status_history or []
    
    context = {
        'page': page_obj,
        'order': order,
        'transactions': transactions,
        'timeline': timeline,
        'status_choices': Order.ORDER_STATUS,
        'payment_status_choices': Order._meta.get_field('payment_status').choices,
    }
    
    return render(request, 'payments/order_detail.html', context)

# Update Order Status View
@login_required
@csrf_exempt
def update_order_status(request, subdomain, order_id):
    """Update order status (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        page_obj = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        order = get_object_or_404(Order, id=order_id, page=page_obj)
        
        data = json.loads(request.body)
        new_status = data.get('status')
        note = data.get('note', '')
        
        if not new_status:
            return JsonResponse({'success': False, 'error': 'Status is required'})
        
        # Validate status
        valid_statuses = [choice[0] for choice in Order.ORDER_STATUS]
        if new_status not in valid_statuses:
            return JsonResponse({'success': False, 'error': 'Invalid status'})
        
        # Update order
        old_status = order.status
        order.status = new_status
        
        # Add to status history
        if not order.status_history:
            order.status_history = []
        
        order.status_history.append({
            'status': new_status,
            'timestamp': timezone.now().isoformat(),
            'note': note or f'Changed from {old_status} to {new_status}',
            'changed_by': request.user.username
        })
        
        # Update payment status for POD orders
        if new_status == 'completed' and order.payment_method == 'pay_on_delivery':
            order.payment_status = 'paid'
            order.paid_at = timezone.now()
        
        order.save()
        
        # Send email notification if configured
        send_order_status_email(order, old_status, new_status, request)
        
        return JsonResponse({
            'success': True,
            'message': f'Order status updated to {new_status}',
            'order_id': order.id,
            'new_status': new_status,
            'new_status_display': order.get_status_display(),
            'status_class': order.get_status_display_class(),
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Update Payment Status View
@login_required
@csrf_exempt
def update_payment_status(request, subdomain, order_id):
    """Update payment status (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        page_obj = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        order = get_object_or_404(Order, id=order_id, page=page_obj)
        
        data = json.loads(request.body)
        new_status = data.get('status')
        note = data.get('note', '')
        
        if not new_status:
            return JsonResponse({'success': False, 'error': 'Status is required'})
        
        # Validate payment status
        valid_statuses = [choice[0] for choice in Order._meta.get_field('payment_status').choices]
        if new_status not in valid_statuses:
            return JsonResponse({'success': False, 'error': 'Invalid payment status'})
        
        # Update payment status
        old_status = order.payment_status
        order.payment_status = new_status
        
        if new_status == 'paid' and not order.paid_at:
            order.paid_at = timezone.now()
        
        order.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Payment status updated to {new_status}',
            'order_id': order.id,
            'new_status': new_status,
            'new_status_display': order.get_payment_status_display(),
            'status_class': order.get_payment_status_display_class(),
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Add Order Note View
@login_required
@csrf_exempt
def add_order_note(request, subdomain, order_id):
    """Add note to order (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        page_obj = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        order = get_object_or_404(Order, id=order_id, page=page_obj)
        
        data = json.loads(request.body)
        note_type = data.get('type', 'internal')  # 'internal' or 'customer'
        content = data.get('content', '')
        
        if not content:
            return JsonResponse({'success': False, 'error': 'Note content is required'})
        
        if note_type == 'internal':
            order.internal_notes += f"\n{timezone.now().strftime('%Y-%m-%d %H:%M:%S')} - {request.user.username}: {content}\n"
        elif note_type == 'customer':
            order.customer_notes += f"\n{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}: {content}\n"
        
        order.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Note added successfully',
            'note_type': note_type,
            'content': content,
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Dashboard View
@login_required
def order_dashboard(request, subdomain):
    """Order dashboard with analytics"""
    page_obj = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Date range for analytics (last 30 days)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    # Get recent orders
    recent_orders = page_obj.orders.all().order_by('-created_at')[:10]
    
    # Get statistics
    total_orders = page_obj.orders.count()
    total_revenue = page_obj.orders.filter(status='completed').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Daily revenue for chart
    daily_revenue = page_obj.orders.filter(
        status='completed',
        created_at__date__gte=start_date.date()
    ).annotate(
        day=TruncDay('created_at')
    ).values('day').annotate(
        revenue=Sum('total_amount'),
        orders=Count('id')
    ).order_by('day')
    
    # Monthly revenue
    monthly_revenue = page_obj.orders.filter(
        status='completed'
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        revenue=Sum('total_amount'),
        orders=Count('id')
    ).order_by('-month')[:12]
    
    # Top products
    top_products = OrderItem.objects.filter(
        order__page=page_obj,
        order__status='completed'
    ).values(
        'product_title'
    ).annotate(
        quantity=Sum('quantity'),
        revenue=Sum('total_price')
    ).order_by('-quantity')[:10]
    
    print("Total orders:", total_orders)
  
    # Status distribution
    # status_distribution = page_obj.orders.values('status').annotate(
    #     count=Count('id'),
    #     percentage=Count('id') * 100.0 / total_orders if total_orders > 0 else 0
    # ).order_by('status')
    
    # Get total orders count
    total_orders = page_obj.orders.count()

    # Annotate status distribution without percentage calculation
    status_distribution = page_obj.orders.values('status').annotate(
        count=Count('id')
    ).order_by('status')

    # Calculate percentage after annotation
    if total_orders > 0:
        for entry in status_distribution:
            entry['percentage'] = (entry['count'] * 100.0) / total_orders
    else:
        for entry in status_distribution:
            entry['percentage'] = 0  # or handle it as needed

# Now status_distribution will contain count and percentage

    context = {
        'page': page_obj,
        'recent_orders': recent_orders,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'daily_revenue': list(daily_revenue),
        'monthly_revenue': list(monthly_revenue),
        'top_products': list(top_products),
        'status_distribution': list(status_distribution),
        'start_date': start_date.date(),
        'end_date': end_date.date(),
    }
    
    return render(request, 'payments/order_dashboard.html', context)

# Export Orders View
@login_required
def export_orders(request, subdomain):
    """Export orders to CSV"""
    page_obj = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get filter parameters from request
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    orders = page_obj.orders.all()
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            orders = orders.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            orders = orders.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="orders_{subdomain}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Order Number',
        'Customer Name',
        'Customer Email',
        'Customer Phone',
        'Order Date',
        'Status',
        'Payment Status',
        'Payment Method',
        'Subtotal',
        'Tax',
        'Shipping',
        'Discount',
        'Total Amount',
        'Items Count',
        'Delivery Address',
        'Delivery City',
        'Delivery State',
        'Delivery Zip',
        'Delivery Country',
    ])
    
    # Write data
    for order in orders:
        writer.writerow([
            order.order_number,
            order.customer_name,
            order.customer_email,
            order.phone,
            order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            order.get_status_display(),
            order.get_payment_status_display(),
            order.get_payment_method_display(),
            str(order.subtotal),
            str(order.tax_amount),
            str(order.shipping_amount),
            str(order.discount_amount),
            str(order.total_amount),
            order.items.count(),
            order.delivery_address,
            order.delivery_city,
            order.delivery_state,
            order.delivery_zip,
            order.delivery_country,
        ])
    
    return response

# Customer Order History View (for customers)
def customer_order_history(request, subdomain):
    """Customer-facing order history page"""
    page_obj = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
    # Get customer email from session or request
    customer_email = request.GET.get('email', '')
    order_number = request.GET.get('order', '')
    # if request.user.is_anonymous:
    #     customer_email=""
        
    # else:
    #     customer_email=request.user.email
    print(f"Oder is {order_number} oder email is {customer_email} user is {customer_email}")
    print(f"Page object is {page_obj}")
    
    if not customer_email and not order_number:
        # Show lookup form
        return render(request, 'payments/customer_order_lookup.html', {
            'page': page_obj,
        })
    
    orders = page_obj.orders.all()
    
    if customer_email:
        orders = orders.filter(customer_email=customer_email)
    
    if order_number:
        orders = orders.filter(order_number=order_number)
    
    orders = orders.order_by('-created_at')
    # orders=Order.objects.filter(page=page_obj)
    
    return render(request, 'payments/customer_order_history.html', {
        'page': page_obj,
        'orders': orders,
        'customer_email': customer_email,
        'order_number': order_number,
    })

# Customer Order Detail View
def customer_order_detail(request, subdomain, order_number):
    """Customer-facing order detail page"""
    page_obj = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
    try:
        order = page_obj.orders.get(order_number=order_number)
        
        # Verify customer has access (by email in session or query param)
        customer_email = request.GET.get('email', '')
        if not customer_email:
            # Try to get from session
            customer_email = request.session.get('customer_email', '')
        
        if order.customer_email != customer_email:
            return render(request, 'payments/customer_order_access_denied.html', {
                'page': page_obj,
            })
        
        # Get related transactions
        transactions = order.transactions.all().order_by('-created_at')
        
        return render(request, 'payments/customer_order_detail.html', {
            'page': page_obj,
            'order': order,
            'transactions': transactions,
        })
        
    except Order.DoesNotExist:
        return render(request, 'payments/customer_order_not_found.html', {
            'page': page_obj,
            'order_number': order_number,
        })

# Utility function for sending emails
def send_order_status_email(order, old_status, new_status):
    """Send email notification for order status change"""
    # This is a placeholder - implement your email sending logic here
    # You can use Django's send_mail function or a service like SendGrid
    pass


def customer_order_lookup(request, subdomain):
    """Customer order lookup form"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    return render(request, 'payments/customer_order_lookup.html', {
        'page': page,
    })

# 11. Customer Order Access Denied View (NEW)
def customer_order_access_denied(request, subdomain):
    """Access denied for customer order view"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    return render(request, 'payments/customer_order_access_denied.html', {
        'page': page,
    })

# 12. Customer Order Not Found View (NEW)
def customer_order_not_found(request, subdomain):
    """Order not found for customer"""
    order_number = request.GET.get('order_number', '')
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    return render(request, 'payments/customer_order_not_found.html', {
        'page': page,
        'order_number': order_number,
    })

# 13. Cancel Order API View (NEW)
@csrf_exempt
@login_required
def cancel_order_api(request, order_id):
    """API endpoint to cancel order"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        order = get_object_or_404(Order, id=order_id)
        
        # Check if user has permission to cancel this order
        if not request.user.is_staff and order.page.user != request.user:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        data = json.loads(request.body)
        reason = data.get('reason', 'Cancelled by admin')
        
        # Check if order can be cancelled
        if not order.can_cancel():
            return JsonResponse({'success': False, 'error': 'Order cannot be cancelled in its current status'})
        
        # Cancel order
        old_status = order.status
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        
        # Add to status history
        order.status_history.append({
            'status': 'cancelled',
            'timestamp': timezone.now().isoformat(),
            'note': f'Cancelled: {reason}',
            'changed_by': request.user.username
        })
        
        order.save()
        
        # Send cancellation email
        send_order_cancellation_email(order, reason)
        
        return JsonResponse({
            'success': True,
            'message': 'Order cancelled successfully',
            'order_id': order.id,
            'order_number': order.order_number,
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# 14. Refund Order API View (NEW)
@csrf_exempt
@login_required
def refund_order_api(request, order_id):
    """API endpoint to refund order"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        order = get_object_or_404(Order, id=order_id)
        
        # Check if user has permission
        if not request.user.is_staff and order.page.user != request.user:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        data = json.loads(request.body)
        amount = data.get('amount')
        reason = data.get('reason', 'Refund requested')
        
        if not amount:
            return JsonResponse({'success': False, 'error': 'Refund amount is required'})
        
        amount = Decimal(str(amount))
        
        # Check if order can be refunded
        if not order.can_refund():
            return JsonResponse({'success': False, 'error': 'Order cannot be refunded in its current status'})
        
        # Check amount
        if amount <= 0:
            return JsonResponse({'success': False, 'error': 'Invalid refund amount'})
        
        if amount > order.total_amount:
            return JsonResponse({'success': False, 'error': 'Refund amount exceeds order total'})
        
        # Process refund based on payment method
        if order.payment_method == 'stripe':
            from .services.stripe_service import StripePaymentService
            # Get latest transaction
            transaction = order.transactions.filter(status='success').first()
            if transaction:
                stripe_service = StripePaymentService(transaction.payment_gateway)
                # Process Stripe refund
                refund_result = stripe_service.refund_payment(transaction.gateway_transaction_id, amount)
        elif order.payment_method == 'paypal':
            from .services.paypal_service import PayPalService
            transaction = order.transactions.filter(status='success').first()
            if transaction:
                paypal_service = PayPalService(transaction.payment_gateway)
                # Process PayPal refund
                refund_result = paypal_service.refund_payment(transaction.gateway_transaction_id, amount)
        else:
            # For POD or other methods, just update status
            refund_result = {'success': True, 'refund_id': f'MANUAL-{uuid.uuid4().hex[:8]}'}
        
        # Update order status
        order.status = 'refunded'
        order.payment_status = 'refunded'
        
        # Add to status history
        order.status_history.append({
            'status': 'refunded',
            'timestamp': timezone.now().isoformat(),
            'note': f'Refunded ${amount}: {reason}',
            'changed_by': request.user.username
        })
        
        order.save()
        
        # Create refund transaction
        Transaction.objects.create(
            order=order,
            payment_gateway=transaction.payment_gateway if transaction else None,
            gateway_transaction_id=refund_result.get('refund_id', f'REFUND-{uuid.uuid4().hex[:8]}'),
            amount=-amount,  # Negative amount for refund
            currency='USD',
            status='success',
            gateway_response=refund_result,
            processed_at=timezone.now()
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Refund of ${amount} processed successfully',
            'order_id': order.id,
            'refund_amount': str(amount),
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# 15. Resend Order Email API View (NEW)
@csrf_exempt
@login_required
def resend_order_email_api(request, order_id):
    """API endpoint to resend order confirmation email"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        order = get_object_or_404(Order, id=order_id)
        
        # Check if user has permission
        if not request.user.is_staff and order.page.user != request.user:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        # Send email
        send_order_confirmation_email(order)
        
        return JsonResponse({
            'success': True,
            'message': 'Order confirmation email resent',
            'order_id': order.id,
            'customer_email': order.customer_email,
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# 16. Get POD Info API View (NEW)
@csrf_exempt
def get_pod_info(request, subdomain):
    """Get Pay on Delivery gateway information for frontend"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
        
        # Get POD gateway
        pod_gateway = page.payment_gateways.filter(
            gateway_type='pay_on_delivery',
            is_active=True
        ).first()
        
        if not pod_gateway:
            return JsonResponse({
                'error': 'Pay on Delivery is not available',
                'available': False
            }, status=404)
        
        return JsonResponse({
            'available': True,
            'pod_minimum_amount': float(pod_gateway.pod_minimum_amount),
            'pod_maximum_amount': float(pod_gateway.pod_maximum_amount),
            'pod_available_zones': pod_gateway.pod_available_zones or [],
            'pod_instructions': pod_gateway.pod_instructions or '',
            'pod_requires_confirmation': pod_gateway.pod_requires_confirmation,
            'is_active': pod_gateway.is_active
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)






# Email utility functions

# Email utility functions
def send_order_confirmation_email(order, request=None):
    """Send order confirmation email to customer"""
    # Implement your email sending logic here
    # You can use Django's send_mail or a service like SendGrid
    subject = f"Order Confirmation: {order.order_number}"
    
    order_detail_url = ""
    if request:
        order_detail_url = f"{request.build_absolute_uri(reverse('payments:customer_order_detail', args=[order.page.subdomain, order.order_number]))}?email={order.customer_email}"
    
    message = f"""
    Thank you for your order!
    
    Order Number: {order.order_number}
    Order Date: {order.created_at.strftime('%B %d, %Y')}
    Total Amount: ${order.total_amount}
    
    Order Status: {order.get_status_display()}
    
    You can view your order details at:
    {order_detail_url}
    
    Thank you,"""
def send_order_status_email(order, old_status, new_status, request=None):
    
    subject = f"Order Status Updated: {order.order_number}"
    
    order_detail_url = ""
    if request:
        order_detail_url = f"{request.build_absolute_uri(reverse('payments:customer_order_detail', args=[order.page.subdomain, order.order_number]))}?email={order.customer_email}"
    
    
    message = f"""
    Your order status has been updated.
    
    Order Number: {order.order_number}
    Previous Status: {old_status}
    New Status: {new_status}
    
    {get_status_change_message(new_status)}
    
    View your order: 
    {order_detail_url}
   
    
    # send_mail(subject, message, 'noreply@yourdomain.com', [order.customer_email])
    View your order: 
    {request.build_absolute_uri(reverse('payments:customer_order_detail', args=[order.page.subdomain, order.order_number]))}?email={order.customer_email}
    """
    
    # send_mail(subject, message, 'noreply@yourdomain.com', [order.customer_email])

def send_order_cancellation_email(order, reason):
    """Send order cancellation email"""
    subject = f"Order Cancelled: {order.order_number}"
    message = f"""
    Your order has been cancelled.
    
    Order Number: {order.order_number}
    Cancellation Reason: {reason}
    
    If you have any questions, please contact us.
    
    {order.page.brand_name}
    """
    
    # send_mail(subject, message, 'noreply@yourdomain.com', [order.customer_email])

def get_status_change_message(status):
    """Get appropriate message for status change"""
    messages = {
        'processing': "Your order is now being processed. We'll notify you when it ships.",
        'ready_for_delivery': "Your order is ready for delivery!",
        'out_for_delivery': "Your order is out for delivery!",
        'completed': "Your order has been completed. Thank you for your purchase!",
        'cancelled': "Your order has been cancelled.",
        'refunded': "Your order has been refunded.",
    }
    return messages.get(status, "Your order status has been updated.")





# Add to imports
from django import forms

class CustomerInfoForm(forms.Form):
    """Form for collecting customer information"""
    email = forms.EmailField(required=True)
    name = forms.CharField(max_length=100, required=True)
    phone = forms.CharField(max_length=20, required=False)
    address = forms.CharField(widget=forms.Textarea, required=True)
    city = forms.CharField(max_length=100, required=True)
    state = forms.CharField(max_length=100, required=False)
    zip_code = forms.CharField(max_length=20, required=True)
    country = forms.CharField(max_length=100, required=True, initial='US')
    
    # Delivery information (if different)
    delivery_address = forms.CharField(widget=forms.Textarea, required=False)
    delivery_city = forms.CharField(max_length=100, required=False)
    delivery_state = forms.CharField(max_length=100, required=False)
    delivery_zip = forms.CharField(max_length=20, required=False)
    delivery_notes = forms.CharField(widget=forms.Textarea, required=False)

def collect_customer_info(request, subdomain):
    """Collect customer information before payment"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
    # Get order data from session or request
    order_data = request.session.get('pending_order', {})
    
    if request.method == 'POST':
        form = CustomerInfoForm(request.POST)
        if form.is_valid():
            customer_data = {
                'email': form.cleaned_data['email'],
                'name': form.cleaned_data['name'],
                'phone': form.cleaned_data['phone'],
                'address': form.cleaned_data['address'],
                'city': form.cleaned_data['city'],
                'state': form.cleaned_data['state'],
                'zip': form.cleaned_data['zip_code'],
                'country': form.cleaned_data['country'],
                'delivery_address': form.cleaned_data['delivery_address'] or form.cleaned_data['address'],
                'delivery_city': form.cleaned_data['delivery_city'] or form.cleaned_data['city'],
                'delivery_state': form.cleaned_data['delivery_state'] or form.cleaned_data['state'],
                'delivery_zip': form.cleaned_data['delivery_zip'] or form.cleaned_data['zip_code'],
                'delivery_notes': form.cleaned_data['delivery_notes'],
            }
            
            # Store in session for payment page
            request.session['customer_info'] = customer_data
            
            # Redirect to payment selection with data
            return redirect('payments:payment_selection', subdomain=subdomain)
    else:
        form = CustomerInfoForm()
    
    return render(request, 'payments/collect_customer_info.html', {
        'page': page,
        'form': form,
        'order_data': order_data,
    })



# def initiate_checkout(request, subdomain):
#     """Start checkout process"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
#     # Get cart data (you need to implement this based on your cart system)
#     cart_data = {
#         'items': request.session.get('cart_items', []),
#         'subtotal': request.session.get('cart_subtotal', 0),
#         'tax_amount': request.session.get('cart_tax', 0),
#         'shipping_amount': request.session.get('cart_shipping', 0),
#         'total_amount': request.session.get('cart_total', 0),
#         'checkout_type': 'cart',
#     }
    
#     # Store in session
#     request.session['pending_order'] = cart_data
    
#     # Redirect to customer info
#     return redirect('payments:collect_customer_info', subdomain=subdomain)

# from builder.models import Cart


# def initiate_checkout(request, subdomain):
#     """Start checkout process with variant data"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
#     # Get the current cart (from session or database)
#     if not request.session.session_key:
#         request.session.create()
#     session_key = request.session.session_key
    
#     # Find the cart
#     cart = None
#     if request.user.is_authenticated:
#         cart = Cart.objects.filter(user=request.user, page=page).first()
#         if not cart:
#             cart = Cart.objects.filter(session_key=session_key, page=page).first()
#     else:
#         cart = Cart.objects.filter(session_key=session_key, page=page).first()
    
#     if not cart:
#         return redirect('view_cart', subdomain=subdomain)
    
#     # Prepare cart data with variant information
#     cart_items = []
#     subtotal = 0
    
    
#     for item in cart.items.all():
#         print(f"Item is: {item}")
#         item_total = item.quantity * item.product.price
#         subtotal += item_total
        
#         cart_items.append({
#             'id': item.id,
#             'product_id': item.product.id,
#             'title': item.product.title,
#             'price': float(item.product.price),
#             'quantity': item.quantity,
#             'total_price': float(item_total),
#             'image_url': item.product.main_image.url if item.product.main_image else '',
#             # Include variant data
#             'selected_color': item.selected_color or '',
#             'selected_size': item.selected_size or '',
#             'sku': item.product.sku or ''
#         })
    
#     # Calculate other amounts (simplified - you'll need your actual tax/shipping logic)
#     tax_rate = 0.08  # 8% tax rate as example
#     shipping_rate = 5.00  # Flat shipping as example
    
#     tax_amount = subtotal * tax_rate
#     shipping_amount = shipping_rate
#     total_amount = subtotal + tax_amount + shipping_amount
    
#     cart_data = {
#         'items': cart_items,
#         'subtotal': float(subtotal),
#         'tax_amount': float(tax_amount),
#         'shipping_amount': float(shipping_amount),
#         'total_amount': float(total_amount),
#         'checkout_type': 'cart',
#     }
    
#     # Store in session
#     request.session['pending_order'] = cart_data
    
#     # Clear cart items from session (they're now in pending_order)
#     if 'cart_items' in request.session:
#         del request.session['cart_items']
    
#     # Redirect to customer info
#     return redirect('payments:collect_customer_info', subdomain=subdomain)
















# views.py (add these to your existing views)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Count, Avg
from django.db.models.functions import TruncMonth, TruncQuarter
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json

from .models import TaxClass, TaxRate, TaxExemptCustomer, TaxReport
from .services.tax_service import TaxService
from builder.models import PublishedPage, Product

# ============= TAX MANAGEMENT VIEWS =============

@login_required
@business_required
def tax_dashboard(request, subdomain):
    """Main tax management dashboard"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create default tax class
    default_tax_class, created = TaxClass.objects.get_or_create(
        page=page,
        slug='standard',
        defaults={
            'name': 'Standard',
            'description': 'Standard tax class for most products',
            'is_default': True
        }
    )
    
    # Get statistics
    tax_classes = page.tax_classes.all()
    tax_rates = page.tax_rates.select_related('tax_class').order_by('country_code', 'state_code')
    
    # Calculate metrics
    total_rates = tax_rates.count()
    active_rates = tax_rates.filter(is_active=True).count()
    
    # Get unique countries
    countries = tax_rates.exclude(country_code='').values_list('country_code', flat=True).distinct()
    
    # Recent activity
    recent_rates = tax_rates.order_by('-created_at')[:5]
    
    # Monthly tax collection (from orders)
    from .models import Order
    last_30_days = timezone.now() - timedelta(days=30)
    monthly_tax = Order.objects.filter(
        page=page,
        created_at__gte=last_30_days,
        status='completed'
    ).aggregate(
        total=Sum('tax_amount')
    )['total'] or 0
    
    context = {
        'page': page,
        'tax_classes': tax_classes,
        'tax_classes_count': tax_classes.count(),
        'tax_rates': tax_rates,
        'total_rates': total_rates,
        'active_rates': active_rates,
        'inactive_rates': total_rates - active_rates,
        'countries': countries,
        'countries_count': countries.count(),
        'recent_rates': recent_rates,
        'monthly_tax': monthly_tax,
        'avg_rate': tax_rates.aggregate(avg=Avg('rate'))['avg'] or 0,
        'default_tax_class': default_tax_class,
    }
    
    return render(request, 'payments/tax_dashboard.html', context)


@login_required
@business_required
def tax_classes_list(request, subdomain):
    """List all tax classes"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    tax_classes = page.tax_classes.all().prefetch_related('rates')
    
    return render(request, 'payments/tax_classes_list.html', {
        'page': page,
        'tax_classes': tax_classes,
    })


@login_required
@csrf_exempt
@business_required
def tax_class_create(request, subdomain):
    """Create a new tax class"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            
            name = request.POST.get('name')
            slug = request.POST.get('slug', name.lower().replace(' ', '-'))
            description = request.POST.get('description', '')
            calculation_type = request.POST.get('calculation_type', 'percentage')
            is_default = request.POST.get('is_default') == 'on'
            is_shipping_taxable = request.POST.get('is_shipping_taxable') == 'on'
            is_compound = request.POST.get('is_compound') == 'on'
            
            with transaction.atomic():
                if is_default:
                    TaxClass.objects.filter(page=page, is_default=True).update(is_default=False)
                
                tax_class = TaxClass.objects.create(
                    page=page,
                    name=name,
                    slug=slug,
                    description=description,
                    calculation_type=calculation_type,
                    is_default=is_default,
                    is_shipping_taxable=is_shipping_taxable,
                    is_compound=is_compound
                )
            
            messages.success(request, f'Tax class "{name}" created successfully!')
            
        except Exception as e:
            messages.error(request, f'Error creating tax class: {str(e)}')
        
        return redirect('payments:tax_dashboard', subdomain=subdomain)
    
    return render(request, 'payments/tax_class_form.html', {
        'page': get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user),
        'form_title': 'Create Tax Class',
    })


@login_required
@csrf_exempt
@business_required
def tax_class_edit(request, subdomain, class_id):
    """Edit tax class"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    tax_class = get_object_or_404(TaxClass, id=class_id, page=page)
    
    if request.method == 'POST':
        try:
            
            tax_class.name = request.POST.get('name', tax_class.name)
            tax_class.slug = request.POST.get('slug', tax_class.slug)
            tax_class.description = request.POST.get('description', tax_class.description)
            tax_class.calculation_type = request.POST.get('calculation_type', tax_class.calculation_type)
            tax_class.is_shipping_taxable = request.POST.get('is_shipping_taxable') == 'on'
            tax_class.is_compound = request.POST.get('is_compound') == 'on'
            
            is_default = request.POST.get('is_default') == 'on'
            if is_default and not tax_class.is_default:
                with transaction.atomic():
                    TaxClass.objects.filter(page=page, is_default=True).update(is_default=False)
                    tax_class.is_default = True
            
            tax_class.save()
            messages.success(request, f'Tax class "{tax_class.name}" updated!')
            
        except Exception as e:
            messages.error(request, f'Error updating tax class: {str(e)}')
        
        return redirect('payments:tax_dashboard', subdomain=subdomain)
    
    return render(request, 'payments/tax_class_form.html', {
        'page': page,
        'tax_class': tax_class,
        'form_title': 'Edit Tax Class',
    })


@login_required
@csrf_exempt
def tax_class_delete(request, subdomain, class_id):
    """Delete tax class"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            tax_class = get_object_or_404(TaxClass, id=class_id, page=page)
            
            if tax_class.is_default:
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot delete default tax class'
                })
            
            # Check if products use this tax class
            if Product.objects.filter(page=page, tax_class=tax_class).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot delete tax class that is assigned to products'
                })
            
            tax_class.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Tax class deleted successfully'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
@business_required
def tax_rates_list(request, subdomain):
    """List all tax rates with filtering"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get filter parameters
    country = request.GET.get('country', '')
    state = request.GET.get('state', '')
    tax_class_id = request.GET.get('tax_class', '')
    status = request.GET.get('status', '')
    
    # Base queryset
    tax_rates = page.tax_rates.select_related('tax_class').all()
    
    # Apply filters
    if country:
        tax_rates = tax_rates.filter(country_code=country.upper())
    if state:
        tax_rates = tax_rates.filter(state_code=state.upper())
    if tax_class_id:
        tax_rates = tax_rates.filter(tax_class_id=tax_class_id)
    if status == 'active':
        tax_rates = tax_rates.filter(is_active=True)
    elif status == 'inactive':
        tax_rates = tax_rates.filter(is_active=False)
    
    # Get unique countries and tax classes for filters
    countries = page.tax_rates.exclude(country_code='').values_list('country_code', flat=True).distinct()
    tax_classes = page.tax_classes.all()
    
    # Pagination
    paginator = Paginator(tax_rates.order_by('country_code', 'state_code'), 50)
    page_number = request.GET.get('page', 1)
    rates_page = paginator.get_page(page_number)
    
    context = {
        'page': page,
        'tax_rates': rates_page,
        'countries': sorted(set(countries)),
        'tax_classes': tax_classes,
        'filters': {
            'country': country,
            'state': state,
            'tax_class': tax_class_id,
            'status': status,
        }
    }
    
    return render(request, 'payments/tax_rates_list.html', context)


@login_required
@csrf_exempt
@business_required
def tax_rate_create(request, subdomain):
    """Create a new tax rate"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            
            tax_class = get_object_or_404(TaxClass, id=request.POST.get('tax_class_id'), page=page)
            
            # Validate with TaxService
            tax_service = TaxService(page)
            rate_data = {
                'tax_class_id': tax_class.id,
                'country_code': request.POST.get('country_code', '').upper(),
                'state_code': request.POST.get('state_code', '').upper(),
                'city': request.POST.get('city', ''),
                'postal_code': request.POST.get('postal_code', ''),
                'rate': request.POST.get('rate', 0),
            }
            
            errors = tax_service.validate_tax_rate(rate_data)
            if errors:
                for error in errors:
                    messages.error(request, error)
                return redirect('payments:tax_rates_list', subdomain=subdomain)
            
            # Create tax rate
            tax_rate = TaxRate.objects.create(
                page=page,
                tax_class=tax_class,
                name=request.POST.get('name'),
                rate=request.POST.get('rate'),
                jurisdiction_type=request.POST.get('jurisdiction_type', 'country'),
                country_code=request.POST.get('country_code', '').upper(),
                state_code=request.POST.get('state_code', '').upper(),
                city=request.POST.get('city', ''),
                postal_code=request.POST.get('postal_code', ''),
                postal_code_match_pattern=request.POST.get('postal_code_match_pattern', ''),
                priority=request.POST.get('priority', 0),
                is_compound=request.POST.get('is_compound') == 'on',
                is_price_inclusive=request.POST.get('is_price_inclusive') == 'on',
                is_shipping_taxable=request.POST.get('is_shipping_taxable') == 'on',
                valid_from=request.POST.get('valid_from') or timezone.now(),
                valid_until=request.POST.get('valid_until') or None,
                created_by=request.user
            )
            
            messages.success(request, f'Tax rate "{tax_rate.name}" created!')
            
        except Exception as e:
            messages.error(request, f'Error creating tax rate: {str(e)}')
        
        return redirect('payments:tax_rates_list', subdomain=subdomain)
    
    # GET request - show form
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    tax_classes = page.tax_classes.all()
    
    return render(request, 'payments/tax_rate_form.html', {
        'page': page,
        'tax_classes': tax_classes,
        'form_title': 'Create Tax Rate',
    })


@login_required
@csrf_exempt
@business_required
def tax_rate_edit(request, subdomain, rate_id):
    """Edit tax rate"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    tax_rate = get_object_or_404(TaxRate, id=rate_id, page=page)
    
    if request.method == 'POST':
        try:
            # Update fields
            tax_rate.name = request.POST.get('name', tax_rate.name)
            tax_rate.rate = request.POST.get('rate', tax_rate.rate)
            tax_rate.jurisdiction_type = request.POST.get('jurisdiction_type', tax_rate.jurisdiction_type)
            tax_rate.country_code = request.POST.get('country_code', '').upper()
            tax_rate.state_code = request.POST.get('state_code', '').upper()
            tax_rate.city = request.POST.get('city', tax_rate.city)
            tax_rate.postal_code = request.POST.get('postal_code', tax_rate.postal_code)
            tax_rate.postal_code_match_pattern = request.POST.get('postal_code_match_pattern', '')
            tax_rate.priority = request.POST.get('priority', tax_rate.priority)
            tax_rate.is_compound = request.POST.get('is_compound') == 'on'
            tax_rate.is_price_inclusive = request.POST.get('is_price_inclusive') == 'on'
            tax_rate.is_shipping_taxable = request.POST.get('is_shipping_taxable') == 'on'
            tax_rate.is_active = request.POST.get('is_active') == 'on'
            
            # Handle dates
            if request.POST.get('valid_from'):
                tax_rate.valid_from = request.POST.get('valid_from')
            if request.POST.get('valid_until'):
                tax_rate.valid_until = request.POST.get('valid_until')
            elif request.POST.get('valid_until') == '':
                tax_rate.valid_until = None
            
            tax_rate.save()
            messages.success(request, f'Tax rate "{tax_rate.name}" updated!')
            
        except Exception as e:
            messages.error(request, f'Error updating tax rate: {str(e)}')
        
        return redirect('payments:tax_rates_list', subdomain=subdomain)
    
    # GET request - show form
    tax_classes = page.tax_classes.all()
    
    return render(request, 'payments/tax_rate_form.html', {
        'page': page,
        'tax_rate': tax_rate,
        'tax_classes': tax_classes,
        'form_title': 'Edit Tax Rate',
    })


@login_required
@csrf_exempt
def tax_rate_delete(request, subdomain, rate_id):
    """Delete tax rate"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            tax_rate = get_object_or_404(TaxRate, id=rate_id, page=page)
            
            tax_rate.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Tax rate deleted successfully'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
@csrf_exempt
def tax_rate_toggle_status(request, subdomain, rate_id):
    """Toggle tax rate active status"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            tax_rate = get_object_or_404(TaxRate, id=rate_id, page=page)
            
            tax_rate.is_active = not tax_rate.is_active
            tax_rate.save()
            
            status = 'activated' if tax_rate.is_active else 'deactivated'
            
            return JsonResponse({
                'success': True,
                'is_active': tax_rate.is_active,
                'message': f'Tax rate {status} successfully'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
@business_required
def tax_exempt_customers(request, subdomain):
    """Manage tax exempt customers"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get filter parameters
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    customers = page.tax_exempt_customers.all()
    
    # Apply filters
    if status == 'active':
        customers = customers.filter(is_active=True)
    elif status == 'inactive':
        customers = customers.filter(is_active=False)
    elif status == 'expired':
        customers = customers.filter(exempt_until__lt=timezone.now())
    elif status == 'pending':
        customers = customers.filter(requires_review=True)
    
    if search:
        customers = customers.filter(
            Q(email__icontains=search) |
            Q(company_name__icontains=search) |
            Q(tax_id__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(customers.order_by('-created_at'), 25)
    page_number = request.GET.get('page', 1)
    customers_page = paginator.get_page(page_number)
    
    context = {
        'page': page,
        'customers': customers_page,
        'filters': {
            'status': status,
            'search': search,
        }
    }
    
    return render(request, 'payments/tax_exempt_customers.html', context)


@login_required
@csrf_exempt
def tax_exempt_customer_create(request, subdomain):
    """Add tax exempt customer"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            
            # Check if customer already exists
            email = request.POST.get('email')
            existing = TaxExemptCustomer.objects.filter(page=page, email=email).first()
            
            if existing:
                # Reactivate if inactive
                if not existing.is_active:
                    existing.is_active = True
                    existing.exempt_until = request.POST.get('exempt_until') or None
                    existing.save()
                    messages.success(request, f'Customer "{email}" reactivated')
                else:
                    messages.warning(request, f'Customer "{email}" is already exempt')
            else:
                # Create new exempt customer
                customer = TaxExemptCustomer.objects.create(
                    page=page,
                    email=email,
                    company_name=request.POST.get('company_name', ''),
                    tax_id=request.POST.get('tax_id', ''),
                    exemption_reason=request.POST.get('exemption_reason', ''),
                    exempt_until=request.POST.get('exempt_until') or None,
                    certificate_number=request.POST.get('certificate_number', ''),
                    notes=request.POST.get('notes', ''),
                    requires_review=request.POST.get('requires_review') == 'on',
                    created_by=request.user
                )
                messages.success(request, f'Customer "{email}" added to exemption list')
            
        except Exception as e:
            messages.error(request, f'Error adding exempt customer: {str(e)}')
        
        return redirect('payments:tax_exempt_customers', subdomain=subdomain)
    
    return render(request, 'payments/tax_exempt_form.html', {
        'page': get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user),
        'form_title': 'Add Tax Exempt Customer',
    })


@login_required
@csrf_exempt
@business_required
def tax_exempt_customer_edit(request, subdomain, customer_id):
    """Edit tax exempt customer"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    customer = get_object_or_404(TaxExemptCustomer, id=customer_id, page=page)
    
    if request.method == 'POST':
        try:
            customer.company_name = request.POST.get('company_name', customer.company_name)
            customer.tax_id = request.POST.get('tax_id', customer.tax_id)
            customer.exemption_reason = request.POST.get('exemption_reason', customer.exemption_reason)
            customer.exempt_until = request.POST.get('exempt_until') or None
            customer.certificate_number = request.POST.get('certificate_number', customer.certificate_number)
            customer.notes = request.POST.get('notes', customer.notes)
            customer.requires_review = request.POST.get('requires_review') == 'on'
            customer.is_active = request.POST.get('is_active') == 'on'
            
            customer.save()
            messages.success(request, f'Customer "{customer.email}" updated')
            
        except Exception as e:
            messages.error(request, f'Error updating customer: {str(e)}')
        
        return redirect('payments:tax_exempt_customers', subdomain=subdomain)
    
    return render(request, 'payments/tax_exempt_form.html', {
        'page': page,
        'customer': customer,
        'form_title': 'Edit Tax Exempt Customer',
    })


@login_required
@csrf_exempt
def tax_exempt_customer_delete(request, subdomain, customer_id):
    """Delete tax exempt customer"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            customer = get_object_or_404(TaxExemptCustomer, id=customer_id, page=page)
            
            customer.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Customer removed from exemption list'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
@business_required
def tax_reports(request, subdomain):
    """Tax reports and analytics"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=365)
    
    # Monthly tax collection
    from .models import Order
    
    monthly_tax = Order.objects.filter(
        page=page,
        created_at__gte=start_date,
        status='completed'
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        tax_collected=Sum('tax_amount'),
        order_count=Count('id'),
        total_sales=Sum('total_amount')
    ).order_by('month')
    
    # Tax by country
    tax_by_country = TaxTransaction.objects.filter(
        order__page=page,
        calculated_at__gte=start_date
    ).values('country_code').annotate(
        total_tax=Sum('tax_amount'),
        transaction_count=Count('id')
    ).order_by('-total_tax')[:10]
    
    # Top tax rates used
    top_rates = TaxRate.objects.filter(
        page=page,
        is_active=True
    ).annotate(
        usage_count=Count('taxtransaction')
    ).order_by('-usage_count')[:10]
    
    context = {
        'page': page,
        'monthly_tax': monthly_tax,
        'tax_by_country': tax_by_country,
        'top_rates': top_rates,
        'start_date': start_date.date(),
        'end_date': end_date.date(),
        'total_tax_collected': monthly_tax.aggregate(Sum('tax_collected'))['tax_collected__sum'] or 0,
    }
    
    return render(request, 'payments/tax_reports.html', context)


@login_required
def tax_settings(request, subdomain):
    """Tax configuration settings"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    if request.method == 'POST':
        try:
            # Get or create settings
            if not hasattr(page, 'settings'):
                page.settings = {}
            
            page.settings['tax'] = {
                'show_tax_in_cart': request.POST.get('show_tax_in_cart') == 'on',
                'prices_include_tax': request.POST.get('prices_include_tax') == 'on',
                'tax_shipping': request.POST.get('tax_shipping') == 'on',
                'display_tax_as': request.POST.get('display_tax_as', 'inclusive'),
                'tax_rounding': request.POST.get('tax_rounding', 'round_per_item'),
                'default_tax_origin': request.POST.get('default_tax_origin', ''),
                'auto_apply_rates': request.POST.get('auto_apply_rates') == 'on',
                'updated_at': timezone.now().isoformat(),
            }
            
            page.save(update_fields=['settings'])
            messages.success(request, 'Tax settings saved successfully!')
            
        except Exception as e:
            messages.error(request, f'Error saving settings: {str(e)}')
        
        return redirect('payments:tax_dashboard', subdomain=subdomain)
    
    # GET request
    tax_settings = page.settings.get('tax', {})
    
    return render(request, 'payments/tax_settings.html', {
        'page': page,
        'settings': tax_settings,
    })


# ============= PUBLIC API ENDPOINTS =============

@csrf_exempt
def api_calculate_tax(request, subdomain):
    """Public API endpoint for tax calculation"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
        data = json.loads(request.body)
        
        # Extract data
        items = data.get('items', [])
        customer = data.get('customer', {})
        shipping_cost = Decimal(str(data.get('shipping_cost', 0)))
        debug = data.get('debug', False)
        
        # Calculate tax
        tax_service = TaxService(page)
        result = tax_service.calculate_tax(
            items=items,
            customer_data=customer,
            shipping_cost=shipping_cost,
            debug=debug
        )
        
        return JsonResponse({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@csrf_exempt
def api_validate_tax_exemption(request, subdomain):
    """Check if customer is tax exempt"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
        data = json.loads(request.body)
        
        email = data.get('email')
        
        if not email:
            return JsonResponse({'success': False, 'error': 'Email required'})
        
        tax_service = TaxService(page)
        is_exempt = tax_service._is_tax_exempt(email)
        
        return JsonResponse({
            'success': True,
            'is_exempt': is_exempt,
            'email': email
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


# ============= QUICK ACTIONS =============

@login_required
@csrf_exempt
def apply_us_sales_tax(request, subdomain):
    """Apply US Sales Tax rates for all states"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            
            # Get or create standard tax class
            tax_class, created = TaxClass.objects.get_or_create(
                page=page,
                slug='standard',
                defaults={
                    'name': 'Standard',
                    'description': 'Standard tax class',
                    'is_default': True
                }
            )
            
            # US States and their sales tax rates
            us_states = {
                'AL': 4.00, 'AK': 0.00, 'AZ': 5.60, 'AR': 6.50, 'CA': 7.25,
                'CO': 2.90, 'CT': 6.35, 'DE': 0.00, 'FL': 6.00, 'GA': 4.00,
                'HI': 4.00, 'ID': 6.00, 'IL': 6.25, 'IN': 7.00, 'IA': 6.00,
                'KS': 6.50, 'KY': 6.00, 'LA': 4.45, 'ME': 5.50, 'MD': 6.00,
                'MA': 6.25, 'MI': 6.00, 'MN': 6.88, 'MS': 7.00, 'MO': 4.23,
                'MT': 0.00, 'NE': 5.50, 'NV': 6.85, 'NH': 0.00, 'NJ': 6.63,
                'NM': 5.13, 'NY': 4.00, 'NC': 4.75, 'ND': 5.00, 'OH': 5.75,
                'OK': 4.50, 'OR': 0.00, 'PA': 6.00, 'RI': 7.00, 'SC': 6.00,
                'SD': 4.50, 'TN': 7.00, 'TX': 6.25, 'UT': 6.10, 'VT': 6.00,
                'VA': 5.30, 'WA': 6.50, 'WV': 6.00, 'WI': 5.00, 'WY': 4.00,
                'DC': 6.00
            }
            
            created_count = 0
            with transaction.atomic():
                for state_code, rate in us_states.items():
                    if rate > 0:  # Skip zero-rate states
                        tax_rate, created = TaxRate.objects.update_or_create(
                            page=page,
                            tax_class=tax_class,
                            country_code='US',
                            state_code=state_code,
                            jurisdiction_type='state',
                            defaults={
                                'name': f'{state_code} Sales Tax',
                                'rate': rate,
                                'is_active': True,
                                'priority': 0,
                            }
                        )
                        if created:
                            created_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'Created {created_count} US state tax rates'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
@csrf_exempt
def apply_eu_vat(request, subdomain):
    """Apply EU VAT rates"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            
            tax_class, created = TaxClass.objects.get_or_create(
                page=page,
                slug='vat',
                defaults={
                    'name': 'VAT',
                    'description': 'Value Added Tax',
                    'is_shipping_taxable': True,
                }
            )
            
            eu_countries = [
                'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
                'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
                'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
            ]
            
            created_count = 0
            with transaction.atomic():
                for country in eu_countries:
                    tax_rate, created = TaxRate.objects.update_or_create(
                        page=page,
                        tax_class=tax_class,
                        country_code=country,
                        jurisdiction_type='country',
                        defaults={
                            'name': f'{country} VAT',
                            'rate': 20.00,  # Standard rate
                            'is_active': True,
                            'priority': 0,
                        }
                    )
                    if created:
                        created_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'Created {created_count} EU VAT rates'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
def export_tax_rates(request, subdomain):
    """Export tax rates to CSV"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="tax_rates_{page.subdomain}_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Tax Class', 'Rate Name', 'Rate %', 'Country', 'State', 'City',
        'Postal Code', 'Jurisdiction Type', 'Priority', 'Active', 'Valid From', 'Valid Until'
    ])
    
    for rate in page.tax_rates.select_related('tax_class').all():
        writer.writerow([
            rate.tax_class.name,
            rate.name,
            rate.rate,
            rate.country_code,
            rate.state_code,
            rate.city,
            rate.postal_code,
            rate.get_jurisdiction_type_display(),
            rate.priority,
            'Yes' if rate.is_active else 'No',
            rate.valid_from.strftime('%Y-%m-%d'),
            rate.valid_until.strftime('%Y-%m-%d') if rate.valid_until else '',
        ])
    
    return response


@login_required
def import_tax_rates(request, subdomain):
    """Import tax rates from CSV"""
    if request.method == 'POST' and request.FILES.get('csv_file'):
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            csv_file = request.FILES['csv_file']
            
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            
            imported = 0
            errors = []
            
            with transaction.atomic():
                for row in reader:
                    try:
                        # Get or create tax class
                        tax_class, _ = TaxClass.objects.get_or_create(
                            page=page,
                            name=row.get('Tax Class', 'Standard'),
                            defaults={'slug': row.get('Tax Class', 'standard').lower().replace(' ', '-')}
                        )
                        
                        # Create tax rate
                        TaxRate.objects.create(
                            page=page,
                            tax_class=tax_class,
                            name=row.get('Rate Name'),
                            rate=row.get('Rate %'),
                            country_code=row.get('Country', ''),
                            state_code=row.get('State', ''),
                            city=row.get('City', ''),
                            postal_code=row.get('Postal Code', ''),
                            jurisdiction_type=row.get('Jurisdiction Type', 'country'),
                            priority=row.get('Priority', 0),
                            is_active=row.get('Active', 'Yes') == 'Yes',
                        )
                        imported += 1
                        
                    except Exception as e:
                        errors.append(f"Row {imported + 1}: {str(e)}")
            
            if errors:
                messages.warning(request, f'Imported {imported} rates with {len(errors)} errors: {", ".join(errors[:3])}')
            else:
                messages.success(request, f'Successfully imported {imported} tax rates!')
            
        except Exception as e:
            messages.error(request, f'Error importing file: {str(e)}')
        
        return redirect('payments:tax_rates_list', subdomain=subdomain)
    
    return render(request, 'payments/tax_import.html', {
        'page': get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    })
 













# In payments/views.py - Add social media configuration view

@login_required
def configure_social_media_gateway(request, subdomain):
    """Configure Social Media payment gateway"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create Social Media gateway
    social_gateway, created = PaymentGateway.objects.get_or_create(
        page=page,
        gateway_type='social_media',
        defaults={
            'is_active': False,
            'social_media_platforms': [],
            'social_media_order_prefix': 'SOC-',
            'social_media_auto_send': True,
        }
    )
    
    if request.method == 'POST':
        # Get enabled platforms
        platforms = request.POST.getlist('social_media_platforms')
        social_gateway.social_media_platforms = platforms
        
        # WhatsApp
        social_gateway.whatsapp_number = request.POST.get('whatsapp_number', '').strip()
        social_gateway.whatsapp_business_name = request.POST.get('whatsapp_business_name', '').strip()
        
        # Facebook
        social_gateway.facebook_page_id = request.POST.get('facebook_page_id', '').strip()
        social_gateway.facebook_messenger_link = request.POST.get('facebook_messenger_link', '').strip()
        social_gateway.facebook_username = request.POST.get('facebook_username', '').strip()
        
        # Instagram
        social_gateway.instagram_username = request.POST.get('instagram_username', '').strip()
        social_gateway.instagram_business_account = request.POST.get('instagram_business_account', '').strip()
        
        # Telegram
        social_gateway.telegram_username = request.POST.get('telegram_username', '').strip()
        social_gateway.telegram_bot_token = request.POST.get('telegram_bot_token', '').strip()
        social_gateway.telegram_chat_id = request.POST.get('telegram_chat_id', '').strip()
        
        # X.com
        social_gateway.x_username = request.POST.get('x_username', '').strip()
        social_gateway.x_dm_link = request.POST.get('x_dm_link', '').strip()
        
        # Settings
        social_gateway.social_media_order_prefix = request.POST.get('social_media_order_prefix', 'SOC-')
        social_gateway.social_media_auto_send = request.POST.get('social_media_auto_send') == 'on'
        social_gateway.social_media_message_template = request.POST.get('social_media_message_template', '').strip()
        
        social_gateway.is_active = request.POST.get('is_active') == 'on'
        social_gateway.save()
        
        messages.success(request, 'Social Media payment configuration saved successfully!')
        return redirect('payments:manage_gateways', subdomain=subdomain)
    
    return render(request, 'payments/configure_social_media.html', {
        'page': page,
        'social_gateway': social_gateway,
    })


# Add success page for social media orders
# payments/views.py

# def social_media_success(request, subdomain):
#     """Social media order success page with CJ fulfillment integration"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain)
#     order_number = request.session.get('last_order_number', '')
#     platform_messages = request.session.get('social_media_messages', {})
    
#     try:
#         order = get_object_or_404(Order,
#             order_number=order_number,
#             page=page,
#             status='pending'  # Social media orders start as 'pending'
#         )
#     except Order.DoesNotExist:
#         order = None
    
#     # Get social media gateway
#     social_gateway = page.payment_gateways.filter(
#         gateway_type='social_media',
#         is_active=True
#     ).first()
    
#     # ========== CJ FULFILLMENT LOGIC (Copied from pod_success) ==========
#     if order and order.can_fulfill_cj():
#         print(f"✅ Order {order.order_number} eligible for CJ fulfillment")
        
#         from builder.services.cj_service import CJManager
#         from builder.models import CJSettings
        
#         # Get CJ settings for this specific page/store
#         account = CJSettings.objects.filter(page=page).first()
        
#         if account and account.access_token:
#             try:
#                 manager = CJManager(token=account.access_token)
                
#                 # Call fulfillment (using the corrected method from previous answer)
#                 success = manager.fulfill_cj_order_corrected(order)
                
#                 if success:
#                     messages.success(request, f"CJ order #{order.cj_order_id} created successfully!")
#                     print(f"✅ CJ order created: {order.cj_order_id}")
#                 else:
#                     messages.error(request, "Failed to create CJ order. Please check CJ dashboard.")
                    
#             except Exception as e:
#                 logger.error(f"CJ fulfillment error for order {order_number}: {str(e)}")
#                 messages.error(request, f"CJ fulfillment error: {str(e)}")
#         else:
#             messages.warning(request, "CJ integration not configured or token missing.")
            
#     elif order:
#         # Order exists but not eligible for CJ
#         if order.is_cj_fulfilled:
#             messages.info(request, f"Order already fulfilled via CJ (#{order.cj_order_id})")
#         elif not order.all_items_have_vid:
#             cj_count = order.cj_items_count
#             manual_count = order.manual_items_count
#             if cj_count > 0 and manual_count > 0:
#                 messages.warning(request, 
#                     f"Order contains {cj_count} CJ item(s) and {manual_count} manual item(s). "
#                     f"CJ fulfillment skipped for mixed orders."
#                 )
#             else:
#                 messages.info(request, "No CJ items in order. Manual fulfillment required.")
    
#     return render(request, 'payments/social_media_success.html', {
#         'page': page,
#         'order': order,
#         'order_number': order_number,
#         'social_gateway': social_gateway,
#         'platform_messages': platform_messages,
#     })


def social_media_success(request, subdomain):
    """Social media order success page with shipping info"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
    # Get order from database
    order_number = request.GET.get('order') or request.session.get('last_order_number', '')
    
    order = None
    if order_number:
        try:
            order = Order.objects.get(order_number=order_number, page=page)
        except Order.DoesNotExist:
            order = None
    
    # If order not found in DB, use session data
    if not order:
        customer_info = request.session.get('last_order_customer', {})
        platform_messages = request.session.get('social_media_messages', {})
        
        # ===== GET SHIPPING DATA FROM SESSION =====
        shipping_info = request.session.get('last_shipping_info', {})
        shipping_cost = shipping_info.get('cost', 0)
        shipping_method = shipping_info.get('name', 'Standard Shipping')
        shipping_estimate = shipping_info.get('delivery_estimate', '3-7 business days')
        
        print(f"✅ Shipping data from session: cost={shipping_cost}, method={shipping_method}, estimate={shipping_estimate}")
        
        # Create a mock order object for template
        class MockOrder:
            pass
        
        order = MockOrder()
        order.order_number = order_number
        order.customer_name = customer_info.get('name', '')
        order.customer_email = customer_info.get('email', '')
        order.phone = customer_info.get('phone', '')
        order.customer_address = customer_info.get('address', '')
        order.customer_city = customer_info.get('city', '')
        order.customer_state = customer_info.get('state', '')
        order.customer_zip = customer_info.get('zip', '')
        order.customer_country = customer_info.get('country', '')
        order.delivery_address = customer_info.get('delivery_address', customer_info.get('address', ''))
        order.delivery_city = customer_info.get('delivery_city', customer_info.get('city', ''))
        order.delivery_state = customer_info.get('delivery_state', customer_info.get('state', ''))
        order.delivery_zip = customer_info.get('delivery_zip', customer_info.get('zip', ''))
        order.delivery_country = customer_info.get('country', '')
        order.delivery_notes = customer_info.get('delivery_notes', '')
        
        # Add shipping fields to mock order
        order.shipping_amount = shipping_cost
        order.shipping_method = shipping_method
        order.shipping_delivery_estimate = shipping_estimate
        order.shipping_carrier = shipping_info.get('rate', {}).get('carrier', '')
        
        # Get items from session
        order_data = request.session.get('last_order_data', {})
        items = order_data.get('cart', {}).get('items', []) or [order_data.get('product', {})]
        
        class MockItem:
            pass
        
        mock_items = []
        for item in items:
            mock_item = MockItem()
            mock_item.product_title = item.get('title', 'Product')
            mock_item.product_price = item.get('price', 0)
            mock_item.quantity = item.get('quantity', 1)
            mock_item.total_price = item.get('total_price', item.get('price', 0) * item.get('quantity', 1))
            mock_item.selected_color = item.get('selected_color', '')
            mock_item.selected_size = item.get('selected_size', '')
            mock_items.append(mock_item)
        
        order.items = mock_items
        order.subtotal = order_data.get('cart', {}).get('subtotal', order_data.get('product', {}).get('price', 0))
        order.tax_amount = order_data.get('tax_amount', 0)
        order.total_amount = order_data.get('total_amount', 0)
        
        context = {
            'page': page,
            'order_number': order_number,
            'order': order,
            'platform_messages': platform_messages,
            'is_session_order': True,
        }
        return render(request, 'payments/social_media_success.html', context)
    
    # Order found in database - get shipping from there
    platform_messages = request.session.get('social_media_messages', {})
    
    context = {
        'page': page,
        'order_number': order_number,
        'order': order,
        'platform_messages': platform_messages,
        'is_session_order': False,
    }
    return render(request, 'payments/social_media_success.html', context)


# payments/views/shipping_views.py
import json
import logging
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import transaction

from payments.models import ShippingZone, ShippingRate, ShippingAddress
from builder.models import PublishedPage

logger = logging.getLogger(__name__)

# Simple country list (ISO code -> Name)
COUNTRIES = {
    'US': 'United States',
    'CA': 'Canada', 
    'GB': 'United Kingdom',
    'AU': 'Australia',
    'DE': 'Germany',
    'FR': 'France',
    'IT': 'Italy',
    'ES': 'Spain',
    'JP': 'Japan',
    'CN': 'China',
    'IN': 'India',
    'BR': 'Brazil',
    'MX': 'Mexico',
    'RU': 'Russia',
    'KR': 'South Korea',
    'SG': 'Singapore',
    'NG': 'Nigeria',
    'ZA': 'South Africa',
    'EG': 'Egypt',
    'KE': 'Kenya',
    'GH': 'Ghana',
    'CM': 'Cameroon',
    'CI': 'Ivory Coast',
    'SN': 'Senegal',
    'TZ': 'Tanzania',
    'ET': 'Ethiopia',
    'UG': 'Uganda',
    'RW': 'Rwanda',
    'BI': 'Burundi',
    'MG': 'Madagascar',
    'MZ': 'Mozambique',
    'ZM': 'Zambia',
    'ZW': 'Zimbabwe',
    'BW': 'Botswana',
    'NA': 'Namibia',
    'LS': 'Lesotho',
    'SZ': 'Eswatini',
    'MW': 'Malawi',
    'AE': 'United Arab Emirates',
    'SA': 'Saudi Arabia',
    'TR': 'Turkey',
    'PK': 'Pakistan',
    'BD': 'Bangladesh',
    'LK': 'Sri Lanka',
    'NP': 'Nepal',
    'MY': 'Malaysia',
    'ID': 'Indonesia',
    'PH': 'Philippines',
    'VN': 'Vietnam',
    'TH': 'Thailand',
    'IL': 'Israel',
    'NZ': 'New Zealand',
}

# Convert to list for template
COUNTRY_LIST = [{'code': code, 'name': name} for code, name in COUNTRIES.items()]


@login_required
def manage_shipping(request, subdomain):
    """Main shipping settings page"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    zones = page.shipping_zones.filter(is_active=True).prefetch_related('rates')
    
    context = {
        'page': page,
        'zones': zones,
        'countries': COUNTRY_LIST,  # Use the simple list
    }
    return render(request, 'payments/shipping/manage_shipping.html', context)


# Update the add_shipping_zone function to use the same country list for display:
@login_required
@require_http_methods(["POST"])
def add_shipping_zone(request, subdomain):
    """Add a new shipping zone (AJAX)"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    try:
        data = json.loads(request.body)
        
        zone = ShippingZone.objects.create(
            page=page,
            name=data.get('name'),
            description=data.get('description', ''),
            zone_type=data.get('zone_type', 'custom'),
            countries=data.get('countries', []),
            regions=data.get('regions', {}),
            postcode_patterns=data.get('postcode_patterns', []),
            is_active=data.get('is_active', True),
            display_order=data.get('display_order', 0),
            show_in_checkout=data.get('show_in_checkout', True),
            show_estimated_delivery=data.get('show_estimated_delivery', True),
        )
        
        # Get country names for response using COUNTRIES dict
        country_names = [COUNTRIES.get(code, code) for code in zone.countries]
        
        return JsonResponse({
            'success': True,
            'zone': {
                'id': zone.id,
                'name': zone.name,
                'zone_type_display': zone.get_zone_type_display(),
                'countries': country_names,
                'rates_count': zone.rates.count(),
                'is_active': zone.is_active,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
@login_required
@require_http_methods(["POST"])
def add_shipping_zone(request, subdomain):
    """Add a new shipping zone (AJAX)"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    try:
        data = json.loads(request.body)
        
        zone = ShippingZone.objects.create(
            page=page,
            name=data.get('name'),
            description=data.get('description', ''),
            zone_type=data.get('zone_type', 'custom'),
            countries=data.get('countries', []),
            regions=data.get('regions', {}),
            postcode_patterns=data.get('postcode_patterns', []),
            is_active=data.get('is_active', True),
            display_order=data.get('display_order', 0),
            show_in_checkout=data.get('show_in_checkout', True),
            show_estimated_delivery=data.get('show_estimated_delivery', True),
        )
        
        return JsonResponse({
            'success': True,
            'zone': {
                'id': zone.id,
                'name': zone.name,
                'zone_type_display': zone.get_zone_type_display(),
                'countries': zone.get_country_names(),
                'rates_count': zone.rates.count(),
                'is_active': zone.is_active,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_shipping_zone(request, subdomain, zone_id):
    """Update shipping zone"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    zone = get_object_or_404(ShippingZone, id=zone_id, page=page)
    
    try:
        data = json.loads(request.body)
        
        zone.name = data.get('name', zone.name)
        zone.description = data.get('description', zone.description)
        zone.zone_type = data.get('zone_type', zone.zone_type)
        zone.countries = data.get('countries', zone.countries)
        zone.regions = data.get('regions', zone.regions)
        zone.postcode_patterns = data.get('postcode_patterns', zone.postcode_patterns)
        zone.is_active = data.get('is_active', zone.is_active)
        zone.display_order = data.get('display_order', zone.display_order)
        zone.show_in_checkout = data.get('show_in_checkout', zone.show_in_checkout)
        zone.show_estimated_delivery = data.get('show_estimated_delivery', zone.show_estimated_delivery)
        zone.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_shipping_zone(request, subdomain, zone_id):
    """Delete shipping zone"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    zone = get_object_or_404(ShippingZone, id=zone_id, page=page)
    
    try:
        zone.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def add_shipping_rate(request, subdomain, zone_id):
    """Add a new shipping rate to zone"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    zone = get_object_or_404(ShippingZone, id=zone_id, page=page)
    
    try:
        data = json.loads(request.body)
        
        rate = ShippingRate.objects.create(
            zone=zone,
            name=data.get('name'),
            description=data.get('description', ''),
            rate_type=data.get('rate_type', 'flat'),
            price=Decimal(data.get('price', '0')),
            condition_type=data.get('condition_type', ''),
            price_tiers=data.get('price_tiers', []),
            weight_tiers=data.get('weight_tiers', []),
            free_shipping_min_price=data.get('free_shipping_min_price'),
            free_shipping_min_weight=data.get('free_shipping_min_weight'),
            delivery_min_days=int(data.get('delivery_min_days', 3)),
            delivery_max_days=int(data.get('delivery_max_days', 7)),
            carrier=data.get('carrier', ''),
            carrier_service=data.get('carrier_service', ''),
            requires_shipping=data.get('requires_shipping', True),
            is_active=data.get('is_active', True),
            display_order=data.get('display_order', 0),
            taxable=data.get('taxable', True),
        )
        
        return JsonResponse({
            'success': True,
            'rate': {
                'id': rate.id,
                'name': rate.name,
                'rate_type_display': rate.get_rate_type_display(),
                'price': str(rate.price),
                'delivery_estimate': rate.get_delivery_estimate(),
                'is_active': rate.is_active,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_shipping_rate(request, subdomain, rate_id):
    """Update shipping rate"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    rate = get_object_or_404(ShippingRate, id=rate_id, zone__page=page)
    
    try:
        data = json.loads(request.body)
        
        rate.name = data.get('name', rate.name)
        rate.description = data.get('description', rate.description)
        rate.rate_type = data.get('rate_type', rate.rate_type)
        rate.price = Decimal(data.get('price', rate.price))
        rate.condition_type = data.get('condition_type', rate.condition_type)
        rate.price_tiers = data.get('price_tiers', rate.price_tiers)
        rate.weight_tiers = data.get('weight_tiers', rate.weight_tiers)
        rate.free_shipping_min_price = data.get('free_shipping_min_price', rate.free_shipping_min_price)
        rate.free_shipping_min_weight = data.get('free_shipping_min_weight', rate.free_shipping_min_weight)
        rate.delivery_min_days = int(data.get('delivery_min_days', rate.delivery_min_days))
        rate.delivery_max_days = int(data.get('delivery_max_days', rate.delivery_max_days))
        rate.carrier = data.get('carrier', rate.carrier)
        rate.carrier_service = data.get('carrier_service', rate.carrier_service)
        rate.requires_shipping = data.get('requires_shipping', rate.requires_shipping)
        rate.is_active = data.get('is_active', rate.is_active)
        rate.display_order = data.get('display_order', rate.display_order)
        rate.taxable = data.get('taxable', rate.taxable)
        rate.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_shipping_rate(request, subdomain, rate_id):
    """Delete shipping rate"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    rate = get_object_or_404(ShippingRate, id=rate_id, zone__page=page)
    
    try:
        rate.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def calculate_product_shipping(product, quantity, cart_total):
    """Calculate shipping for a single product based on its settings"""
    # ========== CRITICAL: Check if custom shipping is enabled ==========
    if not product.use_custom_shipping:
        print(f'⚠️ Product "{product.title}" has custom shipping DISABLED - using store shipping')
        return 0  # Return 0 because this product will use store shipping instead
    
    # Convert to float for safety
    cart_total = float(cart_total)
    quantity = int(quantity)
    
    print(f'🔍 Calculating product shipping for "{product.title}":')
    print(f'   Type: {product.custom_shipping_type}')
    print(f'   Price: ${product.custom_shipping_price}')
    print(f'   Quantity: {quantity}')
    print(f'   Cart Total: ${cart_total}')
    
    if product.custom_shipping_type == 'free':
        # Check free shipping threshold
        if product.custom_free_shipping_min_price and cart_total >= float(product.custom_free_shipping_min_price):
            print(f'   ✅ Free shipping (min price met): 0')
            return 0
        print(f'   ✅ Free shipping: 0')
        return 0
    
    elif product.custom_shipping_type == 'flat':
        shipping = float(product.custom_shipping_price)
        print(f'   ✅ Flat rate: ${shipping}')
        return shipping
    
    elif product.custom_shipping_type == 'per_item':
        per_item = float(product.shipping_per_item or product.custom_shipping_price)
        shipping = per_item * quantity
        print(f'   ✅ Per item (${per_item} x {quantity}): ${shipping}')
        return shipping
    
    elif product.custom_shipping_type == 'calculated':
        # Simple calculated: price per item times quantity
        shipping = float(product.custom_shipping_price) * quantity
        print(f'   ✅ Calculated (${product.custom_shipping_price} x {quantity}): ${shipping}')
        return shipping
    
    print(f'   ⚠️ No matching shipping type, returning 0')
    return 0

def get_shipping_rates(request, subdomain):
    """API endpoint to get available shipping rates for checkout"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
    # Check if this is an instant checkout (product) or cart checkout
    is_instant = request.GET.get('type') == 'instant'
    product_data = request.GET.get('product')
    
    cart_total = 0
    total_weight = 0
    items = []
    
    # Track custom shipping items
    custom_shipping_items = []
    custom_shipping_total = 0
    
    # Track items that need store shipping
    store_shipping_items = []
    store_shipping_total_weight = 0
    store_shipping_total_price = 0
    
    if is_instant and product_data:
        # INSTANT CHECKOUT - Get product details
        try:
            product = json.loads(product_data)
            product_id = product.get('id')
            
            from builder.models import Product
            db_product = None
            if product_id:
                try:
                    db_product = Product.objects.get(id=product_id, page=page)
                except Product.DoesNotExist:
                    pass
            
            price = float(product.get('price', 0))
            quantity = int(product.get('quantity', 1))
            cart_total = price * quantity
            
            if db_product and db_product.use_custom_shipping:
                item_shipping = calculate_product_shipping(db_product, quantity, cart_total)
                custom_shipping_total += item_shipping
                custom_shipping_items.append({
                    'product_id': db_product.id,
                    'title': db_product.title,
                    'quantity': quantity,
                    'shipping_amount': item_shipping,
                    'shipping_note': db_product.shipping_note,
                    'ships_separately': db_product.ships_separately,
                    'use_custom_shipping': True
                })
                print(f'📦 Product "{db_product.title}" using CUSTOM shipping: ${item_shipping}')
            else:
                store_shipping_items.append({
                    'product_id': db_product.id if db_product else product_id,
                    'title': product.get('title', 'Product'),
                    'quantity': quantity,
                    'weight': float(product.get('weight', 0)),
                    'price': price,
                    'use_custom_shipping': False
                })
                store_shipping_total_weight += float(product.get('weight', 0)) * quantity
                store_shipping_total_price += price * quantity
                print(f'📦 Product using STORE shipping')
            
        except Exception as e:
            print(f'Error parsing product data: {e}')
            return JsonResponse({'success': True, 'rates': [], 'cart_empty': True})
    
    else:
        # CART CHECKOUT - Get cart from database
        cart = None
        if request.user.is_authenticated:
            cart = page.cart_set.filter(user=request.user).first()
        else:
            session_key = request.session.session_key
            if session_key:
                cart = page.cart_set.filter(session_key=session_key).first()
        
        if not cart or cart.items.count() == 0:
            return JsonResponse({'success': True, 'rates': [], 'cart_empty': True})
        
        cart_total = float(cart.get_total_price())
        
        for item in cart.items.all():
            weight = float(item.product.weight or 0)
            total_weight += weight * item.quantity
            
            if item.product.use_custom_shipping:
                item_shipping = calculate_product_shipping(item.product, item.quantity, cart_total)
                custom_shipping_total += item_shipping
                custom_shipping_items.append({
                    'product_id': item.product.id,
                    'title': item.product.title,
                    'quantity': item.quantity,
                    'shipping_amount': item_shipping,
                    'shipping_note': item.product.shipping_note,
                    'ships_separately': item.product.ships_separately,
                    'use_custom_shipping': True
                })
                print(f'📦 Product "{item.product.title}" using CUSTOM shipping: ${item_shipping}')
            else:
                store_shipping_items.append({
                    'product_id': item.product.id,
                    'title': item.product.title,
                    'quantity': item.quantity,
                    'weight': weight,
                    'price': float(item.product.price),
                    'use_custom_shipping': False
                })
                store_shipping_total_weight += weight * item.quantity
                store_shipping_total_price += float(item.product.price) * item.quantity
                print(f'📦 Product "{item.product.title}" using STORE shipping')
    
    # ========== GET ALL AVAILABLE STORE SHIPPING RATES ==========
    address_data = request.GET.get('address')
    address = None
    if address_data:
        try:
            address_dict = json.loads(address_data)
            class TempAddress:
                pass
            address = TempAddress()
            address.country_code = address_dict.get('country_code', '')
            address.state = address_dict.get('state', '')
            address.postal_code = address_dict.get('postal_code', '')
            address.city = address_dict.get('city', '')
        except:
            pass
    
    # Get all applicable store shipping rates
    all_store_rates = []
    zones = page.shipping_zones.filter(is_active=True, show_in_checkout=True)
    
    for zone in zones:
        if address and not zone.matches_address(address):
            continue
        
        for rate in zone.rates.filter(is_active=True):
            # For store items only
            if store_shipping_items:
                price = rate.calculate_price(store_shipping_total_price, store_shipping_total_weight)
                if price is not None and price >= 0:
                    all_store_rates.append({
                        'id': rate.id,
                        'zone_id': zone.id,
                        'name': rate.name,
                        'description': rate.description,
                        'price': price,
                        'delivery_estimate': rate.get_delivery_estimate(),
                        'carrier': rate.carrier,
                        'taxable': rate.taxable,
                    })
                    print(f'   ✅ Store rate "{rate.name}" applies: ${price}')
            else:
                # No store items, still get rates for potential combination
                price = rate.calculate_price(cart_total, total_weight)
                if price is not None and price >= 0:
                    all_store_rates.append({
                        'id': rate.id,
                        'zone_id': zone.id,
                        'name': rate.name,
                        'description': rate.description,
                        'price': price,
                        'delivery_estimate': rate.get_delivery_estimate(),
                        'carrier': rate.carrier,
                        'taxable': rate.taxable,
                    })
    
    # Sort store rates by price
    all_store_rates.sort(key=lambda x: x['price'])
    
    # ========== BUILD ALL COMBINATIONS ==========
    all_shipping_options = []
    
    # Case 1: Only custom shipping items
    if custom_shipping_items and not store_shipping_items:
        # Just return the custom shipping as one option
        custom_description = "\n".join([f"• {item['title']} (x{item['quantity']}): ${item['shipping_amount']}" 
                                          for item in custom_shipping_items])
        all_shipping_options.append({
            'id': 0,
            'name': 'Product Shipping',
            'description': custom_description,
            'price': custom_shipping_total,
            'delivery_estimate': 'Calculated per product',
            'type': 'custom_only',
            'custom_shipping_items': custom_shipping_items
        })
    
    # Case 2: Only store shipping items
    elif store_shipping_items and not custom_shipping_items:
        for rate in all_store_rates:
            all_shipping_options.append({
                'id': rate['id'],
                'name': rate['name'],
                'description': rate.get('description', ''),
                'price': rate['price'],
                'delivery_estimate': rate.get('delivery_estimate', ''),
                'carrier': rate.get('carrier', ''),
                'taxable': rate.get('taxable', True),
                'type': 'store_only'
            })
    
    # Case 3: Mixed cart - custom + store items
    elif custom_shipping_items and store_shipping_items:
        print(f'🎯 MIXED CART: {len(custom_shipping_items)} custom items + {len(store_shipping_items)} store items')
        
        # Option A: Custom shipping for custom items + Free shipping for store items
        if custom_shipping_total > 0:
            all_shipping_options.append({
                'id': 0,
                'name': 'Mixed Shipping (Custom + Free Store)',
                'description': f"Custom items: ${custom_shipping_total}\nStore items: Free",
                'price': custom_shipping_total,
                'delivery_estimate': 'Mixed delivery times',
                'type': 'mixed_custom_free',
                'custom_shipping_items': custom_shipping_items,
                'store_shipping_items': store_shipping_items,
                'store_shipping_used': 'free'
            })
        
        # Option B: Custom shipping for custom items + Each store rate option
        for store_rate in all_store_rates:
            total_price = custom_shipping_total + store_rate['price']
            all_shipping_options.append({
                'id': store_rate['id'],
                'name': f"Mixed Shipping (Custom + {store_rate['name']})",
                'description': f"Custom items: ${custom_shipping_total}\nStore items: ${store_rate['price']} - {store_rate.get('description', store_rate['name'])}",
                'price': total_price,
                'delivery_estimate': store_rate.get('delivery_estimate', ''),
                'type': 'mixed_custom_store',
                'custom_shipping_items': custom_shipping_items,
                'store_rate': store_rate
            })
    
    # Case 4: No custom shipping and no store rates (fallback)
    if not all_shipping_options:
        # Check if any zones exist at all
        zones_exist = page.shipping_zones.filter(is_active=True).exists()
        
        if not zones_exist:
            all_shipping_options.append({
                'id': 0,
                'name': 'Free Shipping',
                'description': 'No shipping rates configured. Free shipping applied.',
                'price': 0,
                'delivery_estimate': 'Contact store for delivery estimate',
                'type': 'fallback',
                'is_fallback': True
            })
        else:
            all_shipping_options.append({
                'id': 0,
                'name': 'Contact Store for Shipping',
                'description': f'No applicable shipping rates found. Please contact the store for shipping options.',
                'price': 0,
                'delivery_estimate': 'Contact store',
                'type': 'fallback',
                'is_fallback': True
            })
    
    # Sort options by price
    all_shipping_options.sort(key=lambda x: x['price'])
    
    return JsonResponse({
        'success': True,
        'rates': all_shipping_options,
        'has_custom_shipping': bool(custom_shipping_items),
        'has_store_shipping': bool(store_shipping_items),
        'is_mixed': bool(custom_shipping_items and store_shipping_items),
        'custom_shipping_total': custom_shipping_total,
        'store_rates_available': len(all_store_rates)
    })

@login_required
def manage_shipping_addresses(request, subdomain):
    """Manage saved shipping addresses"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    addresses = ShippingAddress.objects.filter(
        page=page,
        user=request.user,
        address_type__in=['shipping', 'both']
    )
    
    context = {
        'page': page,
        'addresses': addresses,
    }
    return render(request, 'payments/shipping/manage_addresses.html', context)


@login_required
@require_http_methods(["POST"])
def add_shipping_address(request, subdomain):
    """Add a new shipping address (AJAX)"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    try:
        data = json.loads(request.body)
        
        address = ShippingAddress.objects.create(
            page=page,
            user=request.user,
            full_name=data.get('full_name'),
            company=data.get('company', ''),
            address_line1=data.get('address_line1'),
            address_line2=data.get('address_line2', ''),
            city=data.get('city'),
            state=data.get('state', ''),
            postal_code=data.get('postal_code'),
            country_code=data.get('country_code'),
            phone=data.get('phone', ''),
            email=data.get('email', ''),
            address_type=data.get('address_type', 'shipping'),
            is_default=data.get('is_default', False),
        )
        
        return JsonResponse({
            'success': True,
            'address': {
                'id': address.id,
                'full_name': address.full_name,
                'full_address': address.get_full_address(),
                'phone': address.phone,
                'is_default': address.is_default,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_shipping_address(request, subdomain, address_id):
    """Update shipping address"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    address = get_object_or_404(ShippingAddress, id=address_id, page=page, user=request.user)
    
    try:
        data = json.loads(request.body)
        
        address.full_name = data.get('full_name', address.full_name)
        address.company = data.get('company', address.company)
        address.address_line1 = data.get('address_line1', address.address_line1)
        address.address_line2 = data.get('address_line2', address.address_line2)
        address.city = data.get('city', address.city)
        address.state = data.get('state', address.state)
        address.postal_code = data.get('postal_code', address.postal_code)
        address.country_code = data.get('country_code', address.country_code)
        address.phone = data.get('phone', address.phone)
        address.email = data.get('email', address.email)
        address.address_type = data.get('address_type', address.address_type)
        
        if data.get('is_default', False):
            address.is_default = True
        
        address.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_shipping_address(request, subdomain, address_id):
    """Delete shipping address"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    address = get_object_or_404(ShippingAddress, id=address_id, page=page, user=request.user)
    
    try:
        address.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@login_required
@require_http_methods(["GET"])
def get_shipping_rate_details(request, subdomain, rate_id):
    """Get detailed shipping rate information including tiers"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    rate = get_object_or_404(ShippingRate, id=rate_id, zone__page=page)
    
    return JsonResponse({
        'success': True,
        'rate': {
            'id': rate.id,
            'name': rate.name,
            'description': rate.description,
            'rate_type': rate.rate_type,
            'price': str(rate.price),
            'condition_type': rate.condition_type,
            'price_tiers': rate.price_tiers,
            'weight_tiers': rate.weight_tiers,
            'free_shipping_min_price': str(rate.free_shipping_min_price) if rate.free_shipping_min_price else None,
            'free_shipping_min_weight': str(rate.free_shipping_min_weight) if rate.free_shipping_min_weight else None,
            'delivery_min_days': rate.delivery_min_days,
            'delivery_max_days': rate.delivery_max_days,
            'carrier': rate.carrier,
            'requires_shipping': rate.requires_shipping,
            'is_active': rate.is_active,
            'taxable': rate.taxable,
        }
    })










# payments/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.db import transaction

from .models import Plan, Subscription
from .decorators import get_user_subscription


# payments/views.py - Update the pricing_page function

# payments/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Plan, Subscription
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
import uuid


PLANS = {
    'pro': {
        'name': 'Pro',
        'description': 'For growing businesses ready to scale',
        'monthly': 12,
        'yearly': 108,
        # Add limits for display if needed
        'websites': 1,
        'products': 250,
        'storage': '1GB',
        'forms': 250,
    },
    'business': {
        'name': 'Business',
        'description': 'For established businesses with higher demands',
        'monthly': 29,
        'yearly': 261,
        # Add limits for display if needed
        'websites': 3,
        'products': 2000,
        'storage': '10GB',
        'forms': 2500,
    },
    'agency': {
        'name': 'Agency',
        'description': 'For agencies and high-volume businesses',
        'monthly': 79,
        'yearly': 711,
        # Add limits for display if needed
        'websites': 'Unlimited',
        'products': 'Unlimited',
        'storage': '100GB',
        'forms': 'Unlimited',
    },
}

# Your contact info - change here
WHATSAPP_NUMBER = '+237680044151'
TELEGRAM_USERNAME = 'MJerase'
SUPPORT_EMAIL = 'bynupteam@protonmail.com'


def pricing_page(request):
    """Pricing page - no database queries"""
    current_tier = 'free'
    if request.user.is_authenticated:
        from payments.decorators import get_user_plan
        plan = get_user_plan(request.user)
        current_tier = plan.tier if plan else 'free'
    
    return render(request, 'subscriptions/pricing.html', {'current_tier': current_tier})

@login_required
@login_required
def upgrade_to_plan(request, tier):
    """Upgrade to selected plan"""
    if tier not in PLANS:
        messages.error(request, "Invalid plan selected.")
        return redirect('payments:pricing')
    
    plan = PLANS[tier]
    billing_period = request.GET.get('period', 'monthly')
    amount = plan['monthly'] if billing_period == 'monthly' else plan['yearly']
    
    # Check if user already on this plan
    from payments.decorators import get_user_subscription
    subscription = get_user_subscription(request.user)
    if subscription.plan and subscription.plan.tier == tier and subscription.is_active:
        messages.info(request, f"You're already on the {plan['name']} plan!")
        return redirect('payments:pricing')
    
    context = {
        'plan_name': plan['name'],
        'plan_tier': tier,
        'plan_description': plan['description'],
        'amount': amount,
        'billing_period': billing_period,
        'user_name': request.user.get_full_name() or request.user.username,
        'user_email': request.user.email,
    }
    
    return render(request, 'subscriptions/upgrade.html', context)

# payments/views.py - Find submit_payment and fix it

@login_required
def submit_payment(request, tier):
    """User submits payment intent - creates pending subscription"""
    if request.method != 'POST':
        return redirect('payments:pricing')
    
    from payments.models import Subscription, Plan
    from payments.decorators import get_user_subscription
    import uuid
    
    plan = get_object_or_404(Plan, tier=tier, is_active=True)
    subscription = get_user_subscription(request.user)
    
    billing_period = request.POST.get('billing_period', 'monthly')
    payment_method = request.POST.get('payment_method', 'Bank Transfer')
    payment_reference = request.POST.get('payment_reference', '')
    payment_notes = request.POST.get('payment_notes', '')
    
    amount = plan.price_monthly if billing_period == 'monthly' else plan.price_yearly
    
    if not payment_reference:
        payment_reference = f"BYN-{uuid.uuid4().hex[:8].upper()}"
    
    # Only update if NOT already on an active plan
    # This prevents canceling existing active subscriptions
    if subscription.status not in ['active']:
        subscription.plan = plan
        subscription.billing_period = billing_period
        subscription.status = 'pending'
        subscription.amount_paid = amount
        subscription.payment_method = payment_method
        subscription.payment_reference = payment_reference
        subscription.payment_notes = payment_notes
        subscription.save()
    
    messages.success(
        request, 
        f"Thank you! Your upgrade to {plan.name} is pending verification. "
        f"Reference: {payment_reference}. We'll activate your subscription once payment is confirmed."
    )
    
    return redirect('payments:subscription_detail')

def send_admin_notification(subscription):
    """Send notification to admin about new pending payment"""
    # You can implement email notification here
    print(f"""
    ========================================
    NEW PENDING SUBSCRIPTION
    ========================================
    User: {subscription.user.email}
    Plan: {subscription.plan.name}
    Amount: ${subscription.amount_paid}
    Period: {subscription.billing_period}
    Payment Method: {subscription.payment_method}
    Reference: {subscription.payment_reference}
    Notes: {subscription.payment_notes}
    ========================================
    """)


@login_required
def subscription_detail(request):
    """Show user's subscription"""
    from payments.decorators import get_user_subscription, get_user_limits_status
    
    subscription = get_user_subscription(request.user)
    limits = get_user_limits_status(request.user)
    
    context = {
        'subscription': subscription,
        'limits': limits,
    }
    return render(request, 'subscriptions/subscription_detail.html', context)


@login_required
def cancel_subscription(request):
    """Cancel subscription"""
    if request.method != 'POST':
        return redirect('payments:subscription_detail')
    
    from payments.decorators import get_user_subscription
    subscription = get_user_subscription(request.user)
    
    if subscription.status == 'active':
        subscription.status = 'canceled'
        subscription.auto_renew = False
        subscription.save()
        messages.success(request, "Subscription canceled. It will remain active until the end of your billing period.")
    
    return redirect('payments:subscription_detail')

# ============ ADMIN VIEWS ============

def is_staff(user):
    return user.is_staff


@staff_member_required
def admin_pending_payments(request):
    """Admin view to see pending payments with search"""
    from payments.models import Subscription
    from django.utils import timezone
    from datetime import timedelta
    
    search_query = request.GET.get('search', '').strip()
    
    pending = Subscription.objects.filter(status='pending').select_related('user', 'plan')
    
    if search_query:
        pending = pending.filter(
            Q(user__email__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(payment_reference__icontains=search_query)
        )
    
    pending = pending.order_by('-created_at')
    
    # Count activated today
    today = timezone.now().date()
    activated_today = Subscription.objects.filter(
        status='active',
        verified_at__date=today
    ).count()
    
    context = {
        'pending': pending,
        'search_query': search_query,
        'activated_today': activated_today,
    }
    return render(request, 'subscriptions/admin_pending.html', context)

# payments/views.py - Update admin_verify_payment

# payments/views.py - Fixed admin_verify_payment

@staff_member_required
def admin_verify_payment(request, subscription_id):
    """Admin verifies payment and activates subscription"""
    from payments.models import Subscription, Plan
    from django.utils import timezone
    from django.contrib import messages
    
    subscription = get_object_or_404(Subscription, id=subscription_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')
        
        print(f"Admin action: {action} for subscription {subscription_id}")
        
        if action == 'approve':
            # Get duration
            duration_days = request.POST.get('duration_days', '30')
            
            if duration_days == 'custom':
                duration_days = int(request.POST.get('custom_days', 30))
            else:
                duration_days = int(duration_days)
            
            # Activate subscription
            subscription.status = 'active'
            subscription.start_date = timezone.now()
            subscription.end_date = timezone.now() + timezone.timedelta(days=duration_days)
            subscription.verified_by = request.user
            subscription.verified_at = timezone.now()
            
            if admin_notes:
                existing_notes = subscription.payment_notes or ''
                subscription.payment_notes = f"{existing_notes}\n\nAdmin Notes ({timezone.now().date()}): {admin_notes}"
            
            subscription.save()
            
            print(f"Subscription {subscription_id} activated for {subscription.user.email} until {subscription.end_date}")
            
            messages.success(request, f"✅ Subscription activated for {subscription.user.email} until {subscription.end_date.date()}")
            
        elif action == 'reject':
            subscription.status = 'canceled'
            
            if admin_notes:
                existing_notes = subscription.payment_notes or ''
                subscription.payment_notes = f"{existing_notes}\n\nREJECTED ({timezone.now().date()}): {admin_notes}"
            else:
                existing_notes = subscription.payment_notes or ''
                subscription.payment_notes = f"{existing_notes}\n\nREJECTED on {timezone.now().date()}"
            
            subscription.save()
            
            print(f"Subscription {subscription_id} rejected for {subscription.user.email}")
            
            messages.warning(request, f"❌ Payment rejected for {subscription.user.email}")
            
        elif action == 'cancel_period_end':
            subscription.status = 'canceled'
            subscription.auto_renew = False
            subscription.canceled_at = timezone.now()
            
            if admin_notes:
                existing_notes = subscription.payment_notes or ''
                subscription.payment_notes = f"{existing_notes}\n\nCanceled at period end: {admin_notes}"
            
            subscription.save()
            
            messages.warning(request, f"Subscription will cancel at period end: {subscription.end_date.date()}")
            
        elif action == 'cancel_immediate':
            subscription.status = 'canceled'
            subscription.auto_renew = False
            subscription.end_date = timezone.now()
            subscription.canceled_at = timezone.now()
            
            # Revert to free plan
            free_plan = Plan.objects.filter(tier='free').first()
            if free_plan:
                subscription.plan = free_plan
            
            if admin_notes:
                existing_notes = subscription.payment_notes or ''
                subscription.payment_notes = f"{existing_notes}\n\nCanceled immediately: {admin_notes}"
            
            subscription.save()
            
            messages.warning(request, f"Subscription canceled immediately for {subscription.user.email}")
        
        return redirect('payments:admin_pending_payments')
    
    # GET request - show verification page
    context = {
        'subscription': subscription,
    }
    return render(request, 'subscriptions/admin_verify_payment.html', context)



@staff_member_required
def admin_quick_activate(request):
    """Quick activate by email search"""
    from payments.models import Subscription
    from django.contrib.auth.models import User
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        try:
            user = User.objects.get(email=email)
            subscription, created = Subscription.objects.get_or_create(
                user=user,
                defaults={'status': 'pending'}
            )
            
            if subscription.status == 'pending':
                return redirect('payments:admin_verify_payment', subscription_id=subscription.id)
            else:
                messages.info(request, f"User {email} has no pending subscription. Status: {subscription.status}")
        except User.DoesNotExist:
            messages.error(request, f"No user found with email: {email}")
    
    return render(request, 'subscriptions/admin_quick_activate.html')


@user_passes_test(is_staff)
def admin_activate_subscription(request, subscription_id):
    """Admin: Manually activate subscription"""
    from payments.models import Subscription
    from django.utils import timezone
    
    subscription = get_object_or_404(Subscription, id=subscription_id)
    
    if request.method == 'POST':
        duration_days = int(request.POST.get('duration_days', 30))
        
        subscription.status = 'active'
        subscription.start_date = timezone.now()
        subscription.end_date = timezone.now() + timezone.timedelta(days=duration_days)
        subscription.verified_by = request.user
        subscription.verified_at = timezone.now()
        subscription.save()
        
        messages.success(request, f"Subscription activated for {subscription.user.email}")
        return redirect('payments:admin_pending_payments')
    
    return render(request, 'subscriptions/admin_activate.html', {'subscription': subscription})

# ============ API ENDPOINTS ============

@login_required
def api_subscription_status(request):
    """API endpoint for subscription status"""
    subscription = get_user_subscription(request.user)
    
    return JsonResponse({
        'success': True,
        'tier': subscription.plan.tier if subscription.plan else 'free',
        'plan_name': subscription.plan.name if subscription.plan else 'Free',
        'status': subscription.status,
        'is_active': subscription.is_active,
        'days_remaining': subscription.days_remaining,
        'limits': {
            'websites': {
                'used': subscription.websites_created,
                'limit': subscription.plan.max_websites if subscription.plan else 1,
            },
            'products': {
                'used': subscription.products_added,
                'limit': subscription.plan.max_products if subscription.plan else 10,
            },
            'storage': {
                'used': subscription.storage_used_mb,
                'limit': subscription.plan.max_storage_mb if subscription.plan else 100,
            },
        }
    })



# payments/views.py

@login_required
def cancel_subscription(request):
    """Cancel user's subscription"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    from payments.decorators import get_user_subscription
    from payments.models import Subscription
    
    subscription = get_user_subscription(request.user)
    
    if subscription.status != 'active':
        return JsonResponse({'success': False, 'error': 'No active subscription to cancel'})
    
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '')
        
        # Mark as canceled (will expire at period end)
        subscription.status = 'canceled'
        subscription.auto_renew = False
        subscription.canceled_at = timezone.now()
        
        # Store cancellation reason
        if reason:
            subscription.payment_notes = f"{subscription.payment_notes}\n\nCancellation reason: {reason}"
        
        subscription.save()
        
        # Log the cancellation
        print(f"Subscription canceled for {request.user.email}. Reason: {reason}")
        
        return JsonResponse({
            'success': True, 
            'message': 'Subscription canceled successfully. It will remain active until the end of your billing period.'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def reactivate_subscription(request):
    """Reactivate a canceled subscription before it expires"""
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)
    
    from payments.decorators import get_user_subscription
    
    subscription = get_user_subscription(request.user)
    
    if subscription.status == 'canceled' and subscription.end_date and subscription.end_date > timezone.now():
        subscription.status = 'active'
        subscription.auto_renew = True
        subscription.canceled_at = None
        subscription.save()
        
        return JsonResponse({'success': True, 'message': 'Subscription reactivated!'})
    
    return JsonResponse({'success': False, 'error': 'Cannot reactivate subscription'})


    # payments/views.py

@staff_member_required
def admin_subscriptions(request):
    """Admin view to manage all subscriptions"""
    from payments.models import Subscription
    
    status = request.GET.get('status', 'active')
    search_query = request.GET.get('search', '').strip()
    
    subscriptions = Subscription.objects.select_related('user', 'plan')
    
    if status:
        subscriptions = subscriptions.filter(status=status)
    
    if search_query:
        subscriptions = subscriptions.filter(user__email__icontains=search_query)
    
    subscriptions = subscriptions.order_by('-created_at')
    
    context = {
        'subscriptions': subscriptions,
        'current_status': status,
        'search_query': search_query,
    }
    return render(request, 'subscriptions/admin_subscriptions.html', context)

    # payments/views.py

@login_required
def downgrade_subscription(request):
    """Schedule a downgrade at period end"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    from payments.decorators import get_user_subscription
    from payments.models import Plan
    
    subscription = get_user_subscription(request.user)
    
    if subscription.status != 'active':
        return JsonResponse({'success': False, 'error': 'No active subscription'})
    
    try:
        data = json.loads(request.body)
        target_tier = data.get('tier')
        
        # Validate tier is lower than current
        tier_levels = {'free': 0, 'pro': 1, 'business': 2, 'agency': 3}
        current_level = tier_levels.get(subscription.plan.tier, 0)
        target_level = tier_levels.get(target_tier, 0)
        
        if target_level >= current_level:
            return JsonResponse({'success': False, 'error': 'Cannot downgrade to same or higher tier'})
        
        # Get target plan
        target_plan = Plan.objects.get(tier=target_tier, is_active=True)
        
        # Schedule downgrade (store in metadata)
        subscription.downgrade_to = target_plan
        subscription.downgrade_scheduled = True
        subscription.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Your plan will downgrade to {target_plan.name} on {subscription.end_date.date()}'
        })
        
    except Plan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid plan'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# payments/views.py - Add this view

@login_required
def upgrade_from_detail(request):
    """Handle upgrade from subscription detail page"""
    if request.method != 'POST':
        return redirect('payments:pricing')
    
    from payments.decorators import get_user_subscription
    from payments.models import Plan
    
    subscription = get_user_subscription(request.user)
    target_tier = request.POST.get('tier')
    
    if not target_tier:
        messages.error(request, "Please select a plan")
        return redirect('payments:subscription_detail')
    
    # Validate upgrade
    tier_levels = {'free': 0, 'pro': 1, 'business': 2, 'agency': 3}
    current_level = tier_levels.get(subscription.plan.tier, 0) if subscription.plan else 0
    target_level = tier_levels.get(target_tier, 0)
    
    if target_level <= current_level:
        messages.error(request, "Please select a higher plan to upgrade")
        return redirect('payments:subscription_detail')
    
    # Redirect to upgrade page
    return redirect('payments:upgrade', tier=target_tier)



# payments/views.py

from payments.services.cryptomus import CryptomusService
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


# payments/views.py - Find the cryptomus_checkout view and replace it

@login_required
def cryptomus_checkout(request, tier, billing_period='monthly'):
    """
    Create Cryptomus payment and redirect user.
    Does NOT change current subscription until payment is confirmed.
    """
    from payments.models import Plan, PaymentTransaction
    import uuid
    
    plan = get_object_or_404(Plan, tier=tier, is_active=True)
    amount = plan.price_monthly if billing_period == 'monthly' else plan.price_yearly
    order_id = f"SUB-{request.user.id}-{uuid.uuid4().hex[:8].upper()}"
    
    # Create payment transaction ONLY - don't touch subscription
    transaction = PaymentTransaction.objects.create(
        user=request.user,
        plan=plan,
        transaction_id=order_id,
        amount=amount,
        currency='USD',
        billing_period=billing_period,
        status='pending',
        gateway_type='cryptomus',
        metadata={
            'target_plan_tier': tier,
            'billing_period': billing_period,
            'user_id': request.user.id,
        }
    )
    
    # Create Cryptomus payment
    cryptomus = CryptomusService()
    result = cryptomus.create_payment(
        amount=amount,
        order_id=order_id,
        currency='USDT',
        success_url=f"{settings.SITE_URL}/payments/success/",
        cancel_url=f"{settings.SITE_URL}/payments/pricing/",
    )
    
    if result.get('success'):
        transaction.status = 'processing'
        transaction.gateway_transaction_id = result['payment_uuid']
        transaction.gateway_response = result
        transaction.save()
        return redirect(result['payment_url'])
    else:
        transaction.status = 'failed'
        transaction.error_message = result.get('error', 'Payment creation failed')
        transaction.save()
        messages.error(request, f"Payment creation failed: {result.get('error')}")
        return redirect('payments:pricing')

# payments/views.py

@csrf_exempt
@require_http_methods(["POST"])
def cryptomus_webhook(request):
    """Handle Cryptomus webhook - uses sign from webhook body [citation:7]"""
    try:
        webhook_data = json.loads(request.body)
        
        logger.info(f"Webhook received: {webhook_data.get('order_id')}")
        logger.debug(f"Webhook data: {json.dumps(webhook_data, indent=2)}")
        
        cryptomus = CryptomusService()
        result = cryptomus.process_webhook(webhook_data)
        
        if result.get('success'):
            if result.get('subscription_activated'):
                logger.info("✅ Subscription activated via webhook!")
            return JsonResponse({'status': 'OK'})
        else:
            logger.error(f"Webhook failed: {result.get('error')}")
            return JsonResponse({'status': 'error'}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Webhook exception: {e}", exc_info=True)
        return JsonResponse({'status': 'error'}, status=500)

        

@login_required
def cryptomus_payment_status(request, transaction_id):
    """Check payment status"""
    from payments.models import PaymentTransaction
    
    transaction = get_object_or_404(
        PaymentTransaction, 
        transaction_id=transaction_id,
        user=request.user
    )
    
    return JsonResponse({
        'success': True,
        'status': transaction.status,
        'amount': str(transaction.amount),
        'currency': transaction.currency,
        'completed': transaction.status == 'completed',
    })










# payments/views.py - Add this new view

@csrf_exempt
def create_chat_order(request, subdomain):
    """Create order for chat payment without processing payment"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
        data = json.loads(request.body)
        
        order_data = data.get('order_data', {})
        customer_info = data.get('customer', {})
        
        # Merge customer info into order_data
        if customer_info:
            order_data['customer'] = customer_info
        
        # Create order - pass the order_data directly
        order = create_order_from_cart(page, order_data)
        
        # Store order number in session
        request.session['last_order_number'] = order.order_number
        
        return JsonResponse({
            'success': True,
            'order_number': order.order_number,
            'order_id': order.id
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})
    
