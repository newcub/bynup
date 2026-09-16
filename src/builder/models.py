from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
from django.conf import settings
from cloudinary_storage.storage import MediaCloudinaryStorage
import re
from analytics.models import *



class TemplateCategory(models.Model):
    """Category for organizing templates"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, max_length=100)
    description = models.TextField(blank=True)
    display_order = models.IntegerField(default=0, help_text="Higher number appears first")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Template Categories"
        ordering = ['-display_order', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Template(models.Model):
    """Website templates available for selection"""
    name = models.CharField(max_length=100, unique=True)  # e.g., "ecommerce_1"
    title = models.CharField(max_length=200)  # e.g., "Modern Ecommerce"
    description = models.TextField(blank=True)
    category = models.ForeignKey(TemplateCategory, on_delete=models.CASCADE, related_name='templates')
    preview_image = models.ImageField(upload_to='template_previews/',storage=MediaCloudinaryStorage(), blank=True, null=True)
    template_file = models.CharField(max_length=100, help_text="Template filename without extension", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0, help_text="Higher number appears first")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Template features/metadata
    is_responsive = models.BooleanField(default=True)
    has_ecommerce = models.BooleanField(default=False)
    has_blog = models.BooleanField(default=False)
    has_contact_form = models.BooleanField(default=False)

          # NEW: Template type - single page vs multi-page
    template_type = models.CharField(
        max_length=20,
        choices=[
            ('single', 'Single Page'),
            ('multi', 'Multi Page'),
        ],
        default='single'
    )

    # NEW: Available pages for multi-page templates
    available_pages = models.JSONField(
        default=list,
        blank=True,
        null=True,
        help_text="List of available pages for multi-page templates. E.g.: ['home', 'products', 'about', 'contact']"
    )

    
    class Meta:
        ordering = ['-display_order', 'title']
    
    def __str__(self):
        return f"{self.title} ({self.name})"

class PublishedPage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='published_pages', null=True, blank=True)  
    template_name = models.CharField(max_length=100,blank=True, null=True)  # e.g., "ecommerce_1"
    brand_name = models.CharField(max_length=100)
    subdomain = models.SlugField(unique=True, max_length=100, help_text="This will be used as your subdomain")
    # slug = models.SlugField(unique=True, max_length=100)
    is_published = models.BooleanField(default=True)
    component_layout=models.JSONField(default=list, blank=True) #stores applied components in their order
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    contact_number = models.CharField(max_length=100, blank=True, null=True)
    # NEW: Current page for multi-page templates
    current_page = models.CharField(
        max_length=50,
        default='home',
        help_text="Current page being edited/viewed for multi-page templates"
    )
    
    # NEW: Store customizations for each page
    page_customizations = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Store component layouts and customizations for each page"
    )

    # NEW: Store the currently active color palette
    active_palette = models.ForeignKey(
        'ColorPalette',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_on_pages',
        help_text="Currently active color palette for this page"
    )
    
    # NEW: Store the applied colors (cache)
    active_palette_colors = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Cached colors from the active palette"
    )

     # ===== Currency Settings =====
    currency_code = models.CharField(
        max_length=3,
        default='USD',
        choices=[
            # Major World Currencies
            ('USD', 'US Dollar ($)'),
            ('EUR', 'Euro (€)'),
            ('GBP', 'British Pound (£)'),
            ('JPY', 'Japanese Yen (¥)'),
            ('CNY', 'Chinese Yuan (¥)'),
            
            # Americas
            ('CAD', 'Canadian Dollar (C$)'),
            ('MXN', 'Mexican Peso (MX$)'),
            ('BRL', 'Brazilian Real (R$)'),
            ('ARS', 'Argentine Peso ($)'),
            ('CLP', 'Chilean Peso (CLP$)'),
            ('COP', 'Colombian Peso (COL$)'),
            ('PEN', 'Peruvian Sol (S/)'),
            ('UYU', 'Uruguayan Peso ($U)'),
            ('PYG', 'Paraguayan Guarani (₲)'),
            ('BOB', 'Bolivian Boliviano (Bs)'),
            ('VES', 'Venezuelan Bolívar (Bs.S)'),
            ('CRC', 'Costa Rican Colón (₡)'),
            ('DOP', 'Dominican Peso (RD$)'),
            ('GTQ', 'Guatemalan Quetzal (Q)'),
            ('HNL', 'Honduran Lempira (L)'),
            ('NIO', 'Nicaraguan Córdoba (C$)'),
            ('PAB', 'Panamanian Balboa (B/.'),
            ('BSD', 'Bahamian Dollar (B$)'),
            ('BBD', 'Barbadian Dollar (Bds$)'),
            ('BZD', 'Belize Dollar (BZ$)'),
            ('BMD', 'Bermudian Dollar (BD$)'),
            ('KYD', 'Cayman Islands Dollar (CI$)'),
            ('TTD', 'Trinidad & Tobago Dollar (TT$)'),
            ('JMD', 'Jamaican Dollar (J$)'),
            ('HTG', 'Haitian Gourde (G)'),
            ('CUP', 'Cuban Peso (₱)'),
            ('AWG', 'Aruban Florin (Afl)'),
            ('ANG', 'Netherlands Antillean Guilder (ƒ)'),
            
            # Europe
            ('CHF', 'Swiss Franc (Fr)'),
            ('NOK', 'Norwegian Krone (kr)'),
            ('SEK', 'Swedish Krona (kr)'),
            ('DKK', 'Danish Krone (kr)'),
            ('ISK', 'Icelandic Króna (kr)'),
            ('RUB', 'Russian Ruble (₽)'),
            ('TRY', 'Turkish Lira (₺)'),
            ('PLN', 'Polish Złoty (zł)'),
            ('CZK', 'Czech Koruna (Kč)'),
            ('HUF', 'Hungarian Forint (Ft)'),
            ('RON', 'Romanian Leu (lei)'),
            ('BGN', 'Bulgarian Lev (лв)'),
            ('HRK', 'Croatian Kuna (kn)'),
            ('RSD', 'Serbian Dinar (дин)'),
            ('ALL', 'Albanian Lek (L)'),
            ('MKD', 'Macedonian Denar (ден)'),
            ('BAM', 'Bosnian Mark (KM)'),
            ('MDL', 'Moldovan Leu (lei)'),
            ('BYN', 'Belarusian Ruble (Br)'),
            ('UAH', 'Ukrainian Hryvnia (₴)'),
            ('GEL', 'Georgian Lari (₾)'),
            ('AMD', 'Armenian Dram (֏)'),
            ('AZN', 'Azerbaijani Manat (₼)'),
            
            # Asia Pacific
            ('AUD', 'Australian Dollar (A$)'),
            ('NZD', 'New Zealand Dollar (NZ$)'),
            ('SGD', 'Singapore Dollar (S$)'),
            ('HKD', 'Hong Kong Dollar (HK$)'),
            ('KRW', 'South Korean Won (₩)'),
            ('INR', 'Indian Rupee (₹)'),
            ('IDR', 'Indonesian Rupiah (Rp)'),
            ('MYR', 'Malaysian Ringgit (RM)'),
            ('PHP', 'Philippine Peso (₱)'),
            ('THB', 'Thai Baht (฿)'),
            ('VND', 'Vietnamese Dong (₫)'),
            ('PKR', 'Pakistani Rupee (₨)'),
            ('BDT', 'Bangladeshi Taka (৳)'),
            ('LKR', 'Sri Lankan Rupee (Rs)'),
            ('NPR', 'Nepalese Rupee (रू)'),
            ('MMK', 'Myanmar Kyat (K)'),
            ('KHR', 'Cambodian Riel (៛)'),
            ('LAK', 'Lao Kip (₭)'),
            ('MNT', 'Mongolian Tögrög (₮)'),
            ('TWD', 'New Taiwan Dollar (NT$)'),
            ('MOP', 'Macanese Pataca (MOP$)'),
            ('KZT', 'Kazakhstani Tenge (₸)'),
            ('UZS', 'Uzbekistani Som (soʻm)'),
            ('TJS', 'Tajikistani Somoni (SM)'),
            ('KGS', 'Kyrgyzstani Som (с)'),
            ('ILS', 'Israeli Shekel (₪)'),
            ('JOD', 'Jordanian Dinar (د.ا)'),
            ('IQD', 'Iraqi Dinar (ع.د)'),
            ('IRR', 'Iranian Rial (﷼)'),
            ('SAR', 'Saudi Riyal (﷼)'),
            ('AED', 'UAE Dirham (د.إ)'),
            ('QAR', 'Qatari Riyal (ر.ق)'),
            ('KWD', 'Kuwaiti Dinar (د.ك)'),
            ('BHD', 'Bahraini Dinar (د.ب)'),
            ('OMR', 'Omani Rial (ر.ع)'),
            ('YER', 'Yemeni Rial (﷼)'),
            ('LBP', 'Lebanese Pound (ل.ل)'),
            ('SYP', 'Syrian Pound (£S)'),
            ('AFN', 'Afghan Afghani (؋)'),
            
            # Africa
            ('ZAR', 'South African Rand (R)'),
            ('EGP', 'Egyptian Pound (£E)'),
            ('NGN', 'Nigerian Naira (₦)'),
            ('KES', 'Kenyan Shilling (KSh)'),
            ('GHS', 'Ghanaian Cedi (₵)'),
            ('MAD', 'Moroccan Dirham (د.م.)'),
            ('DZD', 'Algerian Dinar (د.ج)'),
            ('TND', 'Tunisian Dinar (د.ت)'),
            ('LYD', 'Libyan Dinar (ل.د)'),
            ('SDG', 'Sudanese Pound (ج.س)'),
            ('ETB', 'Ethiopian Birr (ብር)'),
            ('UGX', 'Ugandan Shilling (USh)'),
            ('TZS', 'Tanzanian Shilling (TSh)'),
            ('RWF', 'Rwandan Franc (FRw)'),
            ('BIF', 'Burundian Franc (FBu)'),
            ('CDF', 'Congolese Franc (FC)'),
            ('GNF', 'Guinean Franc (FG)'),
            ('XOF', 'West African CFA Franc (CFA)'),
            ('XAF', 'Central African CFA Franc (FCFA)'),
            ('MUR', 'Mauritian Rupee (₨)'),
            ('MGA', 'Malagasy Ariary (Ar)'),
            ('ZMW', 'Zambian Kwacha (ZK)'),
            ('MWK', 'Malawian Kwacha (MK)'),
            ('BWP', 'Botswana Pula (P)'),
            ('NAD', 'Namibian Dollar (N$)'),
            ('SZL', 'Eswatini Lilangeni (E)'),
            ('LSL', 'Lesotho Loti (L)'),
            ('ZWL', 'Zimbabwean Dollar (Z$)'),
            ('MZN', 'Mozambican Metical (MT)'),
            ('AOA', 'Angolan Kwanza (Kz)'),
            ('MRO', 'Mauritanian Ouguiya (UM)'),
            ('CVE', 'Cape Verdean Escudo ($)'),
            ('SCR', 'Seychellois Rupee (SR)'),
            ('KMF', 'Comorian Franc (CF)'),
            ('DJF', 'Djiboutian Franc (Fdj)'),
            ('ERN', 'Eritrean Nakfa (Nfk)'),
            ('SOS', 'Somali Shilling (Sh)'),
            ('GMD', 'Gambian Dalasi (D)'),
            ('SLL', 'Sierra Leonean Leone (Le)'),
            ('LRD', 'Liberian Dollar (L$)'),
            
            # Other/Oceania
            ('PGK', 'Papua New Guinean Kina (K)'),
            ('FJD', 'Fijian Dollar (FJ$)'),
            ('SBD', 'Solomon Islands Dollar (SI$)'),
            ('VUV', 'Vanuatu Vatu (Vt)'),
            ('TOP', 'Tongan Paʻanga (T$)'),
            ('WST', 'Samoan Tālā (WS$)'),
            ('KID', 'Kiribati Dollar ($)'),
            ('TVD', 'Tuvaluan Dollar ($)'),
            ('XPF', 'CFP Franc (₣)'),
            
            # Precious Metals & Special
            ('XAU', 'Gold (oz)'),
            ('XAG', 'Silver (oz)'),
            ('XPT', 'Platinum (oz)'),
            ('XPD', 'Palladium (oz)'),
            ('XDR', 'SDR (Special Drawing Rights)'),
        ],

        help_text="Store currency"
    )
    
    currency_symbol = models.CharField(
        max_length=10,
        default='$',
        help_text="Currency symbol for display"
    )
    
    currency_position = models.CharField(
        max_length=15,
        default='before',
        choices=[
            ('before', 'Before amount ($10)'),
            ('after', 'After amount (10$)'),
            ('before_space', 'Before with space ($ 10)'),
            ('after_space', 'After with space (10 $)'),
        ],
        help_text="Position of currency symbol"
    )
    
    thousand_separator = models.CharField(
        max_length=1,
        default=',',
        choices=[
            (',', 'Comma (1,000)'),
            ('.', 'Period (1.000)'),
            (' ', 'Space (1 000)'),
            ('', 'None (1000)'),
        ],
        help_text="Thousand separator"
    )
    
    decimal_separator = models.CharField(
        max_length=2,
        default='.',
        choices=[
            ('.', 'Period (10.50)'),
            (',', 'Comma (10,50)'),
        ],
        help_text="Decimal separator"
    )
    
    decimal_places = models.IntegerField(
        default=2,
        choices=[
            (0, '0 (10)'),
            (1, '1 (10.5)'),
            (2, '2 (10.50)'),
            (3, '3 (10.500)'),
        ],
        help_text="Number of decimal places"
    )
    
    # Payment gateway currency mapping
    payment_currency_mapping = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mappings for different payment gateways"
    )

    settings = models.JSONField(default=dict, blank=True)
     # Custom domain fields
    custom_domain = models.CharField(max_length=255, blank=True, null=True, unique=True, help_text="Your custom domain (e.g., mystore.com)")
    is_custom_domain_active = models.BooleanField(default=False, help_text="Enable to use custom domain instead of subdomain")
    is_live_editing = models.BooleanField(default=False)
    last_auto_save = models.DateTimeField(auto_now=True)

    def clean(self):
        # Validate subdomain
        if self.subdomain:
            if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', self.subdomain):
                raise ValidationError('Subdomain can only contain lowercase letters, numbers, and hyphens')
            if len(self.subdomain) < 2:
                raise ValidationError('Subdomain must be at least 2 characters long')

    
    # def save(self, *args, **kwargs):
    #     if not self.slug:
    #         self.slug = slugify(self.brand_name)
    #     super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        print(f"\n🔍 [PublishedPage.save] ===== SAVE CALLED =====")
        print(f"   self.id: {self.id}")
        print(f"   self.brand_name BEFORE save: '{self.brand_name}'")
        print(f"   self.subdomain BEFORE save: '{self.subdomain}'")
        
        # Check if this is a new instance
        is_new = self.pk is None
        print(f"   Is new instance: {is_new}")
        
        # Only generate subdomain if it's empty
        if not self.subdomain:
            print("   🔑 subdomain is empty - generating from brand name")
            base_subdomain = slugify(self.brand_name)
            counter = 1
            self.subdomain = base_subdomain
            
            while PublishedPage.objects.filter(subdomain=self.subdomain).exists():
                self.subdomain = f"{base_subdomain}-{counter}"
                counter += 1
            
            print(f"   Generated subdomain: '{self.subdomain}'")
        else:
            print(f"   ✅ subdomain already set: '{self.subdomain}'")
        
        # Call the original save
        result = super().save(*args, **kwargs)
        
        print(f"   ✅ Save complete!")
        print(f"   self.brand_name AFTER save: '{self.brand_name}'")
        print(f"   self.subdomain AFTER save: '{self.subdomain}'")
        print("="*60 + "\n")
        
        return result

    def get_absolute_url(self):
        """Get the absolute URL for this published page"""
        if self.is_custom_domain_active and self.custom_domain:
            return f"https://{self.custom_domain}"
        else:
            # Use the production domain from settings
            return f"https://{self.subdomain}.{settings.PRODUCTION_DOMAIN}"
    
    def get_domain_url(self):
        """Return the active domain URL"""
        from django.conf import settings
        
        if self.is_custom_domain_active and self.custom_domain:
            return f"https://{self.custom_domain}"
        else:
            return f"https://{self.subdomain}.{settings.PRODUCTION_DOMAIN.replace('https://', '')}"

    def get_dev_url(self):
        """Return development URL"""
        from django.conf import settings
        
        if settings.DEBUG:
            return f"http://{self.subdomain}.localhost:8000"
        else:
            return self.get_absolute_url()

    def __str__(self):
        return f"{self.brand_name} ({self.template_name})"

    def get_absolute_url(self):
        """Get the absolute URL for this published page"""
        from django.conf import settings
        
        if self.is_custom_domain_active and self.custom_domain:
            return f"https://{self.custom_domain}"
        else:
            if settings.DEBUG:
                return f"http://{self.subdomain}.localhost:8000"
            else:
                return f"https://{self.subdomain}.{settings.PRODUCTION_DOMAIN.replace('https://', '')}"
    

    def get_analytics_summary(self):
        """Get quick analytics summary for dashboard"""
        try:
            analytics = self.analytics
            return {
                'total_visits': analytics.total_visits,
                'unique_visitors': analytics.unique_visitors,
                'bounce_rate': analytics.bounce_rate,
                'last_updated': analytics.last_updated
            }
        except WebsiteAnalytics.DoesNotExist:
            return None
    
    def get_recent_activity(self):
        """Get recent activity for the site"""
        try:
            analytics = self.analytics
            recent_views = analytics.page_views.order_by('-timestamp')[:5]
            return [
                {
                    'timestamp': view.timestamp,
                    'page_url': view.page_url,
                    'country': view.country,
                    'device_type': view.device_type
                }
                for view in recent_views
            ]
        except WebsiteAnalytics.DoesNotExist:
            return []
        
    def get_website_users(self):
        """Get all registered users for this website"""
        return self.registered_users.filter(is_active=True)
    
    def get_website_user_count(self):
        """Get count of registered users"""
        return self.registered_users.filter(is_active=True).count()
    
    def get_color_variable(self, var_name, default=''):
        """Get a color variable value from active palette"""
        if self.active_palette_colors and var_name in self.active_palette_colors:
            color_data = self.active_palette_colors[var_name]
            if isinstance(color_data, dict):
                return color_data.get('hex', default)
            return color_data
        return default
    
    def get_color_variables_css(self):
        """Generate CSS :root variables string"""
        if not self.active_palette_colors:
            return ''

        css = []
        for var_name, color_data in self.active_palette_colors.items():
            hex_value = color_data['hex'] if isinstance(color_data, dict) else color_data
            css.append(f'  --{var_name}: {hex_value};')
            # Add RGB version if available
            if isinstance(color_data, dict) and color_data.get('rgb'):
                css.append(f'  --{var_name}-rgb: {color_data["rgb"]};')

        if css:
            # Fixed line - no backslash inside f-string
            return ':root {\n' + '\n'.join(css) + '\n}'
        return ''

    def get_currency_context(self):
        """Return currency settings for templates"""
        return {
            'code': self.currency_code,
            'symbol': self.currency_symbol,
            'position': self.currency_position,
            'thousand_sep': self.thousand_separator,
            'decimal_sep': self.decimal_separator,
            'decimal_places': self.decimal_places,
        }
    
    def format_price(self, amount):
        """Format price according to store currency settings"""
        if amount is None:
            return ''
        
        try:
            # Format number with thousand separators and decimal places
            amount_float = float(amount)
            
            # Format the number
            if self.decimal_places == 0:
                formatted = f"{int(amount_float):,}".replace(',', self.thousand_separator)
            else:
                formatted = f"{amount_float:,.{self.decimal_places}f}"
                formatted = formatted.replace(',', 'THOUSAND_SEP').replace('.', 'DECIMAL_SEP')
                formatted = formatted.replace('THOUSAND_SEP', self.thousand_separator)
                formatted = formatted.replace('DECIMAL_SEP', self.decimal_separator)
            
            # Add currency symbol based on position
            if self.currency_position == 'before':
                return f"{self.currency_symbol}{formatted}"
            elif self.currency_position == 'after':
                return f"{formatted}{self.currency_symbol}"
            elif self.currency_position == 'before_space':
                return f"{self.currency_symbol} {formatted}"
            elif self.currency_position == 'after_space':
                return f"{formatted} {self.currency_symbol}"
            else:
                return f"{self.currency_symbol}{formatted}"
                
        except (ValueError, TypeError):
            return str(amount)
    
    
class ComponentCustomization(models.Model):
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='component_customizations')
    component_instance_id = models.CharField(max_length=50)  # Unique ID for this component instance
    component_id = models.CharField(max_length=100)  # Reference to component file
    drop_zone = models.CharField(max_length=20, default='end')
    display_order = models.IntegerField(default=0)
    
    # Store all customizations (text, styles, etc.)
    customizations = models.JSONField(default=dict, blank=True)
      # NEW: Store the final rendered HTML for this component instance
    rendered_html = models.TextField(blank=True, null=True, help_text="Final HTML with customizations applied")
    
    class Meta:
        unique_together = ['page', 'component_instance_id']
        ordering = ['display_order']

# Remove old component models (Template, Component, PageComponent, etc.)
    


class TextContent(models.Model):
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='text_contents')
    element_id = models.CharField(max_length=50)  # e.g., "editable-text-1"
    content = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['page', 'element_id']
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.element_id}"

class StyleCustomization(models.Model):
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='style_customizations')
    element_id = models.CharField(max_length=9999)  # e.g., "editable-section-1"
    background_color = models.CharField(max_length=30, blank=True)  # HEX color
    text_color = models.CharField(max_length=30, blank=True)  # HEX color
    font_size = models.CharField(max_length=20, blank=True)  # e.g., "16px"
    font_family = models.CharField(max_length=100, blank=True) 
    font_weight = models.CharField(max_length=20, blank=True, null=True)  # NEW
    padding = models.CharField(max_length=50, blank=True, null=True)  # NEW
    margin = models.CharField(max_length=50, blank=True, null=True)  # NEW
    border_radius = models.CharField(max_length=50, blank=True, null=True)  # NEW
    border = models.CharField(max_length=100, blank=True, null=True)  # NEW

    display = models.CharField(max_length=20, blank=True, null=True, default='', help_text="Display property value, e.g., 'none' to hide, 'block' to show")
    
    class Meta:
        unique_together = ['page', 'element_id']
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.element_id}"
    

class ImageCustomization(models.Model):
    """Store custom images for editable-image elements"""
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='image_customizations')
    element_id = models.CharField(max_length=50)  # e.g., "1", "2", "3"
    image = models.ImageField(upload_to='custom_images/', storage=MediaCloudinaryStorage(),
        blank=True,
        null=True)
    alt_text = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # NEW: Add page_name for multi-page support
    page_name = models.CharField(max_length=50, default='home')
    
    class Meta:
        unique_together = ['page', 'element_id', 'page_name']  # Update unique constraint
    
    def __str__(self):
        return f"{self.page.brand_name} - Image {self.element_id} ({self.page_name})"
    

# models.py - Add these classes


    

# class TaxClass(models.Model):
#     """
#     Tax classes like 'Standard', 'Reduced', 'Zero', etc.
#     Similar to Shopify's tax categories
#     """
#     page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='tax_classes')
#     name = models.CharField(max_length=100, help_text="e.g., Standard, Reduced, Food, Books")
#     slug = models.SlugField(max_length=100)
#     description = models.TextField(blank=True, help_text="Internal description")
#     is_default = models.BooleanField(default=False, help_text="Apply this tax class by default")
#     is_shipping_taxable = models.BooleanField(default=False, help_text="Apply tax to shipping rates")
#     display_order = models.IntegerField(default=0)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         unique_together = ['page', 'slug']
#         ordering = ['display_order', 'name']
    
#     def __str__(self):
#         return f"{self.name} - {self.page.brand_name}"
    
#     def save(self, *args, **kwargs):
#         if not self.slug:
#             self.slug = slugify(self.name)
#         super().save(*args, **kwargs)


# class TaxRate(models.Model):
#     """
#     Individual tax rates applied to locations
#     Similar to Shopify's tax rates
#     """
#     CALCULATION_TYPES = [
#         ('percentage', 'Percentage (%)'),
#         ('fixed', 'Fixed Amount'),
#     ]
    
#     TAX_JURISDICTIONS = [
#         ('country', 'Country'),
#         ('state', 'State/Province'),
#         ('city', 'City'),
#         ('district', 'District'),
#         ('postal_code', 'Postal Code'),
#     ]
    
#     page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='tax_rates')
#     tax_class = models.ForeignKey(TaxClass, on_delete=models.CASCADE, related_name='rates')
#     name = models.CharField(max_length=100, help_text="e.g., US Sales Tax, EU VAT")
    
#     # Tax calculation
#     calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPES, default='percentage')
#     rate = models.DecimalField(max_digits=10, decimal_places=4, help_text="Tax rate (e.g., 10.0000 for 10%)")
    
#     # Jurisdiction
#     jurisdiction_type = models.CharField(max_length=20, choices=TAX_JURISDICTIONS, default='country')
#     country_code = models.CharField(max_length=2, blank=True, help_text="ISO 2-letter country code")
#     state_code = models.CharField(max_length=10, blank=True, help_text="State/province code")
#     city = models.CharField(max_length=100, blank=True)
#     postal_code = models.CharField(max_length=20, blank=True)
#     postal_code_match_pattern = models.CharField(max_length=50, blank=True, 
#                                                  help_text="Regex pattern for postal codes")
    
#     # Applicability
#     is_compound = models.BooleanField(default=False, help_text="Apply on top of other taxes")
#     is_shipping_taxable = models.BooleanField(default=False, help_text="Apply to shipping costs")
#     is_active = models.BooleanField(default=True)
#     priority = models.IntegerField(default=0, help_text="Lower numbers applied first")
    
#     # Tax-inclusive pricing
#     is_price_inclusive = models.BooleanField(default=False, help_text="Prices include this tax")
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         ordering = ['priority', 'name']
#         indexes = [
#             models.Index(fields=['page', 'is_active']),
#             models.Index(fields=['country_code', 'state_code']),
#         ]
    
#     def __str__(self):
#         return f"{self.name} - {self.rate}% ({self.get_jurisdiction_type_display()})"


# class TaxExemptCustomer(models.Model):
#     """
#     Customers who are tax exempt (resellers, non-profits, etc.)
#     """
#     page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='tax_exempt_customers')
#     email = models.EmailField()
#     company_name = models.CharField(max_length=200, blank=True)
#     tax_id = models.CharField(max_length=100, blank=True, help_text="VAT ID, Tax ID, etc.")
#     exemption_certificate = models.FileField(upload_to='tax_exemptions/', blank=True, null=True)
#     exempt_reason = models.CharField(max_length=200, blank=True)
#     applies_to_all = models.BooleanField(default=True)
#     tax_classes = models.ManyToManyField(TaxClass, blank=True, related_name='exempt_customers')
#     valid_from = models.DateTimeField(auto_now_add=True)
#     valid_until = models.DateTimeField(blank=True, null=True)
#     is_active = models.BooleanField(default=True)
#     notes = models.TextField(blank=True)
    
#     def __str__(self):
#         return f"{self.email} - {self.page.brand_name}"


# class CartTaxItem(models.Model):
#     """
#     Store calculated taxes for cart items (temporary, for order summary)
#     """
#     session_key = models.CharField(max_length=100)
#     page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE)
#     tax_rate = models.ForeignKey(TaxRate, on_delete=models.CASCADE)
#     tax_class = models.ForeignKey(TaxClass, on_delete=models.CASCADE)
#     taxable_amount = models.DecimalField(max_digits=10, decimal_places=2)
#     tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
#     is_shipping_tax = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         indexes = [models.Index(fields=['session_key', 'page'])]


# Add tax_class field to Product model
# Add this field to your existing Product model:
# tax_class = models.ForeignKey(TaxClass, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')


# class HomeFirts(models.Model):
#     title = models.CharField(max_length=100)

#     def __str__(self):
#         return self.title
    


class ProductCategory(models.Model):
    """Categories for organizing products"""
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='product_categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='category_images/',storage=MediaCloudinaryStorage(), blank=True, null=True, 
                              help_text="Upload a category image or icon")
    
    class Meta:
        verbose_name_plural = "Product Categories"
        ordering = ['display_order', 'name']
        # unique_together = ['page', 'slug']
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.name}"
    
    def get_active_products_count(self):
        return self.products.filter(status='active').count()
    
    def get_total_products_count(self):
        return self.products.count()
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class ProductInventory(models.Model):
    """Inventory tracking for products"""
    sku = models.CharField(max_length=100, unique=True)
    quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)
    track_quantity = models.BooleanField(default=True)
    allow_backorders = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.sku} - {self.quantity} in stock"

class ProductShipping(models.Model):
    """Shipping information for products"""
    WEIGHT_UNITS = [
        ('kg', 'Kilograms'),
        ('lb', 'Pounds'),
        ('oz', 'Ounces'),
    ]
    
    weight = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    weight_unit = models.CharField(max_length=2, choices=WEIGHT_UNITS, default='kg')
    length = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Length in cm")
    width = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Width in cm")
    height = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Height in cm")
    requires_shipping = models.BooleanField(default=True)
    free_shipping = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = "Product Shipping"

class ProductSeo(models.Model):
    """SEO metadata for products"""
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True, help_text="Comma-separated keywords")
    og_image = models.ImageField(upload_to='product_og_images/', blank=True, null=True)
    canonical_url = models.URLField(blank=True)
    
    class Meta:
        verbose_name = "Product SEO"
        verbose_name_plural = "Product SEO"

class Product(models.Model):
    PRODUCT_STATUS = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('out_of_stock', 'Out of Stock'),
    ]
    
    PRODUCT_TYPE = [
        ('physical', 'Physical Product'),
        ('digital', 'Digital Product'),
        ('service', 'Service'),
        ('subscription', 'Subscription'),
    ]
    
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='products')
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200, blank=True)  # Add this field
    description = models.TextField(blank=True)
    short_description = models.TextField(blank=True, max_length=500)

    # Categorization
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    type = models.CharField(max_length=20, choices=PRODUCT_TYPE, default='physical')
    status = models.CharField(max_length=20, choices=PRODUCT_STATUS, default='draft')
    tags = models.JSONField(default=list, blank=True, help_text="List of product tags")


    #pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Original price for showing discounts")
    cost_per_item = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Cost price for profit calculation")
    # In your Product model (builder/models.py)
    tax_class = models.ForeignKey(
        'payments.TaxClass', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='products'
    )
    charge_tax = models.BooleanField(default=True)
    margin=models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    #category
    category_name=models.CharField(max_length=255, blank=True, null=True)
    brand=models.CharField(max_length=255, blank=True, null=True)
    material=models.CharField(max_length=255, blank=True, null=True)
    specifications=models.CharField(max_length=255, blank=True, null=True)
    vendor=models.CharField(max_length=255, blank=True, null=True)
              
     # Inventory
    inventory = models.OneToOneField(ProductInventory, on_delete=models.CASCADE, null=True, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    quantity = models.IntegerField(default=0)
    track_quantity = models.BooleanField(default=True)
    low_stock_threshold = models.IntegerField(default=5)
    allow_backorders = models.BooleanField(default=False)
    cj_pid=models.CharField(max_length=300, blank=True,null=True)
    cj_vid=models.CharField(max_length=300, blank=True,null=True)
    image_url=models.URLField(max_length=500, blank=True,null=True)
    
    # Shipping
    # shipping = models.OneToOneField(ProductShipping, on_delete=models.CASCADE, null=True, blank=True)
    weight = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Weight in kg")
    weight_unit = models.CharField(max_length=2, choices=[('kg', 'kg'), ('lb', 'lb'), ('oz', 'oz')], default='kg')
    length = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Length in cm")
    width = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Width in cm")
    height = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Height in cm")
    
    use_custom_shipping = models.BooleanField(default=False)
    custom_shipping_type = models.CharField(max_length=20, choices=[
        ('flat', 'Flat Rate'),
        ('free', 'Free Shipping'),
        ('per_item', 'Per Item'),
        ('calculated', 'Calculated by Quantity'),
    ], default='flat', blank=True, null=True)
    custom_shipping_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    custom_free_shipping_min_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    shipping_per_item = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_note = models.CharField(max_length=200, blank=True, null=True)
    ships_separately = models.BooleanField(default=False)

    # tax_class = models.ForeignKey(TaxClass, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    requires_shipping = models.BooleanField(default=True)
    free_shipping = models.BooleanField(default=False)
    # SEO
    # seo = models.OneToOneField(ProductSeo, on_delete=models.CASCADE, null=True, blank=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    slug = models.SlugField(max_length=200, blank=True)
    # Media
    main_image = models.ImageField(upload_to='products/main/',storage=MediaCloudinaryStorage(), blank=True, null=True)
    image_gallery = models.JSONField(default=list, blank=True, help_text="List of additional image URLs")
    is_active = models.BooleanField(default=True)  # Add this field

     # Variants
    colors=models.CharField(max_length=500, blank=True, null=True, help_text="red,black or #20c997, #333")
    sizes=models.CharField(max_length=500, blank=True, null=True, help_text="Separate with comas.")
    has_variants = models.BooleanField(default=False)
    variant_options = models.JSONField(default=dict, blank=True, help_text="Variant options like size, color, etc.")
    
    # Digital Product Fields
    digital_file = models.FileField(upload_to='digital_products/', blank=True, null=True)
    download_limit = models.IntegerField(default=1, help_text="Number of times file can be downloaded")
    download_expiry = models.IntegerField(default=30, help_text="Days until download link expires")
    
    # Visibility
    visible_on_store = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    available_date = models.DateTimeField(null=True, blank=True)
    
    # Sales Data
    view_count = models.IntegerField(default=0)
    sale_count = models.IntegerField(default=0)
    
    # Organization
    vendor = models.CharField(max_length=100, blank=True)
    collection = models.CharField(max_length=100, blank=True)


    # image = models.ImageField(upload_to='products/', blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['page', 'status']),
            models.Index(fields=['page', 'category']),
            models.Index(fields=['page', 'featured']),
        ]

    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
            if not self.sku:
                self.sku = f"SKU-{self.page.id}-{int(timezone.now().timestamp())}"
            if not self.slug:
                self.slug = slugify(self.title)
            if self.status == 'active' and not self.published_at:
                self.published_at = timezone.now()
            super().save(*args, **kwargs)    
    @property
    def is_in_stock(self):
        if not self.inventory or not self.inventory.track_quantity:
            return True
        return self.inventory.quantity > 0
    
    @property
    def is_on_sale(self):
        return self.compare_at_price and self.compare_at_price > self.price
    
    @property
    def discount_percentage(self):
        if self.is_on_sale:
            return int(((self.compare_at_price - self.price) / self.compare_at_price) * 100)
        return 0
    
    def get_average_rating(self):
        """Calculate average rating for this product"""
        from django.db.models import Avg
        result = self.reviews.filter(is_approved=True).aggregate(avg_rating=Avg('rating'))
        return result['avg_rating'] or 0
    
    def get_review_count(self):
        """Get total number of reviews"""
        return self.reviews.filter(is_approved=True).count()
    
    def get_rating_distribution(self):
        """Get rating distribution for this product"""
        from django.db.models import Count
        return self.reviews.filter(is_approved=True).values('rating').annotate(count=Count('id')).order_by('rating')




class ProductImages(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_images')
    image = models.ImageField(upload_to='product-images/',storage=MediaCloudinaryStorage(), blank=True, null=True)

    def __str__(self):
        return f"{self.product.title}"



class ProductSpecification(models.Model):
    """
    Dynamic specifications for products (key-value pairs)
    Allows infinite title/property pairs per product
    """
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='dynamic_specs'
    )
    title = models.CharField(max_length=200, help_text="Specification title (e.g., 'Material', 'Warranty')")
    value = models.CharField(max_length=500, help_text="Specification value (e.g., 'Cotton', '2 Years')")
    display_order = models.IntegerField(default=0, help_text="Order in which specifications appear")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = "Product Specification"
        verbose_name_plural = "Product Specifications"
    
    def __str__(self):
        return f"{self.title}: {self.value}"

    
class ProductVariant(models.Model):
    """Product variants for different options"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    options = models.JSONField(default=dict, help_text="e.g., {'Size': 'Large', 'Color': 'Red'}")

    sku = models.CharField(max_length=100, unique=True)
    barcode = models.CharField(max_length=100, blank=True)

    option1 = models.CharField(max_length=100, null=True, blank=True)
    option2 = models.CharField(max_length=100, null=True, blank=True)
    option3 = models.CharField(max_length=100, null=True, blank=True)

    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_per_item = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    inventory = models.OneToOneField(ProductInventory, on_delete=models.CASCADE, null=True, blank=True)
    # Inventory - separate stock for each variant
    quantity = models.IntegerField(default=0)
    track_quantity = models.BooleanField(default=True)
    low_stock_threshold = models.IntegerField(default=5)

    # Media
    image = models.ImageField(upload_to='variant_images/',storage=MediaCloudinaryStorage(), blank=True, null=True)

    # Shipping
    weight = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    length = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    width = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    height = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    cj_vid = models.CharField(max_length=100, null=True, blank=True)
    # image = models.ImageField(upload_to='product_variants/', storage=MediaCloudinaryStorage(), blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
    
    def __str__(self):
        option_str = ', '.join([f"{k}: {v}" for k, v in self.options.items()])
        return f"{self.product.title} - {option_str}"
    
    def save(self, *args, **kwargs):
        if not self.sku:
            # Generate SKU like: PROD123-Size-Large-Color-Red
            base = f"{self.product.id}"
            for key, value in self.options.items():
                base += f"-{value[:3]}"
            self.sku = f"VAR-{base}-{int(timezone.now().timestamp())}"
        super().save(*args, **kwargs)
    
    @property
    def in_stock(self):
        if not self.track_quantity:
            return True
        return self.quantity > 0
    
    @property
    def is_on_sale(self):
        return self.compare_at_price and self.compare_at_price > self.price
    
    def get_price(self):
        """Get variant price or fallback to product price"""
        return self.price if self.price else self.product.price

class ProductReview(models.Model):
    """Customer reviews for products"""
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)  # Allow anonymous reviews
    session_key = models.CharField(max_length=100, blank=True, null=True)  # For guest users

    rating = models.IntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200)
    comment = models.TextField()
    helpful_count = models.IntegerField(default=0)
    author_name = models.CharField(max_length=100)
    author_email = models.EmailField(blank=True)
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [
            ['product', 'user', 'session_key']
        ]
    
    def __str__(self):
        return f"{self.product.title} - {self.rating} stars"


 # ================================================================

class ProductTier(models.Model):
    """
    Simple pricing tiers for products - quantity based discounts
    """
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='tiers')
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='product_tiers')
    
    quantity = models.PositiveIntegerField(default=1)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    badge_text = models.CharField(max_length=50, blank=True)
    is_default = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'quantity']
        unique_together = ['product', 'quantity']
    
    def __str__(self):
        return f"{self.product.title} - {self.quantity}x (${self.price_per_unit}/each)"
    
    @property
    def total_price(self):
        return self.price_per_unit * self.quantity
    
    @property
    def savings(self):
        """Calculate savings vs buying individually"""
        base_tier = self.product.tiers.filter(is_active=True).order_by('quantity').first()
        if base_tier and base_tier.id != self.id:
            base_total = base_tier.price_per_unit * self.quantity
            return base_total - self.total_price
        return 0
    
# RICH TEXT EDITOR MEDIA MODELS
# ================================================================

class EditorImage(models.Model):
    """Images uploaded via the rich text editor"""
    page = models.ForeignKey('PublishedPage', on_delete=models.CASCADE, related_name='editor_images')
    image = models.ImageField(upload_to='editor_images/')
    alt_text = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.image.name[:50]}"


class EditorMedia(models.Model):
    """Video/audio uploaded via the rich text editor"""
    MEDIA_TYPES = [
        ('video', 'Video'),
        ('audio', 'Audio'),
    ]
    
    page = models.ForeignKey('PublishedPage', on_delete=models.CASCADE, related_name='editor_media')
    file = models.FileField(upload_to='editor_media/')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.file.name[:50]}"   

class BackgroundImage(models.Model):
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='background_images')
    element_id = models.CharField(max_length=50)
    image = models.ImageField(upload_to='backgrounds/', storage=MediaCloudinaryStorage(),
        blank=True,
        null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['page', 'element_id']
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.element_id}"

class IconCustomization(models.Model):
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='icon_customizations')
    element_id = models.CharField(max_length=50)
    icon_class = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=99, blank=True)
    font_size = models.CharField(max_length=20, blank=True)
    
    class Meta:
        unique_together = ['page', 'element_id']
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.element_id}"
    

class PageSection(models.Model):
    """Represents different pages/sections in a multi-page template"""
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='page_sections')
    section_id = models.CharField(max_length=50)  # 'home', 'products', 'about', 'contact'
    title = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['page', 'section_id']
        ordering = ['display_order']
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.section_id}"
    


CATEGORY_CHOICES = [
        ('home', 'Home'),
        ('fashion', 'Fashion'),
        ('beauty', 'Beauty'),
        ('lifestyle', 'Lifestyle'),
    ]

class BlogPost(models.Model):
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='blog_posts')
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='home')
    slug = models.SlugField(unique=True, max_length=200)
    content = models.TextField()
    excerpt = models.TextField(blank=True, max_length=300)
    featured_image = models.ImageField(upload_to='blog_images/', blank=True, null=True)
    author = models.CharField(max_length=100, default='Admin')
    is_published = models.BooleanField(default=True)
    published_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-published_date']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_rating_stars(self):
        """Get star rating as HTML"""
        full_stars = '★' * self.rating
        empty_stars = '☆' * (5 - self.rating)
        return full_stars + empty_stars
    
    def can_user_edit(self, request):
        """Check if current user can edit this review"""
        if request.user.is_authenticated:
            return self.user == request.user
        else:
            return self.session_key == request.session.session_key
        


class ReviewHelpful(models.Model):
    """Track helpful votes for reviews"""
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='helpful_votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    session_key = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    
    def __str__(self):
        return f"Helpful vote for review {self.review.id}"


class FormSubmission(models.Model):
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='form_submissions')
    form_name = models.CharField(max_length=100)  # e.g., 'contact', 'newsletter'
    submitted_data = models.JSONField()  # Store all form fields as JSON
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.form_name} - {self.submitted_at.strftime('%Y-%m-%d %H:%M')}"

# Update the Template model to include blog and form features
# Add these fields to your existing Template model:
# has_blog = models.BooleanField(default=False)
# has_contact_form = models.BooleanField(default=False)

# Add to models.py
class ComponentCategory(models.Model):
    """Categories for organizing drag-and-drop components"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, max_length=100)
    description = models.TextField(blank=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Component Categories"
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name

class Component(models.Model):
    """Reusable components for drag-and-drop building"""
    name = models.CharField(max_length=100)
    category = models.ForeignKey(ComponentCategory, on_delete=models.CASCADE, related_name='components')
    html_content = models.TextField(help_text="HTML content for the component")
    css_content = models.TextField(blank=True, help_text="CSS styles for the component")
    thumbnail = models.ImageField(upload_to='component_thumbnails/',storage=MediaCloudinaryStorage(), blank=True, null=True)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Component metadata
    component_type = models.CharField(max_length=50, choices=[
        ('header', 'Header'),
        ('hero', 'Hero Section'),
        ('content', 'Content Section'),
        ('feature', 'Feature Section'),
        ('cta', 'Call to Action'),
        ('footer', 'Footer'),
        ('product', 'Product Display'),
        ('contact', 'Contact Form'),
    ])
    
    class Meta:
        ordering = ['category__display_order', 'display_order', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.component_type})"

    

class TrackingCode(models.Model):
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='tracking_codes')
    platform = models.CharField(max_length=50)  # e.g., "meta_pixel", "google_analytics"
    code = models.TextField()  # The actual tracking code
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.platform}"
    




    # cart and wishlist

class Cart(models.Model):
    """Shopping cart for users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=100, blank=True, null=True)  # For guest users
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # unique_together = ['user', 'page', 'session_key']  # Update unique constraint
        unique_together = [
            ['user', 'page'],
            ['session_key', 'page']
        ]

    def __str__(self):
        user_display = self.user.username if self.user else f"Guest ({self.session_key})"
        return f"Cart - {user_display} - {self.page.brand_name}"

    def get_total_quantity(self):
        return self.items.aggregate(total=Sum('quantity'))['total'] or 0

    def get_total_price(self):
        return self.items.aggregate(total=Sum(models.F('quantity') * models.F('product__price')))['total'] or 0

    def clean(self):
        """Ensure either user or session_key is provided"""
        if not self.user and not self.session_key:
            raise ValidationError('Either user or session_key must be provided.')

    def save(self, *args, **kwargs):
        # Clear session_key if user is set
        if self.user and self.session_key:
            self.session_key = None
        # Clear user if session_key is set for guest
        elif self.session_key and not self.user:
            # Ensure user is None
            self.user = None
        
        self.clean()
        super().save(*args, **kwargs)

    def get_item(self, product_id):
        """Get a specific cart item by product ID"""
        try:
            return self.items.get(product_id=product_id)
        except CartItem.DoesNotExist:
            return None
    
    def update_item_quantity(self, product_id, quantity):
        """Update quantity for a cart item"""
        cart_item = self.get_item(product_id)
        if cart_item:
            if quantity <= 0:
                cart_item.delete()
            else:
                cart_item.quantity = quantity
                cart_item.save()
            return True
        return False
    
    def increment_item(self, product_id, amount=1):
        """Increment cart item quantity"""
        cart_item = self.get_item(product_id)
        if cart_item:
            cart_item.quantity += amount
            cart_item.save()
            return cart_item.quantity
        return None
    
    def decrement_item(self, product_id, amount=1):
        """Decrement cart item quantity"""
        cart_item = self.get_item(product_id)
        if cart_item:
            cart_item.quantity = max(0, cart_item.quantity - amount)
            if cart_item.quantity == 0:
                cart_item.delete()
                return 0
            else:
                cart_item.save()
                return cart_item.quantity
        return None

class CartItem(models.Model):
    """Items in shopping cart"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')

    quantity = models.IntegerField(default=1)
    selected_options = models.JSONField(default=dict, blank=True)  # Store selected option values for display
    selected_color = models.CharField(max_length=50, blank=True, null=True)
    selected_size = models.CharField(max_length=50, blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['cart', 'product', 'variant']

    def __str__(self):
        variant_info = ''
        if self.selected_color:
            variant_info += f" - Color: {self.selected_color}"
        if self.selected_size:
            variant_info += f" - Size: {self.selected_size}"
        return f"{self.quantity}x {self.product.title}{variant_info}"
    
    def get_price(self):
        """Get the actual price (variant price > product price)"""
        if self.variant and self.variant.price:
            return self.variant.price
        return self.product.price
    
    def get_total_price(self):
        """Get total price for this item"""
        return self.quantity * self.get_price()
    
    def get_variant_image(self):
        """Get variant image if available"""
        if self.variant and self.variant.image:
            return self.variant.image.url
        return None

    def get_item(self, product_id):
        """Get a specific cart item by product ID"""
        try:
            return self.items.get(product_id=product_id)
        except CartItem.DoesNotExist:
            return None
    
    def update_item_quantity(self, product_id, quantity):
        """Update quantity for a cart item"""
        cart_item = self.get_item(product_id)
        if cart_item:
            if quantity <= 0:
                cart_item.delete()
            else:
                cart_item.quantity = quantity
                cart_item.save()
            return True
        return False
    
    def increment_item(self, product_id, amount=1):
        """Increment cart item quantity"""
        cart_item = self.get_item(product_id)
        if cart_item:
            cart_item.quantity += amount
            cart_item.save()
            return cart_item.quantity
        return None
    
    def decrement_item(self, product_id, amount=1):
        """Decrement cart item quantity"""
        cart_item = self.get_item(product_id)
        if cart_item:
            cart_item.quantity = max(0, cart_item.quantity - amount)
            if cart_item.quantity == 0:
                cart_item.delete()
                return 0
            else:
                cart_item.save()
                return cart_item.quantity
        return None
    
class Wishlist(models.Model):
    """User wishlist"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=100, blank=True, null=True)  # For guest users
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # unique_together = ['user', 'page', 'session_key']  # Update unique constraint
         unique_together = [
            ['user', 'page'],
            ['session_key', 'page']
        ]
    def __str__(self):
        user_display = self.user.username if self.user else f"Guest ({self.session_key})"
        return f"Wishlist - {user_display} - {self.page.brand_name}"

    def clean(self):
        """Ensure either user or session_key is provided"""
        if not self.user and not self.session_key:
            raise ValidationError('Either user or session_key must be provided.')

    def save(self, *args, **kwargs):
            if self.user and self.session_key:
                self.session_key = None
            elif self.session_key and not self.user:
                self.user = None
            
            self.clean()
            super().save(*args, **kwargs)

class WishlistItem(models.Model):
    """Items in wishlist"""
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['wishlist', 'product']

    def __str__(self):
        return self.product.title
    






class RecentlyViewedProduct(models.Model):
    """Track rescently viewed products for each visitor"""
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='recently_viewed')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='recently_viewed_by')
    session_key = models.CharField(max_length=40, db_index=True)  # For anonymous users
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # For logged-in users
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-viewed_at']
        # unique_together = ['page', 'product', 'session_key', 'user']
        indexes = [
            models.Index(fields=['session_key', '-viewed_at']),
            models.Index(fields=['user', '-viewed_at']),
        ]
    
    def str(self):
        return f"{self.product.title} - {self.viewed_at}"






# CJ Drop_shipping

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

class CJSettings(models.Model):
    """Store user's CJ Dropshipping API settings per store"""
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='cj_settings')
    
    # API Configuration
    api_key = models.CharField(max_length=255, help_text="Your CJ Dropshipping API key")
    access_token = models.CharField(max_length=9999, blank=True, null=True)
    token_expiry = models.DateTimeField(blank=True, null=True)
    api_status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('invalid', 'Invalid Key'),
            ('rate_limited', 'Rate Limited'),
        ],
        default='inactive'
    )
    last_api_check = models.DateTimeField(null=True, blank=True)
    
    # Feature Toggles
    is_active = models.BooleanField(default=False, help_text="Enable CJ integration for this store")
    auto_fulfill = models.BooleanField(default=False, help_text="Automatically fulfill orders on CJ")
    auto_sync_prices = models.BooleanField(default=True, help_text="Auto-sync price changes from CJ")
    auto_sync_inventory = models.BooleanField(default=True, help_text="Auto-sync inventory levels")
    
    # Business Configuration
    default_profit_margin = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=30.00,
        validators=[MinValueValidator(0), MaxValueValidator(500)],
        help_text="Default profit margin percentage"
    )
    default_warehouse = models.CharField(
        max_length=50,
        default='CN',
        choices=[
            ('CN', 'China Warehouse'),
            ('US', 'USA Warehouse'),
            ('EU', 'Europe Warehouse'),
            ('RU', 'Russia Warehouse'),
        ]
    )
    currency = models.CharField(max_length=3, default='USD')
    
    # Rate Limiting & Safety
    daily_api_calls = models.IntegerField(default=0)
    last_reset_date = models.DateField(default=timezone.now)
    max_daily_calls = models.IntegerField(default=950, help_text="CJ's daily limit is ~1000 calls")
    
    # Sync Configuration
    price_sync_interval = models.IntegerField(
        default=24,
        choices=[
            (1, 'Every Hour'),
            (6, 'Every 6 Hours'),
            (12, 'Every 12 Hours'),
            (24, 'Daily'),
            (168, 'Weekly'),
        ],
        help_text="How often to sync prices"
    )
    inventory_sync_interval = models.IntegerField(
        default=6,
        choices=[
            (1, 'Every Hour'),
            (6, 'Every 6 Hours'),
            (12, 'Every 12 Hours'),
            (24, 'Daily'),
        ],
        help_text="How often to sync inventory"
    )
    
    # Webhook Configuration
    webhook_secret = models.CharField(max_length=64, default=uuid.uuid4, editable=False)
    webhook_url = models.CharField(max_length=255, blank=True, null=True, help_text="Auto-generated webhook URL")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "CJ Dropshipping Settings"
        verbose_name_plural = "CJ Dropshipping Settings"
        unique_together = ['page']
    
    def __str__(self):
        return f"CJ Settings for {self.page.brand_name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate webhook URL
        if not self.webhook_url:
            self.webhook_url = f"https://{self.page.subdomain}.yourdomain.com/webhooks/cj/"
        
        # Reset daily counter if new day
        if self.last_reset_date != timezone.now().date():
            self.daily_api_calls = 0
            self.last_reset_date = timezone.now().date()
        
        super().save(*args, **kwargs)
    
    def can_make_api_call(self):
        """Check if we can make an API call within rate limits"""
        if self.daily_api_calls >= self.max_daily_calls:
            return False, f"Daily limit reached ({self.daily_api_calls}/{self.max_daily_calls})"
        return True, "OK"
    
    def increment_api_calls(self, count=1):
        """Increment API call counter"""
        self.daily_api_calls += count
        self.save(update_fields=['daily_api_calls'])


class CJProduct(models.Model):
    """Store CJ product references and sync data"""
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='cj_products')
    
    # CJ Product Identification
    cj_pid = models.CharField(max_length=100, db_index=True)
    cj_product_id = models.CharField(max_length=100, db_index=True) # The specific field missing[span_1](end_span)
    cj_sku = models.CharField(max_length=100, blank=True)
    cj_variant_id = models.CharField(max_length=100, blank=True)
    
    # Local Product Link
    local_product = models.OneToOneField(
        'Product', 
        on_delete=models.CASCADE,
        related_name='cj_info',
        null=True,
        blank=True
    )
    
    # Product Data Storage
    cj_data = models.JSONField(default=dict, help_text="Full product data from CJ")
    local_data_snapshot = models.JSONField(default=dict, help_text="Snapshot of local product data")
    
    # Sync Status
    sync_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Initial Sync'),
            ('synced', 'Synced'),
            ('failed', 'Sync Failed'),
            ('out_of_sync', 'Out of Sync'),
            ('discontinued', 'Discontinued on CJ'),
        ],
        default='pending'
    )
    
    # Price Tracking
    cj_price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    local_selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    profit_margin_applied = models.DecimalField(max_digits=5, decimal_places=2, default=30.00)
    
    # Inventory Tracking
    cj_stock_quantity = models.IntegerField(default=0)
    local_stock_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    
    # Sync Timestamps
    last_price_sync = models.DateTimeField(null=True, blank=True)
    last_inventory_sync = models.DateTimeField(null=True, blank=True)
    last_full_sync = models.DateTimeField(null=True, blank=True)
    
    # Error Tracking
    last_sync_error = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "CJ Product"
        verbose_name_plural = "CJ Products"
        # unique_together = ['page', 'cj_product_id']
        indexes = [
            models.Index(fields=['page', 'sync_status']),
            models.Index(fields=['last_full_sync']),
        ]
    
    def __str__(self):
        return f"CJ Product {self.cj_product_id} for {self.page.brand_name}"
    
    def calculate_selling_price(self, margin_percent=None):
        """Calculate selling price with profit margin"""
        if not self.cj_price_usd:
            return None
        
        if margin_percent is None:
            try:
                settings = self.page.cj_settings.get()
                margin_percent = settings.default_profit_margin
            except CJSettings.DoesNotExist:
                margin_percent = 30
        
        base_price = float(self.cj_price_usd)
        selling_price = base_price * (1 + float(margin_percent) / 100)
        
        # Round to nearest .95 or .99 for psychological pricing
        rounded = round(selling_price, 2)
        if rounded % 1 < 0.95:
            rounded = int(rounded) + 0.95
        else:
            rounded = int(rounded) + 0.99
        
        return rounded
    
    def needs_sync(self):
        """Check if product needs syncing based on settings"""
        try:
            settings = self.page.cj_settings.get()
        except CJSettings.DoesNotExist:
            return False
        
        if not settings.is_active:
            return False
        
        now = timezone.now()
        
        # Check price sync
        if settings.auto_sync_prices and self.last_price_sync:
            hours_since_price_sync = (now - self.last_price_sync).total_seconds() / 3600
            if hours_since_price_sync >= settings.price_sync_interval:
                return True
        
        # Check inventory sync
        if settings.auto_sync_inventory and self.last_inventory_sync:
            hours_since_inventory_sync = (now - self.last_inventory_sync).total_seconds() / 3600
            if hours_since_inventory_sync >= settings.inventory_sync_interval:
                return True
        
        return False


class CJOrder(models.Model):
    """Track CJ orders and fulfillment"""
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='cj_orders')
    
    # Order Identification
    order_number = models.CharField(max_length=100, unique=True, db_index=True)
    cj_order_id = models.CharField(max_length=100, blank=True, db_index=True)
    local_order_reference = models.CharField(max_length=100, blank=True)
    
    # Order Details
    customer_name = models.CharField(max_length=200, blank=True)
    customer_email = models.EmailField(blank=True)
    shipping_country = models.CharField(max_length=2, blank=True)
    shipping_address = models.JSONField(default=dict)
    
    # Status Tracking
    status = models.CharField(
        max_length=50,
        choices=[
            ('draft', 'Draft'),
            ('pending', 'Pending Fulfillment'),
            ('submitted', 'Submitted to CJ'),
            ('processing', 'Processing at CJ'),
            ('shipped', 'Shipped'),
            ('delivered', 'Delivered'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded'),
            ('failed', 'Fulfillment Failed'),
        ],
        default='draft'
    )
    
    # Financial Details
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cj_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    
    # Shipping Details
    shipping_method = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    tracking_url = models.URLField(blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    
    # Product Details (stored as JSON for flexibility)
    products = models.JSONField(default=list, help_text="List of products in order")
    
    # API Response Storage
    cj_request_data = models.JSONField(default=dict, help_text="Data sent to CJ")
    cj_response_data = models.JSONField(default=dict, help_text="Response from CJ")
    
    # Error Handling
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "CJ Order"
        verbose_name_plural = "CJ Orders"
        indexes = [
            models.Index(fields=['page', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['cj_order_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"CJ Order {self.order_number} ({self.status})"
    
    def calculate_profit(self):
        """Calculate profit for this order"""
        self.profit = self.total_amount - self.cj_cost
        return self.profit
    
    def can_retry(self):
        """Check if order can be retried"""
        if self.status in ['shipped', 'delivered', 'cancelled']:
            return False
        
        if self.retry_count >= 3:
            return False
        
        if self.next_retry_at and timezone.now() < self.next_retry_at:
            return False
        
        return True


class CJSyncLog(models.Model):
    """Log all sync operations for monitoring and debugging"""
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='cj_sync_logs')
    
    # Sync Details
    sync_type = models.CharField(
        max_length=50,
        choices=[
            ('product_search', 'Product Search'),
            ('product_import', 'Product Import'),
            ('price_sync', 'Price Sync'),
            ('inventory_sync', 'Inventory Sync'),
            ('order_submit', 'Order Submission'),
            ('order_status_check', 'Order Status Check'),
            ('category_sync', 'Category Sync'),
            ('webhook', 'Webhook Processing'),
        ]
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('started', 'Started'),
            ('success', 'Success'),
            ('partial', 'Partial Success'),
            ('failed', 'Failed'),
            ('rate_limited', 'Rate Limited'),
        ]
    )
    
    # Data Metrics
    items_processed = models.IntegerField(default=0)
    items_succeeded = models.IntegerField(default=0)
    items_failed = models.IntegerField(default=0)
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    
    # API Usage
    api_calls_made = models.IntegerField(default=0)
    
    # Error Details
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    # Request/Response Data (for debugging)
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "CJ Sync Log"
        verbose_name_plural = "CJ Sync Logs"
        indexes = [
            models.Index(fields=['page', 'sync_type', 'started_at']),
            models.Index(fields=['status', 'started_at']),
        ]
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.sync_type} - {self.status} ({self.page.brand_name})"
    
    def save(self, *args, **kwargs):
        if self.completed_at and self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        super().save(*args, **kwargs)


class CJCachedData(models.Model):
    """Cache frequently accessed CJ data to reduce API calls"""
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='cj_cache')
    
    cache_key = models.CharField(max_length=255, db_index=True)
    cache_type = models.CharField(
        max_length=50,
        choices=[
            ('categories', 'Product Categories'),
            ('shipping_methods', 'Shipping Methods'),
            ('warehouses', 'Warehouses'),
            ('product_details', 'Product Details'),
            ('search_results', 'Search Results'),
        ]
    )
    
    data = models.JSONField(default=dict)
    expires_at = models.DateTimeField(db_index=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    hits = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "CJ Cached Data"
        verbose_name_plural = "CJ Cached Data"
        unique_together = ['page', 'cache_key']
        indexes = [
            models.Index(fields=['expires_at']),
            models.Index(fields=['cache_type', 'page']),
        ]
    
    def __str__(self):
        return f"Cache: {self.cache_key}"
    
    def is_valid(self):
        return timezone.now() < self.expires_at


# builder/models.py - Add at the bottom

class ProductDisplayMode(models.Model):
    """Controls how variants are displayed for a product"""
    
    MODE_CHOICES = [
        ('single', 'Single Product with Swatches'),
        ('grouped', 'Grouped by Attribute'),
        ('flattened', 'Flatten All Variants'),
    ]
    
    product = models.OneToOneField(
        'Product',
        on_delete=models.CASCADE,
        related_name='display_mode'
    )
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='single')
    group_by = models.CharField(max_length=20, default='image')
    primary_attribute = models.CharField(max_length=50, blank=True, null=True)
    
    # Cache for quick lookups
    cached_groups = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.product.title} - {self.get_mode_display()}"


class VariantGroup(models.Model):
    """Groups variants together for display purposes"""
    
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='variant_groups'
    )
    group_key = models.CharField(max_length=100)  # Unique identifier
    display_name = models.CharField(max_length=200)
    variants = models.ManyToManyField('ProductVariant', related_name='variant_groups')

    is_in_stock = models.BooleanField(default=True)
    primary_attribute_value = models.CharField(max_length=100, blank=True, null=True)
    # Representative image (stored via Cloudinary)
    image = models.ImageField(upload_to='variant_groups/', blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    
    display_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['display_order']
        unique_together = ['product', 'group_key']
    
    def __str__(self):
        return f"{self.product.title} - {self.display_name}"

# builder/models.py - Add these new models

class GroupedProduct(models.Model):
    """
    Represents a product created from a variant group.
    This is a separate entity that doesn't modify the Product model.
    """
    # Reference to the original product
    original_product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='grouped_products'
    )
    
    # Reference to the actual product record
    product = models.OneToOneField(
        'Product',
        on_delete=models.CASCADE,
        related_name='grouped_source'
    )
    
    # Which variants this product represents
    variant_ids = models.JSONField(default=list, help_text="List of variant IDs in this group")
    
    # Group identifier
    group_key = models.CharField(max_length=100)
    group_display_name = models.CharField(max_length=200)
    
    # Original product state (for restoration)
    original_status = models.CharField(max_length=20, default='active')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['original_product', 'group_key']
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.original_product.title} - {self.group_display_name}"


class ProductDisplayMode(models.Model):
    """Controls how variants are displayed for a product"""
    
    MODE_CHOICES = [
        ('single', 'Single Product with Swatches'),
        ('grouped', 'Grouped by Attribute'),
        ('flattened', 'Flatten All Variants'),
    ]
    
    GROUP_BY_CHOICES = [
        ('image', 'Group by Image'),
        ('primary_attribute', 'Primary Attribute'),
        ('none', 'No Grouping'),
    ]
    
    product = models.OneToOneField(
        'Product',
        on_delete=models.CASCADE,
        related_name='display_mode'
    )
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='single')
    group_by = models.CharField(max_length=20, choices=GROUP_BY_CHOICES, default='image')
    primary_attribute = models.CharField(max_length=50, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.product.title} - {self.get_mode_display()}"

    
# builder/models.py - Add TemplateColorMapping

class TemplateColorMapping(models.Model):
    """
    Stores discovered color variables for each template
    This is cached to avoid repeated file scanning
    """
    template = models.OneToOneField('Template', on_delete=models.CASCADE, related_name='color_mapping')
    
    # JSON field storing all discovered color variables
    variables = models.JSONField(default=dict, help_text="All color variables found in template")
    
    # Suggested mapping from palette roles to template variables
    suggested_mapping = models.JSONField(default=dict, blank=True)
    
    # Custom user-defined mapping (overrides)
    custom_mapping = models.JSONField(default=dict, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    scan_count = models.IntegerField(default=0, help_text="Number of times this template has been scanned")
    
    class Meta:
        verbose_name = "Template Color Mapping"
        verbose_name_plural = "Template Color Mappings"
    
    def __str__(self):
        return f"Color Mapping for {self.template.name}"
    
    def get_active_mapping(self):
        """Get the active mapping (custom if exists, otherwise suggested)"""
        if self.custom_mapping:
            return self.custom_mapping
        return self.suggested_mapping
    
    def increment_scan_count(self):
        """Separate method to increment scan count - only called on updates"""
        self.scan_count += 1
        self.save(update_fields=['scan_count', 'updated_at'])
    
    def get_variable_preview(self):
        """Get a preview of color variables for admin"""
        preview = {}
        for var_name, var_data in list(self.variables.items())[:10]:
            preview[var_name] = var_data.get('value', '')
        return preview
    

class ColorPalette(models.Model):
    """
    Professional color palettes for templates
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, max_length=100)
    description = models.TextField(blank=True)
    
    # Palette metadata
    category = models.CharField(
        max_length=50,
        choices=[
            ('neutral', 'Neutral & Minimal'),
            ('corporate', 'Corporate & Professional'),
            ('creative', 'Creative & Vibrant'),
            ('ecommerce', 'E-Commerce'),
            ('luxury', 'Luxury & Premium'),
            ('nature', 'Nature & Organic'),
            ('tech', 'Technology & Modern'),
            ('health', 'Health & Wellness'),
            ('education', 'Education'),
            ('food', 'Food & Beverage'),
        ],
        default='corporate'
    )
    
    mood = models.CharField(
        max_length=50,
        choices=[
            ('professional', 'Professional'),
            ('playful', 'Playful'),
            ('elegant', 'Elegant'),
            ('energetic', 'Energetic'),
            ('calm', 'Calm'),
            ('trustworthy', 'Trustworthy'),
            ('luxurious', 'Luxurious'),
            ('modern', 'Modern'),
            ('warm', 'Warm'),
            ('cool', 'Cool'),
        ],
        default='professional'
    )
    
    # Popularity/usage tracking
    usage_count = models.IntegerField(default=0, help_text="Number of times this palette has been used")
    is_premium = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)

    # New: Template compatibility tracking
    compatible_templates = models.ManyToManyField(
        'Template',
        through='PaletteTemplateCompatibility',
        blank=True,
        help_text="Templates this palette has been optimized for"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-display_order', '-usage_count', 'name']
        verbose_name = "Color Palette"
        verbose_name_plural = "Color Palettes"
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"
    
    def increment_usage(self):
        """Increment usage count when palette is applied"""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])



class ColorPaletteColor(models.Model):
    """
    Individual colors within a palette
    """
    palette = models.ForeignKey(ColorPalette, on_delete=models.CASCADE, related_name='colors')
    
    # Color information
    name = models.CharField(max_length=100, help_text="e.g., 'Primary', 'Secondary', 'Accent'")
    variable_name = models.CharField(
        max_length=100, 
        help_text="CSS variable name (without --)",
        db_index=True
    )
    hex_value = models.CharField(max_length=30, help_text="Hex color code (e.g., #4361ee)")
    rgb_value = models.CharField(max_length=30, blank=True, help_text="RGB values (e.g., 67, 97, 238)")
    
    # Color role/usage
    color_type = models.CharField(
        max_length=50,
        choices=[
            ('primary', 'Primary Brand Color'),
            ('secondary', 'Secondary Brand Color'),
            ('accent', 'Accent Color'),
            ('background', 'Background'),
            ('text', 'Text Color'),
            ('heading', 'Heading Color'),
            ('link', 'Link Color'),
            ('success', 'Success State'),
            ('warning', 'Warning State'),
            ('error', 'Error State'),
            ('info', 'Info State'),
            ('border', 'Border Color'),
            ('shadow', 'Shadow Color'),
            ('overlay', 'Overlay Color'),
        ],
        default='primary'
    )

    # NEW: Track which elements use this color
    usage_count = models.IntegerField(default=0, help_text="Number of elements using this color")
    
    # NEW: Store the last applied value for change detection
    last_synced_value = models.CharField(max_length=30, blank=True, null=True)
    
    # Order within palette
    display_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['display_order', 'color_type']
        unique_together = ['palette', 'variable_name']
    
    def __str__(self):
        return f"{self.palette.name} - {self.name} ({self.hex_value})"
    
    def save(self, *args, **kwargs):
        # Auto-generate RGB value from hex if not provided
        if not self.rgb_value and self.hex_value:
            self.rgb_value = self.hex_to_rgb(self.hex_value)
        super().save(*args, **kwargs)
    
    @staticmethod
    def hex_to_rgb(hex_color):
        """Convert hex to RGB string"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return f"{rgb[0]}, {rgb[1]}, {rgb[2]}"
        return ""
    

# NEW MODEL: Track color usage across pages
class PaletteColorUsage(models.Model):
    """
    Tracks which elements on which pages use specific palette colors
    This enables efficient global color updates
    """
    page = models.ForeignKey('PublishedPage', on_delete=models.CASCADE, related_name='color_usages')
    palette = models.ForeignKey('ColorPalette', on_delete=models.CASCADE)
    palette_color = models.ForeignKey('ColorPaletteColor', on_delete=models.CASCADE)
    
    # The CSS variable name this color is mapped to
    variable_name = models.CharField(max_length=100, db_index=True)
    
    # The current hex value (cached for performance)
    current_hex_value = models.CharField(max_length=30)
    
    # How many elements on this page use this color
    element_count = models.IntegerField(default=0)
    
    # When this color was last synced
    last_synced = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['page', 'palette', 'palette_color', 'variable_name']
        indexes = [
            models.Index(fields=['page', 'variable_name']),
            models.Index(fields=['last_synced']),
        ]
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.variable_name} - {self.current_hex_value}"

class PageColorPalette(models.Model):
    """
    Link between a published page and its selected color palette
    """
    page = models.ForeignKey(
        'PublishedPage', 
        on_delete=models.CASCADE, 
        related_name='color_palettes'
    )
    palette = models.ForeignKey(ColorPalette, on_delete=models.CASCADE)
    
    # When this palette was applied
    applied_at = models.DateTimeField(auto_now_add=True)
    
    # Whether this is the active palette for the page
    is_active = models.BooleanField(default=True)
    
    # Store the actual CSS variable values that were applied
    applied_colors = models.JSONField(default=dict, help_text="Snapshot of applied colors")

    # Custom variable mapping for this specific palette+template combination
    variable_mapping = models.JSONField(
        default=dict,
        help_text="Map palette color roles to template variable names"
    )
    
    class Meta:
        ordering = ['-applied_at']
        # FIX: This constraint ensures only ONE active palette per page
        # But we need to handle it properly in the view
        constraints = [
            models.UniqueConstraint(
                fields=['page', 'is_active'],
                name='unique_active_palette_per_page',
                condition=models.Q(is_active=True)
            )
        ]
    
    def __str__(self):
        return f"{self.page.brand_name} - {self.palette.name}"
    

class CustomColorOverride(models.Model):
    """
    Allow users to override specific colors in a palette
    """
    page = models.ForeignKey('PublishedPage', on_delete=models.CASCADE, related_name='color_overrides')
    palette = models.ForeignKey(ColorPalette, on_delete=models.CASCADE)
    
    # Which color variable to override
    variable_name = models.CharField(max_length=100)
    
    # Custom color values
    hex_value = models.CharField(max_length=30)
    rgb_value = models.CharField(max_length=30, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['page', 'palette', 'variable_name']
    
    def save(self, *args, **kwargs):
        if not self.rgb_value and self.hex_value:
            color = ColorPaletteColor.hex_to_rgb(self.hex_value)
            if color:
                self.rgb_value = color
        super().save(*args, **kwargs)


class PaletteTemplateCompatibility(models.Model):
    """
    Tracks which palettes work well with which templates
    and stores custom mappings
    """
    palette = models.ForeignKey(ColorPalette, on_delete=models.CASCADE)
    template = models.ForeignKey('Template', on_delete=models.CASCADE)
    
    # Custom variable mapping for this specific palette+template combination
    variable_mapping = models.JSONField(
        default=dict,
        help_text="Map palette color roles to template variable names"
    )
    
    # How many times this combination has been used
    usage_count = models.IntegerField(default=0)
    
    # Rating (1-5) from users
    average_rating = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['palette', 'template']
    
    def __str__(self):
        return f"{self.palette.name} on {self.template.name}"  
    


class ShippingPolicy(models.Model):
    """
    Shipping and returns policy for each store
    """
    page = models.OneToOneField(PublishedPage, on_delete=models.CASCADE, related_name='shipping_policy')
    
    # Shipping Policy Fields
    processing_time = models.CharField(max_length=100, blank=True, default='1-3 business days')
    shipping_methods = models.TextField(blank=True, help_text="Describe shipping methods and rates")
    delivery_timeframe = models.CharField(max_length=100, blank=True, default='5-10 business days')
    free_shipping_threshold = models.CharField(max_length=100, blank=True, default='Orders over $50')
    
    # Returns Policy Fields
    return_window = models.CharField(max_length=100, blank=True, default='30 days')
    return_conditions = models.TextField(blank=True, help_text="Conditions for returns")
    return_process = models.TextField(blank=True, help_text="How to initiate a return")
    refund_info = models.TextField(blank=True, help_text="Refund process and timeline")
    
    # Additional Information
    international_shipping = models.TextField(blank=True)
    support_contact = models.CharField(max_length=200, blank=True, help_text="Email or contact link")
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Shipping Policy - {self.page.brand_name}"
    
    class Meta:
        verbose_name_plural = "Shipping Policies"




class SocialMedia(models.Model):
    """
    Social media handles for each store
    """
    PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('twitter', 'X (Twitter)'),
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('pinterest', 'Pinterest'),
        ('linkedin', 'LinkedIn'),
        ('youtube', 'YouTube'),
        ('tiktok', 'TikTok'),
        ('snapchat', 'Snapchat'),
        ('threads', 'Threads'),
        ('discord', 'Discord'),
        ('github', 'GitHub'),
        ('medium', 'Medium'),
        ('tumblr', 'Tumblr'),
        ('reddit', 'Reddit'),
        ('etsy', 'Etsy'),
        ('amazon', 'Amazon'),
        ('ebay', 'eBay'),
        ('aliexpress', 'AliExpress'),
        ('shopify', 'Shopify'),
        ('custom', 'Custom Link'),
    ]

    PLATFORM_ICONS = {
        'facebook': 'fab fa-facebook-f',
        'instagram': 'fab fa-instagram',
        'twitter': 'fab fa-x-twitter',
        'whatsapp': 'fab fa-whatsapp',
        'telegram': 'fab fa-telegram-plane',
        'pinterest': 'fab fa-pinterest-p',
        'linkedin': 'fab fa-linkedin-in',
        'youtube': 'fab fa-youtube',
        'tiktok': 'fab fa-tiktok',
        'snapchat': 'fab fa-snapchat-ghost',
        'threads': 'fab fa-threads',
        'discord': 'fab fa-discord',
        'github': 'fab fa-github',
        'medium': 'fab fa-medium',
        'tumblr': 'fab fa-tumblr',
        'reddit': 'fab fa-reddit-alien',
        'etsy': 'fab fa-etsy',
        'amazon': 'fab fa-amazon',
        'ebay': 'fab fa-ebay',
        'aliexpress': 'fas fa-store',
        'shopify': 'fab fa-shopify',
        'custom': 'fas fa-link',
    }

    PLATFORM_COLORS = {
        'facebook': '#1877F2',
        'instagram': '#E4405F',
        'twitter': '#000000',
        'whatsapp': '#25D366',
        'telegram': '#26A5E4',
        'pinterest': '#BD081C',
        'linkedin': '#0A66C2',
        'youtube': '#FF0000',
        'tiktok': '#000000',
        'snapchat': '#FFFC00',
        'threads': '#000000',
        'discord': '#5865F2',
        'github': '#171515',
        'medium': '#000000',
        'tumblr': '#35465C',
        'reddit': '#FF4500',
        'etsy': '#D5641C',
        'amazon': '#FF9900',
        'ebay': '#E53238',
        'aliexpress': '#E42F2F',
        'shopify': '#96BF48',
        'custom': '#6B7A8A',
    }

     # Platform-specific field definitions
    PLATFORM_FIELDS = {
        'facebook': {
            'field_type': 'text',
            'placeholder': 'yourpage or yourusername',
            'help_text': 'Enter your Facebook page name, username, or full URL',
            'example': 'mybrand or https://facebook.com/mybrand'
        },
        'instagram': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your Instagram username (without @)',
            'example': 'mybrand'
        },
        'twitter': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your X (Twitter) username (without @)',
            'example': 'mybrand'
        },
        'whatsapp': {
            'field_type': 'tel',
            'placeholder': '+1234567890',
            'help_text': 'Enter your WhatsApp number with country code',
            'example': '+14155552671'
        },
        'telegram': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your Telegram username (without @)',
            'example': 'mybrand'
        },
        'pinterest': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your Pinterest username',
            'example': 'mybrand'
        },
        'linkedin': {
            'field_type': 'text',
            'placeholder': 'username or company name',
            'help_text': 'Enter your LinkedIn username or company name',
            'example': 'mybrand or my-company'
        },
        'youtube': {
            'field_type': 'text',
            'placeholder': 'channel/handle',
            'help_text': 'Enter your YouTube channel handle or ID',
            'example': '@mybrand or UCxxxxx'
        },
        'tiktok': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your TikTok username (without @)',
            'example': 'mybrand'
        },
        'snapchat': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your Snapchat username',
            'example': 'mybrand'
        },
        'threads': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your Threads username (without @)',
            'example': 'mybrand'
        },
        'discord': {
            'field_type': 'text',
            'placeholder': 'invite link',
            'help_text': 'Enter your Discord invite link',
            'example': 'https://discord.gg/invitecode'
        },
        'github': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your GitHub username',
            'example': 'mybrand'
        },
        'medium': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your Medium username (without @)',
            'example': 'mybrand'
        },
        'tumblr': {
            'field_type': 'text',
            'placeholder': 'blogname',
            'help_text': 'Enter your Tumblr blog name',
            'example': 'mybrand'
        },
        'reddit': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your Reddit username',
            'example': 'mybrand'
        },
        'etsy': {
            'field_type': 'text',
            'placeholder': 'shopname',
            'help_text': 'Enter your Etsy shop name',
            'example': 'mybrand'
        },
        'amazon': {
            'field_type': 'text',
            'placeholder': 'store ID',
            'help_text': 'Enter your Amazon store ID',
            'example': 'mybrand-20'
        },
        'ebay': {
            'field_type': 'text',
            'placeholder': 'username',
            'help_text': 'Enter your eBay username',
            'example': 'mybrand'
        },
        'aliexpress': {
            'field_type': 'text',
            'placeholder': 'store ID',
            'help_text': 'Enter your AliExpress store ID',
            'example': '1234567'
        },
        'shopify': {
            'field_type': 'text',
            'placeholder': 'storename',
            'help_text': 'Enter your Shopify store name (without .myshopify.com)',
            'example': 'mybrand'
        },
        'custom': {
            'field_type': 'url',
            'placeholder': 'https://example.com/yourpage',
            'help_text': 'Enter the full URL to your custom page',
            'example': 'https://example.com/mybrand'
        },
    }

    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='social_media')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    raw_handle = models.CharField(max_length=255, help_text="Your username or full URL")
     # Store the raw input from user
    # raw_handle = models.CharField(max_length=255, help_text="Raw input from user (username, phone, or URL)")
    display_name = models.CharField(max_length=100, blank=True, help_text="Custom display name (optional)")
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    open_in_new_tab = models.BooleanField(default=True, help_text="Open link in new tab")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'platform']
        unique_together = ['page', 'platform']

    def __str__(self):
        return f"{self.get_platform_display()} - {self.page.brand_name}"

    def get_icon(self):
        return self.PLATFORM_ICONS.get(self.platform, 'fas fa-link')

    def get_color(self):
        return self.PLATFORM_COLORS.get(self.platform, '#6B7A8A')
    
    def get_field_info(self):
        """Get platform-specific field information"""
        return self.PLATFORM_FIELDS.get(self.platform, {
            'field_type': 'text',
            'placeholder': 'Enter your handle',
            'help_text': 'Enter your social media handle',
            'example': 'mybrand'
        })

    def get_url(self):
        """Generate the full URL from raw_handle based on platform - with no validation"""
        handle = self.raw_handle.strip()  # Fixed: changed from self.handle to self.raw_handle
        
        # If it's already a full URL, return as is
        if handle.startswith(('http://', 'https://')):
            return handle
            
        # Platform-specific URL patterns
        url_patterns = {
            'facebook': f'https://facebook.com/{handle}',
            'instagram': f'https://instagram.com/{handle}',
            'twitter': f'https://twitter.com/{handle}',
            'whatsapp': f'https://wa.me/{handle}',
            'telegram': f'https://t.me/{handle}',
            'pinterest': f'https://pinterest.com/{handle}',
            'linkedin': f'https://linkedin.com/in/{handle}',
            'youtube': f'https://youtube.com/@{handle}',
            'tiktok': f'https://tiktok.com/@{handle}',
            'snapchat': f'https://snapchat.com/add/{handle}',
            'threads': f'https://threads.net/@{handle}',
            'discord': handle,  # Discord invites are full URLs usually
            'github': f'https://github.com/{handle}',
            'medium': f'https://medium.com/@{handle}',
            'tumblr': f'https://{handle}.tumblr.com',
            'reddit': f'https://reddit.com/user/{handle}',
            'etsy': f'https://etsy.com/shop/{handle}',
            'amazon': f'https://amazon.com/shops/{handle}',
            'ebay': f'https://ebay.com/str/{handle}',
            'aliexpress': f'https://aliexpress.com/store/{handle}',
            'shopify': f'https://{handle}.myshopify.com',
            'custom': handle,  # For custom links, use as is
        }
        
        return url_patterns.get(self.platform, handle)


class TermsAndConditions(models.Model):
    """
    Terms and Conditions for each store
    """
    page = models.OneToOneField(PublishedPage, on_delete=models.CASCADE, related_name='terms')
    
    # Content
    content = models.TextField(blank=True, help_text="Full terms and conditions content")
    
    # Optional sections for structured display
    introduction = models.TextField(blank=True, help_text="Introduction section")
    agreement_to_terms = models.TextField(blank=True, help_text="Agreement to terms section")
    intellectual_property = models.TextField(blank=True, help_text="Intellectual property section")
    user_responsibilities = models.TextField(blank=True, help_text="User responsibilities section")
    prohibited_activities = models.TextField(blank=True, help_text="Prohibited activities section")
    termination = models.TextField(blank=True, help_text="Termination section")
    governing_law = models.TextField(blank=True, help_text="Governing law section")
    disputes = models.TextField(blank=True, help_text="Dispute resolution section")
    limitations = models.TextField(blank=True, help_text="Limitations of liability section")
    contact_info = models.TextField(blank=True, help_text="Contact information for legal inquiries")
    
    # Settings
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Terms & Conditions - {self.page.brand_name}"
    
    class Meta:
        verbose_name_plural = "Terms and Conditions"


class PrivacyPolicy(models.Model):
    """
    Privacy Policy for each store
    """
    page = models.OneToOneField(PublishedPage, on_delete=models.CASCADE, related_name='privacy')
    
    # Content
    content = models.TextField(blank=True, help_text="Full privacy policy content")
    
    # Optional sections for structured display
    introduction = models.TextField(blank=True, help_text="Introduction section")
    information_collected = models.TextField(blank=True, help_text="What information we collect")
    how_we_use = models.TextField(blank=True, help_text="How we use your information")
    cookies = models.TextField(blank=True, help_text="Cookie policy")
    third_party = models.TextField(blank=True, help_text="Third-party disclosure")
    data_security = models.TextField(blank=True, help_text="Data security measures")
    your_rights = models.TextField(blank=True, help_text="Your privacy rights")
    children_privacy = models.TextField(blank=True, help_text="Children's privacy")
    international_transfers = models.TextField(blank=True, help_text="International data transfers")
    policy_changes = models.TextField(blank=True, help_text="Changes to this policy")
    contact_info = models.TextField(blank=True, help_text="Contact for privacy questions")
    
    # GDPR/CCPA compliance
    gdpr_compliant = models.BooleanField(default=False, help_text="GDPR compliant")
    ccpa_compliant = models.BooleanField(default=False, help_text="CCPA compliant")
    
    # Settings
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Privacy Policy - {self.page.brand_name}"
    
    class Meta:
        verbose_name_plural = "Privacy Policies"

class ContactSubmission(models.Model):
    """Store contact form submissions"""
    name = models.CharField(max_length=200)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.subject}"



# Add at the end of your models.py file

class ProductOption(models.Model):
    """Product option types like Size, Color, Material"""
    OPTION_TYPES = [
        ('text', 'Text (Dropdown)'),
        ('color', 'Color Swatch'),
        ('button', 'Button (Pills)'),
        ('image', 'Image Swatch'),
    ]
    
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='product_options')
    name = models.CharField(max_length=100, help_text="e.g., Size, Color, Material")
    option_type = models.CharField(max_length=20, choices=OPTION_TYPES, default='text')
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['display_order']
        unique_together = ['page', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.page.brand_name})"


class ProductOptionValue(models.Model):
    """Individual option values like Small/Red/Cotton"""
    option = models.ForeignKey(ProductOption, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=100)
    color_code = models.CharField(max_length=20, blank=True, null=True, help_text="For color swatches")
    image = models.ImageField(upload_to='option_images/', blank=True, null=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']
        unique_together = ['option', 'value']
    
    def __str__(self):
        return f"{self.option.name}: {self.value}"


# Add to builder/models.py - After ImageCustomization class

class VideoCustomization(models.Model):
    """
    Store custom videos for editable-image elements
    """
    page = models.ForeignKey(PublishedPage, on_delete=models.CASCADE, related_name='video_customizations')
    element_id = models.CharField(max_length=50)  # e.g., "1", "2", "3"
    video_url = models.URLField(max_length=500, blank=True, null=True, 
                                help_text="YouTube, Vimeo, or direct video URL")
    video_file = models.FileField(upload_to='custom_videos/', 
                                
                                  blank=True, null=True)
    poster_image = models.ImageField(upload_to='video_posters/', 
                                      
                                     blank=True, null=True,
                                     help_text="Preview image shown before video plays")
    alt_text = models.CharField(max_length=200, blank=True)
    autoplay = models.BooleanField(default=False)
    loop = models.BooleanField(default=False)
    muted = models.BooleanField(default=True)
    controls = models.BooleanField(default=True)
    show_play_button = models.BooleanField(default=True, help_text="Show play button overlay on video")
    created_at = models.DateTimeField(auto_now_add=True)
    page_name = models.CharField(max_length=50, default='home')
    
    class Meta:
        unique_together = ['page', 'element_id', 'page_name']
    
    def __str__(self):
        return f"{self.page.brand_name} - Video {self.element_id} ({self.page_name})"
    
    def get_video_embed_url(self):
        """Convert YouTube/Vimeo URLs to embed format"""
        if not self.video_url:
            return None
        
        # YouTube
        if 'youtube.com/watch' in self.video_url or 'youtu.be' in self.video_url:
            import re
            # Extract video ID
            patterns = [
                r'(?:youtube\.com\/watch\?v=)([\w-]+)',
                r'(?:youtu\.be\/)([\w-]+)',
                r'(?:youtube\.com\/embed\/)([\w-]+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, self.video_url)
                if match:
                    video_id = match.group(1)
                    return f"https://www.youtube.com/embed/{video_id}"
        
        # Vimeo
        elif 'vimeo.com' in self.video_url:
            import re
            match = re.search(r'vimeo\.com\/(\d+)', self.video_url)
            if match:
                video_id = match.group(1)
                return f"https://player.vimeo.com/video/{video_id}"
        
        # Direct URL or already embed
        return self.video_url




# ============================================================
# DOMAIN FULFILLMENT SYSTEM
# ============================================================

class DomainRequest(models.Model):
    """
    User's request for a custom domain on their store.
    This is the user-facing intent + the operational state machine.
    """
    STATUS_CHOICES = [
        ('pending_review', 'Pending Review'),
        ('approved', 'Approved'),
        ('purchasing', 'Processing'),
        ('purchased', 'Processed'),
        ('configuring_dns', 'Configuring DNS'),
        ('active', 'Active'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    TERMINAL_STATUSES = ['active', 'failed', 'rejected', 'cancelled']

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='domain_requests'
    )
    page = models.ForeignKey(
        PublishedPage,
        on_delete=models.CASCADE,
        related_name='domain_requests',
        null=True,
        blank=True,
        help_text="The store this domain is intended for"
    )

    # The requested domain
    domain_name = models.CharField(max_length=255, db_index=True)
    tld = models.CharField(max_length=20, db_index=True)
    is_free_tier = models.BooleanField(
        default=True,
        help_text="True if this request is covered by the user's plan (free domain benefit)"
    )

    # State machine
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending_review',
        db_index=True
    )

    # Admin review
    admin_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_domain_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Registrar details (populated after purchase)
    registrar = models.CharField(max_length=50, blank=True)
    registrar_order_id = models.CharField(max_length=100, blank=True)
    purchase_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    purchase_currency = models.CharField(max_length=3, default='USD')
    purchase_date = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateTimeField(null=True, blank=True)

    # DNS / activation
    dns_configured = models.BooleanField(default=False)
    dns_verified_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Domain Request"
        verbose_name_plural = "Domain Requests"
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['domain_name']),
        ]

    def __str__(self):
        return f"{self.domain_name} - {self.get_status_display()} ({self.user.username})"

    @property
    def is_terminal(self):
        return self.status in self.TERMINAL_STATUSES

    @property
    def is_active_request(self):
        return not self.is_terminal


class PurchasedDomain(models.Model):
    """
    A domain that has been purchased and is owned by the platform.
    Domain assets outlive any single user, so this is decoupled from DomainRequest.
    """
    domain_name = models.CharField(max_length=255, unique=True, db_index=True)
    registrar = models.CharField(max_length=50, default='namecheap')

    purchase_date = models.DateTimeField()
    expiry_date = models.DateTimeField(db_index=True)
    auto_renew = models.BooleanField(default=True)

    purchase_cost = models.DecimalField(max_digits=10, decimal_places=2)
    renewal_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default='USD')

    # Linkage
    assigned_page = models.ForeignKey(
        PublishedPage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchased_domains'
    )
    source_request = models.ForeignKey(
        DomainRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchased_domain'
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Purchased Domain"
        verbose_name_plural = "Purchased Domains"
        indexes = [
            models.Index(fields=['expiry_date']),
            models.Index(fields=['assigned_page']),
        ]

    def __str__(self):
        return self.domain_name


class DomainAvailabilityCache(models.Model):
    """
    Short-lived cache of RDAP availability checks.
    Reduces registry load and speeds up the search UX.
    """
    domain_name = models.CharField(max_length=255, unique=True, db_index=True)
    is_available = models.BooleanField()
    checked_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = "Domain Availability Cache"
        verbose_name_plural = "Domain Availability Cache"
        indexes = [
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.domain_name} - {'available' if self.is_available else 'taken'}"

    @property
    def is_valid(self):
        return timezone.now() < self.expires_at


    
