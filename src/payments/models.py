from django.utils import timezone
import uuid
from django.db import models
from django.contrib.auth.models import User
from builder.models import PublishedPage
from django.core.exceptions import ValidationError
import json

from django.core.exceptions import ImproperlyConfigured
from django.core.signing import Signer, BadSignature
from django.conf import settings
from django.core.validators import MinValueValidator
import json

# SIMPLE ENCRYPTION HELPERS - REPLACE ALL OLD ENCRYPTION CODE WITH THIS
# def encrypt_value(value):
#     """Encrypt a string value using Django's signing"""
#     if not value:
#         return value
#     signer = Signer()
#     return signer.sign(value)

# def decrypt_value(encrypted_value):
#     """Decrypt a string value"""
#     if not encrypted_value:
#         return encrypted_value
#     try:
#         signer = Signer()
#         return signer.unsign(encrypted_value)
#     except BadSignature:
#         return ''
    
# class EncryptedField(models.CharField):
#     """Simple encrypted field using Django's signing"""
    
#     def init(self, *args, **kwargs):
#         kwargs['max_length'] = 500  # Increased length for signed data
#         super().init(*args, **kwargs)
    
#     def from_db_value(self, value, expression, connection):
#         if value is None:
#             return value
#         return decrypt_value(value)
    
#     def to_python(self, value):
#         if value is None:
#             return value
#         if isinstance(value, str) and ':' in value and ':' in value.split(':')[1]:
#             # Already encrypted format
#             return decrypt_value(value)
#         return value
    
#     def get_prep_value(self, value):
#         if value is None:
#             return value
#         return encrypt_value(value)

import base64
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from cryptography.fernet import Fernet, InvalidToken

# --- ENCRYPTION ENGINE ---

import base64
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

class EncryptionService:
    @staticmethod
    def get_fernet():
        key = settings.SECRET_KEY[:32].encode().ljust(32)
        return Fernet(base64.urlsafe_b64encode(key))

    @classmethod
    def encrypt(cls, value):
        if not value or not isinstance(value, str) or value.startswith('$enc$'):
            return value
        f = cls.get_fernet()
        return f"$enc${f.encrypt(value.encode()).decode()}"

    @classmethod
    def decrypt(cls, value):
        if not value or not isinstance(value, str):
            return value
        
        # Determine if it's our encrypted format
        if value.startswith('$enc$'):
            token = value[5:]
        elif value.startswith('gAAAA'):
            token = value
        else:
            return value # Already plain text

        f = cls.get_fernet()
        try:
            return f.decrypt(token.encode()).decode()
        except Exception:
            return value

# 2. DEFINE FIELD SECOND
class EncryptedField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 1000)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        return EncryptionService.decrypt(value)

    # def to_python(self, value):
    #     if value is None:
    #         return value
    #     return EncryptionService.decrypt(value)

    def to_python(self, value):
        if value is None:
            return value
        # Only decrypt values that look encrypted; leave plaintext alone.
        if isinstance(value, str) and (value.startswith('$enc$') or value.startswith('gAAAA')):
            return EncryptionService.decrypt(value)
        return value
    
    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return EncryptionService.encrypt(str(value))


# --- PAYMENT MODEL ---

class PaymentGateway(models.Model):
    GATEWAY_CHOICES = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('razorpay', 'Razorpay'),
        ('fincra', 'Fincra'),
        ('cryptomus', 'Cryptomus'), 
        ('paystack', 'Paystack'),
        ('flutterwave', 'Flutterwave'),
        ('pay_on_delivery', 'Pay on Delivery'),
        ('social_media', 'Social Media'),
    ]
    
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='payment_gateways')
    gateway_type = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    is_active = models.BooleanField(default=False)
    is_test_mode = models.BooleanField(default=True)
    
    # Encrypted credentials
    test_public_key = EncryptedField(blank=True, null=True) 
    test_secret_key = EncryptedField(blank=True, null=True) 

    # PayPal-specific credentials
    paypal_client_id = EncryptedField(blank=True, null=True) 
    paypal_client_secret = EncryptedField(blank=True, null=True) 

    live_public_key = EncryptedField(blank=True, null=True)  #stripe
    live_secret_key = EncryptedField(blank=True, null=True)     #stripe
    
    # PayPal live credentials
    paypal_live_client_id = EncryptedField(blank=True, null=True) 
    paypal_live_client_secret = EncryptedField(blank=True, null=True) 

    # RAZORPAY FIELDS
    razorpay_key_id = EncryptedField(blank=True, null=True)       # Test/Live key_id
    razorpay_key_secret = EncryptedField(blank=True, null=True)   # Test/Live key_secret
    razorpay_webhook_secret = EncryptedField(blank=True, null=True) 

     # FINCRA FIELDS
    fincra_api_key = EncryptedField(blank=True, null=True)            # Fincra API Key
    fincra_secret_key = EncryptedField(blank=True, null=True)         # Fincra Secret Key
    fincra_business_id = EncryptedField(blank=True, null=True)        # Fincra Business ID
    fincra_subaccount_id = EncryptedField(blank=True, null=True)      # Optional: Subaccount ID

    # Pay on Delivery specific fields
    pod_minimum_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Minimum order amount for Pay on Delivery"
    )
    pod_maximum_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=500,
        help_text="Maximum order amount for Pay on Delivery"
    )
    pod_available_zones = models.JSONField(
        default=list,
        blank=True, null=True, 
        help_text="List of delivery zones where Pay on Delivery is available"
    )
    pod_instructions = models.TextField(
        blank=True, null=True, 
        help_text="Instructions for Pay on Delivery customers"
    )
    pod_requires_confirmation = models.BooleanField(
        default=True,
        help_text="Require admin confirmation before processing Pay on Delivery orders"
    )

    cryptomus_api_key = EncryptedField(blank=True, null=True)
    cryptomus_merchant_uuid = EncryptedField(blank=True, null=True)
    cryptomus_webhook_secret = EncryptedField(blank=True, null=True)

    # NEW: Social Media Gateway Fields
    social_media_platforms = models.JSONField(
        default=list,
        blank=True,
        help_text="List of enabled social media platforms"
    )
    
    # WhatsApp specific
    whatsapp_number = models.CharField(max_length=50, blank=True, null=True)
    whatsapp_business_name = models.CharField(max_length=100, blank=True, null=True)
    
    # Facebook Messenger
    facebook_page_id = models.CharField(max_length=100, blank=True, null=True)
    facebook_messenger_link = models.URLField(blank=True, null=True)
    facebook_username = models.CharField(max_length=100, blank=True, null=True)
    
    # Instagram
    instagram_username = models.CharField(max_length=100, blank=True, null=True)
    instagram_business_account = models.CharField(max_length=100, blank=True, null=True)
    
    # Telegram
    telegram_username = models.CharField(max_length=100, blank=True, null=True)
    telegram_bot_token = EncryptedField(blank=True, null=True)  # Optional for bot integration
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    
    # X.com (Twitter)
    x_username = models.CharField(max_length=100, blank=True, null=True)
    x_dm_link = models.URLField(blank=True, null=True)  # Direct message link
    
    # General social media settings
    social_media_order_prefix = models.CharField(
        max_length=20,
        default='SOC-',
        help_text="Prefix for social media order numbers"
    )
    social_media_auto_send = models.BooleanField(
        default=True,
        help_text="Automatically send order details to social media"
    )
    social_media_message_template = models.TextField(
        blank=True,
        null=True,
        help_text="Custom message template for social media orders"
    )

    # Webhook configuration
    # webhook_secret = EncryptedField(models.CharField(max_length=200, blank=True, null=True) )
    webhook_secret = EncryptedField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['page', 'gateway_type']
        verbose_name = "Payment Gateway"
        verbose_name_plural = "Payment Gateways"

    def __str__(self):
        return f"{self.page.brand_name} - {self.get_gateway_type_display()}"
    #  CRYPTOMUS METHODS
    def get_cryptomus_api_key(self):
        """Get Cryptomus API Key"""
        return self.cryptomus_api_key
    
    def get_cryptomus_merchant_uuid(self):
        """Get Cryptomus Merchant UUID"""
        return self.cryptomus_merchant_uuid
    
    def get_cryptomus_webhook_secret(self):
        """Get Cryptomus webhook secret"""
        return self.cryptomus_webhook_secret
    
     #  FINCRA METHODS
    def get_fincra_api_key(self):
        """Get Fincra API Key"""
        return self.fincra_api_key
    
    def get_fincra_secret_key(self):
        """Get Fincra Secret Key"""
        return self.fincra_secret_key
    
    def get_fincra_business_id(self):
        """Get Fincra Business ID"""
        return self.fincra_business_id
    
    def get_fincra_subaccount_id(self):
        """Get Fincra Subaccount ID"""
        return self.fincra_subaccount_id
    
     #  RAZORPAY METHODS
    def get_razorpay_key_id(self):
        """Get Razorpay key_id"""
        return self.razorpay_key_id
    
    def get_razorpay_key_secret(self):
        """Get Razorpay key_secret"""
        return self.razorpay_key_secret
    
    def get_razorpay_webhook_secret(self):
        """Get Razorpay webhook secret"""
        return self.razorpay_webhook_secret
    
    #paypal methods
    def get_paypal_client_id(self):
        """Get appropriate PayPal client ID based on mode"""
        if self.is_test_mode:
            return self.paypal_client_id
        return self.paypal_live_client_id
    
    def get_paypal_client_secret(self):
        """Get appropriate PayPal client secret based on mode"""
        if self.is_test_mode:
            return self.paypal_client_secret
        return self.paypal_live_client_secret
    
    # def get_secret_key(self):
    #     """Get the appropriate secret key based on mode"""
    #     if self.is_test_mode:
    #         return self.test_secret_key
    #     return self.live_secret_key
    
    
    # def get_public_key(self):
    #     """Get the appropriate public key based on mode"""
    #     if self.is_test_mode:
    #         return self.test_public_key
    #     return self.live_public_key
    
    def get_secret_key(self):
        """
        The Central Intelligence for keys. 
        Everything in your app should call this.
        """
        raw_key = self.test_secret_key if self.is_test_mode else self.live_secret_key
        
        if not raw_key:
            return None
            
        # If it's encrypted, decrypt it on the fly
        if isinstance(raw_key, str) and (raw_key.startswith('$enc$') or raw_key.startswith('gAAAA')):
            return EncryptionService.decrypt(raw_key)
            
        return raw_key

    def get_public_key(self):
        """Same logic for public keys to keep the frontend happy"""
        raw_key = self.test_public_key if self.is_test_mode else self.live_public_key
        
        if not raw_key:
            return None
            
        if isinstance(raw_key, str) and (raw_key.startswith('$enc$') or raw_key.startswith('gAAAA')):
            return EncryptionService.decrypt(raw_key)
            
        return raw_key

    # Apply this logic to other gateways too
    @property
    def decrypted_api_key(self):
        if self.api_key and self.api_key.startswith('gAAAA'):
            return EncryptionService.decrypt(self.api_key)
        return self.api_key

        
    
    
    
    
def generate_order_number():
    return f"ORD-{uuid.uuid4().hex[:8].upper()}"

class Order(models.Model):
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('pending_pod', 'Pending Pay on Delivery'), 
        ('processing', 'Processing'),
        ('ready_for_delivery', 'Ready for Delivery'),
        ('out_for_delivery', 'Out for Delivery'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed')
    ]

    PAYMENT_METHODS = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('pay_on_delivery', 'Pay on Delivery'),
        ('bank_transfer', 'Bank Transfer'),
        ('other', 'Other'),
    ]
    
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True,  default=generate_order_number)
    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    customer_address = models.TextField(blank=True)
    customer_city = models.CharField(max_length=100, blank=True)
    customer_state = models.CharField(max_length=100, blank=True)
    customer_zip = models.CharField(max_length=20, blank=True)
    # customer_name = models.CharField(max_length=100, blank=True)
    country_iso = models.CharField(max_length=100, blank=True)
    customer_country = models.CharField(max_length=100, blank=True)

    currency = models.CharField(max_length=3, default='USD') 


    # Delivery information
    delivery_address = models.TextField(blank=True)
    delivery_city = models.CharField(max_length=100, blank=True)
    delivery_state = models.CharField(max_length=100, blank=True)
    delivery_zip = models.CharField(max_length=20, blank=True)
    delivery_country = models.CharField(max_length=100, blank=True, default='US')
    delivery_notes = models.TextField(blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    delivery_time_slot = models.CharField(max_length=50, blank=True)
    vid = models.CharField(max_length=200, blank=True, null=True) #CJ VID
    
    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    shipping_method = models.CharField(max_length=100, blank=True, null=True)
    shipping_delivery_estimate = models.CharField(max_length=100, blank=True, null=True)
    shipping_carrier = models.CharField(max_length=100, blank=True, null=True)

     # Payment information
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='stripe')
    payment_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
    ], default='pending')

    # Status
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    status_history = models.JSONField(default=list, blank=True)

     # Notes
    internal_notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

     # ========== ADD CJ FIELDS HERE ==========
    cj_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    cj_fulfilled_at = models.DateTimeField(null=True, blank=True)
    cj_tracking_number = models.CharField(max_length=100, blank=True, null=True)
    cj_shipping_method = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['customer_email']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return f"Order {self.order_number} - {self.customer_email}"
    
    def save(self, *args, **kwargs):
        # Add to status history if status changed
        if self.pk:
            old_status = Order.objects.get(pk=self.pk).status
            if old_status != self.status:
                self.status_history.append({
                    'status': self.status,
                    'timestamp': timezone.now().isoformat(),
                    'note': f'Changed from {old_status} to {self.status}'
                })
        
        # Set timestamps based on status
        if self.status == 'completed' and not self.paid_at:
            self.paid_at = timezone.now()
        elif self.status == 'cancelled' and not self.cancelled_at:
            self.cancelled_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def get_status_display_class(self):
        """Return CSS class for status badge"""
        status_classes = {
            'pending': 'warning',
            'pending_pod': 'warning',
            'processing': 'info',
            'ready_for_delivery': 'primary',
            'out_for_delivery': 'primary',
            'completed': 'success',
            'cancelled': 'danger',
            'refunded': 'secondary',
            'failed': 'danger',
        }
        return status_classes.get(self.status, 'secondary')
    
    def get_payment_status_display_class(self):
        """Return CSS class for payment status badge"""
        status_classes = {
            'pending': 'warning',
            'paid': 'success',
            'partially_paid': 'info',
            'refunded': 'secondary',
            'failed': 'danger',
        }
        return status_classes.get(self.payment_status, 'secondary')
    
    def get_items_total_quantity(self):
        """Get total quantity of items in order"""
        return sum(item.quantity for item in self.items.all())
    
    def update_totals(self):
        """Update order totals from items"""
        self.subtotal = sum(item.total_price for item in self.items.all())
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_amount - self.discount_amount
        self.save()
    
    def can_cancel(self):
        """Check if order can be cancelled"""
        cancellable_statuses = ['pending', 'pending_pod', 'processing']
        return self.status in cancellable_statuses
    
    def can_refund(self):
        """Check if order can be refunded"""
        return self.status == 'completed' and self.payment_status == 'paid'
    
    def get_absolute_url(self):
        """Get absolute URL for order detail"""
        from django.urls import reverse
        return reverse('payments:order_detail', args=[self.page.subdomain, self.id])
    
     # ========== ADD CJ-RELATED PROPERTIES AND METHODS ==========
    @property
    def is_cj_fulfilled(self):
        """Check if order has been fulfilled through CJ"""
        return bool(self.cj_order_id)
    
    @property
    def has_cj_items(self):
        """Check if order contains any CJ items"""
        return self.items.filter(vid__isnull=False).exists()
    
    @property
    def all_items_have_vid(self):
        """Check if ALL items in order have CJ VIDs"""
        if not self.items.exists():
            return False
        return not self.items.filter(vid__isnull=True).exists()
    
    @property
    def cj_items_count(self):
        """Count of CJ items in order"""
        return self.items.filter(vid__isnull=False).count()
    
    @property
    def manual_items_count(self):
        """Count of manual items in order"""
        return self.items.filter(vid__isnull=True).count()
    
    def get_cj_items(self):
        """Get all CJ items in order"""
        return self.items.filter(vid__isnull=False)
    
    def get_manual_items(self):
        """Get all manual items in order"""
        return self.items.filter(vid__isnull=True)
    
    def update_cj_fulfillment(self, cj_order_id, tracking_number=None, shipping_method=None):
        """Update order with CJ fulfillment details"""
        self.cj_order_id = cj_order_id
        self.cj_fulfilled_at = timezone.now()
        self.cj_tracking_number = tracking_number
        self.cj_shipping_method = shipping_method
        self.status = 'fulfilled'  # Or 'processing' if you prefer
        self.save()
    
    def can_fulfill_cj(self):
        """Check if order can be fulfilled through CJ"""
        # Conditions:
        # 1. Not already fulfilled through CJ
        # 2. All items have VIDs
        # 3. Order is in a state that allows fulfillment
        return (
            not self.is_cj_fulfilled and
            self.all_items_have_vid and
            self.status in ['pending', 'pending_pod', 'processing']
        )

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_id = models.CharField(max_length=100, blank=True)
    product_title = models.CharField(max_length=200)
    product_description = models.TextField(blank=True)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    selected_color =models.CharField(max_length=100, blank=True, null=True)
    selected_size =models.CharField(max_length=100, blank=True, null=True)

     # Variants
    product_variant = models.CharField(max_length=200, blank=True)
    product_sku = models.CharField(max_length=100, blank=True)
    product_image = models.URLField(blank=True)

    vid = models.CharField(max_length=100, blank=True, null=True) #CJ VID
    # country_iso = models.CharField(max_length=100, blank=True, null=True)
    # country_iso = models.CharField(max_length=100, blank=True, null=True)
    # country_iso = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        return f"{self.quantity} x {self.product_title}"
    
    def save(self, *args, **kwargs):
        # Calculate total price if not set
        if not self.total_price:
            self.total_price = self.product_price * self.quantity
        super().save(*args, **kwargs)

class Transaction(models.Model):
    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='transactions')
    payment_gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE)
    
    # Gateway references
    gateway_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    gateway_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Amount and currency
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Status
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    
    # Gateway response data
    gateway_response = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Transaction {self.gateway_transaction_id} - {self.status}"










# models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.auth.models import User
from builder.models import PublishedPage, Product
import uuid

class TaxClass(models.Model):
    """
    Tax classes like Standard, Reduced, Zero, etc.
    Each product can be assigned to a tax class.
    """
    CALCULATION_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='tax_classes')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    
    # Tax calculation settings
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_CHOICES, default='percentage')
    is_shipping_taxable = models.BooleanField(default=False, help_text="Apply tax to shipping costs")
    is_compound = models.BooleanField(default=False, help_text="Apply on top of other taxes")
    
    # Default settings
    is_default = models.BooleanField(default=False, help_text="Default tax class for new products")
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['page', 'slug']
        ordering = ['name']
        verbose_name = 'Tax Class'
        verbose_name_plural = 'Tax Classes'
    
    def __str__(self):
        return f"{self.name} - {self.page.brand_name}"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            # Remove default from other tax classes
            TaxClass.objects.filter(page=self.page, is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def rates_count(self):
        return self.rates.count()
    
    @property
    def active_rates_count(self):
        return self.rates.filter(is_active=True).count()


class TaxRate(models.Model):
    """
    Individual tax rates for specific jurisdictions.
    Supports nested locations (country → state → city → postal code)
    """
    JURISDICTION_CHOICES = [
        ('country', 'Country'),
        ('state', 'State/Province'),
        ('city', 'City'),
        ('postal_code', 'Postal Code'),
        ('special', 'Special Zone'),
    ]
    
    PRIORITY_CHOICES = [(i, f"Priority {i}") for i in range(10)]
    
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='tax_rates')
    tax_class = models.ForeignKey(TaxClass, on_delete=models.CASCADE, related_name='rates')
    
    # Rate identification
    name = models.CharField(max_length=100)
    rate = models.DecimalField(
        max_digits=6, 
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Tax rate percentage (e.g., 10.0000 for 10%)"
    )
    
    # Jurisdiction
    jurisdiction_type = models.CharField(max_length=20, choices=JURISDICTION_CHOICES, default='country')
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    state_code = models.CharField(max_length=10, blank=True, db_index=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    postal_code_match_pattern = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Regex pattern for postal code matching"
    )
    
    # Tax calculation rules
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=0, help_text="Lower numbers apply first")
    is_compound = models.BooleanField(default=False, help_text="Apply on top of other taxes")
    is_price_inclusive = models.BooleanField(default=False, help_text="Tax is included in product price")
    is_shipping_taxable = models.BooleanField(default=False, help_text="Apply to shipping costs")
    
    # Status
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['priority', 'country_code', 'state_code', 'city']
        indexes = [
            models.Index(fields=['country_code', 'state_code']),
            models.Index(fields=['tax_class', 'is_active']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
        verbose_name = 'Tax Rate'
        verbose_name_plural = 'Tax Rates'
    
    def __str__(self):
        location_parts = []
        if self.country_code:
            location_parts.append(self.country_code)
        if self.state_code:
            location_parts.append(self.state_code)
        if self.city:
            location_parts.append(self.city)
        
        location = ' - '.join(location_parts) if location_parts else 'Global'
        return f"{self.name}: {self.rate}% ({location})"
    
    @property
    def is_valid(self):
        now = timezone.now()
        if self.valid_until:
            return self.is_active and self.valid_from <= now <= self.valid_until
        return self.is_active and self.valid_from <= now


class TaxExemptCustomer(models.Model):
    """
    Customers exempt from paying taxes (wholesale, resellers, non-profits)
    """
    EXEMPTION_REASONS = [
        ('reseller', 'Reseller'),
        ('nonprofit', 'Non-profit Organization'),
        ('government', 'Government Entity'),
        ('wholesale', 'Wholesale Customer'),
        ('tax_exempt', 'Tax Exempt'),
        ('other', 'Other'),
    ]
    
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='tax_exempt_customers')
    email = models.EmailField(db_index=True)
    company_name = models.CharField(max_length=200, blank=True)
    tax_id = models.CharField(max_length=50, blank=True, help_text="VAT/Tax ID number")
    
    # Exemption details
    exemption_reason = models.CharField(max_length=20, choices=EXEMPTION_REASONS, blank=True)
    exempt_from = models.DateTimeField(default=timezone.now)
    exempt_until = models.DateTimeField(null=True, blank=True)
    
    # Documentation
    certificate_file = models.FileField(upload_to='tax_certificates/', null=True, blank=True)
    certificate_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    requires_review = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_exemptions')
    
    class Meta:
        unique_together = ['page', 'email']
        ordering = ['-created_at']
        verbose_name = 'Tax Exempt Customer'
        verbose_name_plural = 'Tax Exempt Customers'
    
    def __str__(self):
        return f"{self.email} - {self.get_exemption_reason_display()}"
    
    @property
    def is_currently_exempt(self):
        now = timezone.now()
        if self.exempt_until:
            return self.is_active and self.exempt_from <= now <= self.exempt_until
        return self.is_active and self.exempt_from <= now


class TaxTransaction(models.Model):
    """
    Record of tax calculations for auditing purposes
    """
    STATUS_CHOICES = [
        ('calculated', 'Calculated'),
        ('applied', 'Applied'),
        ('refunded', 'Refunded'),
        ('voided', 'Voided'),
    ]
    
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='tax_transactions', null=True, blank=True)
    transaction_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    
    # Tax details
    tax_class = models.ForeignKey(TaxClass, on_delete=models.SET_NULL, null=True)
    tax_rate = models.ForeignKey(TaxRate, on_delete=models.SET_NULL, null=True)
    
    # Calculation details
    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    rate_applied = models.DecimalField(max_digits=6, decimal_places=4)
    
    # Jurisdiction
    jurisdiction_type = models.CharField(max_length=20)
    jurisdiction_name = models.CharField(max_length=200)
    country_code = models.CharField(max_length=2, blank=True)
    state_code = models.CharField(max_length=10, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='calculated')
    
    # Metadata
    calculated_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    customer_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-calculated_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self):
        return f"Tax {self.transaction_id}: {self.tax_amount} ({self.rate_applied}%)"


class TaxReport(models.Model):
    """
    Tax reporting for specific periods
    """
    REPORT_TYPES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom'),
    ]
    
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='tax_reports')
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    
    # Date range
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Report data (JSON field for flexibility)
    report_data = models.JSONField(default=dict)
    
    # Summary totals
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax_collected = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Export
    export_file = models.FileField(upload_to='tax_reports/', null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        unique_together = ['page', 'report_type', 'start_date', 'end_date']
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.get_report_type_display()} Report: {self.start_date} to {self.end_date}"





from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.conf import settings
import json
import re


class ShippingZone(models.Model):
    """
    Shipping zones similar to Shopify - group countries/regions with similar shipping rules
    """
    ZONE_TYPES = [
        ('domestic', 'Domestic'),
        ('regional', 'Regional'),
        ('international', 'International'),
        ('custom', 'Custom'),
    ]
    
    page = models.ForeignKey('builder.PublishedPage', on_delete=models.CASCADE, related_name='shipping_zones')
    name = models.CharField(max_length=100, help_text="e.g., Domestic, International, Europe")
    description = models.TextField(blank=True, help_text="Internal description")
    zone_type = models.CharField(max_length=20, choices=ZONE_TYPES, default='custom')
    
    # Countries included (ISO 2-letter codes)
    countries = models.JSONField(default=list, help_text="List of country codes")
    
    # Regions/states (optional)
    regions = models.JSONField(default=dict, blank=True, help_text="Optional: Regions per country")
    
    # Postcode/ZIP patterns
    postcode_patterns = models.JSONField(default=list, blank=True, help_text="Regex patterns for postcodes")
    
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0, help_text="Higher number appears first")
    show_in_checkout = models.BooleanField(default=True)
    show_estimated_delivery = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-display_order', 'name']
        unique_together = ['page', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.page.brand_name})"
    
    def get_country_names(self):
        """Get list of country names"""
        # Simple country mapping
        country_names = {
            'US': 'United States', 'CA': 'Canada', 'GB': 'United Kingdom',
            'AU': 'Australia', 'DE': 'Germany', 'FR': 'France', 'IT': 'Italy',
            'ES': 'Spain', 'JP': 'Japan', 'CN': 'China', 'IN': 'India',
            'BR': 'Brazil', 'MX': 'Mexico', 'RU': 'Russia', 'KR': 'South Korea',
            'SG': 'Singapore', 'NG': 'Nigeria', 'ZA': 'South Africa', 'EG': 'Egypt',
            'KE': 'Kenya', 'GH': 'Ghana', 'CM': 'Cameroon', 'CI': 'Ivory Coast',
            'SN': 'Senegal', 'TZ': 'Tanzania', 'ET': 'Ethiopia', 'UG': 'Uganda',
            'RW': 'Rwanda', 'BI': 'Burundi', 'MG': 'Madagascar', 'MZ': 'Mozambique',
            'ZM': 'Zambia', 'ZW': 'Zimbabwe', 'BW': 'Botswana', 'NA': 'Namibia',
            'LS': 'Lesotho', 'SZ': 'Eswatini', 'MW': 'Malawi', 'AE': 'United Arab Emirates',
            'SA': 'Saudi Arabia', 'TR': 'Turkey', 'PK': 'Pakistan', 'BD': 'Bangladesh',
            'LK': 'Sri Lanka', 'NP': 'Nepal', 'MY': 'Malaysia', 'ID': 'Indonesia',
            'PH': 'Philippines', 'VN': 'Vietnam', 'TH': 'Thailand', 'IL': 'Israel',
            'NZ': 'New Zealand',
        }
        return [country_names.get(code, code) for code in self.countries]
    
    def matches_address(self, address):
        """Check if address matches this zone"""
        if address.country_code not in self.countries:
            return False
        
        if address.state and address.country_code in self.regions:
            if address.state not in self.regions[address.country_code]:
                return False
        
        if self.postcode_patterns and address.postal_code:
            matches = any(re.match(pattern, address.postal_code) for pattern in self.postcode_patterns)
            if not matches:
                return False
        
        return True


class ShippingRate(models.Model):
    """
    Individual shipping rates within a zone
    """
    RATE_TYPES = [
        ('flat', 'Flat Rate'),
        ('calculated', 'Calculated by Weight/Price'),
        ('free', 'Free Shipping'),
        ('local_pickup', 'Local Pickup'),
    ]
    
    CONDITION_TYPES = [
        ('weight', 'By Weight'),
        ('price', 'By Order Price'),
    ]
    
    zone = models.ForeignKey(ShippingZone, on_delete=models.CASCADE, related_name='rates')
    name = models.CharField(max_length=100, help_text="e.g., Standard Shipping, Express")
    description = models.TextField(blank=True, help_text="Additional details")
    rate_type = models.CharField(max_length=20, choices=RATE_TYPES, default='flat')
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Condition-based pricing
    condition_type = models.CharField(max_length=20, blank=True, choices=CONDITION_TYPES)
    
    # Tiered pricing (like Shopify)
    price_tiers = models.JSONField(default=list, blank=True, help_text="Price tiers")
    weight_tiers = models.JSONField(default=list, blank=True, help_text="Weight tiers")
    
    # Free shipping conditions
    free_shipping_min_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    free_shipping_min_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Delivery estimates
    delivery_min_days = models.IntegerField(default=3)
    delivery_max_days = models.IntegerField(default=7)
    
    # Carrier information
    carrier = models.CharField(max_length=50, blank=True)
    carrier_service = models.CharField(max_length=50, blank=True)
    
    # Additional settings
    requires_shipping = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    taxable = models.BooleanField(default=True, help_text="Apply tax to shipping")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-display_order', 'price']
    
    def __str__(self):
        return f"{self.name} - {self.get_rate_type_display()}"
    
    def calculate_price(self, cart_total, total_weight):
        """
        Calculate shipping price based on cart total and weight
        Returns the calculated price, or None if this rate doesn't apply
        """
        # Convert to float for safety
        cart_total = float(cart_total)
        total_weight = float(total_weight)
        
        print(f'🔍 calculate_price called for rate: {self.name}')
        print(f'   rate_type: {self.rate_type}')
        print(f'   cart_total: {cart_total}, total_weight: {total_weight}')
        
        # ========== LOCAL PICKUP ==========
        if self.rate_type == 'local_pickup':
            print(f'   ✅ Local pickup: 0')
            return 0
        
        # ========== FREE SHIPPING RATE TYPE ==========
        if self.rate_type == 'free':
            print(f'   ✅ Free shipping rate: 0')
            return 0
        
        # ========== CHECK FREE SHIPPING CONDITIONS ==========
        if self.free_shipping_min_price and cart_total >= float(self.free_shipping_min_price):
            print(f'   ✅ Free shipping (min price met): 0')
            return 0
        
        if self.free_shipping_min_weight and total_weight >= float(self.free_shipping_min_weight):
            print(f'   ✅ Free shipping (min weight met): 0')
            return 0
        
        # ========== FLAT RATE ==========
        if self.rate_type == 'flat':
            print(f'   ✅ Flat rate: ${self.price}')
            return float(self.price)
        
        # ========== TIERED BY PRICE ==========
        if self.condition_type == 'price' and self.price_tiers:
            # Sort tiers by min value
            tiers = sorted(self.price_tiers, key=lambda x: float(x.get('min', 0)))
            
            matched_tier = None
            
            for tier in tiers:
                min_val = float(tier.get('min', 0))
                max_val = tier.get('max')
                price = float(tier.get('price', self.price))
                
                print(f'   Checking price tier: min=${min_val}, max=${max_val}, price=${price}')
                
                # Check if cart total falls within this tier
                if cart_total >= min_val:
                    if max_val is None or cart_total <= float(max_val):
                        matched_tier = tier
                        print(f'   ✅ Matched tier: ${price}')
                        break
                else:
                    # Cart total is below the minimum of this tier
                    # This tier does NOT apply
                    print(f'   ❌ Cart total ${cart_total} is below min ${min_val}')
                    # Continue to check if there's a lower tier? No, tiers are sorted by min
                    # If we're below the first tier's min, no tier applies
                    if tier == tiers[0]:
                        print(f'   ❌ Cart total below minimum tier, rate does NOT apply')
                        return None
            
            if matched_tier:
                return float(matched_tier.get('price', self.price))
            else:
                # No tier matched - rate does NOT apply
                print(f'   ❌ No price tier matched for cart_total={cart_total}')
                return None
        
        # ========== TIERED BY WEIGHT ==========
        if self.condition_type == 'weight' and self.weight_tiers:
            # Sort tiers by min value
            tiers = sorted(self.weight_tiers, key=lambda x: float(x.get('min', 0)))
            
            matched_tier = None
            
            for tier in tiers:
                min_val = float(tier.get('min', 0))
                max_val = tier.get('max')
                price = float(tier.get('price', self.price))
                
                print(f'   Checking weight tier: min={min_val}kg, max={max_val}kg, price=${price}')
                
                # Check if weight falls within this tier
                if total_weight >= min_val:
                    if max_val is None or total_weight <= float(max_val):
                        matched_tier = tier
                        print(f'   ✅ Matched tier: ${price}')
                        break
                else:
                    # Weight is below the minimum of this tier
                    if tier == tiers[0]:
                        print(f'   ❌ Weight {total_weight}kg is below min {min_val}kg, rate does NOT apply')
                        return None
            
            if matched_tier:
                return float(matched_tier.get('price', self.price))
            else:
                print(f'   ❌ No weight tier matched for weight={total_weight}')
                return None
        
        # ========== DEFAULT FALLBACK ==========
        # If it's a calculated rate with no tiers, use base price
        if self.rate_type == 'calculated':
            print(f'   ✅ Calculated rate with no tiers, using base price: ${self.price}')
            return float(self.price)
        
        # If we get here, rate doesn't apply
        print(f'   ❌ Rate does not apply')
        return None


    def get_delivery_estimate(self):
        """Get formatted delivery estimate"""
        if self.delivery_min_days == self.delivery_max_days:
            return f"{self.delivery_min_days} business day(s)"
        return f"{self.delivery_min_days}-{self.delivery_max_days} business days"



class ShippingAddress(models.Model):
    """
    Shipping address for orders
    """
    ADDRESS_TYPES = [
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
        ('both', 'Both'),
    ]
    
    page = models.ForeignKey('builder.PublishedPage', on_delete=models.CASCADE, related_name='shipping_addresses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='shipping_addresses')
    session_key = models.CharField(max_length=100, blank=True, null=True)
    
    # Address fields
    full_name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20)
    country_code = models.CharField(max_length=2)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    address_type = models.CharField(max_length=20, default='shipping', choices=ADDRESS_TYPES)
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        return f"{self.full_name} - {self.address_line1}, {self.city}"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            ShippingAddress.objects.filter(
                page=self.page,
                user=self.user if self.user else None,
                session_key=self.session_key if not self.user else None
            ).update(is_default=False)
        super().save(*args, **kwargs)
    
    def get_full_address(self):
        """Return formatted full address"""
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        parts.append(f"{self.city}, {self.state} {self.postal_code}" if self.state else f"{self.city} {self.postal_code}")
        return ", ".join(parts)
    







# payments/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from builder.models import PublishedPage


class Plan(models.Model):
    """
    Simple subscription plans
    """
    TIERS = [
        ('free', 'Starter - Free'),
        ('pro', 'Pro - $12/mo'),
        ('business', 'Business - $29/mo'),
        ('agency', 'Agency - $79/mo'),
    ]
    
    name = models.CharField(max_length=100)
    tier = models.CharField(max_length=20, choices=TIERS, unique=True)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Limits
    max_websites = models.IntegerField(default=1, help_text="-1 for unlimited")
    max_products = models.IntegerField(default=10, help_text="-1 for unlimited")
    max_storage_mb = models.IntegerField(default=100, help_text="-1 for unlimited")
    max_visitors = models.IntegerField(default=1000, help_text="Monthly, -1 for unlimited")
    max_form_submissions = models.IntegerField(default=10, help_text="Monthly, -1 for unlimited")
    max_emails = models.IntegerField(default=0, help_text="Monthly, 0 for none")
    max_domains = models.IntegerField(
        default=0,
        help_text="Max custom domains per user account. 0 = no domains, -1 = unlimited"
    )
    free_domain_tlds = models.JSONField(
        default=list,
        blank=True,
        help_text="List of TLDs this plan can register for free. e.g. ['store'] or ['com', 'store']"
    )
    # Features
    custom_domain = models.BooleanField(default=False)
    remove_branding = models.BooleanField(default=False)
    advanced_seo = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    email_marketing = models.BooleanField(default=False)
    abandoned_cart = models.BooleanField(default=False)
    discount_codes = models.BooleanField(default=False)
    white_label = models.BooleanField(default=False)
    custom_templates = models.BooleanField(default=False)
    referral_links = models.JSONField(default=list, blank=True, null=True)
    
    # Display
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    badge = models.CharField(max_length=50, blank=True, help_text="e.g., 'Most Popular'")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['display_order', 'price_monthly']
    
    def __str__(self):
        return self.name
    
    def get_limit(self, limit_name):
        """Get limit value, returns -1 for unlimited"""
        limits = {
            'websites': self.max_websites,
            'products': self.max_products,
            'storage': self.max_storage_mb,
            'visitors': self.max_visitors,
            'form_submissions': self.max_form_submissions,
            'emails': self.max_emails,
        }
        return limits.get(limit_name, 0)
    
    def has_feature(self, feature_name):
        """Check if plan has a feature"""
        features = {
            'custom_domain': self.custom_domain,
            'remove_branding': self.remove_branding,
            'advanced_seo': self.advanced_seo,
            'priority_support': self.priority_support,
            'email_marketing': self.email_marketing,
            'abandoned_cart': self.abandoned_cart,
            'discount_codes': self.discount_codes,
            'white_label': self.white_label,
            'custom_templates': self.custom_templates,
        }
        return features.get(feature_name, False)


class Subscription(models.Model):
    """
    User's subscription - simple and clean
    """
    STATUS_CHOICES = [
        ('free', 'Free Plan'),
        ('pending', 'Payment Pending'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('canceled', 'Canceled'),
    ]
    
    BILLING_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='free')
    billing_period = models.CharField(max_length=10, choices=BILLING_CHOICES, default='monthly')
    
    # Dates
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    
    # Payment tracking
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=50, blank=True, help_text="e.g., 'Bank Transfer', 'Cash', 'Mobile Money'")
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_notes = models.TextField(blank=True)
    
    # Admin verification
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_subscriptions')
    verified_at = models.DateTimeField(null=True, blank=True)

    downgrade_to = models.ForeignKey(
        'Plan', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='scheduled_downgrades'
    )
    downgrade_scheduled = models.BooleanField(default=False)
    
    
    # Auto-renew
    auto_renew = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name if self.plan else 'Free'}"
    
    @property
    def is_active(self):
        """Check if subscription is currently active"""
        if self.status == 'active':
            if self.end_date:
                return self.end_date > timezone.now()
            return True
        return False
    
    @property
    def days_remaining(self):
        """Days until subscription expires"""
        if self.end_date and self.status == 'active':
            delta = self.end_date - timezone.now()
            return max(0, delta.days)
        return 0
    
    
    def send_activation_email(self):
        """Send email notification when subscription is activated"""
        # Implement your email logic here
        pass
    

# payments/models.py - Add this model

class PaymentTransaction(models.Model):
    """Payment transaction records"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('canceled', 'Canceled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_transactions')
    subscription = models.ForeignKey('Subscription', on_delete=models.SET_NULL, null=True, blank=True)
    plan = models.ForeignKey('Plan', on_delete=models.SET_NULL, null=True, blank=True)
    
    transaction_id = models.CharField(max_length=100, unique=True)
    gateway_type = models.CharField(max_length=50, default='cryptomus')
    gateway_transaction_id = models.CharField(max_length=200, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    billing_period = models.CharField(max_length=10, default='monthly')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    gateway_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.transaction_id} - {self.status}"
    
    def generate_transaction_id(self):
        import uuid
        return f"TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        super().save(*args, **kwargs)