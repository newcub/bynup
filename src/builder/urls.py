
from django.urls import path
from . import views
from . import views, admin_views



urlpatterns = [
    # Main pages
    path('templates/', views.template_selection, name='template_selection'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Editor and publishing
    path('editor/<str:template_name>/', views.editor, name='editor'),
    path('editor/<str:template_name>/<str:subdomain>/', views.editor, name='editor_with_page'),
    path('load-template/<str:template_name>/', views.load_template, name='load_template'),
    path('publish/', views.publish_page, name='publish_page'),
     path('recently-viewed/<str:subdomain>/', views.get_recently_viewed_products, name='get_recently_viewed'),


    # path('edit/<str:subdomain>/', views.edit_page, name='edit_page'),
    
    # Component management
    path('get-components/', views.get_components, name='get_components'),
    path('load-component/<str:component_id>/', views.load_component, name='load_component'),
    path('save-component-layout/<str:subdomain>/', views.save_component_layout, name='save_component_layout'),
    
    # Page management
    path('delete-page/<str:subdomain>/', views.delete_page, name='delete_page'),
   
     path('api/delete-background-image/<str:subdomain>/', views.delete_background_image, name='delete_background_image'),
    
    # Content management
    path('manage-products/<str:subdomain>/', views.manage_products, name='manage_products'),
    path('delete-product/<str:subdomain>/<int:product_id>/', views.delete_product, name='delete_product'),
    path('manage-blog-posts/<str:subdomain>/', views.manage_blog_posts, name='manage_blog_posts'),
#     path('manage-forms/<str:subdomain>/', views.manage_forms, name='manage_forms'),
    
    # Domain and tracking
    path('manage-domains/<str:subdomain>/', views.manage_domains, name='manage_domains'),
    path('manage-tracking-codes/<str:subdomain>/', views.manage_tracking_codes, name='manage_tracking_codes'),
    path('delete-tracking-code/<str:subdomain>/<int:code_id>/', views.delete_tracking_code, name='delete_tracking_code'),
    
    # Public form submissions
    path('submit-form/<str:subdomain>/', views.submit_form, name='submit_form'),
     path('manage-forms/<str:subdomain>/', views.manage_form_submissions, name='manage_form_submissions'),

     # Simple product management
    path('manage-products/<str:subdomain>/', views.manage_products, name='manage_products'),
    path('quick-edit-product/<str:subdomain>/<int:product_id>/', views.quick_edit_product, name='quick_edit_product'),
    path('add-product-simple/<str:subdomain>/', views.add_product_simple, name='add_product'),
    path('update-product/<str:subdomain>/<int:product_id>/', views.update_product, name='update_product'),
    path('delete-product/<str:subdomain>/<int:product_id>/', views.delete_product, name='delete_product'),
    path('product-editor/<str:subdomain>/<int:product_id>/', views.single_product_editor, name='product_editor'),
    
    # Category management
    path('manage-product-categories/<str:subdomain>/', views.manage_product_categories, name='manage_product_categories'),
    path('update-category/<str:subdomain>/<int:category_id>/', views.update_category, name='update_category'),
    path('delete-category/<str:subdomain>/<int:category_id>/', views.delete_category, name='delete_category'),
    
    # API endpoints
    path('api/products/<int:product_id>/status/', views.update_product_status, name='update_product_status'),

    path('upload-editor-image/<str:subdomain>/', views.upload_editor_image, name='upload_editor_image'),
     path('upload-editor-media/<str:subdomain>/', views.upload_editor_media, name='upload_editor_media'),


    path('cart/update/<str:subdomain>/', views.update_cart_item, name='update_cart_item'),
    path('cart/increment/<str:subdomain>/', views.increment_cart_item, name='increment_cart_item'),
    path('cart/decrement/<str:subdomain>/', views.decrement_cart_item, name='decrement_cart_item'),
    path('cart/clear/<str:subdomain>/', views.clear_cart, name='clear_cart'),
    path('wishlist/clear/<str:subdomain>/', views.clear_wishlist, name='clear_wishlist'),

    path('cart/add/<str:subdomain>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<str:subdomain>/', views.remove_from_cart, name='remove_from_cart'),
    path('wishlist/add/<str:subdomain>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<str:subdomain>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('cart/data/<str:subdomain>/', views.get_cart_data, name='get_cart_data'),
    path('cart/<str:subdomain>/', views.view_cart, name='view_cart'),
    path('wishlist/<str:subdomain>/', views.view_wishlist, name='view_wishlist'),

    path('review/submit/<str:subdomain>/', views.submit_review, name='submit_review'),
    path('review/helpful/<str:subdomain>/', views.mark_review_helpful, name='mark_review_helpful'),
    path('reviews/<str:subdomain>/<int:product_id>/', views.get_product_reviews, name='get_product_reviews'),
    path('products/', views.product_list_page, name='product_list'),
    path('product/<slug:product_slug>/', views.product_detail_page, name='product_detail'),  

    path('test-auth/', views.test_auth, name='test_auth'),
    path('test-middleware/', views.test_middleware_order, name='test_middleware_order'),


    # Product categories management
    path('manage-product-categories/<str:subdomain>/', 
         views.manage_product_categories, name='manage_product_categories'),
    path('edit-product-category/<str:subdomain>/<int:category_id>/', 
         views.edit_product_category, name='edit_product_category'),
    path('delete-product-category/<str:subdomain>/<int:category_id>/', 
         views.delete_product_category, name='delete_product_category'), 

     # Variant Management URLs
     path('variants-simple/<str:subdomain>/<int:product_id>/', views.manage_variants_simple, name='manage_variants_simple'),
    path('api/add-variant-simple/<str:subdomain>/<int:product_id>/', views.add_variant_simple, name='add_variant_simple'),
    path('api/upload-variant-image/<str:subdomain>/<int:variant_id>/', views.upload_variant_image, name='upload_variant_image'),

    path('variants/<str:subdomain>/<int:product_id>/', views.manage_variants, name='manage_variants'),
    path('api/create-option/<str:subdomain>/', views.create_product_option, name='create_product_option'),
    path('api/bulk-update-variants/<str:subdomain>/<int:product_id>/', views.bulk_update_variants, name='bulk_update_variants'),
    path('api/delete-option/<str:subdomain>/<int:option_id>/', views.delete_option, name='delete_option'),
    path('api/quick-edit-variant/<str:subdomain>/<int:variant_id>/', views.quick_edit_variant, name='quick_edit_variant'),
    path('api/delete-variant/<str:subdomain>/<int:variant_id>/', views.delete_variant, name='delete_variant'),
    path('api/duplicate-variant/<str:subdomain>/<int:variant_id>/', views.duplicate_variant, name='duplicate_variant'),
    path('api/get-variant/<str:subdomain>/<int:product_id>/', views.get_product_variant, name='get_product_variant'), 
    path('manage-tiers/<str:subdomain>/<int:product_id>/', 
     views.manage_product_tiers, 
     name='manage_product_tiers'),

    
     path('upload-video/', views.upload_video, name='upload_video'),
path('save-video-url/', views.save_video_url, name='save_video_url'),
path('remove-video/<str:subdomain>/', views.remove_video, name='remove_video'),



     # CJ Dropshipping URLs
    path('cj-settings/<str:subdomain>/', views.cj_settings, name='cj_settings'),
    path('cj-dashboard/<str:subdomain>/', views.cj_dashboard, name='cj_dashboard'),
    
    # Product Management
    path('cj-search/<str:subdomain>/', views.cj_product_search, name='cj_product_search'),
    path('cj-search-page/<str:subdomain>/', views.cj_search_page, name='cj_search_page'),  # NEW
    path('cj-categories/<str:subdomain>/', views.cj_categories, name='cj_categories'),
    path('cj-product/<str:subdomain>/<str:product_id>/', views.cj_product_details, name='cj_product_details'),
#     path('cj-import-product/<str:subdomain>/<str:cj_product_id>/>', views.cj_import_product, name='cj_import_product'),
    #  path('cj-import-product/<slug:subdomain>/<str:product_id>/', views.cj_import_product, name='cj_import_product'),
    # path('cj-import/<str:subdomain>/', views.cj_import_product, name='cj_import_product'),
    path(
        'cj-import-product/<str:subdomain>/<str:pid>/', 
        views.cj_import_product, 
        name='cj_import_product'
    ),
    
    path('cj-products/<str:subdomain>/', views.cj_products_list, name='cj_products_list'),
    path('cj-sync-product/<str:subdomain>/<str:cj_product_id>/', views.cj_sync_product, name='cj_sync_product'),
    path('cj-bulk-sync/<str:subdomain>/', views.cj_bulk_sync, name='cj_bulk_sync'),
    path('cj/validate-api-key/', views.validate_cj_api_key, name='validate_cj_api_key'),
    
    # Order Management
    path('cj-create-order/<str:subdomain>/', views.cj_create_order, name='cj_create_order'),
    path('cj-orders/<str:subdomain>/', views.cj_orders_list, name='cj_orders'),
    path('cj-order/<str:subdomain>/<int:order_id>/', views.cj_order_detail, name='cj_order_detail'),
    path('cj-check-order/<str:subdomain>/<int:order_id>/', views.cj_check_order_status, name='cj_check_order_status'),
    
    # Monitoring & Logs
    path('cj-sync-logs/<str:subdomain>/', views.cj_sync_logs, name='cj_sync_logs'),
    
    # Webhook (no authentication required)
    path('webhooks/cj/<str:subdomain>/', views.cj_webhook, name='cj_webhook'),
    # Public page (this should be the last pattern)
      # Variant Grouping URLs
    path('product-grouping/<str:subdomain>/<int:product_id>/', 
         views.product_grouping_view, 
         name='product_grouping_view'),
    
    path('api/update-grouping/<str:subdomain>/<int:product_id>/', 
         views.update_product_grouping, 
         name='update_product_grouping'),
    
    path('api/auto-detect-groups/<str:subdomain>/<int:product_id>/', 
         views.auto_detect_groups, 
         name='auto_detect_groups'),
    
    path('api/manual-group/<str:subdomain>/<int:product_id>/', 
         views.manual_group_variants, 
         name='manual_group_variants'),
    
    path('api/delete-group/<str:subdomain>/<int:product_id>/<int:group_id>/', 
         views.delete_variant_group, 
         name='delete_variant_group'),
    
    path('api/get-variant-options/<str:subdomain>/', 
         views.get_variant_by_options, 
         name='get_variant_by_options'),

     path('api/apply-grouping/<str:subdomain>/<int:product_id>/', 
         views.apply_grouping, 
         name='apply_grouping'),
    
    path('api/restore-original/<str:subdomain>/<int:product_id>/', 
         views.restore_original_product, 
         name='restore_original_product'),
    
    path('api/auto-detect-groups/<str:subdomain>/<int:product_id>/', 
         views.auto_detect_groups, 
         name='auto_detect_groups'),

     # Color Palette System
    path('api/color-palettes/', views.get_color_palettes, name='get_color_palettes'),
    path('api/color-palettes/<int:palette_id>/', views.get_palette_detail, name='get_palette_detail'),
    path('api/apply-color-palette/<str:subdomain>/', views.apply_color_palette, name='apply_color_palette'),
    path('api/page-palette/<str:subdomain>/', views.get_page_palette, name='get_page_palette'),
    path('api/reset-page-palette/<str:subdomain>/', views.reset_page_palette, name='reset_page_palette'),
    # Template Color Variable Discovery
    path('api/template-color-variables/<str:template_name>/', 
         views.get_template_color_variables, 
         name='get_template_color_variables'),
    
    # Enhanced color palette application
    path('api/apply-color-palette/<str:subdomain>/', 
         views.apply_color_palette, 
         name='apply_color_palette'),

    # NEW: Global palette color update
    path('api/update-palette-color/<str:subdomain>/', 
         views.update_palette_color, 
         name='update_palette_color'),
    
    # NEW: Scan color usage
    path('api/scan-color-usage/<str:subdomain>/', 
         views.scan_page_color_usage, 
         name='scan_color_usage'),

     path('currency-settings/<str:subdomain>/', 
     views.currency_settings, 
     name='currency_settings'),

     # Shipping policy management and social media management
     path('shipping-policy/<str:subdomain>/edit/', views.edit_shipping_policy, name='edit_shipping_policy'),
     path('shipping-policy/<str:subdomain>/', views.public_shipping_policy, name='public_shipping_policy'),
     path('social-media/<str:subdomain>/', views.manage_social_media, name='manage_social_media'),

     # Terms & Privacy URLs
     path('terms/<str:subdomain>/edit/', views.edit_terms, name='edit_terms'),
     path('terms/<str:subdomain>/', views.public_terms, name='public_terms'),
     path('privacy/<str:subdomain>/edit/', views.edit_privacy, name='edit_privacy'),
     path('privacy/<str:subdomain>/', views.public_privacy, name='public_privacy'),
     # Add to your builder/urls.py

     path('api/check-subdomain/', views.check_subdomain_availability, name='check_subdomain'),
     # builder/urls.py - Add these new URLs
     path('upload-image/', views.upload_image, name='upload_image'),
     path('check-image-status/<str:subdomain>/', views.check_image_status, name='check_image_status'),

     path('get-csrf-token/', views.get_csrf_token, name='get_csrf_token'),

     # path('manage/<str:subdomain>/', views.website_management, name='website_management'),


     path('api/storage-info/', views.get_storage_info, name='storage_info'),
     path('api/storage-info/', views.api_storage_info, name='api_storage_info'),

          # Support page
     path('support/', views.support_page, name='support'),
     path('contact/', views.contact_page, name='contact'),
     path('contact/submit/', views.submit_contact, name='submit_contact'),
     path('about/', views.about_page, name='about'),
     # Legal pages
    path('privacy/', views.privacy_policy, name='privacy'),
    path('terms/', views.terms_of_service, name='terms'),

    path('demo/', views.demo_page, name='demo'),
    path('onboarding/', views.onboarding_wizard, name='onboarding'),
    path('onboarding/launch-editor/', views.launch_editor, name='launch_editor'),
    path('templates/api/', views.get_templates_api, name='templates_api'),

     # Copywriting System URLs
    path('api/copy/template/<str:template_name>/', views.get_template_copy, name='get_template_copy'),
    path('api/copy/page/<str:subdomain>/<str:page_name>/', views.get_page_copy, name='get_page_copy'),
    path('api/copy/save/<str:subdomain>/', views.save_copy_changes, name='save_copy_changes'),
    path('api/copy/export/<str:subdomain>/', views.export_copy_json, name='export_copy_json'),
    path('api/copy/import/<str:subdomain>/', views.import_copy_json, name='import_copy_json'),
    path('api/copy/bulk-import/<str:subdomain>/', views.bulk_import_copy, name='bulk_import_copy'),
    path('api/copy/ai-prompt/<str:subdomain>/', views.generate_ai_prompt, name='generate_ai_prompt'),
    path('api/copy/apply-ai/<str:subdomain>/', views.apply_ai_copy, name='apply_ai_copy'),
    path('api/copy/extract/<str:template_name>/', views.extract_template_copy, name='extract_template_copy'),
    path('api/copy/list-templates/', views.list_templates_copy, name='list_templates_copy'),
    path('api/copy/stats/<str:subdomain>/', views.get_copy_stats, name='get_copy_stats'),
    
    # Copy Editor UI
    path('copy-editor/<str:subdomain>/', views.copy_editor_view, name='copy_editor'),

      path('api/memory/status/', views.memory_status, name='memory_status'),
    path('api/memory/test-public/', views.memory_test_public, name='memory_test_public'),
    path('api/memory/test-auth/', views.memory_test_auth, name='memory_test_auth'),


        # Domain management
         path('domains/<str:subdomain>/', views.domains_page, name='domains_page'),
    path('domains/search/<str:subdomain>/', views.search_domain, name='search_domain'),
    path('domains/request/<str:subdomain>/', views.request_domain, name='request_domain'),
    path('domains/list/<str:subdomain>/', views.list_domain_requests, name='list_domain_requests'),
     
         # Staff-only admin dashboard for domain fulfillment
     # Staff-only dashboard for domain fulfillment (uses /staff/ to avoid Django admin collision)
     path('staff/domains/queue/', admin_views.admin_domain_queue, name='admin_domain_queue'),
     path('staff/domains/in-progress/', admin_views.admin_domain_in_progress, name='admin_domain_in_progress'),
     path('staff/domains/history/', admin_views.admin_domain_history, name='admin_domain_history'),
     path('staff/domains/action/<int:request_id>/', admin_views.admin_domain_action, name='admin_domain_action'),

     path('staff/<str:subdomain>/', views.manage_website, name='manage_website'),


    path('', views.public_page, name='public_page'),
]