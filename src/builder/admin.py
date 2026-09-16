from django.contrib import admin
from .models import *

@admin.register(PublishedPage)
class PublishedPageAdmin(admin.ModelAdmin):
    list_display = ['brand_name', 'template_name', 'template', 'user', 'is_published', 'created_at']
    list_filter = ['template_name','template', 'is_published', 'created_at']
    search_fields = ['brand_name', 'user__username']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'page', 'price', 'created_at']
    list_filter = ['page__template_name','page__template', 'created_at']

admin.site.register(TextContent)
admin.site.register(StyleCustomization)
admin.site.register(TrackingCode)
admin.site.register(BackgroundImage)
admin.site.register(IconCustomization)
admin.site.register(PageSection)
admin.site.register(BlogPost)
admin.site.register(FormSubmission)
admin.site.register(ComponentCustomization)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Wishlist)
admin.site.register(WishlistItem)
admin.site.register(CJCachedData)
admin.site.register(CJOrder)
admin.site.register(CJProduct)
admin.site.register(CJSettings)
admin.site.register(CJSyncLog)

@admin.register(TemplateCategory)
class TemplateCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'display_order', 'is_active', 'template_count']
    list_editable = ['display_order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    
    def template_count(self, obj):
        return obj.templates.count()
    template_count.short_description = 'Templates'

admin.site.register(Template)
admin.site.register(ImageCustomization)
admin.site.register(ProductVariant)
admin.site.register(ProductInventory)
admin.site.register(ProductSeo)
admin.site.register(ProductCategory)
admin.site.register(ProductShipping)
admin.site.register(ProductReview)
admin.site.register(ReviewHelpful)
admin.site.register(RecentlyViewedProduct)
admin.site.register(ProductImages)
# class TemplateAdmin(admin.ModelAdmin):
#     list_display = ['title', 'name', 'category', 'is_active', 'template_type', 'display_order', 'created_at']
#     list_editable = ['is_active', 'display_order']
#     list_filter = ['template_type','category', 'is_active', 'is_responsive', 'has_ecommerce']
#     search_fields = ['title', 'name', 'description']
#     readonly_fields = ['created_at', 'updated_at']

#     def formfield_for_dbfield(self, db_field, **kwargs):
#         if db_field.name == 'available_pages':
#             kwargs['help_text'] = 'Enter pages as JSON list: ["home", "products", "about", "contact"]'
#         return super().formfield_for_dbfield(db_field, **kwargs)
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('name', 'title', 'description', 'category', 'template_file')
#         }),
#         ('Display Settings', {
#             'fields': ('preview_image', 'display_order', 'is_active')
#         }),
#         ('Template Features', {
#             'fields': ('is_responsive', 'has_ecommerce', 'has_blog', 'has_contact_form'),
#             'classes': ('collapse',)
#         }),
#         ('Timestamps', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         })
#     )

@admin.register(ComponentCategory)
class ComponentCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'display_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['display_order', 'is_active']

@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'component_type', 'is_active', 'display_order']
    list_filter = ['category', 'component_type', 'is_active']
    search_fields = ['name', 'html_content']
    list_editable = ['display_order', 'is_active']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'component_type', 'is_active', 'display_order')
        }),
        ('Content', {
            'fields': ('html_content', 'css_content'),
            'classes': ('wide',)
        }),
        ('Thumbnail', {
            'fields': ('thumbnail',),
            'classes': ('collapse',)
        })
    )


# admin.site.register(TaxClass)
# admin.site.register(TaxRate)
# admin.site.register(TaxExemptCustomer)
# admin.site.register(CartTaxItem)
# admin.site.register(HomeFirts)


# builder/admin.py - Add this


from django.utils.html import format_html
from .models import ColorPalette, ColorPaletteColor, PageColorPalette, CustomColorOverride

class ColorPaletteColorInline(admin.TabularInline):
    model = ColorPaletteColor
    extra = 5
    fields = ['color_type', 'name', 'variable_name', 'hex_value', 'color_preview', 'display_order']
    readonly_fields = ['color_preview']
    
    def color_preview(self, obj):
        if obj.hex_value:
            return format_html(
                '<div style="width: 30px; height: 30px; background-color: {}; border-radius: 4px;"></div>',
                obj.hex_value
            )
        return "-"
    color_preview.short_description = "Preview"


@admin.register(ColorPalette)
class ColorPaletteAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'mood', 'palette_preview', 'usage_count', 'is_premium', 'is_active', 'display_order']
    list_filter = ['category', 'mood', 'is_premium', 'is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ColorPaletteColorInline]
    actions = ['duplicate_palette', 'reset_usage_counts']
    
    fieldsets = (
        ('Palette Information', {
            'fields': ('name', 'slug', 'description', 'category', 'mood')
        }),
        ('Settings', {
            'fields': ('is_premium', 'is_active', 'display_order', 'usage_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['created_at', 'updated_at', 'usage_count']
    
    def palette_preview(self, obj):
        colors = obj.colors.all()[:5]
        preview_html = '<div style="display: flex; gap: 2px;">'
        for color in colors:
            preview_html += f'<div style="width: 20px; height: 20px; background-color: {color.hex_value}; border-radius: 3px;"></div>'
        preview_html += '</div>'
        return format_html(preview_html)
    palette_preview.short_description = "Preview"
    
    def duplicate_palette(self, request, queryset):
        for palette in queryset:
            palette.pk = None
            palette.name = f"{palette.name} (Copy)"
            palette.slug = f"{palette.slug}-copy"
            palette.usage_count = 0
            palette.save()
            
            # Copy colors
            for color in palette.colors.all():
                color.pk = None
                color.palette = palette
                color.save()
                
        self.message_user(request, f"{queryset.count()} palette(s) duplicated successfully.")
    duplicate_palette.short_description = "Duplicate selected palettes"
    
    def reset_usage_counts(self, request, queryset):
        queryset.update(usage_count=0)
        self.message_user(request, "Usage counts reset successfully.")
    reset_usage_counts.short_description = "Reset usage counts"


@admin.register(PageColorPalette)
class PageColorPaletteAdmin(admin.ModelAdmin):
    list_display = ['page', 'palette', 'applied_at', 'is_active']
    list_filter = ['is_active', 'palette__category']
    search_fields = ['page__brand_name', 'palette__name']
    readonly_fields = ['applied_at']

admin.site.register(TemplateColorMapping)
admin.site.register(PaletteTemplateCompatibility)

admin.site.register(PaletteColorUsage)

admin.site.register(CustomColorOverride)
admin.site.register(ProductSpecification)
admin.site.register(ShippingPolicy)
admin.site.register(SocialMedia)
admin.site.register(TermsAndConditions)
admin.site.register(PrivacyPolicy)
admin.site.register(ContactSubmission)
admin.site.register(VideoCustomization)
admin.site.register(DomainRequest)
admin.site.register(PurchasedDomain)
admin.site.register(DomainAvailabilityCache)

