from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment Gateway Management
    path('manage-gateways/<str:subdomain>/', views.manage_payment_gateways, name='manage_gateways'),
    path('configure-stripe/<str:subdomain>/', views.configure_stripe_gateway, name='configure_stripe'),
    
    # Checkout & Payments
    path('create-checkout/<str:subdomain>/', views.create_checkout_session, name='create_checkout'),
    path('checkout-success/<str:subdomain>/', views.checkout_success, name='checkout_success'),
    path('checkout-cancel/<str:subdomain>/', views.checkout_cancel, name='checkout_cancel'),
    
    # Webhooks
    path('webhook/stripe/<str:subdomain>/', views.stripe_webhook, name='stripe_webhook'),

    path('checkout/instant/<str:subdomain>/', views.create_instant_checkout, name='instant_checkout'),
    path('checkout/cart/<str:subdomain>/', views.create_cart_checkout, name='cart_checkout'),
    path('checkout/status/<str:subdomain>/<str:order_number>/', views.get_checkout_status, name='checkout_status'),
    path('select-payment/<str:subdomain>/', views.payment_selection, name='payment_selection'),
    # path('select-payment-test/<str:subdomain>/', views.payment_selection_test, name='payment_selection_test'),
    path('process-payment/<str:subdomain>/', views.process_payment_selection, name='process_payment'),

    # paypal
    path('paypal/success/<str:subdomain>/', views.paypal_success, name='paypal_success'),
    path('paypal/cancel/<str:subdomain>/', views.paypal_cancel, name='paypal_cancel'),
    path('webhook/paypal/<str:subdomain>/', views.paypal_webhook, name='paypal_webhook'),
    # Payment Gateway Configuration
    path('configure-paypal/<str:subdomain>/', views.configure_paypal_gateway, name='configure_paypal'),
    path('test-paypal-connection/<str:subdomain>/', views.test_paypal_connection, name='test_paypal_connection'),
    path('paypal/create-order/<str:subdomain>/', views.paypal_create_order_api, name='paypal_create_order'),
path('paypal/capture-order/<str:subdomain>/', views.paypal_capture_order_api, name='paypal_capture_order'),

    # Razorpay
    path('configure-razorpay/<str:subdomain>/', views.configure_razorpay_gateway, name='configure_razorpay'),
    path('verify-razorpay/<str:subdomain>/', views.verify_razorpay_payment, name='verify_razorpay'),
    path('webhook/razorpay/<str:subdomain>/', views.razorpay_webhook, name='razorpay_webhook'),

    # Fincra
    path('configure-fincra/<str:subdomain>/', views.configure_fincra_gateway, name='configure_fincra'),
    path('callback/fincra/<str:subdomain>/', views.fincra_callback, name='fincra_callback'),
    path('verify-fincra/<str:subdomain>/', views.verify_fincra_payment, name='verify_fincra'),
    path('webhook/fincra/<str:subdomain>/', views.fincra_webhook, name='fincra_webhook'),

     # Cryptomus
    path('configure-cryptomus/<str:subdomain>/', views.configure_cryptomus_gateway, name='configure_cryptomus'),
    path('callback/cryptomus/<str:subdomain>/', views.cryptomus_callback, name='cryptomus_callback'),
    path('check-cryptomus/<str:subdomain>/<str:payment_uuid>/', views.check_cryptomus_payment, name='check_cryptomus'),
    path('webhook/cryptomus/<str:subdomain>/', views.cryptomus_webhook, name='cryptomus_webhook'),
    

     # Pay on Delivery URLs
    path('configure-pod/<str:subdomain>/', views.configure_pod_gateway, name='configure_pod'),
    path('pod-success/<str:subdomain>/', views.pod_success, name='pod_success'),
    path('manage-pod-orders/<str:subdomain>/', views.manage_pod_orders, name='manage_pod_orders'),
    path('confirm-pod-payment/<str:subdomain>/<int:transaction_id>/', views.confirm_pod_payment, name='confirm_pod_payment'),
    path('cancel-pod-order/<str:subdomain>/<int:transaction_id>/', views.cancel_pod_order, name='cancel_pod_order'),
    path('api/pod-info/<str:subdomain>/', views.get_pod_info, name='get_pod_info'),

    # Social Media Payment Gateway
    path('configure-social-media/<str:subdomain>/', views.configure_social_media_gateway, name='configure_social_media'),
    path('social-media-success/<str:subdomain>/', views.social_media_success, name='social_media_success'),

     # Order Management
    path('orders/<str:subdomain>/', views.order_list, name='order_list'),
    path('orders/dashboard/<str:subdomain>/', views.order_dashboard, name='order_dashboard'),
    path('orders/detail/<str:subdomain>/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/update-status/<str:subdomain>/<int:order_id>/', views.update_order_status, name='update_order_status'),
    path('orders/update-payment-status/<str:subdomain>/<int:order_id>/', views.update_payment_status, name='update_payment_status'),
    path('orders/add-note/<str:subdomain>/<int:order_id>/', views.add_order_note, name='add_order_note'),
    path('orders/export/<str:subdomain>/', views.export_orders, name='export_orders'),
    
    # Customer-facing order pages
    path('customer/orders/<str:subdomain>/', views.customer_order_history, name='customer_order_history'),
    path('customer/orders/<str:subdomain>/<str:order_number>/', views.customer_order_detail, name='customer_order_detail'),
    
    # API endpoints
    path('api/orders/<int:order_id>/cancel/', views.cancel_order_api, name='cancel_order_api'),
    path('api/orders/<int:order_id>/refund/', views.refund_order_api, name='refund_order_api'),
    path('api/orders/<int:order_id>/resend-email/', views.refund_order_api, name='resend_order_email_api'),

     # Checkout flow
    path('checkout/customer-info/<str:subdomain>/', views.collect_customer_info, name='collect_customer_info'),
    # path('select-payment/<str:subdomain>/', views.payment_selection, name='payment_selection'),
    path('process-payment/<str:subdomain>/', views.process_payment_selection, name='process_payment'),

    # Order Management
    # path('orders/<str:subdomain>/', views.order_list, name='order_list'),
    # path('order-detail/<str:subdomain>/<int:order_id>/', views.order_detail, name='order_detail'),


     # Tax Management
    # Tax Management URLs
path('tax/<str:subdomain>/', views.tax_dashboard, name='tax_dashboard'),
path('tax/<str:subdomain>/classes/', views.tax_classes_list, name='tax_classes_list'),
path('tax/<str:subdomain>/class/create/', views.tax_class_create, name='tax_class_create'),
path('tax/<str:subdomain>/class/<int:class_id>/edit/', views.tax_class_edit, name='tax_class_edit'),
path('tax/<str:subdomain>/class/<int:class_id>/delete/', views.tax_class_delete, name='tax_class_delete'),

path('tax/<str:subdomain>/rates/', views.tax_rates_list, name='tax_rates_list'),
path('tax/<str:subdomain>/rate/create/', views.tax_rate_create, name='tax_rate_create'),
path('tax/<str:subdomain>/rate/<int:rate_id>/edit/', views.tax_rate_edit, name='tax_rate_edit'),
path('tax/<str:subdomain>/rate/<int:rate_id>/delete/', views.tax_rate_delete, name='tax_rate_delete'),
path('tax/<str:subdomain>/rate/<int:rate_id>/toggle/', views.tax_rate_toggle_status, name='tax_rate_toggle'),

path('tax/<str:subdomain>/exempt/', views.tax_exempt_customers, name='tax_exempt_customers'),
path('tax/<str:subdomain>/exempt/create/', views.tax_exempt_customer_create, name='tax_exempt_customer_create'),
path('tax/<str:subdomain>/exempt/<int:customer_id>/edit/', views.tax_exempt_customer_edit, name='tax_exempt_customer_edit'),
path('tax/<str:subdomain>/exempt/<int:customer_id>/delete/', views.tax_exempt_customer_delete, name='tax_exempt_customer_delete'),

path('tax/<str:subdomain>/reports/', views.tax_reports, name='tax_reports'),
path('tax/<str:subdomain>/settings/', views.tax_settings, name='tax_settings'),

# Quick Actions
path('tax/<str:subdomain>/apply-us-tax/', views.apply_us_sales_tax, name='apply_us_tax'),
path('tax/<str:subdomain>/apply-eu-vat/', views.apply_eu_vat, name='apply_eu_vat'),

# Import/Export
path('tax/<str:subdomain>/export/', views.export_tax_rates, name='export_tax_rates'),
path('tax/<str:subdomain>/import/', views.import_tax_rates, name='import_tax_rates'),

# Public API
path('api/tax/calculate/<str:subdomain>/', views.api_calculate_tax, name='api_calculate_tax'),
path('api/tax/validate-exemption/<str:subdomain>/', views.api_validate_tax_exemption, name='api_validate_exemption'),


# Shipping management
    path('shipping/<str:subdomain>/',views.manage_shipping, name='manage_shipping'),
    path('shipping/zone/add/<str:subdomain>/',views.add_shipping_zone, name='add_shipping_zone'),
    path('shipping/zone/update/<str:subdomain>/<int:zone_id>/',views.update_shipping_zone, name='update_shipping_zone'),
    path('shipping/zone/delete/<str:subdomain>/<int:zone_id>/',views.delete_shipping_zone, name='delete_shipping_zone'),
    
    # Shipping rates
    path('shipping/rate/add/<str:subdomain>/<int:zone_id>/',views.add_shipping_rate, name='add_shipping_rate'),
    path('shipping/rate/update/<str:subdomain>/<int:rate_id>/',views.update_shipping_rate, name='update_shipping_rate'),
    path('shipping/rate/delete/<str:subdomain>/<int:rate_id>/',views.delete_shipping_rate, name='delete_shipping_rate'),
    
    # Public API
    path('shipping/rates/<str:subdomain>/',views.get_shipping_rates, name='get_shipping_rates'),
    
    # Address management
    path('shipping/addresses/<str:subdomain>/',views.manage_shipping_addresses, name='manage_shipping_addresses'),
    path('shipping/address/add/<str:subdomain>/',views.add_shipping_address, name='add_shipping_address'),
    path('shipping/address/update/<str:subdomain>/<int:address_id>/',views.update_shipping_address, name='update_shipping_address'),
    path('shipping/address/delete/<str:subdomain>/<int:address_id>/',views.delete_shipping_address, name='delete_shipping_address'),
    path('shipping/rate/details/<str:subdomain>/<int:rate_id>/', 
         views.get_shipping_rate_details, 
         name='get_shipping_rate_details'),


     # Public pages
    path('pricing/', views.pricing_page, name='pricing'),
    path('upgrade/<str:tier>/', views.upgrade_to_plan, name='upgrade'),
    path('submit-payment/<str:tier>/', views.submit_payment, name='submit_payment'),
    
    # User pages
    path('subscription/', views.subscription_detail, name='subscription_detail'),
    path('cancel/', views.cancel_subscription, name='cancel_subscription'),
    
    # API
    path('api/status/', views.api_subscription_status, name='api_status'),
    
    # Admin pages
    path('admin/pending/', views.admin_pending_payments, name='admin_pending_payments'),
    path('admin/verify/<int:subscription_id>/', views.admin_verify_payment, name='admin_verify_payment'),
    path('admin/quick-activate/', views.admin_quick_activate, name='admin_quick_activate'), 

    # User actions
    path('cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('reactivate/', views.reactivate_subscription, name='reactivate_subscription'),
    
    # Admin actions
    path('admin/subscriptions/', views.admin_subscriptions, name='admin_subscriptions'),   

    # path('subscription/', views.subscription_detail, name='subscription_detail'),
    path('downgrade/', views.downgrade_subscription, name='downgrade_subscription'),
    path('upgrade-from-detail/', views.upgrade_from_detail, name='upgrade_from_detail'),

     # Cryptomus subscription
    path('checkout/cryptomus/<str:tier>/', views.cryptomus_checkout, name='cryptomus_checkout'),
    path('checkout/cryptomus/<str:tier>/<str:billing_period>/', views.cryptomus_checkout, name='cryptomus_checkout_period'),
    path('webhook/cryptomus/', views.cryptomus_webhook, name='cryptomus_webhook'),
    path('payment-status/<str:transaction_id>/', views.cryptomus_payment_status, name='payment_status'),


    # payments/urls.py - Add this URL

path('create-chat-order/<str:subdomain>/', views.create_chat_order, name='create_chat_order'),
]