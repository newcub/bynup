

from decimal import Decimal
from sqlite3 import IntegrityError
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta
from django.template import engines
from django.template import TemplateDoesNotExist
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, F
from payments.decorators import (
    pro_required, business_required, paid_plan_required,
    check_website_limit, check_product_limit, check_form_submission_limit,
    custom_domain_required, remove_branding_required
)
from payments.decorators import get_user_subscription
from payments.models import Subscription
from payments.decorators import check_storage_before_upload
from payments.storage import get_user_storage_usage, format_bytes, get_storage_limit
from django.db.models import Avg
import json
import base64
import uuid
import re
import os
from django.conf import settings

from builder.utils.color_extractor import TemplateColorExtractor

from .models import *
from .models import  ProductDisplayMode,VariantGroup

@login_required
@custom_domain_required
def manage_domains(request, subdomain):
    """Manage custom domains for a published page"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    if request.method == 'POST':
        custom_domain = request.POST.get('custom_domain', '').strip().lower()
        is_active = request.POST.get('is_custom_domain_active') == 'on'
        
        # Validate domain
        if custom_domain:
            domain_pattern = r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$'
            if not re.match(domain_pattern, custom_domain):
                messages.error(request, 'Please enter a valid domain name (e.g., mystore.com)')
                return redirect('manage_domains', subdomain=subdomain)
            
            # Check if domain is already taken
            existing = PublishedPage.objects.filter(custom_domain=custom_domain).exclude(id=page.id).first()
            if existing:
                messages.error(request, f'Domain {custom_domain} is already in use by another store.')
                return redirect('manage_domains', subdomain=subdomain)
        
        page.custom_domain = custom_domain if custom_domain else None
        page.is_custom_domain_active = is_active if custom_domain else False
        page.save()
        
        if custom_domain and is_active:
            messages.success(request, f'Custom domain {custom_domain} activated successfully!')
        elif custom_domain:
            messages.info(request, f'Custom domain {custom_domain} saved but not activated.')
        else:
            messages.info(request, 'Custom domain removed. Using subdomain.')
        
        return redirect('manage_domains', subdomain=subdomain)
    
    return render(request, 'builder/manage_domains.html', {
        'page': page,
    })

@login_required
@custom_domain_required
def domains_page(request, subdomain):
    """Render the new 'Get a Domain' page."""
    page = get_object_or_404(
        PublishedPage, subdomain=subdomain, user=request.user
    )
    limits = get_user_limits_status(request.user)
    return render(request, 'builder/domains.html', {
        'page': page,
        'domain_limits': limits['domains'],
        'SITE_DOMAIN': getattr(settings, 'SITE_DOMAIN', 'bynup.store'),
    })


@login_required
def manage_blog_posts(request, subdomain):
    """Manage blog posts for a published page - user must own it"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Filter by category if provided
    category_filter = request.GET.get('category', 'all')
    if category_filter != 'all':
        blog_posts = page.blog_posts.filter(category=category_filter)
    else:
        blog_posts = page.blog_posts.all()
    
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        excerpt = request.POST.get('excerpt')
        category = request.POST.get('category', 'home')
        featured_image = request.FILES.get('featured_image')
        
        blog_post = BlogPost(
            page=page,
            title=title,
            content=content,
            excerpt=excerpt,
            category=category
        )
        
        if featured_image:
            blog_post.featured_image = featured_image
        
        blog_post.save()
        return redirect('manage_blog_posts', subdomain=subdomain)
    
    return render(request, 'builder/manage_blog_posts.html', {
        'page': page,
        'blog_posts': blog_posts,
        'current_category': category_filter
    })

# @login_required
# def manage_forms(request, subdomain):
#     """Manage form submissions for a published page - user must own it"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
#     form_submissions = page.form_submissions.all()
    
#     return render(request, 'builder/manage_forms.html', {
#         'page': page,
#         'form_submissions': form_submissions
#     })


@csrf_exempt
@check_form_submission_limit
def submit_form(request, subdomain):
    """Handle form submissions from published pages"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain)
            form_name = request.POST.get('form_name', 'contact')
            
            # Collect all form data
            form_data = {}
            for key, value in request.POST.items():
                if key != 'csrfmiddlewaretoken' and key != 'form_name':
                    form_data[key] = value
            
            # Create form submission
            submission = FormSubmission.objects.create(
                page=page,
                form_name=form_name,
                submitted_data=form_data,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')

            )
            
            # Optional: Send email notification
            # send_form_notification(page, submission)
            
            return JsonResponse({'success': True, 'message': 'Form submitted successfully'})
        
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})




def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@login_required
def manage_form_submissions(request, subdomain):
    """Display form submissions for a store"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get filter parameters
    form_name = request.GET.get('form_name', '')
    date_range = request.GET.get('date_range', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    submissions = page.form_submissions.all()
    
    # Apply filters
    if form_name:
        submissions = submissions.filter(form_name=form_name)
    
    if date_range:
        today = timezone.now().date()
        if date_range == 'today':
            submissions = submissions.filter(submitted_at__date=today)
        elif date_range == 'week':
            week_ago = today - timedelta(days=7)
            submissions = submissions.filter(submitted_at__date__gte=week_ago)
        elif date_range == 'month':
            month_ago = today - timedelta(days=30)
            submissions = submissions.filter(submitted_at__date__gte=month_ago)
        elif date_range == 'year':
            year_ago = today - timedelta(days=365)
            submissions = submissions.filter(submitted_at__date__gte=year_ago)
    
    if search:
        submissions = submissions.filter(
            Q(submitted_data__icontains=search)
        )
    
    # Order by most recent
    submissions = submissions.order_by('-submitted_at')
    
    # Pagination
    paginator = Paginator(submissions, 20)
    page_number = request.GET.get('page')
    submissions_page = paginator.get_page(page_number)
    
    # Get unique form names for filter dropdown
    form_names = page.form_submissions.values_list('form_name', flat=True).distinct()
    
    # Calculate stats
    submissions_count = submissions.count()
    monthly_count = submissions.filter(submitted_at__date__gte=timezone.now().date() - timedelta(days=30)).count()
    unique_contacts = submissions.values('submitted_data__email').distinct().count()
    response_rate = 85  # Placeholder - implement actual logic
    
    context = {
        'page': page,
        'submissions': submissions_page,
        'form_names': form_names,
        'submissions_count': submissions_count,
        'monthly_count': monthly_count,
        'unique_contacts': unique_contacts,
        'response_rate': response_rate,
    }
    
    return render(request, 'builder/manage_forms.html', context)


from django.urls import reverse
# In your views.py, add this import and decorator
from .decorators import debug_authentication
from django.conf import settings

def landing_page(request):
    """
    Professional landing page for bynUp website builder
    Called when no published page is found for the domain
    """
    return render(request, 'builder/landing.html', {
        'site_name': 'bynUp',
        'year': timezone.now().year,
    })



@debug_authentication
def public_page(request):
    """Render published page based on domain type with file-based components"""
    if not hasattr(request, 'published_page') or not request.published_page:
        # raise Http404("Page not found or domain not configured")
        return landing_page(request)
    page = request.published_page
    print(f"🌐 Rendering public page: {page.brand_name} ({page.subdomain})")

    # Determine current page from URL
    current_page = 'home'  # Default
    site_domain=settings.SITE_DOMAIN
    
    # Check URL parameters first
    if request.GET.get('page'):
        current_page = request.GET.get('page')
    # Check path for pretty URLs (e.g., /about/, /products/)
    elif request.path != '/':
        path_parts = request.path.strip('/').split('/')
        if path_parts and path_parts[0]:
            current_page = path_parts[0]

    print(f"📄 Current page determined: {current_page}")

    # Load page-specific data from page_customizations
    home_page='home'
    # home_page='products'
    home_page_data = page.page_customizations.get('home', {})
    # page_data = {**home_page_data, **page.page_customizations.get(current_page, {})}
    # print(f"Page data is {page_data}")
    # page_data = page.page_customizations.get(current_page and home_page, {})
    # print(f"Page data is {page_data}")
    # Load both
    home_page_data = page.page_customizations.get('home', {})
    current_page_data = page.page_customizations.get(current_page, {})

    # Print raw data structure
    print("\n" + "="*50)
    print(f"HOMEPAGE DATA STRUCTURE:")
    print(f"Type: {type(home_page_data)}")
    print(f"Keys: {list(home_page_data.keys())}")
    if 'text_contents' in home_page_data:
        print(f"Homepage text_contents keys: {list(home_page_data['text_contents'].keys())}")
        print(f"Homepage text_contents values: {home_page_data['text_contents']}")

    print("\n" + "="*50)
    print(f"CURRENT PAGE ({current_page}) DATA STRUCTURE:")
    print(f"Type: {type(current_page_data)}")
    print(f"Keys: {list(current_page_data.keys())}")
    if 'text_contents' in current_page_data:
        print(f"Current page text_contents keys: {list(current_page_data['text_contents'].keys())}")
        print(f"Current page text_contents values: {current_page_data['text_contents']}")

    # Now merge properly
    page_data = {}

    # Copy all homepage data first
    for key, value in home_page_data.items():
        if isinstance(value, dict):
            page_data[key] = value.copy()  # Deep copy for nested dicts
        else:
            page_data[key] = value

    # Overlay with current page data
    for key, value in current_page_data.items():
        if key in page_data and isinstance(page_data[key], dict) and isinstance(value, dict):
            # Merge nested dictionaries
            page_data[key].update(value)
        else:
            page_data[key] = value

    print("\n" + "="*50)
    print(f"MERGED DATA STRUCTURE:")
    print(f"Keys: {list(page_data.keys())}")
    if 'text_contents' in page_data:
        print(f"Merged text_contents keys: {list(page_data['text_contents'].keys())}")
        print(f"Merged text_contents values: {page_data['text_contents']}")
    print("="*50 + "\n")
    home_page_data = page.page_customizations.get(home_page, {})
        # GET HIDDEN SECTIONS - This is crucial!
    hidden_sections = page_data.get('hidden_sections', {})

    # print(f"📦 Loaded page data for {current_page}:", {
    #     'texts': len(page_data.get('text_contents', {})),
    #     'styles': len(page_data.get('style_customizations', {})),
    #     'components': len(page_data.get('component_layout', [])),
    #     'component_customizations': len(page_data.get('component_customizations', []))
    # })

    # Load component layout from page data
    components_data = []
    component_layout = page_data.get('component_layout', [])
    component_customizations_list = page_data.get('component_customizations', [])
    # print(f"Component customizations: {len(component_customizations_list)}")
    if component_layout:
        # print(f"🧩 Loading {len(component_layout)} components from layout")
        for component_ref in component_layout:
            try:
                component = load_component_from_file(component_ref['component_id'])
                if component:
                    # Get customizations for this component instance
                    customizations = {}
                    for comp_custom in component_customizations_list:
                        if comp_custom.get('instance_id') == component_ref.get('instance_id'):
                            customizations = comp_custom.get('customizations', {})
                            break

                    # print(f"🔧 Processing component {component_ref['instance_id']} with {len(customizations.get('texts', {}))} text customizations")

                    # Apply ALL customizations (both text and styles) to the HTML
                    processed_html = apply_component_customizations(
                        component['html_content'],
                        customizations
                    )

                    components_data.append({
                        'instance_id': component_ref['instance_id'],
                        'component_id': component_ref['component_id'],
                        'drop_zone': component_ref.get('drop_zone', 'end'),
                        'html_content': mark_safe(processed_html),  # Mark as safe after processing
                        'customizations': customizations,
                    })
                    
            except Exception as e:
                print(f"❌ Error loading component {component_ref['component_id']}: {e}")
   
    else:
        print("ℹ️ No component layout found for page")

    # Load other customizations
    text_contents = page_data.get('text_contents', {})
    home_text_contents = home_page_data.get('text_contents', {})
    style_customizations = page_data.get('style_customizations', {})
    # home_style_customizations = home_page_data.get('style_customizations', {})
    # home_style_customizations_2 = home_page_data.get('style_customizations', {})
    print("===================================================================")
    # print("Customization is",home_style_customizations_2)
    print("===================================================================")
    # home_style_customizations_1 = home_page_data.get('style_customizations', {})

    

    background_images = page_data.get('background_images', {})
    home_background_images = home_page_data.get('background_images', {})
    home_background_images_1 = home_page_data.get('background_images', {})
    # ===== ADD THIS: Load icon customizations =====
    icon_customizations = page_data.get('icon_customizations', {})
    home_icon_customizations = home_page_data.get('icon_customizations', {})
    print(f"🎨 Loaded {len(icon_customizations)} icon customizations for {current_page}")
      # NEW: Prepare dynamic style ranges
    section_range = list(range(1, 500))  # Support up to 50 sections
    component_range = list(range(1, 500))  # Support up to 20 components per section

    # Other dynamic data
    # products = page.products.all().order_by('-created_at') #if current_page == 'products' else []
    products = page.products.filter(is_active=True, status='active').order_by('-created_at')
    categories = page.product_categories.all().order_by('-id')
      # Get requested category from URL
   # Get requested category from URL
    category_slug = request.GET.get('category')
    current_category = None
    filtered_products = None
    print(f"Category slug is: {category_slug}")

    # If on products page, handle category filtering
    if current_page == 'products':
        # Get all active categories for this page
        categories = ProductCategory.objects.filter(page=page, is_active=True)
        
        # If category slug provided, get that category
        if category_slug:
            current_category = get_object_or_404(
                ProductCategory,
                page=page,
                slug=category_slug,
                is_active=True
            )
            filtered_products = current_category.products.filter(is_active=True, status='active')
        else:
            filtered_products = page.products.filter(is_active=True, status='active')
    blog_posts = page.blog_posts.filter(is_published=True)
    tracking_codes = page.tracking_codes.filter(is_active=True)

    # ===== LOAD VIDEO CUSTOMIZATIONS FROM DATABASE =====
    video_customizations = {}
    
    # Get videos for the current page
    video_objects = VideoCustomization.objects.filter(
        page=page,
        page_name=current_page
    )
    
    print(f"🎥 Found {video_objects.count()} video customizations for page '{current_page}'")
    
    for video in video_objects:
        video_customizations[video.element_id] = {
            'video_url': video.video_file.url if video.video_file else video.video_url,
            'poster_url': video.poster_image.url if video.poster_image else None,
            'alt_text': video.alt_text or '',
            'autoplay': video.autoplay,
            'loop': video.loop,
            'muted': video.muted,
            'controls': video.controls,
            'show_play_button': video.show_play_button,
            'element_id': video.element_id
        }
        print(f"  ✅ Loaded video: {video.element_id}")

    # Load background images from database
    # ===== CRITICAL: Load background images from database =====
    background_images = {}
    
    # Method 1: Load from BackgroundImage model (most reliable)
    bg_objects = BackgroundImage.objects.filter(page=page)
    print(f"🖼️ Loading {bg_objects.count()} background images from database")
    
    for bg in bg_objects:
        if bg.image:
            # Generate proper URL for the image
            image_url = bg.image.url
            # Get the element_id (already stored as clean numeric ID)
            element_id = bg.element_id
            
            background_images[element_id] = {
                'image_url': image_url,
                'element_id': bg.element_id,
                'has_image': True
            }
            print(f"✅ Background image loaded from DB: {element_id} -> {image_url}")
    
    # Method 2: Fallback to page_customizations if needed
    if not background_images:
        background_images = page_data.get('background_images', {})
        print(f"📦 Loaded {len(background_images)} background images from page_customizations")
    # # Load image customizations from database
    # image_customizations = {}
    # image_objects = page.image_customizations.filter(page_name=current_page)
    # print(f"🖼️ Loading {image_objects.count()} custom images for {current_page}")
    
     # ===== CRITICAL: Load image customizations from database =====
    # Get images for the current page
    image_customizations = {}
    
    # Query the ImageCustomization model for this page and current page
    image_objects = ImageCustomization.objects.filter(
        page=page, 
        page_name=current_page
    )
    
    print(f"🖼️ Found {image_objects.count()} image customizations for page '{current_page}'")
    
    for img in image_objects:
        if img.image:
            # Generate the full URL for the image
            image_url = img.image.url
            image_customizations[img.element_id] = {
                'image_url': image_url,
                'alt_text': img.alt_text or '',
                'element_id': img.element_id
            }
            print(f"  ✅ Loaded image: {img.element_id} -> {image_url}")

    # Also load home page images if needed for context
    home_image_customizations = {}
    if current_page != 'home':
        home_images = ImageCustomization.objects.filter(
            page=page, 
            page_name='home'
        )
        for img in home_images:
            if img.image:
                home_image_customizations[img.element_id] = {
                    'image_url': img.image.url,
                    'alt_text': img.alt_text or ''
                }

   

    # anonymouse user check

    # if request.user.is_authenticated:
    #     cart = Cart.objects.filter(user=request.user, page=page).first()
    # else:
    #     # For guest users, use session key
    #     if not request.session.session_key:
    #         request.session.create()
    #     cart = Cart.objects.filter(session_key=request.session.session_key, page=page).first()

    if request.user.is_authenticated:
        # print(f"✅ User is authenticated: {request.user.username} (ID: {request.user.id})")
        # print(f"📧 User email: {request.user.email}")
        
        # Try to get user cart first
        cart = Cart.objects.filter(user=request.user, page=page).first()
        
        # If no user cart, check for session cart and transfer
        if not cart and request.session.session_key:
            session_cart = Cart.objects.filter(
                session_key=request.session.session_key,
                page=page,
                user__isnull=True
            ).first()
            if session_cart:
                session_cart.user = request.user
                session_cart.session_key = None
                session_cart.save()
                cart = session_cart
    else:
        # print(f"👤 User is NOT authenticated (guest)")
        # For guest users, use session key
        if not request.session.session_key:
            request.session.create()
        cart = Cart.objects.filter(
            session_key=request.session.session_key, 
            page=page,
            user__isnull=True
        ).first()

    
    if request.user.is_authenticated:
        # print(f"✅ User is authenticated: {request.user.username} (ID: {request.user.id})")
        # print(f"📧 User email: {request.user.email}")
        
        # Try to get user cart first
        wishlist = Wishlist.objects.filter(user=request.user, page=page).first()
        
        # If no user cart, check for session cart and transfer
        if not cart and request.session.session_key:
            session_wishlist = Wishlist.objects.filter(
                session_key=request.session.session_key,
                page=page,
                user__isnull=True
            ).first()
            if session_wishlist:
                session_wishlist.user = request.user
                session_wishlist.session_key = None
                session_wishlist.save()
                session_wishlist = session_wishlist
    else:
        # print(f"👤 User is NOT authenticated (guest)")
        # For guest users, use session key
        if not request.session.session_key:
            request.session.create()
        wishlist = Wishlist.objects.filter(
            session_key=request.session.session_key, 
            page=page,
            user__isnull=True
        ).first()


    # wishlist = Wishlist.objects.filter(user=request.user, page=page)
    print(f"Whish list is {wishlist}")
    # wish_price_total= sum(WishlistItem.product.price for whish_item in wishlist)
    # wish_items=WishlistItem.objects.all()
    # wish_price_total = wish_items.aggregate(total=Sum('product__price'))['total'] or 0
    # wish_low_stock_items = WishlistItem.objects.filter(product__quantity__lt=5)  

    if not request.user.is_anonymous:

        wish_user=request.user
        print(f"Wish user is: {wish_user}")
        wishlist_qs = Wishlist.objects.filter(user=wish_user, page=page)

        wishlist_items = WishlistItem.objects.filter(
            wishlist__in=wishlist_qs
        )

        wish_price_total = wishlist_items.aggregate(
            total=Sum('product__price')
        )['total'] or 0

        wish_low_stock_items = WishlistItem.objects.filter(wishlist__page=page,product__quantity__lt=5)  
        wish_low_stock_count=wish_low_stock_items.count()

    else:
        wish_price_total=0
        wish_low_stock_count=0
        wishlist_items={}


    variants = ProductVariant.objects.filter(
    product__page=page,
    cj_vid__isnull=False
    )

    print(f"Variants are {variants}")


     # ===== CRITICAL: Load active color palette =====
    active_palette_colors = {}
    active_palette = None
    
    # Try to get from PublishedPage first (cached)
    if page.active_palette and page.active_palette_colors:
        active_palette = page.active_palette
        active_palette_colors = page.active_palette_colors
        print(f"🎨 Using cached palette: {active_palette.name} with {len(active_palette_colors)} colors")
    else:
        # Fallback to PageColorPalette
        active_palette_record = page.color_palettes.filter(is_active=True).first()
        if active_palette_record:
            active_palette = active_palette_record.palette
            active_palette_colors = active_palette_record.applied_colors
            
            # Cache it on the PublishedPage for next time
            page.active_palette = active_palette
            page.active_palette_colors = active_palette_colors
            page.save(update_fields=['active_palette', 'active_palette_colors'])
            print(f"🎨 Loaded and cached palette: {active_palette.name}")
    
    # Determine current page from URL
    current_page = 'home'
    if request.GET.get('page'):
        current_page = request.GET.get('page')
    elif request.path != '/':
        path_parts = request.path.strip('/').split('/')
        if path_parts and path_parts[0]:
            current_page = path_parts[0]
    
    # Load page-specific data from page_customizations
    page_data = page.page_customizations.get(current_page, {})
    
    print(f"🎨 Public page has active palette: {active_palette.name if active_palette else 'None'}")
    print(f"🎨 Colors available: {len(active_palette_colors)} variables")
    print(f"🎨 Colors available: {active_palette_colors} ")

    # Generate CSS variables string for the template
    palette_css_variables = ""
    if active_palette_colors:
        css_lines = [":root {"]
        for var_name, color_data in active_palette_colors.items():
            # Handle both string and dict formats
            if isinstance(color_data, dict):
                hex_value = color_data.get('hex', '')
            else:
                hex_value = color_data
            
            if hex_value:
                css_lines.append(f"    --{var_name}: {hex_value};")
        css_lines.append("}")
        palette_css_variables = "\n".join(css_lines)
        print(f"🎨 Generated CSS variables:\n{palette_css_variables}")

    # ===== CRITICAL: Load any overridden palette colors =====
    if page.active_palette:
        # Check if there are custom overrides in the database
        from .models import CustomColorOverride
        overrides = CustomColorOverride.objects.filter(
            page=page, 
            palette=page.active_palette
        )
        
        for override in overrides:
            if page.active_palette_colors and override.variable_name in page.active_palette_colors:
                # Update the cached colors with the override
                if isinstance(page.active_palette_colors[override.variable_name], dict):
                    page.active_palette_colors[override.variable_name]['hex'] = override.hex_value
                    page.active_palette_colors[override.variable_name]['rgb'] = override.rgb_value or ''
                else:
                    page.active_palette_colors[override.variable_name] = override.hex_value

        
        
        # Save the updated colors
        page.save(update_fields=['active_palette_colors', 'updated_at'])

    # # Get or create tiers for this product
    # tiers = product.tiers.filter(is_active=True).order_by('display_order', 'quantity')
    
    # # If no tiers exist, create default tiers from product price
    # if not tiers.exists():
    #     base_price = product.price
    #     # Create default tier objects (not saved to DB)
    #     tier_data = [
    #         {'quantity': 1, 'price_per_unit': base_price, 'badge_text': '', 'is_default': False},
    #         {'quantity': 2, 'price_per_unit': round(base_price * 0.95, 2), 'badge_text': 'Save 5%', 'is_default': True},
    #         {'quantity': 3, 'price_per_unit': round(base_price * 0.90, 2), 'badge_text': '🔥 Best Value', 'is_default': False},
    #     ]
        
    #     # Convert to list of dicts for the template
    #     tiers_list = []
    #     for td in tier_data:
    #         tiers_list.append({
    #             'quantity': td['quantity'],
    #             'price_per_unit': td['price_per_unit'],
    #             'total_price': td['price_per_unit'] * td['quantity'],
    #             'badge_text': td['badge_text'],
    #             'is_default': td['is_default'],
    #             'savings': (base_price * td['quantity']) - (td['price_per_unit'] * td['quantity'])
    #         })
    #     tiers = tiers_list
    # else:
    #     # Convert queryset to list of dicts for consistent template handling
    #     tiers_list = []
    #     base_tier = product.tiers.filter(is_active=True).order_by('quantity').first()
    #     base_price = base_tier.price_per_unit if base_tier else product.price
        
    #     for tier in tiers:
    #         tiers_list.append({
    #             'id': tier.id,
    #             'quantity': tier.quantity,
    #             'price_per_unit': tier.price_per_unit,
    #             'total_price': tier.total_price,
    #             'badge_text': tier.badge_text,
    #             'is_default': tier.is_default,
    #             'savings': (base_price * tier.quantity) - tier.total_price
    #         })
    #     tiers = tiers_list
    
    # Add tiers to context
    # context['tiers'] = tiers
    # ============ TIERED PRICING - ONLY IF TIERS EXIST ============
    # ============ TIERED PRICING ============
    # Get the first product to use for tiered pricing

    first_product = page.products.filter(is_active=True, status='active').first()

    tiers = []
    if first_product:
        # Get the original product price
        original_price = float(first_product.price)
        
        # Get tiers from the database
        product_tiers = first_product.tiers.filter(is_active=True).order_by('display_order', 'quantity')
        
        # ALWAYS add the first tier as the original product price (quantity = 1)
        tiers.append({
            'quantity': 1,
            'price_per_unit': original_price,
            'total_price': original_price,
            'badge_text': '',
            'is_default': False,
            'savings': 0,
            'is_original': True,
            'tier_id': None
        })
        
        # If there are tiers in the database, add them
        if product_tiers.exists():
            for tier in product_tiers:
                # Convert Decimal to float
                tier_quantity = int(tier.quantity)
                tier_price_per_unit = float(tier.price_per_unit)
                tier_total = float(tier.total_price)
                
                # Calculate savings vs original price
                savings = float((original_price * tier_quantity) - tier_total)
                
                tiers.append({
                    'id': tier.id,
                    'quantity': tier_quantity,
                    'price_per_unit': tier_price_per_unit,
                    'total_price': tier_total,
                    'badge_text': tier.badge_text,
                    'is_default': True,
                    'savings': savings,
                    'is_original': False,
                    'tier_id': tier.id
                })
        
        # Mark the SECOND tier as default
        if len(tiers) > 1:
            tiers[1]['is_default'] = True

    for product in products:
            reviews = product.reviews.all()
            total_reviews = reviews.count()
            
            if total_reviews > 0:
                # ✅ Use Avg from django.db.models
                avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
            else:
                avg_rating = 0
            
            # Attach review_stats to the product object
            product.review_stats = {
                'average_rating': float(avg_rating or 0),
                'total_reviews': total_reviews
            }
    # anonymouse user check end
    context = {
        'page': page,
        'site_domain':site_domain,
        'current_page': current_page,
        'components': components_data,
        'text_contents': text_contents,
        'home_text_contents':home_text_contents,
        # 'home_style_customizations': home_style_customizations,
        'style_customizations': style_customizations,
        'background_images': background_images,
        'home_background_images':home_background_images,
        # ===== CRITICAL: Pass image customizations to template =====
        'image_customizations': image_customizations,
        'home_image_customizations': home_image_customizations,  
        'icon_customizations': icon_customizations,
        'home_icon_customizations': home_icon_customizations,
        # 'products': products,
        # Products - Use filtered products if category is selected
        'products': filtered_products if current_page == 'products' and filtered_products else products,
        # 'filtered_products': filtered_products,
        'categories':categories,
# ===== VIDEO AND IMAGE CUSTOMIZATIONS =====
        'video_customizations': video_customizations,
        'image_customizations': image_customizations,
        'home_image_customizations': home_image_customizations,        'variants':variants,
        'first_product': first_product,
        'tiers': tiers,  # Will be empty list if no tiers exist

        'current_category': current_category,
        # 'products': filtered_products,
        'all_products_count': page.products.filter(is_active=True).count(),

        'blog_posts': blog_posts,
        'tracking_codes': tracking_codes,
        'domain_type': getattr(request, 'domain_type', 'subdomain'),
        'has_components': len(components_data) > 0,
        'hidden_sections': hidden_sections,  # Pass to template

         # NEW: Dynamic style ranges
        'section_range': section_range,
        'component_range': component_range,
        'cart':cart,
        'wishlist':wishlist,
        'wish_price_total':wish_price_total,
        'wish_low_stock_count':wish_low_stock_count,
        'wishlist_items':wishlist_items,

        # ===== CRITICAL: Pass palette data to template =====
        'active_palette': active_palette,
        'active_palette_colors': active_palette_colors,
        'palette_css_variables': palette_css_variables,  # Pre-generated CSS string

        'show_auth_links': True,  # Enable auth widgets on this page
        'registration_url': reverse('accounts:website_register', args=[page.subdomain]),
        'login_url': reverse('accounts:universal_login') + f'?website_id={page.id}',
    }


    # Determine correct template path
    template_path = f'builder/public_templates/{page.template_name}/{current_page}.html'
    print(f"🎯 Rendering template: {template_path}")

    try:
        return render(request, template_path, context)
    except TemplateDoesNotExist:
        # Fallback to single page template
        fallback_path = f'builder/public_templates/{page.template_name}.html'
        print(f"⚠️ Template not found, using fallback: {fallback_path}")
        return render(request, fallback_path, context)

import re
def apply_component_customizations(html_content, customizations, background_images=None):
    """
    Apply customizations to component HTML
    """
    if not customizations and not background_images:
        return html_content
    
    try:
        processed_html = html_content
        
        # Apply text customizations
        if 'texts' in customizations:
            for element_id, content in customizations['texts'].items():
                try:
                    escaped_content = content.replace('"', '&quot;').replace("'", "&#39;")
                    pattern = f'(<[^>]*data-text="{element_id}"[^>]*>)(.*?)(</[^>]*>)'
                    
                    def replace_content(match):
                        return f'{match.group(1)}{escaped_content}{match.group(3)}'
                    
                    processed_html = re.sub(pattern, replace_content, processed_html, flags=re.DOTALL)
                except Exception as e:
                    print(f"⚠️ Error replacing text for {element_id}: {e}")
        
        # Apply style customizations
        if 'styles' in customizations:
            for element_id, styles in customizations['styles'].items():
                try:
                    if not styles:
                        continue
                    
                    style_parts = []
                    for prop, value in styles.items():
                        if value and value.strip():
                            css_prop = prop.replace('_', '-')
                            style_parts.append(f'{css_prop}: {value}')
                    
                    if not style_parts:
                        continue
                    
                    style_string = '; '.join(style_parts)
                    pattern = f'(<[^>]*data-section="{element_id}"[^>]*)(>)'
                    
                    def add_style_to_element(match):
                        element_start = match.group(1)
                        closing_bracket = match.group(2)
                        
                        if 'style="' in element_start:
                            style_pattern = r'style="([^"]*)"'
                            def append_to_style(style_match):
                                existing_styles = style_match.group(1)
                                combined = f'{existing_styles}; {style_string}'
                                return f'style="{combined}"'
                            updated_element = re.sub(style_pattern, append_to_style, element_start)
                            return f'{updated_element}{closing_bracket}'
                        else:
                            return f'{element_start} style="{style_string}"{closing_bracket}'
                    
                    processed_html = re.sub(pattern, add_style_to_element, processed_html)
                except Exception as e:
                    print(f"⚠️ Error applying styles for {element_id}: {e}")
        
        # Apply background images
        if background_images:
            for element_id, image_data in background_images.items():
                try:
                    if not image_data:
                        continue
                    
                    image_url = image_data
                    if isinstance(image_data, dict) and image_data.get('image_url'):
                        image_url = image_data['image_url']
                    
                    if not image_url or image_url == 'none':
                        continue
                    
                    bg_style = f'background-image: url("{image_url}"); background-size: cover; background-position: center; background-repeat: no-repeat;'
                    pattern = f'(<[^>]*data-section="{element_id}"[^>]*)(>)'
                    
                    def add_background_image(match):
                        element_start = match.group(1)
                        closing_bracket = match.group(2)
                        
                        if 'style="' in element_start:
                            style_pattern = r'style="([^"]*)"'
                            def append_background(style_match):
                                existing_styles = style_match.group(1)
                                cleaned_styles = re.sub(r'background-image[^;]*;?', '', existing_styles)
                                cleaned_styles = re.sub(r'background-size[^;]*;?', '', cleaned_styles)
                                cleaned_styles = re.sub(r'background-position[^;]*;?', '', cleaned_styles)
                                cleaned_styles = re.sub(r'background-repeat[^;]*;?', '', cleaned_styles)
                                cleaned_styles = cleaned_styles.strip().strip(';')
                                
                                if cleaned_styles:
                                    combined = f'{cleaned_styles}; {bg_style}'
                                else:
                                    combined = bg_style
                                return f'style="{combined}"'
                            updated_element = re.sub(style_pattern, append_background, element_start)
                            return f'{updated_element}{closing_bracket}'
                        else:
                            return f'{element_start} style="{bg_style}"{closing_bracket}'
                    
                    processed_html = re.sub(pattern, add_background_image, processed_html)
                except Exception as e:
                    print(f"⚠️ Error applying background image for {element_id}: {e}")
        
        return processed_html
        
    except Exception as e:
        print(f"❌ Error in apply_component_customizations: {e}")
        import traceback
        traceback.print_exc()
        return html_content
    
def find_element_by_data_attribute(html, attr_name, attr_value):
    """Helper to find element with specific data attribute"""
    pattern = f'<[^>]*{attr_name}="{attr_value}"[^>]*>.*?</[^>]*>'
    match = re.search(pattern, html, re.DOTALL)
    return match.group(0) if match else None
    
def generate_component_styles(component_customizations):
    """Generate CSS styles from component customizations"""
    styles = []
    
    for instance_id, customizations in component_customizations.items():
        if 'styles' in customizations:
            selector = f'[data-instance-id="{instance_id}"]'
            style_rules = []
            
            for prop, value in customizations['styles'].items():
                if value:  # Only add non-empty values
                    css_prop = prop.replace('_', '-')
                    style_rules.append(f'{css_prop}: {value};')
            
            if style_rules:
                styles.append(f'{selector} {{ {" ".join(style_rules)} }}')
    
    return '\n'.join(styles)

def load_component_from_file(component_id):
    """
    Load component HTML from file system
    """
    try:
        components_path = os.path.join(settings.BASE_DIR, 'builder', 'components')
        manifest_path = os.path.join(components_path, 'component_manifest.json')
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        for category in manifest.get('categories', []):
            for component in category.get('components', []):
                if component.get('id') == component_id:
                    component_file = os.path.join(components_path, component.get('file', ''))
                    if os.path.exists(component_file):
                        with open(component_file, 'r') as f:
                            return {
                                'id': component.get('id'),
                                'name': component.get('name'),
                                'html_content': f.read()
                            }
        return None
    except Exception as e:
        print(f"Error loading component {component_id} from file: {e}")
        return None


def get_component_customizations(page, instance_id):
    """Get customizations for a component instance"""
    try:
        customization = ComponentCustomization.objects.get(
            page=page,
            component_instance_id=instance_id
        )
        print(f"📦 Loaded customizations for {instance_id}: {customization.customizations}")
        return customization.customizations
    except ComponentCustomization.DoesNotExist:
        print(f"ℹ️ No customizations found for component {instance_id}")
        return {}
    


def template_selection(request):
    """Main page showing available templates organized by categories"""
    categories = TemplateCategory.objects.filter(
        is_active=True,
        templates__is_active=True
    ).distinct().prefetch_related('templates')
    
    # Get featured templates (no specific category)
    featured_templates = Template.objects.filter(
        is_active=True
    ).order_by('-display_order', 'title')
    
    context = {
        'categories': categories,
        'featured_templates': featured_templates,
    }
    return render(request, 'builder/template_selection.html', context)



# builder/views.py - Fixed load_template view
def load_template(request, template_name):
    """Load template HTML as snippet for editor"""
    try:
        context = {}
        page_subdomain = request.GET.get('edit')
        current_page = request.GET.get('page', 'home')  # NEW: Get current page
        
        if page_subdomain and request.user.is_authenticated:
            try:
                page = PublishedPage.objects.get(subdomain=page_subdomain, user=request.user)
                context['is_editing_published'] = True
                context['page'] = page
                context['current_page'] = current_page  # NEW
                context['brand_name'] = page.brand_name  # ✅ CHANGE 1: Added this line

                print(f"🔄 Loading template for editing published page: {page.brand_name}")
                 # Load existing data for the CURRENT PAGE
                page_data = page.page_customizations.get(current_page, {})
                
                text_contents = page_data.get('text_contents', {})
                style_customizations = page_data.get('style_customizations', {})
                background_images = page_data.get('background_images', {})
                icon_customizations = page_data.get('icon_customizations', {})
                component_layout = page_data.get('component_layout', [])
                component_customizations = page_data.get('component_customizations', [])

                # Load all existing data (same as in editor view)
                text_contents = {}
                for tc in page.text_contents.all():
                    key_simple = tc.element_id.split('-')[-1] if '-' in tc.element_id else tc.element_id
                    key_full = f"editable_text_{tc.element_id.replace('-', '_')}"
                    key_original = tc.element_id
                    text_contents[key_simple] = tc.content
                    text_contents[key_full] = tc.content
                    text_contents[key_original] = tc.content

                style_customizations = {}
                for sc in page.style_customizations.all():
                    key_simple = sc.element_id.split('-')[-1] if '-' in sc.element_id else sc.element_id
                    key_full = f"editable_section_{sc.element_id.replace('-', '_')}"
                    key_original = sc.element_id
                    style_data = {
                        'background_color': sc.background_color or '',
                        'text_color': sc.text_color or '',
                        'font_size': sc.font_size or '',
                        'font_family': sc.font_family or '',
                        'font_weight': sc.font_weight or '',
                        'padding': sc.padding or '',
                        'margin': sc.margin or '',
                        'border_radius': sc.border_radius or '',
                        'border': sc.border or '',
                    }
                    style_customizations[key_simple] = style_data
                    style_customizations[key_full] = style_data
                    style_customizations[key_original] = style_data

                # Load background images
                background_images = {}
                bg_objects = page.background_images.all()
                print(f"🖼️ Loading {bg_objects.count()} background images")
                
                for bg in bg_objects:
                        # Generate proper URL for the image
                        image_url = bg.image.url if bg.image else None
                        
                        # Handle different element ID formats
                        if bg.element_id.isdigit():
                            key_simple = bg.element_id
                            key_full = f"editable_section_{bg.element_id}"
                            key_original = f"editable-section-{bg.element_id}"
                        else:
                            key_simple = bg.element_id.split('-')[-1] if '-' in bg.element_id else bg.element_id
                            key_full = bg.element_id.replace('-', '_')
                            key_original = bg.element_id

                        image_data = {
                            'image_url': image_url,
                            'element_id': bg.element_id,
                            'has_image': bool(bg.image)
                        }
                        
                        background_images[key_simple] = image_data
                        background_images[key_full] = image_data
                        background_images[key_original] = image_data
                        
                        print(f"✅ Background image loaded: {bg.element_id} -> {image_url}")

                icon_customizations = {}
                for ic in page.icon_customizations.all():
                    key = ic.element_id.replace('-', '_')
                    icon_customizations[key] = {
                        'icon_class': ic.icon_class or '',
                        'color': ic.color or '',
                        'font_size': ic.font_size or ''
                    }

                # Load component data
                component_layout = page.component_layout if page.component_layout else []
                component_customizations = []
                
                for comp_ref in component_layout:
                    try:
                        comp_customization = ComponentCustomization.objects.get(
                            page=page,
                            component_instance_id=comp_ref['instance_id']
                        )
                        component_customizations.append({
                            'instance_id': comp_ref['instance_id'],
                            'component_id': comp_ref['component_id'],
                            'drop_zone': comp_ref.get('drop_zone', 'end'),
                            'display_order': comp_ref.get('display_order', 0),
                            'customizations': comp_customization.customizations
                        })
                    except ComponentCustomization.DoesNotExist:
                        component_customizations.append({
                            'instance_id': comp_ref['instance_id'],
                            'component_id': comp_ref['component_id'],
                            'drop_zone': comp_ref.get('drop_zone', 'end'),
                            'display_order': comp_ref.get('display_order', 0),
                            'customizations': {}
                        })

                # Pass data to template
                context['editor_text_contents'] = text_contents
                context['editor_style_customizations'] = style_customizations
                context['editor_background_images'] = background_images
                context['editor_icon_customizations'] = icon_customizations
                context['editor_component_layout'] = component_layout
                context['editor_component_customizations'] = component_customizations

                print(f"✅ Loaded existing data for template: {len(component_layout)} components")

            except PublishedPage.DoesNotExist:
                context['is_editing_published'] = False
                print(f"❌ Page {page_subdomain} not found for template loading")
        else:
            context['is_editing_published'] = False
            
        # NEW: Load the specific page for multi-page templates
        template_html = load_multi_page_template(template_name, current_page)
        
        # ✅ CHANGE 2: Replace {brand} placeholder with actual brand name
        brand_name = context.get('brand_name', 'My Store')
        template_html = template_html.replace('{brand}', brand_name)
        
        return HttpResponse(template_html)    
        # return render(request, f'builder/templates/{template_name}.html', context)
        
    except Exception as e:
        print(f"ERROR in load_template: {e}")
        import traceback
        traceback.print_exc()
        return HttpResponse('Template not found', status=404)

def load_multi_page_template_with_palette(template_name, page_name, context):
    """
    Load specific page from multi-page template with palette applied.
    ✅ Injects CSS variables for the palette.
    """
    try:
        # Get the template HTML
        template_html = render_to_string(
            f'builder/public_templates/{template_name}/{page_name}.html',
            context
        )
        
        # ✅ Inject palette CSS variables into the template
        palette_css = context.get('palette_css_variables', '')
        if palette_css:
            # Insert the palette CSS at the beginning of the head or body
            # Look for <style> tags or inject at the top
            if '<style>' in template_html:
                # Insert after the first <style> tag
                template_html = template_html.replace(
                    '<style>',
                    f'<style>\n/* Palette CSS */\n{palette_css}\n'
                )
            elif '</head>' in template_html:
                # Insert before </head>
                template_html = template_html.replace(
                    '</head>',
                    f'<style>\n/* Palette CSS */\n{palette_css}\n</style>\n</head>'
                )
            else:
                # Inject at the top
                template_html = f'<style>\n/* Palette CSS */\n{palette_css}\n</style>\n{template_html}'
        
        return template_html
        
    except TemplateDoesNotExist:
        # Fallback to single page template
        template_html = render_to_string(
            f'builder/public_templates/{template_name}.html',
            context
        )
        # Apply palette CSS to fallback as well
        palette_css = context.get('palette_css_variables', '')
        if palette_css:
            if '<style>' in template_html:
                template_html = template_html.replace(
                    '<style>',
                    f'<style>\n/* Palette CSS */\n{palette_css}\n'
                )
            elif '</head>' in template_html:
                template_html = template_html.replace(
                    '</head>',
                    f'<style>\n/* Palette CSS */\n{palette_css}\n</style>\n</head>'
                )
            else:
                template_html = f'<style>\n/* Palette CSS */\n{palette_css}\n</style>\n{template_html}'
        return template_html
    
@login_required
def editor(request, template_name, subdomain=None):
    """
    Main editor interface - handles both new pages and editing existing pages.
    MODIFIED: Detects onboarding and preloads all data automatically.
    """

    print(f"\n📝 [editor] ===== VIEW CALLED =====")
    print(f"   template_name: {template_name}")
    print(f"   subdomain: {subdomain}")
    print(f"   user: {request.user.username}")

    context = {
        'template_name': template_name,
        'SITE_DOMAIN': getattr(settings, 'SITE_DOMAIN', 'bynup.store'),
    }
    
    # Get current page and available pages
    current_page = request.GET.get('page', 'home')
    available_pages = get_template_pages(template_name)
    context['current_page'] = current_page
    context['available_pages'] = available_pages
    context['is_multi_page'] = len(available_pages) > 1
    
    # ============ CHECK FOR ONBOARDING ============
    is_onboarding = request.GET.get('onboarding', 'false') == 'true'
    onboarding_brand = request.GET.get('brand', '')
    context['is_onboarding'] = is_onboarding
    context['onboarding_brand'] = onboarding_brand
    
    # ============ HANDLE EXISTING PAGE OR CREATE NEW ============
    page_subdomain = request.GET.get('edit') or subdomain
    page = None
    is_new_page = False
    
    if page_subdomain and request.user.is_authenticated:
        try:
            page = PublishedPage.objects.get(subdomain=page_subdomain, user=request.user)
            print(f"\n📄 [editor] Page found:")
            print(f"   ID: {page.id}")
            print(f"   brand_name: '{page.brand_name}'")
            print(f"   subdomain: '{page.subdomain}'")
            print(f"   template: {page.template_name}")
            context['page'] = page
            context['is_editing_published'] = True
            print(f"✅ Found existing page: {page.brand_name} ({page.subdomain})")
            
        except PublishedPage.DoesNotExist:
            context['is_editing_published'] = False
            print(f"❌ Page {page_subdomain} not found for editing")
            
            # 🔑 If this is onboarding, create the page automatically
            if is_onboarding:
                try:
                    template = Template.objects.get(name=template_name)
                    
                    # Create page with onboarding data
                    page = PublishedPage.objects.create(
                        user=request.user,
                        template=template,
                        template_name=template_name,
                        brand_name=onboarding_brand or 'My Store',
                        subdomain=page_subdomain,
                        is_published=False,
                        currency_code='USD',
                    )
                    
                    context['page'] = page
                    context['is_editing_published'] = True
                    is_new_page = True
                    
                    print(f"✅ Created new page during onboarding: {page.brand_name} ({page.subdomain})")
                    
                    # Show welcome notification via context
                    context['onboarding_success'] = True
                    
                except Template.DoesNotExist:
                    print(f"❌ Template {template_name} not found")
                    messages.error(request, f'Template "{template_name}" not found.')
                    return redirect('template_selection')
                except Exception as e:
                    print(f"❌ Failed to create page during onboarding: {e}")
                    messages.error(request, f'Error creating page: {str(e)}')
                    return redirect('template_selection')
            else:
                # Not onboarding - redirect to template selection
                messages.warning(request, 'Page not found. Please create a new page.')
                return redirect('template_selection')
    else:
        context['is_editing_published'] = False
        print("ℹ️ No subdomain provided or user not authenticated")
    
    # ============ IF NO PAGE YET, SHOW EMPTY EDITOR ============
    if not page:
        return render(request, 'builder/editor.html', context)
    
    # ============ LOAD ALL EXISTING DATA ============
    
    # Get current page data from page_customizations
    page_data = page.page_customizations.get(current_page, {})
    
    # Initialize data containers
    text_contents = {}
    style_customizations = {}
    background_images = {}
    icon_customizations = {}
    image_customizations = {}
    component_layout = []
    component_customizations = []
    
    # ===== 1. LOAD TEXT CONTENTS =====
    text_contents_from_db = page.text_contents.all()
    for tc in text_contents_from_db:
        key_simple = tc.element_id.split('-')[-1] if '-' in tc.element_id else tc.element_id
        key_full = f"editable_text_{tc.element_id.replace('-', '_')}"
        key_original = tc.element_id
        
        text_contents[key_simple] = tc.content
        text_contents[key_full] = tc.content
        text_contents[key_original] = tc.content
    
    # Also load from page_customizations
    if 'text_contents' in page_data:
        for key, value in page_data['text_contents'].items():
            text_contents[key] = value
    
    # ===== 2. LOAD STYLE CUSTOMIZATIONS =====
    style_customizations_from_db = page.style_customizations.all()
    for sc in style_customizations_from_db:
        clean_id = extract_numeric_id(sc.element_id)
        if clean_id:
            style_data = {
                'background_color': sc.background_color or '',
                'text_color': sc.text_color or '',
                'font_size': sc.font_size or '',
                'font_family': sc.font_family or '',
                'font_weight': sc.font_weight or '',
                'padding': sc.padding or '',
                'margin': sc.margin or '',
                'border_radius': sc.border_radius or '',
                'border': sc.border or '',
                'display': sc.display or '',
            }
            style_customizations[clean_id] = style_data
            
            # Also store by original ID
            style_customizations[sc.element_id] = style_data
    
    # Load from page_customizations (overrides)
    if 'style_customizations' in page_data:
        for key, value in page_data['style_customizations'].items():
            if key not in style_customizations:
                style_customizations[key] = value
            else:
                # Merge
                style_customizations[key].update(value)
    
    # ===== 3. LOAD BACKGROUND IMAGES =====
    bg_objects = page.background_images.all()
    for bg in bg_objects:
        clean_id = extract_numeric_id(bg.element_id)
        if clean_id and bg.image:
            image_data = {
                'image_url': bg.image.url,
                'element_id': bg.element_id,
                'has_image': True,
                'page_name': current_page,
            }
            background_images[clean_id] = image_data
            background_images[bg.element_id] = image_data
    
    # Load from page_customizations
    if 'background_images' in page_data:
        for key, value in page_data['background_images'].items():
            if key not in background_images:
                background_images[key] = value
    
    # ===== 4. LOAD ICON CUSTOMIZATIONS =====
    icon_objects = page.icon_customizations.all()
    for ic in icon_objects:
        key = ic.element_id.replace('-', '_')
        icon_data = {
            'icon_class': ic.icon_class or '',
            'color': ic.color or '',
            'font_size': ic.font_size or '',
            'page_name': current_page,
        }
        icon_customizations[key] = icon_data
        icon_customizations[ic.element_id] = icon_data
    
    # Load from page_customizations
    if 'icon_customizations' in page_data:
        for key, value in page_data['icon_customizations'].items():
            if key not in icon_customizations:
                icon_customizations[key] = value
    
    # ===== 5. LOAD IMAGE CUSTOMIZATIONS =====
    image_objects = ImageCustomization.objects.filter(page=page, page_name=current_page)
    for img in image_objects:
        if img.image:
            image_customizations[img.element_id] = {
                'image_url': img.image.url,
                'alt_text': img.alt_text or '',
                'element_id': img.element_id,
                'page_name': img.page_name,
            }
    
    # Load from page_customizations
    if 'image_customizations' in page_data:
        for key, value in page_data['image_customizations'].items():
            if key not in image_customizations:
                image_customizations[key] = value
    
    # ===== 6. LOAD COMPONENT LAYOUT =====
    component_layout = page.component_layout if page.component_layout else []
    
    # Load from page_customizations
    if 'component_layout' in page_data and page_data['component_layout']:
        component_layout = page_data['component_layout']
    
    # ===== 7. LOAD COMPONENT CUSTOMIZATIONS =====
    comp_customs = ComponentCustomization.objects.filter(page=page)
    for comp in comp_customs:
        comp_data = {
            'instance_id': comp.component_instance_id,
            'component_id': comp.component_id,
            'drop_zone': comp.drop_zone,
            'display_order': comp.display_order,
            'customizations': comp.customizations,
        }
        component_customizations.append(comp_data)
    
    # Load from page_customizations
    if 'component_customizations' in page_data:
        for comp_data in page_data['component_customizations']:
            # Check if already exists
            exists = any(c.get('instance_id') == comp_data.get('instance_id') 
                        for c in component_customizations)
            if not exists:
                component_customizations.append(comp_data)
    
    # ===== 8. LOAD COLOR PALETTE =====
    active_palette = None
    active_palette_colors = {}
    
    # Check if page has active palette cached
    if page.active_palette and page.active_palette_colors:
        active_palette = page.active_palette
        active_palette_colors = page.active_palette_colors
        print(f"🎨 Using cached palette: {active_palette.name}")
    else:
        # Try to get from PageColorPalette
        active_palette_record = page.color_palettes.filter(is_active=True).first()
        if active_palette_record:
            active_palette = active_palette_record.palette
            active_palette_colors = active_palette_record.applied_colors
            
            # Cache on page
            page.active_palette = active_palette
            page.active_palette_colors = active_palette_colors
            page.save(update_fields=['active_palette', 'active_palette_colors'])
            print(f"🎨 Loaded and cached palette: {active_palette.name}")
    
    # Apply palette colors to context
    context['active_palette'] = active_palette
    context['active_palette_colors'] = active_palette_colors
    
    # Generate CSS variables for palette
    palette_css_variables = ""
    if active_palette_colors:
        css_lines = [":root {"]
        for var_name, color_data in active_palette_colors.items():
            if isinstance(color_data, dict):
                hex_value = color_data.get('hex', '')
            else:
                hex_value = color_data
            if hex_value:
                css_lines.append(f"  --{var_name}: {hex_value};")
        css_lines.append("}")
        palette_css_variables = "\n".join(css_lines)
    context['palette_css_variables'] = palette_css_variables
    
    # ===== 9. BUILD ALL PAGE DATA FOR JAVASCRIPT =====
    all_page_data = {}
    for page_name in available_pages:
        page_specific_data = page.page_customizations.get(page_name, {})
        all_page_data[page_name] = {
            'text_contents': page_specific_data.get('text_contents', {}),
            'style_customizations': page_specific_data.get('style_customizations', {}),
            'background_images': page_specific_data.get('background_images', {}),
            'icon_customizations': page_specific_data.get('icon_customizations', {}),
            'component_layout': page_specific_data.get('component_layout', []),
            'component_customizations': page_specific_data.get('component_customizations', []),
            'image_customizations': page_specific_data.get('image_customizations', {}),
        }
    
    # ===== 10. LOAD PRODUCTS FOR EDITOR PREVIEW =====
    products = page.products.filter(is_active=True, status='active').order_by('-created_at')[:10]
    categories = page.product_categories.filter(is_active=True)
    
    # ===== 11. SETUP CONTEXT =====
    context.update({
        'page':page,
        # Editor data
        'editor_text_contents': text_contents,
        'editor_style_customizations': style_customizations,
        'editor_background_images': background_images,
        'editor_icon_customizations': icon_customizations,
        'editor_image_customizations': image_customizations,
        'editor_component_layout': component_layout,
        'editor_component_customizations': component_customizations,
        
        # All page data for JavaScript
        'existing_page_data': all_page_data,
        
        # JSON for JavaScript
        'existing_text_contents': json.dumps(text_contents),
        'existing_style_customizations': json.dumps(style_customizations),
        'existing_background_images': json.dumps(background_images),
        'existing_icon_customizations': json.dumps(icon_customizations),
        'existing_image_customizations': json.dumps(image_customizations),
        'existing_component_layout': json.dumps(component_layout),
        'existing_component_customizations': json.dumps(component_customizations),
        
        # Products
        'products': products,
        'categories': categories,
        
        # Flags
        'is_new_page': is_new_page,
        'show_auth_links': True,
        'registration_url': reverse('accounts:website_register', args=[page.subdomain]) if hasattr(page, 'subdomain') else '#',
        'login_url': reverse('accounts:universal_login') + f'?website_id={page.id}',
    })
    
    print(f"📊 Editor loaded with: {len(text_contents)} texts, {len(style_customizations)} styles, "
          f"{len(component_layout)} components, {len(image_customizations)} images")
    
    if is_onboarding and is_new_page:
        print(f"🎉 Onboarding complete! New page created: {page.brand_name}")
        messages.success(request, f'🎉 Welcome {page.brand_name}! Your store is ready to edit.')
    
    return render(request, 'builder/editor.html', context)


def get_components(request):
    """Load components from files"""
    try:
        components_path = os.path.join(settings.BASE_DIR, 'builder', 'components')
        manifest_path = os.path.join(components_path, 'component_manifest.json')
        
        print(f"📁 Looking for manifest at: {manifest_path}")
        
        if not os.path.exists(manifest_path):
            return JsonResponse({'error': f'Manifest not found at {manifest_path}'}, status=404)
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        print(f"📦 Found manifest with {len(manifest.get('categories', []))} categories")
        
        # Load HTML content for each component
        for category in manifest.get('categories', []):
            for component in category.get('components', []):
                component_file = os.path.join(components_path, component['file'])
                print(f"📄 Loading component file: {component_file}")
                
                if os.path.exists(component_file):
                    with open(component_file, 'r') as f:
                        component['html_content'] = f.read()
                else:
                    component['html_content'] = f'<div class="alert alert-warning">Component file {component_file} not found</div>'
                    print(f"⚠️ Component file not found: {component_file}")
        
        return JsonResponse(manifest)
        
    except Exception as e:
        print(f"❌ Error loading components: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def load_component(request, component_id):
    """Load a single component by ID"""
    try:
        components_path = os.path.join(settings.BASE_DIR, 'builder', 'components')
        manifest_path = os.path.join(components_path, 'component_manifest.json')
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Find the component
        for category in manifest.get('categories', []):
            for component in category.get('components', []):
                if component['id'] == component_id:
                    component_file = os.path.join(components_path, component['file'])
                    
                    if os.path.exists(component_file):
                        with open(component_file, 'r') as f:
                            html_content = f.read()
                        
                        return JsonResponse({
                            'id': component['id'],
                            'name': component['name'],
                            'html_content': html_content
                        })
        
        return JsonResponse({'error': 'Component not found'}, status=404)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@login_required
def save_component_layout(request, subdomain):
    """Save component layout and customizations"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            data = json.loads(request.body)
            
            # Save component layout
            page.component_layout = data.get('component_layout', [])
            page.save()
            
            # Save individual component customizations
            for component_data in data.get('component_customizations', []):
                ComponentCustomization.objects.update_or_create(
                    page=page,
                    component_instance_id=component_data['instance_id'],
                    defaults={
                        'component_id': component_data['component_id'],
                        'drop_zone': component_data.get('drop_zone', 'end'),
                        'display_order': component_data.get('display_order', 0),
                        'customizations': component_data.get('customizations', {})
                    }
                )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})



# Add this to views.py
from django.views.decorators.http import require_http_methods

@csrf_exempt
@login_required
@require_http_methods(["POST"])
def delete_background_image(request, subdomain):
    """
    Immediately delete a background image from the database
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        data = json.loads(request.body)
        
        element_id = data.get('element_id')
        page_name = data.get('page_name', 'home')
        
        if not element_id:
            return JsonResponse({
                'success': False, 
                'error': 'Element ID is required'
            })
        
        # Extract numeric ID for consistency
        clean_element_id = extract_numeric_id(element_id)
        print(f"🗑️ Deleting background image for element: {clean_element_id} on page: {page_name}")
        
        # STEP 1: Delete from BackgroundImage model
        deleted_count, _ = BackgroundImage.objects.filter(
            page=page,
            element_id=clean_element_id
        ).delete()
        
        print(f"   Deleted {deleted_count} records from BackgroundImage model")
        
        # STEP 2: Remove from page_customizations JSON
        if page_name in page.page_customizations:
            # Remove from background_images
            if 'background_images' in page.page_customizations[page_name]:
                if clean_element_id in page.page_customizations[page_name]['background_images']:
                    del page.page_customizations[page_name]['background_images'][clean_element_id]
                    print(f"   Removed from page_customizations[{page_name}]['background_images']")
            
            # Also remove from style_customizations if present
            if 'style_customizations' in page.page_customizations[page_name]:
                if clean_element_id in page.page_customizations[page_name]['style_customizations']:
                    # Remove background-image related styles
                    style_dict = page.page_customizations[page_name]['style_customizations'][clean_element_id]
                    for key in ['background_image', 'background-image', 'background-size', 
                               'background-position', 'background-repeat']:
                        if key in style_dict:
                            del style_dict[key]
                    print(f"   Cleaned style_customizations for {clean_element_id}")
        
        # STEP 3: Save the updated page_customizations
        page.save(update_fields=['page_customizations'])
        print(f"   Saved updated page_customizations")
        
        # STEP 4: Also clear from the page's active palette cache if needed
        if page.active_palette_colors and f'bg-{clean_element_id}' in page.active_palette_colors:
            del page.active_palette_colors[f'bg-{clean_element_id}']
            page.save(update_fields=['active_palette_colors'])
        
        return JsonResponse({
            'success': True,
            'message': 'Background image deleted successfully',
            'deleted_count': deleted_count,
            'element_id': clean_element_id
        })
        
    except PublishedPage.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'Page not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False, 
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        print(f"❌ Error in delete_background_image: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)

# Add these imports at the top with your existing imports
import threading
import queue
import time
from django.db import transaction
from django.core.cache import cache

# builder/views.py - Complete publish_page with update_or_create

# @csrf_exempt
# @login_required
# def publish_page(request):
#     # Always return JSON, even on errors
#     response_data = {'success': False}
#     """Handle page publishing - using update_or_create (slower but safer)"""
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             print(f"📥 Received publish request")
            
#             # Get all data
#             template_name = data.get('template_name')
#             all_page_data = data.get('all_page_data', {})
#             current_page = data.get('current_page', 'home')
#             brand_name = data.get('brand_name')
#             subdomain = data.get('subdomain')
#             page_subdomain = data.get('page_subdomain')
            
#             # Get or create template
#             template = Template.objects.get_or_create(
#                 name=template_name,
#                 defaults={
#                     'title': template_name.replace('_', ' ').title(),
#                     'template_file': template_name,
#                     'is_active': True
#                 }
#             )[0]
            
#             # Get or create page
#             if page_subdomain:
#                 # Update existing page
#                 page = get_object_or_404(PublishedPage, subdomain=page_subdomain, user=request.user)
#                 page.brand_name = brand_name or page.brand_name
#                 print(f"✅ Updating existing page: {page.brand_name}")
#             else:
#                 # Create new page
#                 page, created = PublishedPage.objects.get_or_create(
#                     subdomain=subdomain,
#                     defaults={
#                         'user': request.user,
#                         'brand_name': brand_name,
#                         'template': template,
#                         'template_name': template_name,
#                         'is_published': True,
#                         'current_page': current_page,
#                         'page_customizations': {}
#                     }
#                 )
#                 if created:
#                     print(f"✅ Created new page: {page.brand_name}")
#                 else:
#                     print(f"✅ Found existing page: {page.brand_name}")
            
#             # Update page fields
#             page.template = template
#             page.template_name = template_name
#             page.is_published = True
#             page.current_page = current_page
#             page.page_customizations = all_page_data
#             page.save()
            
#             # ===== PROCESS ALL PAGE DATA USING UPDATE_OR_CREATE =====
            
#             # Track counts for logging
#             text_count = 0
#             style_count = 0
#             icon_count = 0
#             component_count = 0
            
#             # Process each page in the multi-page site
#             for page_name, page_data in all_page_data.items():
#                 print(f"   📄 Processing {page_name} page...")
                
#                 # ===== 1. TEXT CONTENTS =====
#                 text_contents = page_data.get('text_contents', {})
#                 for element_id, content in text_contents.items():
#                     clean_element_id = extract_numeric_id(element_id)
#                     if clean_element_id:
#                         obj, created = TextContent.objects.update_or_create(
#                             page=page,
#                             element_id=clean_element_id,
#                             defaults={'content': content}
#                         )
#                         text_count += 1
#                         if created:
#                             print(f"      ✨ Created text: {clean_element_id}")
                
#                 # ===== 2. STYLE CUSTOMIZATIONS =====
#                 style_customizations = page_data.get('style_customizations', {})
#                 for element_id, styles in style_customizations.items():
#                     clean_element_id = extract_numeric_id(element_id)
#                     if clean_element_id:
#                         # Check if there are any styles to save
#                         has_styles = any(styles.values())
                        
#                         if has_styles:
#                             obj, created = StyleCustomization.objects.update_or_create(
#                                 page=page,
#                                 element_id=clean_element_id,
#                                 defaults={
#                                     'background_color': styles.get('background_color', ''),
#                                     'text_color': styles.get('text_color', ''),
#                                     'font_size': styles.get('font_size', ''),
#                                     'font_family': styles.get('font_family', ''),
#                                     'font_weight': styles.get('font_weight', ''),
#                                     'padding': styles.get('padding', ''),
#                                     'margin': styles.get('margin', ''),
#                                     'border_radius': styles.get('border_radius', ''),
#                                     'border': styles.get('border', ''),
#                                     'display': styles.get('display', ''),
#                                 }
#                             )
#                             style_count += 1
#                             if created:
#                                 print(f"      ✨ Created style: {clean_element_id}")
#                         else:
#                             # Delete if no styles
#                             deleted, _ = StyleCustomization.objects.filter(
#                                 page=page, 
#                                 element_id=clean_element_id
#                             ).delete()
#                             if deleted:
#                                 print(f"      🗑️ Deleted empty style: {clean_element_id}")
                
#                 # ===== 3. BACKGROUND IMAGES (only non-base64) =====
#                 background_images = page_data.get('background_images', {})
#                 for element_id, image_data in background_images.items():
#                     clean_element_id = extract_numeric_id(element_id)
#                     if clean_element_id and image_data:
#                         # Only process if it's a media URL (already saved)
#                         if isinstance(image_data, str) and image_data.startswith('/media/'):
#                             obj, created = BackgroundImage.objects.update_or_create(
#                                 page=page,
#                                 element_id=clean_element_id,
#                                 defaults={'image': image_data}
#                             )
#                             print(f"      🖼️ Updated background image: {clean_element_id}")
                
#                 # ===== 4. ICON CUSTOMIZATIONS =====
#                 icon_customizations = page_data.get('icon_customizations', {})
#                 for element_id, icons in icon_customizations.items():
#                     clean_element_id = extract_numeric_id(element_id)
#                     if clean_element_id:
#                         obj, created = IconCustomization.objects.update_or_create(
#                             page=page,
#                             element_id=clean_element_id,
#                             defaults={
#                                 'icon_class': icons.get('icon_class', ''),
#                                 'color': icons.get('color', ''),
#                                 'font_size': icons.get('font_size', '')
#                             }
#                         )
#                         icon_count += 1
#                         if created:
#                             print(f"      ✨ Created icon: {clean_element_id}")
                
#                 # ===== 5. IMAGE CUSTOMIZATIONS (editable-image elements) =====
#                  # For images, just update metadata (images already in Cloudinary)
#                 image_customizations = page_data.get('image_customizations', {})
#                 for element_id, image_data in image_customizations.items():
#                     if image_data and isinstance(image_data, dict):
#                         # Just update alt text - image already exists from upload
#                         ImageCustomization.objects.filter(
#                             page=page,
#                             element_id=element_id,
#                             page_name=page_name
#                         ).update(
#                             alt_text=image_data.get('alt_text', '')
#                         )
                
#                 # ===== 6. COMPONENT CUSTOMIZATIONS =====
#                 component_customizations = page_data.get('component_customizations', [])
#                 for comp_data in component_customizations:
#                     instance_id = comp_data.get('instance_id')
#                     if instance_id:
#                         obj, created = ComponentCustomization.objects.update_or_create(
#                             page=page,
#                             component_instance_id=instance_id,
#                             defaults={
#                                 'component_id': comp_data.get('component_id'),
#                                 'drop_zone': comp_data.get('drop_zone', 'end'),
#                                 'display_order': comp_data.get('display_order', 0),
#                                 'customizations': comp_data.get('customizations', {})
#                             }
#                         )
#                         component_count += 1
#                         if created:
#                             print(f"      ✨ Created component: {instance_id}")
            
#             # ===== 7. HANDLE DELETED BACKGROUND IMAGES =====
#             for page_name, page_data in all_page_data.items():
#                 deleted_backgrounds = page_data.get('deleted_background_images', [])
#                 for element_id in deleted_backgrounds:
#                     clean_element_id = extract_numeric_id(element_id)
#                     if clean_element_id:
#                         deleted, _ = BackgroundImage.objects.filter(
#                             page=page,
#                             element_id=clean_element_id
#                         ).delete()
#                         if deleted:
#                             print(f"      🗑️ Deleted background image: {clean_element_id}")
            
#             # ===== 8. COLOR PALETTE =====
#             if 'color_palette' in all_page_data.get(current_page, {}):
#                 palette_data = all_page_data[current_page]['color_palette']
#                 try:
#                     palette = ColorPalette.objects.get(id=palette_data.get('palette_id'))
#                     page.active_palette = palette
#                     page.active_palette_colors = palette_data.get('colors', {})
#                     page.save(update_fields=['active_palette', 'active_palette_colors'])
#                     print(f"      🎨 Updated color palette: {palette.name}")
#                 except ColorPalette.DoesNotExist:
#                     pass
            
#             print(f"✅ Successfully published {page.brand_name}")
#             print(f"   📊 Stats - Texts: {text_count}, Styles: {style_count}, Icons: {icon_count}, Components: {component_count}")
            
#             return JsonResponse({
#                 'success': True,
#                 'subdomain': page.subdomain,
#                 'page_url': page.get_absolute_url(),
#                 'message': 'Page published successfully!',
#                 'stats': {
#                     'texts': text_count,
#                     'styles': style_count,
#                     'icons': icon_count,
#                     'components': component_count
#                 }
#             })
            
#         except Exception as e:
#             print(f"❌ Publish error: {str(e)}")
#             import traceback
#             traceback.print_exc()
#             return JsonResponse({'success': False, 'error': str(e)})
    
#     return JsonResponse({'success': False, 'error': 'Invalid request method'})


# builder/views.py - Update your publish_page view with better error handling

# @csrf_exempt
# @login_required
# @check_website_limit
# def publish_page(request):
#     """Handle page publishing - with comprehensive error handling"""
    
#     # Always return JSON, even on errors
#     response_data = {'success': False}
    
#     try:
#         if request.method != 'POST':
#             response_data['error'] = 'Invalid request method'
#             return JsonResponse(response_data, status=405)
        
#         # Log the request for debugging
#         print("=" * 50)
#         print("📥 PUBLISH REQUEST RECEIVED")
#         print(f"User: {request.user.username} (ID: {request.user.id})")
#         print(f"Content-Type: {request.content_type}")
#         print(f"Content-Length: {len(request.body)}")
        
#         # Try to parse JSON
#         try:
#             data = json.loads(request.body)
#             print(f"✅ JSON parsed successfully")
#             print(f"Template: {data.get('template_name')}")
#             print(f"Pages: {list(data.get('all_page_data', {}).keys())}")
#         except json.JSONDecodeError as e:
#             print(f"❌ JSON Parse Error: {e}")
#             print(f"Raw body preview: {request.body[:200]}")
#             response_data['error'] = f'Invalid JSON: {str(e)}'
#             return JsonResponse(response_data, status=400)
        
#         # Get all data
#         template_name = data.get('template_name')
#         all_page_data = data.get('all_page_data', {})
#         current_page = data.get('current_page', 'home')
#         brand_name = data.get('brand_name')
#         subdomain = data.get('subdomain')
#         page_subdomain = data.get('page_subdomain')
        
#         # Validate required fields
#         if not template_name:
#             response_data['error'] = 'Template name is required'
#             return JsonResponse(response_data, status=400)
        
#         # Get or create template
#         template, created = Template.objects.get_or_create(
#             name=template_name,
#             defaults={
#                 'title': template_name.replace('_', ' ').title(),
#                 'template_file': template_name,
#                 'is_active': True
#             }
#         )
#         print(f"✅ Template: {template.name} ({'created' if created else 'existing'})")
        
#         # Get or create page
#         try:
#             if page_subdomain:
#                 page = PublishedPage.objects.get(subdomain=page_subdomain, user=request.user)
#                 print(f"✅ Found existing page: {page.brand_name}")
#                 if brand_name:
#                     page.brand_name = brand_name
#             else:
#                 page, created = PublishedPage.objects.get_or_create(
#                     subdomain=subdomain,
#                     defaults={
#                         'user': request.user,
#                         'brand_name': brand_name,
#                         'template': template,
#                         'template_name': template_name,
#                         'is_published': True,
#                         'current_page': current_page
#                     }
#                 )
#                 print(f"✅ Page {'created' if created else 'found'}: {page.brand_name}")
#         except Exception as e:
#             print(f"❌ Page error: {e}")
#             response_data['error'] = f'Page error: {str(e)}'
#             return JsonResponse(response_data, status=400)
        
#         # Update page
#         page.template = template
#         page.template_name = template_name
#         page.is_published = True
#         page.current_page = current_page
#         page.page_customizations = all_page_data
#         page.save()
        
#         # ===== DELETE OLD DATA =====
#         print("🗑️ Deleting old data...")
#         TextContent.objects.filter(page=page).delete()
#         StyleCustomization.objects.filter(page=page).delete()
#         ComponentCustomization.objects.filter(page=page).delete()
#         IconCustomization.objects.filter(page=page).delete()
#         # Don't delete BackgroundImage or ImageCustomization - they have files
        
#         # ===== SAVE NEW DATA =====
#         print("💾 Saving new data...")
        
#         text_count = 0
#         style_count = 0
#         component_count = 0
#         icon_count = 0
        
#         for page_name, page_data in all_page_data.items():
#             # Text contents
#             # for element_id, content in page_data.get('text_contents', {}).items():
#             #     clean_id = extract_numeric_id(element_id)
#             #     if clean_id:
#             #         TextContent.objects.create(
#             #             page=page,
#             #             element_id=clean_id,
#             #             content=content
#             #         )
#             #         text_count += 1
#             # Save text contents - USE UPDATE_OR_CREATE to avoid duplicates
#             # Save text contents - FAST: Delete all then bulk create
#             text_contents = page_data.get('text_contents', {})
#             print(f"📝 Saving {len(text_contents)} text contents")

#             # Delete ALL existing text contents for this page in one query
#             deleted_count = TextContent.objects.filter(page=page).delete()[0]
#             print(f"  🗑️ Deleted {deleted_count} existing text contents")

#             # Prepare all new objects
#             text_objects = []
#             for element_id, content in text_contents.items():
#                 clean_element_id = extract_numeric_id(element_id)
#                 if clean_element_id:
#                     text_objects.append(
#                         TextContent(
#                             page=page,
#                             element_id=clean_element_id,
#                             content=content
#                         )
#                     )

#             # Bulk create all at once
#             if text_objects:
#                 created_count = TextContent.objects.bulk_create(text_objects)
#                 print(f"  ✅ Bulk created {len(text_objects)} text contents")
#             else:
#                 print(f"  ℹ️ No text contents to save")            
#             # Style customizations

#             # Save style customizations
#             style_customizations = page_data.get('style_customizations', {})
#             for element_id, styles in style_customizations.items():
#                 clean_element_id = extract_numeric_id(element_id)
#                 if clean_element_id:
#                     # Check if any styles have values
#                     has_styles = any(styles.values())
                    
#                     if has_styles:
#                         StyleCustomization.objects.update_or_create(
#                             page=page,
#                             element_id=clean_element_id,
#                             defaults={
#                                 'background_color': styles.get('background_color', ''),
#                                 'text_color': styles.get('text_color', ''),
#                                 'font_size': styles.get('font_size', ''),
#                                 'font_family': styles.get('font_family', ''),
#                                 'font_weight': styles.get('font_weight', ''),
#                                 'padding': styles.get('padding', ''),
#                                 'margin': styles.get('margin', ''),
#                                 'border_radius': styles.get('border_radius', ''),
#                                 'border': styles.get('border', ''),
#                                 'display': styles.get('display', ''),
#                             }
#                         )
#                     else:
#                         # Delete if no styles exist
#                         StyleCustomization.objects.filter(
#                             page=page,
#                             element_id=clean_element_id
#                         ).delete()

           
#             # Save icon customizations - FIXED to handle duplicates
#             icon_customizations = page_data.get('icon_customizations', {})
#             for element_id, icons in icon_customizations.items():
#                 clean_element_id = extract_numeric_id(element_id)
#                 if clean_element_id:
#                     try:
#                         # Use update_or_create instead of create to avoid duplicates
#                         IconCustomization.objects.update_or_create(
#                             page=page,
#                             element_id=clean_element_id,
#                             defaults={
#                                 'icon_class': icons.get('icon_class', ''),
#                                 'color': icons.get('color', ''),
#                                 'font_size': icons.get('font_size', '')
#                             }
#                         )
#                         print(f"✅ Saved icon customization for {clean_element_id}")
#                     except Exception as e:
#                         print(f"❌ Error saving icon for {element_id}: {e}")

#             # Component customizations
#             for comp_data in page_data.get('component_customizations', []):
#                 instance_id = comp_data.get('instance_id')
#                 if instance_id:
#                     ComponentCustomization.objects.create(
#                         page=page,
#                         component_instance_id=instance_id,
#                         component_id=comp_data.get('component_id'),
#                         drop_zone=comp_data.get('drop_zone', 'end'),
#                         display_order=comp_data.get('display_order', 0),
#                         customizations=comp_data.get('customizations', {})
#                     )
#                     component_count += 1
        
#         print(f"✅ Saved: {text_count} texts, {style_count} styles, {icon_count} icons, {component_count} components")
        
#         # Handle color palette
#         if 'color_palette' in all_page_data.get(current_page, {}):
#             palette_data = all_page_data[current_page]['color_palette']
#             try:
#                 palette = ColorPalette.objects.get(id=palette_data.get('palette_id'))
#                 page.active_palette = palette
#                 page.active_palette_colors = palette_data.get('colors', {})
#                 page.save(update_fields=['active_palette', 'active_palette_colors'])
#                 print(f"🎨 Applied palette: {palette.name}")
#             except Exception as e:
#                 print(f"⚠️ Palette error: {e}")
        
#         print(f"✅ Publish complete for {page.brand_name}")
        
#         return JsonResponse({
#             'success': True,
#             'subdomain': page.subdomain,
#             'page_url': page.get_absolute_url(),
#             'message': 'Page published successfully!'
#         })
        
#     except Exception as e:
#         print(f"❌ CRITICAL ERROR: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         response_data['error'] = str(e)
#         return JsonResponse(response_data, status=500)
       

# builder/views.py

# builder/views.py - Complete fixed publish_page view

@csrf_exempt
@login_required
@check_website_limit
def publish_page(request):
    """
    Handle page publishing with optimized database operations.
    ✅ FIXED: Preserves brand_name instead of overwriting with subdomain
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        print(f"\n📤 [publish_page] ===== PUBLISH REQUEST =====")
        print(f"   brand_name from request: '{data.get('brand_name')}'")
        print(f"   subdomain from request: '{data.get('subdomain')}'")
        print(f"   page_subdomain from request: '{data.get('page_subdomain')}'")
        
        # Extract data
        template_name = data.get('template_name')
        all_page_data = data.get('all_page_data', {})
        current_page = data.get('current_page', 'home')
        brand_name = data.get('brand_name')
        subdomain = data.get('subdomain')
        page_subdomain = data.get('page_subdomain')
        
        print(f"\n🔑 [publish_page] CRITICAL VALUES:")
        print(f"   brand_name: '{brand_name}'")
        print(f"   subdomain: '{subdomain}'")
        print(f"   page_subdomain: '{page_subdomain}'")
        
        if not template_name:
            return JsonResponse({'success': False, 'error': 'Template name required'}, status=400)
        
        try:
            with transaction.atomic():
                # Get or create template
                template, _ = Template.objects.get_or_create(
                    name=template_name,
                    defaults={
                        'title': template_name.replace('_', ' ').title(),
                        'template_file': template_name,
                        'is_active': True
                    }
                )
                
                # Get or create page
                if page_subdomain:
                    # ✅ CRITICAL FIX: Get the page but DON'T overwrite brand_name
                    page = PublishedPage.objects.get(
                        subdomain=page_subdomain,
                        user=request.user
                    )
                    print(f"✅ Found existing page: {page.brand_name} (subdomain: {page.subdomain})")
                    
                    # ✅ PRESERVE the existing brand_name - don't overwrite it
                    # Only update if a new brand_name is provided AND it's different from subdomain
                    if brand_name and brand_name.strip():
                        # ✅ NEVER set brand_name = subdomain
                        if brand_name.strip() != page.subdomain:
                            page.brand_name = brand_name.strip()
                            print(f"   Updating brand_name to: '{page.brand_name}'")
                        else:
                            print(f"   ⚠️ brand_name matches subdomain, keeping existing: '{page.brand_name}'")
                    else:
                        print(f"   Keeping existing brand_name: '{page.brand_name}'")
                    
                    # ✅ Ensure subdomain is correct
                    if subdomain and subdomain != page.subdomain:
                        # Only update subdomain if it's different and valid
                        page.subdomain = subdomain
                        print(f"   Updating subdomain to: '{page.subdomain}'")
                    
                else:
                    # Create new page
                    if not brand_name or not subdomain:
                        return JsonResponse({
                            'success': False,
                            'error': 'Brand name and subdomain required for new pages'
                        }, status=400)
                    
                    # ✅ Create with separate brand_name and subdomain
                    page = PublishedPage.objects.create(
                        user=request.user,
                        brand_name=brand_name.strip(),
                        subdomain=subdomain,
                        template=template,
                        template_name=template_name,
                        is_published=True,
                        current_page=current_page
                    )
                    print(f"✅ Created new page: {page.brand_name} (subdomain: {page.subdomain})")
                
                # ✅ Update page fields - NEVER overwrite brand_name with subdomain
                page.template = template
                page.template_name = template_name
                page.is_published = True
                page.current_page = current_page
                page.page_customizations = all_page_data
                
                # ✅ CRITICAL: Log what we're saving
                print(f"\n📝 [publish_page] SAVING PAGE:")
                print(f"   page.brand_name (about to save): '{page.brand_name}'")
                print(f"   page.subdomain (about to save): '{page.subdomain}'")
                
                # Save the page
                page.save()
                
                # ✅ Verify after save
                page.refresh_from_db()
                print(f"\n✅ [publish_page] AFTER SAVE:")
                print(f"   page.brand_name: '{page.brand_name}'")
                print(f"   page.subdomain: '{page.subdomain}'")
                
                # ===== BULK DELETE EXISTING DATA =====
                print("\n🗑️ [publish_page] Deleting existing data...")
                TextContent.objects.filter(page=page).delete()
                StyleCustomization.objects.filter(page=page).delete()
                ComponentCustomization.objects.filter(page=page).delete()
                IconCustomization.objects.filter(page=page).delete()
                
                # ===== BULK CREATE NEW DATA =====
                print("💾 [publish_page] Creating new data...")
                text_objects = []
                style_objects = []
                icon_objects = []
                component_objects = []
                
                for page_name, page_data in all_page_data.items():
                    # Text contents
                    for element_id, content in page_data.get('text_contents', {}).items():
                        clean_id = extract_numeric_id(element_id)
                        if clean_id and content:
                            text_objects.append(
                                TextContent(page=page, element_id=clean_id, content=content)
                            )
                    
                    # Style customizations
                    for element_id, styles in page_data.get('style_customizations', {}).items():
                        clean_id = extract_numeric_id(element_id)
                        if clean_id and any(styles.values()):
                            style_objects.append(
                                StyleCustomization(
                                    page=page,
                                    element_id=clean_id,
                                    background_color=styles.get('background_color', ''),
                                    text_color=styles.get('text_color', ''),
                                    font_size=styles.get('font_size', ''),
                                    font_family=styles.get('font_family', ''),
                                    font_weight=styles.get('font_weight', ''),
                                    padding=styles.get('padding', ''),
                                    margin=styles.get('margin', ''),
                                    border_radius=styles.get('border_radius', ''),
                                    border=styles.get('border', ''),
                                    display=styles.get('display', ''),
                                )
                            )
                    
                    # Icon customizations
                    for element_id, icons in page_data.get('icon_customizations', {}).items():
                        clean_id = extract_numeric_id(element_id)
                        if clean_id:
                            icon_objects.append(
                                IconCustomization(
                                    page=page,
                                    element_id=clean_id,
                                    icon_class=icons.get('icon_class', ''),
                                    color=icons.get('color', ''),
                                    font_size=icons.get('font_size', '')
                                )
                            )
                    
                    # Component customizations
                    for comp_data in page_data.get('component_customizations', []):
                        if comp_data.get('instance_id'):
                            component_objects.append(
                                ComponentCustomization(
                                    page=page,
                                    component_instance_id=comp_data['instance_id'],
                                    component_id=comp_data.get('component_id'),
                                    drop_zone=comp_data.get('drop_zone', 'end'),
                                    display_order=comp_data.get('display_order', 0),
                                    customizations=comp_data.get('customizations', {})
                                )
                            )
                
                # Bulk create all objects
                if text_objects:
                    TextContent.objects.bulk_create(text_objects, ignore_conflicts=True)
                    print(f"   Created {len(text_objects)} text contents")
                if style_objects:
                    StyleCustomization.objects.bulk_create(style_objects, ignore_conflicts=True)
                    print(f"   Created {len(style_objects)} style customizations")
                if icon_objects:
                    IconCustomization.objects.bulk_create(icon_objects, ignore_conflicts=True)
                    print(f"   Created {len(icon_objects)} icon customizations")
                if component_objects:
                    ComponentCustomization.objects.bulk_create(component_objects, ignore_conflicts=True)
                    print(f"   Created {len(component_objects)} component customizations")
                
                # Handle background images
                for page_name, page_data in all_page_data.items():
                    bg_images = page_data.get('background_images', {})
                    for element_id, image_data in bg_images.items():
                        clean_id = extract_numeric_id(element_id)
                        if clean_id and isinstance(image_data, str) and image_data.startswith('data:image'):
                            try:
                                format, imgstr = image_data.split(';base64,')
                                ext = format.split('/')[-1]
                                image_file = ContentFile(
                                    base64.b64decode(imgstr),
                                    name=f"bg_{page_name}_{clean_id}_{uuid.uuid4()}.{ext}"
                                )
                                BackgroundImage.objects.update_or_create(
                                    page=page,
                                    element_id=clean_id,
                                    defaults={'image': image_file}
                                )
                            except Exception as e:
                                print(f"⚠️ Background image error for {clean_id}: {e}")
                
                # Handle image customizations
                for page_name, page_data in all_page_data.items():
                    img_customizations = page_data.get('image_customizations', {})
                    for element_id, image_data in img_customizations.items():
                        if image_data and isinstance(image_data, dict):
                            image_url = image_data.get('image_url', '')
                            if image_url and image_url.startswith('data:image'):
                                try:
                                    format, imgstr = image_url.split(';base64,')
                                    ext = format.split('/')[-1]
                                    image_file = ContentFile(
                                        base64.b64decode(imgstr),
                                        name=f"img_{page_name}_{element_id}_{uuid.uuid4()}.{ext}"
                                    )
                                    ImageCustomization.objects.update_or_create(
                                        page=page,
                                        element_id=element_id,
                                        page_name=page_name,
                                        defaults={
                                            'image': image_file,
                                            'alt_text': image_data.get('alt_text', '')
                                        }
                                    )
                                except Exception as e:
                                    print(f"⚠️ Image customization error for {element_id}: {e}")
                
                # Handle color palette
                palette_data = all_page_data.get(current_page, {}).get('color_palette')
                if palette_data:
                    try:
                        from builder.models import ColorPalette
                        palette = ColorPalette.objects.get(id=palette_data.get('palette_id'))
                        page.active_palette = palette
                        page.active_palette_colors = palette_data.get('colors', {})
                        page.save(update_fields=['active_palette', 'active_palette_colors'])
                        print(f"🎨 Applied palette: {palette.name}")
                    except ColorPalette.DoesNotExist:
                        pass
                
                print(f"\n✅ Published: {page.subdomain} - "
                      f"Brand: {page.brand_name}, "
                      f"Texts: {len(text_objects)}, "
                      f"Styles: {len(style_objects)}, "
                      f"Icons: {len(icon_objects)}, "
                      f"Components: {len(component_objects)}")
                
                return JsonResponse({
                    'success': True,
                    'subdomain': page.subdomain,
                    'brand_name': page.brand_name,
                    'page_url': page.get_absolute_url(),
                    'message': 'Page published successfully!',
                    'stats': {
                        'texts': len(text_objects),
                        'styles': len(style_objects),
                        'icons': len(icon_objects),
                        'components': len(component_objects),
                    }
                })
                
        except PublishedPage.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Page not found'
            }, status=404)
            
    except json.JSONDecodeError as e:
        return JsonResponse({
            'success': False,
            'error': f'Invalid JSON: {str(e)}'
        }, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    
# builder/views.py - Add this new view

# builder/views.py - Updated upload_image

# builder/views.py - Production-ready upload view

from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token
import logging

logger = logging.getLogger(__name__)

# builder/views.py - Ultra-simple upload view

@login_required
@csrf_exempt
@check_storage_before_upload('image')
def upload_image(request):
    """Upload image - Cloudinary handles everything automatically"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        # Get data
        subdomain = request.POST.get('subdomain')
        image_file = request.FILES.get('image')
        element_id = request.POST.get('element_id')
        page_name = request.POST.get('page_name', 'home')
        
        if not all([subdomain, image_file, element_id]):
            return JsonResponse({'success': False, 'error': 'Missing fields'})
        
        # Get the page
        page = PublishedPage.objects.get(subdomain=subdomain, user=request.user)
        
        # Determine type
        is_background = 'bg' in element_id or 'section' in element_id
        
        # Save - THAT'S IT! Cloudinary handles the upload automatically
        if is_background:
            clean_id = extract_numeric_id(element_id)
            
            # Delete old image first (optional)
            BackgroundImage.objects.filter(page=page, element_id=clean_id).delete()
            
            # Create new with the file
            bg = BackgroundImage.objects.create(
                page=page,
                element_id=clean_id,
                image=image_file  # Just assign the file!
            )
            image_url = bg.image.url  # Returns Cloudinary URL
        
        else:
            # Delete old image first (optional)
            ImageCustomization.objects.filter(
                page=page, 
                element_id=element_id,
                page_name=page_name
            ).delete()
            
            # Create new with the file
            img = ImageCustomization.objects.create(
                page=page,
                element_id=element_id,
                page_name=page_name,
                image=image_file,  # Just assign the file!
                alt_text=request.POST.get('alt_text', '')
            )
            image_url = img.image.url  # Returns Cloudinary URL
        
        return JsonResponse({
            'success': True,
            'image_url': image_url,
            'element_id': element_id
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})



# builder/views.py - Add debug view

@login_required
def debug_upload(request):
    """Debug view to check upload configuration"""
    import sys
    import os
    from django.conf import settings
    
    debug_info = {
        'user': {
            'id': request.user.id,
            'username': request.user.username,
            'is_authenticated': request.user.is_authenticated,
            'is_active': request.user.is_active,
        },
        'session': {
            'session_key': request.session.session_key,
            'has_csrf_token': 'csrftoken' in request.COOKIES,
        },
        'request': {
            'method': request.method,
            'path': request.path,
            'secure': request.is_secure(),
            'host': request.get_host(),
        },
        'settings': {
            'debug': settings.DEBUG,
            'media_url': settings.MEDIA_URL,
            'media_root': str(settings.MEDIA_ROOT),
            'media_root_exists': os.path.exists(settings.MEDIA_ROOT),
            'static_url': settings.STATIC_URL,
        },
        'python_version': sys.version,
    }
    
    # Check if media directories are writable
    if os.path.exists(settings.MEDIA_ROOT):
        debug_info['media_root_writable'] = os.access(settings.MEDIA_ROOT, os.W_OK)
        
        # Check subdirectories
        for subdir in ['custom_images', 'backgrounds']:
            path = os.path.join(settings.MEDIA_ROOT, subdir)
            if os.path.exists(path):
                debug_info[f'{subdir}_writable'] = os.access(path, os.W_OK)
            else:
                debug_info[f'{subdir}_exists'] = False
    
    return JsonResponse(debug_info)


# builder/views.py
from django.middleware.csrf import get_token

@login_required
def get_csrf_token(request):
    """Return a fresh CSRF token"""
    return JsonResponse({
        'csrfToken': get_token(request)
    })

# builder/views.py - Add this to check if images are processed

@login_required
def check_image_status(request, subdomain):
    """Check if images for a page have been processed"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        # Count pending images
        from .utils.image_processor import processor
        
        # You could also check database for unprocessed flags
        # For now, just return queue size
        queue_size = processor.queue.qsize() if hasattr(processor, 'queue') else 0
        
        return JsonResponse({
            'success': True,
            'queue_size': queue_size,
            'processed': queue_size == 0
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# builder/views.py - Add this endpoint for clients to check status

@login_required
def get_processed_images(request, subdomain):
    """Get list of processed images for a page"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        # Get all processed custom images
        custom_images = ImageCustomization.objects.filter(page=page)
        processed_images = []
        
        for img in custom_images:
            if img.image:
                processed_images.append({
                    'element_id': img.element_id,
                    'page_name': img.page_name,
                    'image_url': img.image.url,
                    'alt_text': img.alt_text
                })
        
        return JsonResponse({
            'success': True,
            'images': processed_images
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

def extract_numeric_id(element_id):
    """
    Extract only numeric part from element ID
    """
    if not element_id:
        return None
    
    if isinstance(element_id, int):
        return str(element_id)
    
    import re
    match = re.search(r'\d+', str(element_id))
    return match.group() if match else None





# builder/views.py - Update dashboard view

# builder/views.py - Update dashboard view
# builder/views.py

@login_required
def dashboard(request):
    """User dashboard showing their published pages"""
    from payments.decorators import get_user_limits_status
    from analytics.models import PageView
    from django.db.models import Count, Q
    pages = PublishedPage.objects.filter(
        user=request.user
    ).exclude(subdomain__isnull=True).exclude(subdomain='').order_by('-created_at')
    
    # Get limits with safe fallback
    try:
        limits = get_user_limits_status(request.user)
        print(f"Dashboard limits for {request.user.email}: {limits}")
    except Exception as e:
        print(f"Error getting limits: {e}")
        limits = {
            'tier': 'free',
            'plan_name': 'Free',
            'is_paid': False,
            'websites': {'used': 0, 'limit': 1},
            'products': {'used': 0, 'limit': 10},
            'forms_this_month': {'used': 0, 'limit': 10},
            'storage': {'used_mb': 0, 'limit_mb': 100, 'percentage': 0},
        }

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    for page in pages:
        if hasattr(page, 'analytics'):
            analytics = page.analytics
            
            # Get all page views for this page in last 30 days
            page_views = PageView.objects.filter(
                analytics=analytics,
                timestamp__date__range=[start_date, end_date]
            )
            
            # Total visits (corrected)
            page.corrected_visits = page_views.count() // 2
            
            # Unique visitors
            page.corrected_visitors = page_views.values('visitor_id').distinct().count()
            
            # Bounce rate - single query approach
            session_data = page_views.values('session_id').annotate(
                view_count=Count('id')
            )
            
            total = session_data.count()
            if total > 0:
                bounces = sum(1 for s in session_data if (s['view_count'] // 2) <= 1)
                page.corrected_bounce = round((bounces / total) * 100, 1)
            else:
                page.corrected_bounce = 0
        else:
            page.corrected_visits = 0
            page.corrected_visitors = 0
            page.corrected_bounce = 0
    
    return render(request, 'builder/dashboard.html', {
        'published_pages': pages,
        'limits': limits,
    })
    
def edit_page(request, subdomain):
    """Edit an existing published page"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Redirect to editor with the correct page data
    return redirect(f'/builder/editor/{page.template_name}/{page.subdomain}/')


@login_required
def delete_page(request, subdomain):
    """Delete a published page"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    if request.method == 'POST':
        page.delete()
        messages.success(request, f'Page "{page.brand_name}" has been deleted successfully.')
        return redirect('dashboard')
    
    return render(request, 'builder/delete_page.html', {
        'page': page
    })

from django.db.models import F
   
@login_required
def manage_products(request, subdomain):
    """Ecwid-style simple product management"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Simple filtering
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    products = page.products.select_related('category', 'inventory').all()
    
    if status_filter:
        products = products.filter(status=status_filter)
    if search_query:
        products = products.filter(title__icontains=search_query)
    
    # Pagination
    paginator = Paginator(products, 10)  # 10 products per page for clean layout
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)
    
    # Simple statistics
    total_products = page.products.count()
    active_products = page.products.filter(status='active').count()
    low_stock_count = page.products.filter(
        inventory__quantity__lte=F('inventory__low_stock_threshold'),
        inventory__track_quantity=True
    )
       
    total_views = page.products.aggregate(total_views=Sum('view_count'))['total_views'] or 0
    
    context = {
        'page': page,
        'products': products_page,
        'total_products': total_products,
        'active_products': active_products,
        'low_stock_count': low_stock_count,
        'total_views': total_views,
    }
    
    return render(request, 'builder/manage_products.html', context)

@login_required
def quick_edit_product(request, subdomain, product_id):
    """Quick edit modal with tabs"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    product = get_object_or_404(Product, id=product_id, page=page)
    categories = page.product_categories.filter(is_active=True)
    # Get existing specifications
    specifications = product.dynamic_specs.all().order_by('display_order')
    
    context = {
        'page': page,
        'product': product,
        'categories': categories,
        'specifications': specifications,
    }
    
    return render(request, 'builder/partials/quick_edit_product.html', context)

@login_required
@check_product_limit(count=1)
@check_storage_before_upload('image')
def add_product_simple(request, subdomain):
    """Simple product creation with basic fields"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    if request.method == 'POST':
        try:
            # Create basic product
            product = Product(
                page=page,
                title=request.POST.get('title'),
                description=request.POST.get('description', ''),
                price=request.POST.get('price'),
                status='draft'
            )
            
            # Handle compare price
            compare_price = request.POST.get('compare_at_price')
            if compare_price:
                product.compare_at_price = compare_price
            
            # Handle image
            if 'main_image' in request.FILES:
                product.main_image = request.FILES['main_image']
            
            product.save()
            
            return JsonResponse({'success': True, 'product_id': product.id})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def single_product_editor(request, subdomain, product_id):
    """Single page product editor with tabs"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    product = get_object_or_404(Product, id=product_id, page=page)
    categories = page.product_categories.filter(is_active=True)
    # Get existing specifications using the new related name
    specifications = product.dynamic_specs.all().order_by('display_order')  # Changed from 'specifications' to 'dynamic_specs'
    context = {
        'page': page,
        'product': product,
        'categories': categories,
        'specifications': specifications,
    }
    
    return render(request, 'builder/product_editor.html', context)


@login_required
@check_storage_before_upload('image')
def update_product(request, subdomain, product_id):
    """Update product with all advanced features"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    product = get_object_or_404(Product, id=product_id, page=page)
    
    if request.method == 'POST':
        try:
            # Debug: Print received POST data
            print("📥 Received POST data:")
            for key, value in request.POST.items():
                print(f"   {key}: {value}")
            
            # ========== CRITICAL: Handle use_custom_shipping FIRST ==========
            # Check both the checkbox value and the hidden field
            use_custom_shipping_raw = request.POST.get('use_custom_shipping')
            
            # Determine if custom shipping should be enabled
            # Checkbox sends "on" when checked, hidden field sends "off" when unchecked
            use_custom_shipping = (use_custom_shipping_raw == 'on')
            
            print(f"🔧 use_custom_shipping_raw: {use_custom_shipping_raw}")
            print(f"🔧 use_custom_shipping: {use_custom_shipping}")
            
            # Set the flag FIRST
            product.use_custom_shipping = use_custom_shipping
            
            # If custom shipping is disabled, clear all related fields
            if not use_custom_shipping:
                print(f"🔄 Custom shipping DISABLED - clearing all custom shipping fields")
                product.custom_shipping_type = 'flat'
                product.custom_shipping_price = Decimal('0')
                product.shipping_per_item = Decimal('0')
                product.custom_free_shipping_min_price = None
                product.shipping_note = ''
                product.ships_separately = False
            
            # Update all other fields from different tabs
            update_fields = [
                # Basic Info
                'title', 'description', 'short_description', 'colors', 'sizes', 'status', 'type', 'category',
                # Pricing
                'price', 'compare_at_price', 'cost_per_item', 'charge_tax',
                # Inventory
                'sku', 'barcode', 'quantity', 'track_quantity', 'low_stock_threshold', 'allow_backorders',
                # Shipping (original)
                'weight', 'weight_unit', 'length', 'width', 'height', 'requires_shipping', 'free_shipping',
                # SEO
                'meta_title', 'meta_description', 'slug',
                # Digital
                'download_limit', 'download_expiry',
                # Organization
                'vendor', 'collection', 'tags', 'featured', 'visible_on_store',
                # Custom shipping fields (only process if custom shipping is enabled)
                'custom_shipping_type', 'custom_shipping_price', 
                'shipping_per_item', 'custom_free_shipping_min_price', 'shipping_note', 'ships_separately'
            ]
            
            for field in update_fields:
                if field in request.POST:
                    value = request.POST.get(field)
                    
                    # Skip processing custom shipping fields if custom shipping is disabled
                    if field in ['custom_shipping_type', 'custom_shipping_price', 'shipping_per_item', 
                                 'custom_free_shipping_min_price', 'shipping_note', 'ships_separately']:
                        if not use_custom_shipping:
                            continue  # Skip - fields already cleared above
                    
                    if value == '' and field in ['compare_at_price', 'cost_per_item', 'custom_free_shipping_min_price']:
                        setattr(product, field, None)
                    elif field == 'tags':
                        # Convert comma-separated tags to list
                        tags = [tag.strip() for tag in value.split(',') if tag.strip()]
                        product.tags = tags
                    elif field == 'category':
                        category_id = value
                        if category_id:
                            product.category = ProductCategory.objects.get(id=category_id, page=page)
                        else:
                            product.category = None
                    elif field in ['charge_tax', 'track_quantity', 'allow_backorders', 'requires_shipping', 
                                 'free_shipping', 'featured', 'visible_on_store', 'ships_separately']:
                        setattr(product, field, value == 'on')
                    elif field in ['custom_shipping_price', 'shipping_per_item']:
                        # Handle decimal fields
                        setattr(product, field, Decimal(value) if value else Decimal('0'))
                    elif field == 'custom_free_shipping_min_price':
                        # Handle nullable decimal field
                        if value and value.strip():
                            setattr(product, field, Decimal(value))
                        else:
                            setattr(product, field, None)
                    else:
                        setattr(product, field, value)
            
            # Handle file uploads
            if 'main_image' in request.FILES:
                product.main_image = request.FILES['main_image']
            if 'digital_file' in request.FILES:
                product.digital_file = request.FILES['digital_file']
            
            # Handle variant data
            variant_data = request.POST.get('variant_data')
            if variant_data:
                update_product_variants(product, json.loads(variant_data))
                    
            product.save()
            
            # Log the saved state
            print(f"💾 Product saved: use_custom_shipping = {product.use_custom_shipping}")
            if product.use_custom_shipping:
                print(f"   Custom shipping type: {product.custom_shipping_type}")
                print(f"   Custom shipping price: {product.custom_shipping_price}")
            
            files = request.FILES.getlist('images')
            for file in files:
                ProductImages.objects.create(product=product, image=file)

            # ===== Handle Specifications =====
            spec_titles = request.POST.getlist('spec_title[]')
            spec_values = request.POST.getlist('spec_value[]')
            
            # Delete existing specifications
            product.dynamic_specs.all().delete()
            
            # Create new specifications
            for i, (title, value) in enumerate(zip(spec_titles, spec_values)):
                if title.strip() and value.strip():
                    ProductSpecification.objects.create(
                        product=product,
                        title=title.strip(),
                        value=value.strip(),
                        display_order=i
                    )
            
            return JsonResponse({'success': True, 'message': 'Product updated successfully'})
            
        except Exception as e:
            print(f"Error updating product: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})



def update_product_variants(product, variant_data):
    """Update product variants"""
    # This would handle creating/updating/deleting variants
    # Implementation depends on your variant structure
    pass

@login_required
def delete_product(request, subdomain, product_id):
    """Delete a product"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    product = get_object_or_404(Product, id=product_id, page=page)
    
    if request.method == 'POST':
        product.delete()
        return JsonResponse({'success': True})
    
    # If GET request, show confirmation (optional)
    return JsonResponse({'success': False, 'error': 'Use POST method to delete'})

@login_required
def update_product_status(request, product_id):
    """API endpoint to update product status"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            
            if new_status in ['draft', 'active', 'archived']:
                product.status = new_status
                product.save()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Invalid status'})
                
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
@check_storage_before_upload('image')
def manage_product_categories(request, subdomain):
    """Manage product categories with AJAX responses"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            
            if not name:
                return JsonResponse({
                    'success': False, 
                    'error': 'Category name is required'
                })
            
            # Handle image upload
            image = request.FILES.get('image')
            
            # Create category
            category = ProductCategory.objects.create(
                page=page,
                name=name,
                description=description,
                image=image if image else None
            )
            
            # Return the created category data
            return JsonResponse({
                'success': True,
                'message': 'Category created successfully!',
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'slug': category.slug,
                    'image_url': category.image.url if category.image else None,
                    'products_count': category.products.count(),
                    'active_products_count': category.get_active_products_count()
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    # GET request - return categories as JSON if requested
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        categories = page.product_categories.all().order_by('display_order', 'name')
        data = [{
            'id': cat.id,
            'name': cat.name,
            'description': cat.description,
            'slug': cat.slug,
            'image_url': cat.image.url if cat.image else None,
            'products_count': cat.products.count(),
            'active_products_count': cat.get_active_products_count()
        } for cat in categories]
        
        return JsonResponse({
            'success': True,
            'categories': data
        })
    
    # Regular template render
    categories = page.product_categories.all().order_by('display_order', 'name')
    return render(request, 'builder/manage_product_categories.html', {
        'page': page,
        'categories': categories
    })


@login_required
def update_category(request, subdomain, category_id):
    """Update product category with JSON response"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    category = get_object_or_404(ProductCategory, id=category_id, page=page)
    
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            
            if not name:
                return JsonResponse({
                    'success': False,
                    'error': 'Category name is required'
                })
            
            # Update fields
            category.name = name
            category.description = description
            
            # Handle image update if provided
            if 'image' in request.FILES:
                # Delete old image if exists
                if category.image:
                    category.image.delete(save=False)
                category.image = request.FILES['image']
            
            category.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Category updated successfully!',
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'slug': category.slug,
                    'image_url': category.image.url if category.image else None,
                    'products_count': category.products.count(),
                    'active_products_count': category.get_active_products_count()
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def delete_category(request, subdomain, category_id):
    """Delete product category with JSON response"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    category = get_object_or_404(ProductCategory, id=category_id, page=page)
    
    if request.method == 'POST':
        try:
            # Check if category has products
            if category.products.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot delete category with products. Move products first.'
                })
            
            # Delete image if exists
            if category.image:
                category.image.delete(save=False)
            
            category_name = category.name
            category.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Category "{category_name}" deleted successfully!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


# ================================================================
# RICH TEXT EDITOR - MEDIA UPLOAD VIEWS
# ================================================================

@login_required
@csrf_exempt
def upload_editor_image(request, subdomain):
    """
    Upload image for rich text editor.
    Returns JSON with the image URL for CKEditor.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        # Check if image was sent
        if 'upload' in request.FILES:
            image = request.FILES['upload']
        elif 'image' in request.FILES:
            image = request.FILES['image']
        else:
            return JsonResponse({'success': False, 'error': 'No image provided'})
        
        # Validate file type
        if not image.content_type.startswith('image/'):
            return JsonResponse({'success': False, 'error': 'File must be an image'})
        
        # Save the image
        editor_image = EditorImage.objects.create(
            page=page,
            image=image,
            alt_text=image.name,
            uploaded_by=request.user
        )
        
        # CKEditor expects this format
        return JsonResponse({
            'uploaded': True,
            'url': editor_image.image.url,
            'fileName': image.name,
        })
        
    except Exception as e:
        return JsonResponse({'uploaded': False, 'error': {'message': str(e)}})


@login_required
@csrf_exempt
def upload_editor_media(request, subdomain):
    """
    Upload image or video for Froala Editor.
    Froala expects a specific response format.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'})
    
    try:
        # Get the page
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        # Check if file was uploaded
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No file provided'})
        
        file = request.FILES['file']
        media_type = request.POST.get('media_type', 'image')
        
        # Validate file type
        if media_type == 'image' and not file.content_type.startswith('image/'):
            return JsonResponse({
                'success': False, 
                'error': f'File must be an image (got {file.content_type})'
            })
        elif media_type == 'video' and not file.content_type.startswith('video/'):
            return JsonResponse({
                'success': False, 
                'error': f'File must be a video (got {file.content_type})'
            })
        
        # Import the model
        from .models import EditorMedia
        
        # Save the media
        editor_media = EditorMedia.objects.create(
            page=page,
            file=file,
            media_type=media_type,
            uploaded_by=request.user
        )
        
        # Build full URL for the file
        file_url = editor_media.file.url
        if file_url.startswith('/'):
            file_url = request.build_absolute_uri(file_url)
        
        # ====== FROALA EXPECTS THIS SPECIFIC RESPONSE FORMAT ======
        return JsonResponse({
            'success': True,
            'link': file_url,  # Froala uses 'link' for the URL
            'url': file_url,
            'fileName': file.name,
            'fileId': editor_media.id,
            'media_type': media_type
        })
        
    except PublishedPage.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'Page not found'
        })
    except Exception as e:
        import traceback
        print(f"❌ Upload error: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False, 
            'error': str(e)
        })
# End


@login_required
def delete_product(request, subdomain, product_id):
    """Delete a product"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    product = get_object_or_404(Product, id=product_id, page=page)
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, f'Product "{product.title}" has been deleted.')
        return redirect('manage_products', subdomain=subdomain)
    
    return render(request, 'builder/delete_product.html', {
        'page': page,
        'product': product
    })

@login_required
def manage_tracking_codes(request, subdomain):
    """Manage tracking codes for a published page"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    tracking_codes = page.tracking_codes.all()
    
    if request.method == 'POST':
        platform = request.POST.get('platform')
        code = request.POST.get('code')
        is_active = request.POST.get('is_active') == 'on'
        
        TrackingCode.objects.update_or_create(
            page=page,
            platform=platform,
            defaults={
                'code': code,
                'is_active': is_active
            }
        )
        
        messages.success(request, f'Tracking code for {platform} has been updated.')
        return redirect('manage_tracking_codes', subdomain=subdomain)
    
    return render(request, 'builder/manage_tracking_codes.html', {
        'page': page,
        'tracking_codes': tracking_codes
    })

@login_required
def delete_tracking_code(request, subdomain, code_id):
    """Delete a tracking code"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    tracking_code = get_object_or_404(TrackingCode, id=code_id, page=page)
    
    if request.method == 'POST':
        tracking_code.delete()
        messages.success(request, f'Tracking code for {tracking_code.platform} has been deleted.')
        return redirect('manage_tracking_codes', subdomain=subdomain)
    
    return render(request, 'builder/delete_tracking_code.html', {
        'page': page,
        'tracking_code': tracking_code
    })

def get_template_pages(template_name):
    """
    Get available pages for a template
    """
    try:
        template = Template.objects.get(name=template_name)
        if template.template_type == 'multi' and template.available_pages:
            return template.available_pages
    except Template.DoesNotExist:
        pass
    return ['home']  # Default to home page

def load_multi_page_template(template_name, page_name):
    """Load specific page from multi-page template"""
    try:
        # Try to load from multi-page template directory
        return render_to_string(f'builder/templates/{template_name}/{page_name}.html')
    except:
        # Fallback to single page template
        return render_to_string(f'builder/templates/{template_name}.html')
    





# cart and Wishlist views

import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST



# @csrf_exempt
# @require_POST
# def add_to_cart(request, subdomain):
#     """Add product to cart with variant support - FIXED"""
#     try:
#         print(f"🛒 ADD TO CART - Subdomain: {subdomain}")
        
#         page = get_object_or_404(PublishedPage, subdomain=subdomain)
        
#         # Parse request body
#         try:
#             data = json.loads(request.body)
#         except json.JSONDecodeError:
#             return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        
        
#         product_id = data.get('product_id')
#         variant_id = data.get('variant_id')
#         selected_options = data.get('options', {})
#         quantity = int(data.get('quantity', 1))
        
#         print(f"📦 Product ID: {product_id}, Variant ID: {variant_id}, Quantity: {quantity}")
#         print(f"📦 Options: {selected_options}")
        
#         # Get product
#         product = get_object_or_404(Product, id=product_id, page=page)
#         print(f"✅ Product found: {product.title}")
        
#         # Get variant if specified
#         variant = None
#         if variant_id:
#             try:
#                 variant = ProductVariant.objects.get(id=variant_id, product=product)
#                 print(f"✅ Variant found: {variant}")
#             except ProductVariant.DoesNotExist:
#                 print(f"⚠️ Variant {variant_id} not found, trying options match")
#                 if selected_options:
#                     variant = product.variants.filter(options=selected_options).first()
#                     if variant:
#                         print(f"✅ Variant found by options: {variant}")
#         elif selected_options:
#             variant = product.variants.filter(options=selected_options).first()
#             if variant:
#                 print(f"✅ Variant found by options: {variant}")
        
#         # Ensure session exists
#         if not request.session.session_key:
#             request.session.create()
#         session_key = request.session.session_key
#         print(f"🔑 Session: {session_key}")
#         print(f"👤 User authenticated: {request.user.is_authenticated}")
        
#         # Get or create cart - FIXED: Use correct lookup
#         if request.user.is_authenticated:
#             # For authenticated users, try to get existing cart or create new
#             cart, created = Cart.objects.get_or_create(
#                 user=request.user,
#                 page=page,
#                 defaults={
#                     'session_key': None,
#                     'created_at': timezone.now(),
#                     'updated_at': timezone.now()
#                 }
#             )
#             # If there's a session cart, transfer it
#             if not created:
#                 session_cart = Cart.objects.filter(session_key=session_key, page=page, user__isnull=True).first()
#                 if session_cart:
#                     # Transfer items from session cart to user cart
#                     for item in session_cart.items.all():
#                         item.cart = cart
#                         item.save()
#                     session_cart.delete()
#                     print("🔄 Transferred session cart to user cart")
#         else:
#             # For guest users, use session key
#             cart, created = Cart.objects.get_or_create(
#                 session_key=session_key,
#                 page=page,
#                 defaults={
#                     'user': None,
#                     'created_at': timezone.now(),
#                     'updated_at': timezone.now()
#                 }
#             )
        
#         print(f"🛒 Cart: {cart.id}, Created: {created}")
        
#         # Check if item already exists in cart (with same variant)
#         existing_item = CartItem.objects.filter(
#             cart=cart,
#             product=product,
#             variant=variant
#         ).first()
        
#         if existing_item:
#             print(f"📦 Item exists, updating quantity from {existing_item.quantity} to {existing_item.quantity + quantity}")
#             existing_item.quantity += quantity
#             existing_item.save()
#             message = f'Updated {product.title} quantity'
#         else:
#             print(f"📦 Creating new cart item")
#             CartItem.objects.create(
#                 cart=cart,
#                 product=product,
#                 variant=variant,
#                 selected_options=selected_options,
#                 quantity=quantity
#             )
#             message = f'Added {product.title} to cart'
        
#         # Get updated counts
#         total_qty = cart.get_total_quantity()
#         items_count = cart.items.count()
        
#         print(f"✅ Success: {message}, Total: {total_qty}, Items: {items_count}")
        
#         return JsonResponse({
#             'success': True,
#             'message': message,
#             'cart_total': total_qty,
#             'cart_items_count': items_count
#         })
        
#     except Product.DoesNotExist:
#         print(f"❌ Product not found: {product_id}")
#         return JsonResponse({'success': False, 'error': 'Product not found'})
#     except Exception as e:
#         print(f"❌ Cart error: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return JsonResponse({'success': False, 'error': str(e)})
    

# builder/views.py - Complete updated add_to_cart

from builder.services.variant_grouping import VariantGroupManager

@csrf_exempt
@require_POST
def add_to_cart(request, subdomain):
    """Add product to cart with variant support - FIXED for multiple variants"""
    try:
        print(f"🛒 ADD TO CART - Subdomain: {subdomain}")
        page = get_object_or_404(PublishedPage, subdomain=subdomain)

        # Parse request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})

        product_id = data.get('product_id')
        variant_id = data.get('variant_id')
        selected_options = data.get('options', {})
        selected_color = data.get('selected_color', '')
        selected_size = data.get('selected_size', '')
        quantity = int(data.get('quantity', 1))

        print(f"📦 Product ID: {product_id}, Variant ID: {variant_id}, Quantity: {quantity}")
        print(f"📦 Options: {selected_options}, Color: {selected_color}, Size: {selected_size}")

        # Get product
        product = get_object_or_404(Product, id=product_id, page=page)
        print(f"✅ Product found: {product.title}")

        # Get variant if specified
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, product=product)
                print(f"✅ Variant found: {variant}")
            except ProductVariant.DoesNotExist:
                print(f"⚠️ Variant {variant_id} not found, trying options match")
                if selected_options:
                    variant = product.variants.filter(options=selected_options).first()
                    if variant:
                        print(f"✅ Variant found by options: {variant}")

        # If no variant found but we have color/size, try to find one
        if not variant and (selected_color or selected_size):
            variants = product.variants.all()
            for v in variants:
                v_options = v.options or {}
                v_color = v_options.get('color', '')
                v_size = v_options.get('size', '')
                if (not selected_color or v_color.lower() == selected_color.lower()) and \
                   (not selected_size or v_size.lower() == selected_size.lower()):
                    variant = v
                    print(f"✅ Variant found by color/size: {variant}")
                    break

        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        print(f"🔑 Session: {session_key}")
        print(f"👤 User authenticated: {request.user.is_authenticated}")

        # Get or create cart
        if request.user.is_authenticated:
            cart, created = Cart.objects.get_or_create(
                user=request.user,
                page=page,
                defaults={
                    'session_key': None,
                    'created_at': timezone.now(),
                    'updated_at': timezone.now()
                }
            )
            # Transfer session cart if exists
            if not created:
                session_cart = Cart.objects.filter(session_key=session_key, page=page, user__isnull=True).first()
                if session_cart:
                    for item in session_cart.items.all():
                        item.cart = cart
                        item.save()
                    session_cart.delete()
                    print("🔄 Transferred session cart to user cart")
        else:
            cart, created = Cart.objects.get_or_create(
                session_key=session_key,
                page=page,
                defaults={
                    'user': None,
                    'created_at': timezone.now(),
                    'updated_at': timezone.now()
                }
            )

        print(f"🛒 Cart: {cart.id}, Created: {created}")

        # Check if item exists with SAME variant (or no variant)
        existing_item = CartItem.objects.filter(
            cart=cart,
            product=product,
            variant=variant
        ).first()

        cart_item = None  # ✅ Store the cart item

        if existing_item:
            # Increment quantity instead of error
            existing_item.quantity += quantity
            existing_item.save()
            cart_item = existing_item  # ✅ Store reference
            message = f'Updated {product.title} quantity to {existing_item.quantity}'
            print(f"📦 Item exists, updated quantity to {existing_item.quantity}")
        else:
            # Create new cart item with variant
            cart_item = CartItem.objects.create(  # ✅ Store the created item
                cart=cart,
                product=product,
                variant=variant,
                selected_options=selected_options,
                selected_color=selected_color,
                selected_size=selected_size,
                quantity=quantity
            )
            message = f'Added {product.title} to cart'
            print(f"📦 Created new cart item with ID: {cart_item.id}")

        # Get updated counts
        total_qty = cart.get_total_quantity()
        items_count = cart.items.count()

        print(f"✅ Success: {message}, Total: {total_qty}, Items: {items_count}")

        # ✅ FIX: Return cart_item_id
        return JsonResponse({
            'success': True,
            'message': message,
            'cart_total': total_qty,
            'cart_items_count': items_count,
            'cart_item_id': cart_item.id  # ✅ ADD THIS
        })

    except Product.DoesNotExist:
        print(f"❌ Product not found: {product_id}")
        return JsonResponse({'success': False, 'error': 'Product not found'})
    except Exception as e:
        print(f"❌ Cart error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_POST
def add_to_wishlist(request, subdomain):
    """Add product to wishlist"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        data = json.loads(request.body)
        product_id = data.get('product_id')

        product = get_object_or_404(Product, id=product_id, page=page)

        # Ensure session exists for guest users
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key

        # Get or create wishlist - handle both authenticated and guest users
        wishlist_filter = {
            'page': page,
        }
        
        if request.user.is_authenticated:
            wishlist_filter['user'] = request.user
            wishlist_filter['session_key'] = None
        else:
            wishlist_filter['user'] = None
            wishlist_filter['session_key'] = session_key

        wishlist, created = Wishlist.objects.get_or_create(**wishlist_filter)

        # Add to wishlist
        wishlist_item, created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            product=product
        )

        return JsonResponse({
            'success': True,
            'message': f'Added {product.title} to wishlist',
            'wishlist_count': wishlist.items.count()
        })

    except Exception as e:
        print(f"❌ Wishlist error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


# builder/views.py - Update get_cart_data

# builder/views.py - Fixed get_cart_data

def get_cart_data(request, subdomain):
    """Get cart data with variant info - FIXED for multiple variants"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)

        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        print(f"🔍 Getting cart data for: {subdomain}")
        print(f"🔑 Session: {session_key}")
        print(f"👤 User: {request.user}")

        # Find cart
        cart = None
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user, page=page).first()
            if cart:
                print(f"✅ Found user cart: {cart.id}")
            else:
                cart = Cart.objects.filter(session_key=session_key, page=page).first()
                if cart:
                    print(f"✅ Found session cart: {cart.id}")
                    cart.user = request.user
                    cart.session_key = None
                    cart.save()
                    print(f"🔄 Transferred session cart to user: {cart.id}")
        else:
            cart = Cart.objects.filter(session_key=session_key, page=page).first()
            if cart:
                print(f"✅ Found guest cart: {cart.id}")

        cart_data = {
            'cart_total': 0,
            'cart_items_count': 0,
            'cart_items': []
        }

        if cart:
            items_count = cart.items.count()
            total_qty = cart.get_total_quantity()

            cart_data['cart_total'] = total_qty
            cart_data['cart_items_count'] = items_count

            print(f"📦 Cart {cart.id} has {items_count} items, total quantity: {total_qty}")

            for item in cart.items.select_related('product', 'variant').all():
                # Get variant image or product image
                image_url = None
                if item.variant and item.variant.image:
                    image_url = item.variant.image.url
                elif item.product.main_image:
                    image_url = item.product.main_image.url

                # Build variant display info
                variant_display = []
                if item.selected_color:
                    variant_display.append(f"Color: {item.selected_color}")
                if item.selected_size:
                    variant_display.append(f"Size: {item.selected_size}")
                if item.variant and item.variant.options:
                    for key, value in item.variant.options.items():
                        if key.lower() not in ['color', 'size']:
                            variant_display.append(f"{key}: {value}")

                item_data = {
                    'id': item.id,
                    'product_id': item.product.id,
                    'title': item.product.title,
                    'price': float(item.get_price()),
                    'quantity': item.quantity,
                    'total_price': float(item.get_total_price()),
                    'image_url': image_url,
                    'variant_id': item.variant.id if item.variant else None,
                    'variant_display': ', '.join(variant_display) if variant_display else 'Default',
                    'selected_options': item.selected_options,
                    'selected_color': item.selected_color,
                    'selected_size': item.selected_size,
                }
                cart_data['cart_items'].append(item_data)
                print(f" 📦 Item: {item.product.title} ({item_data['variant_display']}), Qty: {item.quantity}")
        else:
            print("ℹ️ No cart found")

        return JsonResponse(cart_data)

    except Exception as e:
        print(f"❌ Get cart data error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

# def get_cart_data_for_template(request, page):
#     """Get cart data for template context - handles both authenticated and guest users"""
#     try:
#         # Ensure session exists for guest users
#         if not request.session.session_key:
#             request.session.create()
        
#         session_key = request.session.session_key

#         # Find cart - handle both authenticated and guest users
#         cart = None
#         wishlist = None
        
#         if request.user.is_authenticated:
#             # For authenticated users, try user cart first
#             cart = Cart.objects.filter(user=request.user, page=page).first()
#             wishlist = Wishlist.objects.filter(user=request.user, page=page).first()
            
#             # If no user cart found, try session cart and transfer it
#             if not cart:
#                 session_cart = Cart.objects.filter(session_key=session_key, page=page).first()
#                 if session_cart:
#                     session_cart.user = request.user
#                     session_cart.session_key = None
#                     session_cart.save()
#                     cart = session_cart
            
#             if not wishlist:
#                 session_wishlist = Wishlist.objects.filter(session_key=session_key, page=page).first()
#                 if session_wishlist:
#                     session_wishlist.user = request.user
#                     session_wishlist.session_key = None
#                     session_wishlist.save()
#                     wishlist = session_wishlist
#         else:
#             # For guest users, use session
#             cart = Cart.objects.filter(session_key=session_key, page=page).first()
#             wishlist = Wishlist.objects.filter(session_key=session_key, page=page).first()

#         cart_data = {
#             'cart_total': cart.get_total_quantity() if cart else 0,
#             'cart_items_count': cart.items.count() if cart else 0,
#             'wishlist_count': wishlist.items.count() if wishlist else 0,
#             'cart': cart,  # Pass the cart object itself
#             'wishlist': wishlist,  # Pass the wishlist object itself
#         }

#         return cart_data

#     except Exception as e:
#         print(f"❌ Error getting cart data for template: {e}")
#         return {
#             'cart_total': 0,
#             'cart_items_count': 0,
#             'wishlist_count': 0,
#             'cart': None,
#             'wishlist': None,
#         }


def get_cart_data_for_template(request, page):
    """Get cart data for template context - PROPERLY handle authenticated users"""
    try:
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        
        # Debug: Check authentication status
        print(f"🔍 get_cart_data_for_template - User: {request.user}, Authenticated: {request.user.is_authenticated}")
        print(f"🔍 Session key: {session_key}")
        
        # Initialize cart and wishlist
        cart = None
        wishlist = None
        
        if request.user.is_authenticated:
            print(f"✅ User is authenticated: {request.user.username} (ID: {request.user.id})")
            
            # FIRST: Look for user-specific cart
            cart = Cart.objects.filter(user=request.user, page=page).first()
            wishlist = Wishlist.objects.filter(user=request.user, page=page).first()
            
            print(f"🔍 User cart found: {cart}")
            print(f"🔍 User wishlist found: {wishlist}")
            
            # SECOND: If no user cart, check for session cart and transfer it
            if not cart:
                session_cart = Cart.objects.filter(
                    session_key=session_key, 
                    page=page,
                    user__isnull=True  # Only get carts without users
                ).first()
                
                if session_cart:
                    print(f"🔄 Transferring session cart to user")
                    # Transfer session cart to authenticated user
                    session_cart.user = request.user
                    session_cart.session_key = None  # Clear session key
                    session_cart.save()
                    cart = session_cart
            
            if not wishlist:
                session_wishlist = Wishlist.objects.filter(
                    session_key=session_key, 
                    page=page,
                    user__isnull=True  # Only get wishlists without users
                ).first()
                
                if session_wishlist:
                    print(f"🔄 Transferring session wishlist to user")
                    session_wishlist.user = request.user
                    session_wishlist.session_key = None
                    session_wishlist.save()
                    wishlist = session_wishlist
                    
        else:
            print(f"👤 User is NOT authenticated (guest)")
            # For guest users, use session only
            cart = Cart.objects.filter(
                session_key=session_key, 
                page=page,
                user__isnull=True  # Ensure no user is attached
            ).first()
            
            wishlist = Wishlist.objects.filter(
                session_key=session_key, 
                page=page,
                user__isnull=True
            ).first()
        
        print(f"📦 Final cart: {cart}")
        print(f"❤️ Final wishlist: {wishlist}")
        
        cart_data = {
            'cart_total': cart.get_total_quantity() if cart else 0,
            'cart_items_count': cart.items.count() if cart else 0,
            'wishlist_count': wishlist.items.count() if wishlist else 0,
            'cart': cart,  # Pass the cart object itself
            'wishlist': wishlist,  # Pass the wishlist object itself
            'is_authenticated': request.user.is_authenticated,
            'user_id': request.user.id if request.user.is_authenticated else None,
            'username': request.user.username if request.user.is_authenticated else 'Guest',
        }
        
        return cart_data
        
    except Exception as e:
        print(f"❌ Error in get_cart_data_for_template: {e}")
        import traceback
        traceback.print_exc()
        return {
            'cart_total': 0,
            'cart_items_count': 0,
            'wishlist_count': 0,
            'cart': None,
            'wishlist': None,
            'is_authenticated': False,
            'user_id': None,
            'username': 'Guest',
        }


# @csrf_exempt
# @require_POST
# def remove_from_cart(request, subdomain):
#     """Remove item from cart"""
#     try:
#         page = get_object_or_404(PublishedPage, subdomain=subdomain)
#         data = json.loads(request.body)
#         product_id = data.get('product_id')

#         # Ensure session exists
#         if not request.session.session_key:
#             request.session.create()
        
#         session_key = request.session.session_key

#         # Find cart - try user first, then session
#         cart = None
#         if request.user.is_authenticated:
#             cart = Cart.objects.filter(
#                 user=request.user,
#                 page=page
#             ).first()
            
#             if not cart:
#                 cart = Cart.objects.filter(
#                     session_key=session_key,
#                     page=page
#                 ).first()
#         else:
#             cart = Cart.objects.filter(
#                 session_key=session_key,
#                 page=page
#             ).first()

#         if not cart:
#             return JsonResponse({'success': False, 'error': 'Cart not found'})

#         cart_item = get_object_or_404(CartItem, cart=cart, product_id=product_id)
#         cart_item.delete()

#         return JsonResponse({
#             'success': True,
#             'message': 'Item removed from cart',
#             'cart_total': cart.get_total_quantity(),
#             'cart_items_count': cart.items.count()
#         })

#     except Exception as e:
#         print(f"❌ Remove from cart error: {str(e)}")
#         return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_POST
def remove_from_cart(request, subdomain):
    """Remove item from cart - supports both cart_item_id and product_id"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        data = json.loads(request.body)
        
        cart_item_id = data.get('cart_item_id')
        product_id = data.get('product_id')

        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key

        # Find cart
        cart = None
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user, page=page).first()
            if not cart:
                cart = Cart.objects.filter(session_key=session_key, page=page).first()
        else:
            cart = Cart.objects.filter(session_key=session_key, page=page).first()

        if not cart:
            return JsonResponse({'success': False, 'error': 'Cart not found'})

        # ✅ Check which parameter was provided
        if cart_item_id:
            # Remove by specific cart item ID
            cart_item = CartItem.objects.filter(id=cart_item_id, cart=cart).first()
            if not cart_item:
                return JsonResponse({'success': False, 'error': 'Item not found in cart'})
            cart_item.delete()
            deleted_count = 1
            print(f"🗑️ Removed cart item {cart_item_id}")
        elif product_id:
            # Fallback: Remove ALL items with this product_id
            cart_items = CartItem.objects.filter(cart=cart, product_id=product_id)
            if not cart_items.exists():
                return JsonResponse({'success': False, 'error': 'Item not found in cart'})
            deleted_count = cart_items.count()
            cart_items.delete()
            print(f"🗑️ Removed {deleted_count} items with product_id {product_id}")
        else:
            return JsonResponse({'success': False, 'error': 'Either cart_item_id or product_id required'})

        cart_total = cart.get_total_quantity()
        cart_items_count = cart.items.count()

        return JsonResponse({
            'success': True,
            'message': f'Removed {deleted_count} item(s) from cart',
            'cart_total': cart_total,
            'cart_items_count': cart_items_count,
            'deleted_count': deleted_count
        })

    except Exception as e:
        print(f"❌ Remove from cart error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})
@csrf_exempt
@require_POST
def remove_from_wishlist(request, subdomain):
    """Remove item from wishlist"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        data = json.loads(request.body)
        product_id = data.get('product_id')

        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key

        # Find wishlist - try user first, then session
        wishlist = None
        if request.user.is_authenticated:
            wishlist = Wishlist.objects.filter(
                user=request.user,
                page=page
            ).first()
            
            if not wishlist:
                wishlist = Wishlist.objects.filter(
                    session_key=session_key,
                    page=page
                ).first()
        else:
            wishlist = Wishlist.objects.filter(
                session_key=session_key,
                page=page
            ).first()

        if not wishlist:
            return JsonResponse({'success': False, 'error': 'Wishlist not found'})

        wishlist_item = get_object_or_404(WishlistItem, wishlist=wishlist, product_id=product_id)
        wishlist_item.delete()

        return JsonResponse({
            'success': True,
            'message': 'Item removed from wishlist',
            'wishlist_count': wishlist.items.count()
        })

    except Exception as e:
        print(f"❌ Remove from wishlist error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

# Cart and Wishlist management views
@login_required
def view_cart(request, subdomain):
    """View shopping cart"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    cart = Cart.objects.filter(user=request.user, page=page).first()
    
    return render(request, 'builder/cart.html', {
        'page': page,
        'cart': cart
    })




@login_required
def view_wishlist(request, subdomain):
    """View wishlist"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    wishlist = Wishlist.objects.filter(user=request.user, page=page).first()
    
    return render(request, 'builder/wishlist.html', {
        'page': page,
        'wishlist': wishlist
    })

@csrf_exempt
@require_POST
def update_cart_item(request, subdomain):
    """Update cart item quantity"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))

        print(f"🛒 Updating cart item - Product: {product_id}, Quantity: {quantity}")

        # Get the product
        product = get_object_or_404(Product, id=product_id, page=page)

        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key

        # Find cart
        cart = find_cart(request, page, session_key)
        if not cart:
            return JsonResponse({'success': False, 'error': 'Cart not found'})

        # Update quantity
        if quantity <= 0:
            # Remove item if quantity is 0 or less
            cart_item = get_object_or_404(CartItem, cart=cart, product=product)
            cart_item.delete()
            message = f'Removed {product.title} from cart'
        else:
            # Update quantity
            cart.update_item_quantity(product_id, quantity)
            message = f'Updated {product.title} quantity to {quantity}'

        return JsonResponse({
            'success': True,
            'message': message,
            'cart_total': cart.get_total_quantity(),
            'cart_items_count': cart.items.count(),
            'item_quantity': quantity if quantity > 0 else 0
        })

    except Exception as e:
        print(f"❌ Update cart item error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST
def increment_cart_item(request, subdomain):
    """Increment cart item quantity"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        data = json.loads(request.body)
        product_id = data.get('product_id')
        amount = int(data.get('amount', 1))

        print(f"🛒 Incrementing cart item - Product: {product_id}, Amount: {amount}")

        # Get the product
        product = get_object_or_404(Product, id=product_id, page=page)

        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key

        # Find cart
        cart = find_cart(request, page, session_key)
        if not cart:
            return JsonResponse({'success': False, 'error': 'Cart not found'})

        # Increment quantity
        new_quantity = cart.increment_item(product_id, amount)
        
        if new_quantity is not None:
            return JsonResponse({
                'success': True,
                'message': f'Increased {product.title} quantity to {new_quantity}',
                'cart_total': cart.get_total_quantity(),
                'cart_items_count': cart.items.count(),
                'item_quantity': new_quantity
            })
        else:
            # Item doesn't exist in cart, add it
            return add_to_cart(request, subdomain)

    except Exception as e:
        print(f"❌ Increment cart item error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST
def decrement_cart_item(request, subdomain):
    """Decrement cart item quantity"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        data = json.loads(request.body)
        product_id = data.get('product_id')
        amount = int(data.get('amount', 1))

        print(f"🛒 Decrementing cart item - Product: {product_id}, Amount: {amount}")

        # Get the product
        product = get_object_or_404(Product, id=product_id, page=page)

        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key

        # Find cart
        cart = find_cart(request, page, session_key)
        if not cart:
            return JsonResponse({'success': False, 'error': 'Cart not found'})

        # Decrement quantity
        new_quantity = cart.decrement_item(product_id, amount)
        
        if new_quantity is not None:
            if new_quantity == 0:
                message = f'Removed {product.title} from cart'
            else:
                message = f'Decreased {product.title} quantity to {new_quantity}'
            
            return JsonResponse({
                'success': True,
                'message': message,
                'cart_total': cart.get_total_quantity(),
                'cart_items_count': cart.items.count(),
                'item_quantity': new_quantity
            })
        else:
            return JsonResponse({'success': False, 'error': 'Item not found in cart'})

    except Exception as e:
        print(f"❌ Decrement cart item error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST
def clear_cart(request, subdomain):
    """Clear all items from cart"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)

        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key

        # Find cart
        cart = find_cart(request, page, session_key)
        if not cart:
            return JsonResponse({'success': False, 'error': 'Cart not found'})

        # Clear all items
        cart_items_count = cart.items.count()
        cart.items.all().delete()

        return JsonResponse({
            'success': True,
            'message': f'Cleared {cart_items_count} items from cart',
            'cart_total': 0,
            'cart_items_count': 0
        })

    except Exception as e:
        print(f"❌ Clear cart error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})



@csrf_exempt
@require_POST
def clear_wishlist(request, subdomain):
    """Clear all items from wishlist"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)

        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key

        # Find cart
        wishlist = find_wishlist(request, page, session_key)
        if not wishlist:
            return JsonResponse({'success': False, 'error': 'Wishlist not found'})

        # Clear all items
        wishlist_items_count = wishlist.items.count()
        wishlist.items.all().delete()

        return JsonResponse({
            'success': True,
            'message': f'Cleared {wishlist_items_count} items from wishlist',
            'wishlist_total': 0,
            'wishlist_items_count': 0
        })

    except Exception as e:
        print(f"❌ Clear wishlist error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})



# Helper function to find cart
# def find_cart(request, page, session_key):
#     """Helper function to find cart for user/session"""
#     if request.user.is_authenticated:
#         # Try user cart first
#         cart = Cart.objects.filter(user=request.user, page=page).first()
#         if not cart:
#             # Try session cart and transfer to user if found
#             session_cart = Cart.objects.filter(session_key=session_key, page=page).first()
#             if session_cart:
#                 session_cart.user = request.user
#                 session_cart.session_key = None
#                 session_cart.save()
#                 return session_cart
#     else:
#         # Use session cart
#         cart = Cart.objects.filter(session_key=session_key, page=page).first()
    
#     return cart


def find_cart(request, page, session_key):
    """Helper function to find cart for user/session - FIXED VERSION"""
    print(f"🔍 find_cart - User: {request.user}, Authenticated: {request.user.is_authenticated}")
    
    cart = None
    
    if request.user.is_authenticated:
        print(f"✅ Looking for user cart for {request.user.username}")
        
        # First: Try user cart
        cart = Cart.objects.filter(
            user=request.user,
            page=page
        ).first()
        
        print(f"🔍 User cart found: {cart}")
        
        # Second: If no user cart, try session cart and transfer
        if not cart:
            print(f"🔍 Looking for session cart to transfer")
            session_cart = Cart.objects.filter(
                session_key=session_key,
                page=page,
                user__isnull=True  # Only carts without users
            ).first()
            
            if session_cart:
                print(f"🔄 Transferring session cart to user")
                session_cart.user = request.user
                session_cart.session_key = None
                session_cart.save()
                cart = session_cart
                
    else:
        print(f"👤 User is guest, using session cart")
        # For guest users, use session cart
        cart = Cart.objects.filter(
            session_key=session_key,
            page=page,
            user__isnull=True  # Ensure no user attached
        ).first()
    
    print(f"📦 Final cart found: {cart}")
    return cart




def find_wishlist(request, page, session_key):
    """Helper function to find wishlist for user/session - FIXED VERSION"""
    print(f"🔍 find_wishlist - User: {request.user}, Authenticated: {request.user.is_authenticated}")
    
    wishlist = None
    
    if request.user.is_authenticated:
        print(f"✅ Looking for user wishlist for {request.user.username}")
        
        # First: Try user cart
        wishlist = Wishlist.objects.filter(
            user=request.user,
            page=page
        ).first()
        
        print(f"🔍 User cart found: {wishlist}")
        
        # Second: If no user cart, try session cart and transfer
        if not wishlist:
            print(f"🔍 Looking for session cart to transfer")
            session_wishlist = Wishlist.objects.filter(
                session_key=session_key,
                page=page,
                user__isnull=True  # Only carts without users
            ).first()
            
            if session_wishlist:
                print(f"🔄 Transferring session cart to user")
                session_wishlist.user = request.user
                session_wishlist.session_key = None
                session_wishlist.save()
                wishlist = session_wishlist
                
    else:
        print(f"👤 User is guest, using session cart")
        # For guest users, use session cart
        wishlist = Wishlist.objects.filter(
            session_key=session_key,
            page=page,
            user__isnull=True  # Ensure no user attached
        ).first()
    
    print(f"📦 Final cart found: {wishlist}")
    return wishlist





@csrf_exempt
@require_POST
def submit_review(request, subdomain):
    """Submit a product review - FIXED authentication"""
    try:
        print(f"🎯 SUBMIT REVIEW - User: {request.user}, Auth: {request.user.is_authenticated}")
        
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        # data = json.loads(request.body)

         # Get form data
        product_id = request.POST.get('product_id')
        user_name = request.POST.get('user_name', '').strip()
        rating = int(request.POST.get('rating', 0))
        title = request.POST.get('title', '').strip()
        comment = request.POST.get('comment', '').strip()
        is_verified = request.POST.get('is_verified') == 'on'

        # Validation
        if not user_name:
            return JsonResponse({'success': False, 'error': 'Please enter your name'})
        
        if not 1 <= rating <= 5:
            return JsonResponse({'success': False, 'error': 'Please select a valid rating'})
        
        if not comment:
            return JsonResponse({'success': False, 'error': 'Please write your review'})
        
        # Debug user info
        if request.user.is_authenticated:
            print(f"✅ Submitting as authenticated user: {request.user.username} (ID: {request.user.id})")
        else:
            print(f"👤 Submitting as guest user")
        
        # # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        
        # # Check for existing review
        # review_filter = {'product_id': product_id}
        
        # if request.user.is_authenticated:
        #     review_filter['user'] = request.user
        #     review_filter['session_key__isnull'] = True  # Only user reviews
        # else:
        #     review_filter['user__isnull'] = True  # Only guest reviews
        #     review_filter['session_key'] = session_key
        
        # existing_review = ProductReview.objects.filter(**review_filter).first()
        
        # if existing_review:
        #     return JsonResponse({
        #         'success': False, 
        #         'error': 'You have already reviewed this product'
        #     })
        
        # Create review
        review = ProductReview.objects.create(
            product_id=product_id,
            user=request.user if request.user.is_authenticated else None,
            author_name=user_name,
            session_key=session_key if not request.user.is_authenticated else None,
            rating=rating,
            title=title,
            comment=comment,
            is_verified_purchase=is_verified,
            is_approved=True
        )
        
        print(f"✅ Review created: ID {review.id}, User: {review.user}, Session: {review.session_key}")
        
        return JsonResponse({
            'success': True,
            'message': 'Review submitted successfully',
            'review_id': review.id
        })
        
    except Exception as e:
        print(f"❌ Review error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})
    

@csrf_exempt
@require_POST
def mark_review_helpful(request, subdomain):
    """Mark a review as helpful"""
    try:
        data = json.loads(request.body)
        review_id = data.get('review_id')
        
        review = get_object_or_404(ProductReview, id=review_id)
        
        # Ensure session exists for guest users
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        
        # Check if already voted
        vote_filter = {
            'review': review,
        }
        
        if request.user.is_authenticated:
            vote_filter['user'] = request.user
            vote_filter['session_key'] = None
        else:
            vote_filter['user'] = None
            vote_filter['session_key'] = session_key
        
        existing_vote = ReviewHelpful.objects.filter(**vote_filter).first()
        if existing_vote:
            return JsonResponse({'success': False, 'error': 'You have already marked this review as helpful'})
        
        # Create helpful vote
        ReviewHelpful.objects.create(
            review=review,
            user=request.user if request.user.is_authenticated else None,
            session_key=session_key if not request.user.is_authenticated else None
        )
        
        # Update helpful count
        review.helpful_count += 1
        review.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Review marked as helpful',
            'helpful_count': review.helpful_count
        })
        
    except Exception as e:
        print(f"❌ Helpful vote error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

from django.db.models import Avg, Count  # Import Avg and Count

def get_product_reviews(request, subdomain, product_id):
    """Get reviews for a product"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        product = get_object_or_404(Product, id=product_id, page=page)

        # DEBUG: Add logging
        print(f"🔍 Looking for reviews for product {product_id} on page {subdomain}")
        print(f"📦 Found product: {product.title if product else 'NOT FOUND'}")
        
        reviews = product.reviews.filter(is_approved=True).select_related('user')

        # DEBUG: Log review count
        print(f"📝 Found {reviews.count()} reviews for product {product_id}")
        
        # Calculate rating statistics
        # total_reviews = reviews.count()
        # if total_reviews > 0:
        #     avg_rating = reviews.aggregate(avg=models.Avg('rating'))['avg']
        #     rating_distribution = reviews.values('rating').annotate(count=models.Count('id')).order_by('rating')
        # else:
        #     avg_rating = 0
        #     rating_distribution = []

        # Assuming 'reviews' is a queryset of your review model
        # total_reviews = reviews.count()

        # Assuming 'reviews' is a queryset of your review model
        # reviews = Review.objects.all()  # Replace with your actual queryset

        # Initialize the rating distribution dictionary
        rating_distribution = {i: 0 for i in range(1, 6)}  # Assuming ratings are from 1 to 5

        # Count total reviews
        total_reviews = reviews.count()

        if total_reviews > 0:
            # Populate the rating distribution
            for review in reviews:
                if review.rating in rating_distribution:
                    rating_distribution[review.rating] += 1

            # Calculate average rating
            total_rating = sum(review.rating for review in reviews)
            avg_rating = total_rating / total_reviews
        else:
            avg_rating = 0  # Handle case where there are no reviews

        # Now you can use rating_distribution and avg_rating
        print("Average Rating:", avg_rating)
        print("Rating Distribution:", rating_distribution)
        
        reviews_data = []
        for review in reviews:
            reviews_data.append({
                'id': review.id,
                # 'user_name': review.author_name if review.user else 'Anonymous',
                'user_name': review.author_name or 'Anonymous',  # Use author_name here
                'author_name': review.author_name or 'Anonymous',  # ADD THIS
                'rating': review.rating,
                'title': review.title,
                'comment': review.comment,
                'helpful_count': review.helpful_count,
                'created_at': review.created_at.strftime('%B %d, %Y'),
                'is_verified': review.is_verified_purchase,
            })
        
        return JsonResponse({
            'success': True,
            'reviews': reviews_data,
            'statistics': {
                'total_reviews': total_reviews,
                'average_rating': round(avg_rating, 1) if avg_rating else 0,
                'rating_distribution': list(rating_distribution),
            }
        })
        
    except Exception as e:
        print(f"❌ Get reviews error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}) 



# builder/views.py - Update product_detail_page function
# builder/views.py - Update product_detail_page function
def product_detail_page(request, product_slug):
    """Product detail page with all customizations"""
    # Get subdomain from request (set by middleware)
    subdomain = getattr(request, 'subdomain', None)
    
    if not subdomain:
        # Fallback: try to extract from published_page
        if hasattr(request, 'published_page'):
            subdomain = request.published_page.subdomain
        else:
            # Last resort: try to extract from host
            host = request.get_host().lower()
            if 'localhost' in host:
                parts = host.split('.')
                subdomain = parts[0] if len(parts) > 1 else None
            else:
                parts = host.split('.')
                subdomain = parts[0] if len(parts) >= 3 else None
    
    if not subdomain:
        raise Http404("Subdomain not found")
    
    # Get the website
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
    # Get the product
    product = get_object_or_404(Product, slug=product_slug, page=page)
    if product.colors:
        colors=[w.strip() for w in product.colors.split(',')]
    else:
        colors=''
    
    if product.sizes:
        sizes=[w.strip() for w in product.sizes.split(',')]
    else:
        sizes=''

    images=product.product_images.all()[:4]


   # ADD THIS TRACKING LOGIC:
    from django.utils import timezone
    from django.db import transaction
    
    try:
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        
        # Use atomic transaction to handle potential race conditions
        with transaction.atomic():
            # Try to get existing entry
            existing = RecentlyViewedProduct.objects.filter(
                page=page,
                product=product,
                session_key=session_key,
                user=request.user if request.user.is_authenticated else None
            ).first()
            
            if existing:
                # Update timestamp
                existing.viewed_at = timezone.now()
                existing.save()
                print(f"🔄 Updated timestamp for existing entry")
            else:
                # Create new entry
                RecentlyViewedProduct.objects.create(
                    page=page,
                    product=product,
                    session_key=session_key,
                    user=request.user if request.user.is_authenticated else None,
                    viewed_at=timezone.now()
                )
                print(f"✅ Created new recently viewed entry")
                
    except IntegrityError:
        # If we get integrity error (race condition), just update existing
        RecentlyViewedProduct.objects.filter(
            page=page,
            product=product,
            session_key=session_key,
            user=request.user if request.user.is_authenticated else None
        ).update(viewed_at=timezone.now())
        print(f"🔄 Recovered from integrity error by updating")
        
    except Exception as e:
        print(f"⚠️ Recently viewed tracking failed: {str(e)}")
        # Continue with page render even if tracking fails  

    # Get recently viewed products for this user/session
    if request.user.is_authenticated:
        recent_products = RecentlyViewedProduct.objects.filter(
            page=page,
            user=request.user
        ).order_by('-viewed_at').select_related('product')[:10]
    else:
        recent_products = RecentlyViewedProduct.objects.filter(
            page=page,
            session_key=session_key
        ).order_by('-viewed_at').select_related('product')[:10]

    
   
        
    
    print(f"🛍️ Rendering product detail: {product.title} on {page.brand_name}")
    
    # Load customizations from the 'products' page
    page_key = 'product-details'
    page_key2='home'
    page_data = page.page_customizations.get(page_key and page_key2, {})

    home_page_data = page.page_customizations.get(page_key2, {})
    current_page_data = page.page_customizations.get(page_key, {})

    # Print raw data structure
    print("\n" + "="*50)
    print(f"HOMEPAGE DATA STRUCTURE:")
    print(f"Type: {type(home_page_data)}")
    print(f"Keys: {list(home_page_data.keys())}")
    if 'text_contents' in home_page_data:
        print(f"Homepage text_contents keys: {list(home_page_data['text_contents'].keys())}")
        print(f"Homepage text_contents values: {home_page_data['text_contents']}")

    print("\n" + "="*50)
    print(f"CURRENT PAGE ({page_key}) DATA STRUCTURE:")
    print(f"Type: {type(current_page_data)}")
    print(f"Keys: {list(current_page_data.keys())}")
    if 'text_contents' in current_page_data:
        print(f"Current page text_contents keys: {list(current_page_data['text_contents'].keys())}")
        print(f"Current page text_contents values: {current_page_data['text_contents']}")

    # Now merge properly
    page_data = {}

    # Copy all homepage data first
    for key, value in home_page_data.items():
        if isinstance(value, dict):
            page_data[key] = value.copy()  # Deep copy for nested dicts
        else:
            page_data[key] = value

    # Overlay with current page data
    for key, value in current_page_data.items():
        if key in page_data and isinstance(page_data[key], dict) and isinstance(value, dict):
            # Merge nested dictionaries
            page_data[key].update(value)
        else:
            page_data[key] = value

    print("\n" + "="*50)
    print(f"MERGED DATA STRUCTURE:")
    print(f"Keys: {list(page_data.keys())}")
    if 'text_contents' in page_data:
        print(f"Merged text_contents keys: {list(page_data['text_contents'].keys())}")
        print(f"Merged text_contents values: {page_data['text_contents']}")
    print("="*50 + "\n")
    home_page_data = page.page_customizations.get(page_key2, {})
        # GET HIDDEN SECTIONS - This is crucial!
    hidden_sections = page_data.get('hidden_sections', {})

    
    print(f"📦 Loaded customizations from '{page_key}' page:", {
        'texts': len(page_data.get('text_contents', {})),
        'styles': len(page_data.get('style_customizations', {})),
        'components': len(page_data.get('component_layout', [])),
        'component_customizations': len(page_data.get('component_customizations', []))
    })
    print(f"Page texts {page_data.get('text_contents', {})}")
    
    # Load component layout from page data
    components_data = []
    component_layout = page_data.get('component_layout', [])
    component_customizations_list = page_data.get('component_customizations', [])
    
    if component_layout:
        print(f"🧩 Loading {len(component_layout)} components from layout")
        for component_ref in component_layout:
            try:
                component = load_component_from_file(component_ref['component_id'])
                if component:
                    # Get customizations for this component instance
                    customizations = {}
                    for comp_custom in component_customizations_list:
                        if comp_custom.get('instance_id') == component_ref.get('instance_id'):
                            customizations = comp_custom.get('customizations', {})
                            break

                    # Apply customizations
                    processed_html = apply_component_customizations(
                        component['html_content'],
                        customizations
                    )

                    components_data.append({
                        'instance_id': component_ref['instance_id'],
                        'component_id': component_ref['component_id'],
                        'drop_zone': component_ref.get('drop_zone', 'end'),
                        'html_content': mark_safe(processed_html),
                        'customizations': customizations,
                    })
            except Exception as e:
                print(f"❌ Error loading component {component_ref['component_id']}: {e}")
    
    # Load other customizations
    text_contents = page_data.get('text_contents', {})
    style_customizations = page_data.get('style_customizations', {})
    background_images = page_data.get('background_images', {})
    icon_customizations = page_data.get('icon_customizations', {})

    home_text_contents = home_page_data.get('text_contents', {})
    home_style_customizations = home_page_data.get('style_customizations', {})
    home_background_images = home_page_data.get('background_images', {})
    home_icon_customizations = home_page_data.get('icon_customizations', {})

    

    
    # ===== LOAD VIDEO CUSTOMIZATIONS =====
    video_customizations = {}
    video_objects = VideoCustomization.objects.filter(
        page=page,
        page_name=page_key
    )
    
    for video in video_objects:
        video_customizations[video.element_id] = {
            'video_url': video.video_file.url if video.video_file else video.video_url,
            'poster_url': video.poster_image.url if video.poster_image else None,
            'alt_text': video.alt_text or '',
            'autoplay': video.autoplay,
            'loop': video.loop,
            'muted': video.muted,
            'controls': video.controls,
            'show_play_button': video.show_play_button,
            'element_id': video.element_id
        }

    # Load background images from database
    background_images_db = {}
    bg_objects = page.background_images.all()
    
    for bg in bg_objects:
        image_url = bg.image.url if bg.image else None
        clean_element_id = extract_numeric_id(bg.element_id)
        if clean_element_id and image_url:
            background_images_db[clean_element_id] = {
                'image_url': image_url,
                'element_id': bg.element_id,
                'has_image': True
            }
    
    # Get related products
    # related_products = page.products.exclude(id=product.id).order_by('-created_at')[:4]
    related_products = Product.objects.filter(category=product.category, page=page).exclude(id=product.id)[:5]

    
    # Check if user is authenticated and a member
    is_website_member = False
    if request.user.is_authenticated:
        try:
            from accounts.models import WebsiteUser
            is_website_member = WebsiteUser.objects.filter(
                user=request.user,
                website=page,
                is_active=True
            ).exists()
        except ImportError:
            pass
    
    # Get all products for navigation
    all_products = page.products.all().order_by('title')
    
    # Dynamic style ranges
    section_range = list(range(1, 500))
    component_range = list(range(1, 500))

    variants = ProductVariant.objects.filter(
        product__page=page,
        cj_vid__isnull=False
    )

    print(f"Variants are {variants}")
    reviews = ProductReview.objects.filter(product=product).order_by('-created_at')
     # Calculate statistics
    review_count = reviews.count()
    
    if review_count > 0:
        average_rating = reviews.aggregate(Avg('rating'))['rating__avg']
        average_rating = round(average_rating, 1)
    else:
        average_rating = 0.0

     # Only approved reviews
    reviews_qs = product.reviews.filter(is_approved=True)

    total_reviews = reviews_qs.count()

    # Count ratings
    rating_counts = reviews_qs.values('rating').annotate(count=Count('rating'))

    # Initialize defaults
    rating_data = {
        1: {'count': 0, 'percentage': 0},
        2: {'count': 0, 'percentage': 0},
        3: {'count': 0, 'percentage': 0},
        4: {'count': 0, 'percentage': 0},
        5: {'count': 0, 'percentage': 0},
    }

    # Fill counts
    for r in rating_counts:
        rating_data[r['rating']]['count'] = r['count']

    # Calculate percentages
    if total_reviews > 0:
        for star in rating_data:
            rating_data[star]['percentage'] = round(
                (rating_data[star]['count'] / total_reviews) * 100, 1
            )
    full_stars = int(average_rating)
    has_half_star = (average_rating - full_stars) >= 0.5
    # Context for template rendering
    context = {
        'page': page,
        'product': product,
        'product_images':images,
        'related_products': related_products,
        'all_products': all_products,
        'recently_viewed_products': recent_products,
        'colors':colors,
        'sizes':sizes,
        'variants':variants,

        # ===== VIDEO AND IMAGE CUSTOMIZATIONS =====
        'video_customizations': video_customizations,
        # 'image_customizations': image_customizations,

        'reviews': reviews,
        'review_count': review_count,
        'average_rating': average_rating,
        'reviews': reviews_qs,
        'total_reviews': total_reviews,
        'rating_data': rating_data,
        'full_stars': full_stars,
        'has_half_star': has_half_star,
        
        # CUSTOMIZATIONS - THESE WERE MISSING!
        'current_page': 'product_details',
        'components': components_data,
        'text_contents': text_contents,
        'home_text_contents': home_text_contents,
        'style_customizations': style_customizations,
        'home_style_customizations':home_style_customizations,
        'background_images': background_images_db,
        'home_background_images': home_background_images,
        'icon_customizations': icon_customizations,
        
        # Other data
        'is_website_member': is_website_member,
        'user': request.user,
        
        # Dynamic style ranges
        'section_range': section_range,
        'component_range': component_range,
        
        # Hidden sections (if any)
        'hidden_sections': page_data.get('hidden_sections', {}),
    }
    
    # Try to render product detail template
    try:
        # First try: template_name/product_details.html
        template_path = f'builder/public_templates/{page.template_name}/product_details.html'
        return render(request, template_path, context)
    except TemplateDoesNotExist:
        # Second try: template_name/product_detail.html
        try:
            template_path = f'builder/public_templates/{page.template_name}/product_detail.html'
            return render(request, template_path, context)
        except TemplateDoesNotExist:
            # Third try: template_name/product.html
            try:
                template_path = f'builder/public_templates/{page.template_name}/product.html'
                return render(request, template_path, context)
            except TemplateDoesNotExist:
                # Fallback: generic product detail template
                return render(request, 'builder/product_detail.html', context)


# builder/views.py - Add this function

from django.http import JsonResponse
import json

def get_variant_by_options(request, subdomain):
    """
    API endpoint to get variant details by selected options.
    Used for AJAX swatch selection in grouped product display.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)
    
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
        
        product_id = request.GET.get('product_id')
        group_id = request.GET.get('group_id')
        options_json = request.GET.get('options', '{}')
        
        try:
            options = json.loads(options_json)
        except json.JSONDecodeError:
            options = {}
        
        product = get_object_or_404(Product, id=product_id, page=page)
        
        variant = None
        
        # If group_id is provided, find variant in that group
        if group_id:
            from builder.services.variant_grouping import VariantGroupManager
            group_manager = VariantGroupManager(product)
            variant = group_manager.get_variant_for_cart(group_id, options)
        
        # If no variant found and options provided, try direct match
        if not variant and options:
            variant = product.variants.filter(options=options).first()
        
        # If still no variant, get first in-stock variant
        if not variant:
            variant = product.variants.filter(quantity__gt=0).first()
        
        # Last resort: first variant
        if not variant:
            variant = product.variants.first()
        
        if not variant:
            return JsonResponse({
                'success': False,
                'error': 'No variant found'
            }, status=404)
        
        return JsonResponse({
            'success': True,
            'variant': {
                'id': variant.id,
                'price': float(variant.price) if variant.price else None,
                'compare_at_price': float(variant.compare_at_price) if variant.compare_at_price else None,
                'quantity': variant.quantity,
                'sku': variant.sku,
                'cj_vid': variant.cj_vid,
                'image_url': variant.image.url if variant.image else None,
                'options': variant.options,
                'is_in_stock': variant.quantity > 0 if variant.track_quantity else True,
            }
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

def product_list_page(request):
    """Product listing page for published websites"""
    try:
        # Get the page from the request (using middleware)
        if not hasattr(request, 'published_page') or not request.published_page:
            raise Http404("Page not found")
        
        page = request.published_page
        
        # Get filter parameters
        category = request.GET.get('category', '')
        sort = request.GET.get('sort', 'newest')
        search = request.GET.get('search', '')
        
        # Base queryset
        products = Product.objects.filter(page=page, is_active=True)
        
        # Apply filters
        if category:
            products = products.filter(category__iexact=category)
        
        if search:
            products = products.filter(
                models.Q(title__icontains=search) | 
                models.Q(description__icontains=search)
            )
        
        # Apply sorting
        if sort == 'newest':
            products = products.order_by('-created_at')
        elif sort == 'price_low':
            products = products.order_by('price')
        elif sort == 'price_high':
            products = products.order_by('-price')
        elif sort == 'name':
            products = products.order_by('title')
        elif sort == 'rating':
            # This would require a more complex query for average rating
            products = products.order_by('-created_at')
        
        # Get categories for filter dropdown
        categories = Product.objects.filter(page=page, is_active=True).values_list('category', flat=True).distinct()
        
        context = {
            'page': page,
            'products': products,
            'categories': [cat for cat in categories if cat],  # Remove empty categories
            'current_category': category,
            'current_sort': sort,
            'current_search': search,
        }
        
        # Try to use product list template specific to this template, fallback to default
        try:
            return render(request, f'builder/public_templates/{page.template_name}/products.html', context)
        except TemplateDoesNotExist:
            return render(request, 'builder/public_products.html', context)
            
    except PublishedPage.DoesNotExist:
        raise Http404("Page not found")




def test_auth(request):
    """Test authentication endpoint"""
    data = {
        'user_id': request.user.id,
        'username': request.user.username,
        'is_authenticated': request.user.is_authenticated,
        'is_staff': request.user.is_staff,
        'is_superuser': request.user.is_superuser,
        'email': request.user.email,
        'session_key': request.session.session_key,
        'auth_user_id': request.session.get('_auth_user_id'),
    }
    return JsonResponse(data)


def test_middleware_order(request):
    """Test if middleware is running in correct order"""
    response_data = {
        'middleware_tested': 'SubdomainMiddleware',
        'user_at_view_level': {
            'username': request.user.username,
            'is_authenticated': request.user.is_authenticated,
            'class': str(request.user.__class__),
        },
        'session_data': {
            'auth_user_id': request.session.get('_auth_user_id'),
        },
        'custom_attrs': {
            'has_published_page': hasattr(request, 'published_page'),
            'has_subdomain': hasattr(request, 'subdomain'),
            'published_page': str(getattr(request, 'published_page', None)),
            'subdomain': getattr(request, 'subdomain', None),
        }
    }
    
    # Check specific URLs
    if 'admin' in request.path:
        response_data['is_admin'] = True
    
    return JsonResponse(response_data)



from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import ProductCategory


@login_required
def manage_product_categories(request, subdomain):
    """Manage product categories with AJAX responses"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Handle POST request for creating categories
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            
            if not name:
                return JsonResponse({
                    'success': False, 
                    'error': 'Category name is required'
                })
            
            # Handle image upload
            image = request.FILES.get('image')
            
            # Create category
            category = ProductCategory.objects.create(
                page=page,
                name=name,
                description=description,
                image=image if image else None
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Category created successfully!',
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'slug': category.slug,
                    'image_url': category.image.url if category.image else None,
                    'products_count': category.products.count(),
                    'active_products_count': category.get_active_products_count()
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    # Handle AJAX GET request for loading categories
    elif request.method == 'GET' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            categories = page.product_categories.all().order_by('display_order', 'name')
            data = [{
                'id': cat.id,
                'name': cat.name,
                'description': cat.description,
                'slug': cat.slug,
                'image_url': cat.image.url if cat.image else None,
                'products_count': cat.products.count(),
                'active_products_count': cat.get_active_products_count()
            } for cat in categories]
            
            return JsonResponse({
                'success': True,
                'categories': data
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    # Regular template render for initial page load
    categories = page.product_categories.all().order_by('display_order', 'name')
    return render(request, 'builder/manage_product_categories.html', {
        'page': page,
        'categories': categories
    })

@login_required
def edit_product_category(request, subdomain, category_id):
    """Edit a product category"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    category = get_object_or_404(ProductCategory, id=category_id, page=page)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        display_order = request.POST.get('display_order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if name:
            category.name = name
            category.description = description
            category.display_order = display_order
            category.is_active = is_active
            category.save()
            
            messages.success(request, f'Category "{name}" updated successfully!')
            return redirect('manage_product_categories', subdomain=subdomain)
    
    return render(request, 'builder/edit_product_category.html', {
        'page': page,
        'category': category
    })

@login_required
def delete_product_category(request, subdomain, category_id):
    """Delete a product category"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    category = get_object_or_404(ProductCategory, id=category_id, page=page)
    
    if request.method == 'POST':
        category_name = category.name
        category.delete()
        messages.success(request, f'Category "{category_name}" deleted successfully!')
        return redirect('manage_product_categories', subdomain=subdomain)
    
    return render(request, 'builder/delete_product_category.html', {
        'page': page,
        'category': category
    })




def get_recently_viewed_products(request, subdomain):
    """Get 10 most recently viewed products for current visitor"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain)
        
        # Get session key for anonymous users
        session_key = request.session.session_key
        
        # Query recently viewed products
        if request.user.is_authenticated:
            # For logged-in users, use user ID
            recently_viewed = RecentlyViewedProduct.objects.filter(
                page=page,
                user=request.user
            ).select_related('product').order_by('-viewed_at')[:10]
        else:
            # For anonymous users, use session key
            recently_viewed = RecentlyViewedProduct.objects.filter(
                page=page,
                session_key=session_key
            ).select_related('product').order_by('-viewed_at')[:10]
        
        # Prepare product data
        products_data = []
        for rvp in recently_viewed:
            product = rvp.product
            products_data.append({
                'id': product.id,
                'title': product.title,
                'description': product.description[:100] + '...' if len(product.description) > 100 else product.description,
                'price': str(product.price),
                'image_url': product.image.url if product.image else None,
                'viewed_at': rvp.viewed_at.strftime('%b %d, %Y'),
                'page_url': f"/products/{product.id}/"  # Adjust based on your URL pattern
            })
        
        return JsonResponse({
            'success': True,
            'products': products_data,
            'count': len(products_data)
        })
        
    except Exception as e:
        print(f"❌ Error getting recently viewed products: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})
    










# CJ Dropshipping

import json
import logging
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.contrib import messages
from django.db.models import F
   
from .models import PublishedPage, CJSettings, CJProduct, CJOrder, CJSyncLog
import json
import logging
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib import messages

from .models import PublishedPage, CJSettings, CJProduct, CJOrder, CJSyncLog, Product
from .services.cj_service import CJService, CJOrderRequest,CJManager

from builder import models

import json
import logging
from datetime import timedelta
from typing import Dict, Any

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.views.decorators.csrf import csrf_protect

from .models import PublishedPage, CJSettings, CJProduct, CJOrder, CJSyncLog, Product


logger = logging.getLogger(__name__)


@login_required
def cj_settings(request, subdomain):
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)

    try:
        cj_settings_obj = page.cj_settings.get()
    except CJSettings.DoesNotExist:
        cj_settings_obj = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_settings':
            # Create or update settings
            if not cj_settings_obj:
                cj_settings_obj = CJSettings(page=page)

            api_key = request.POST.get('api_key', '').strip()

            # Only update if a new key is provided
            if api_key:
                cj_settings_obj.api_key = api_key

                # TEST THE API KEY HERE
                try:
                    # Import your CJ service
                    from .services.cj_service import CJService
                    
                    # Try to get access token with the API key
                    test_service = CJService(api_key)
                    # Try a simple API call to validate
                    response = test_service.get_warehouses()
                    
                    # If we got a valid response (even empty list is fine)
                    if response is not None:
                        cj_settings_obj.api_status = 'active'
                        cj_settings_obj.is_active = True
                        messages.success(request, 'API key validated successfully!')
                    else:
                        cj_settings_obj.api_status = 'invalid'
                        cj_settings_obj.is_active = False
                        messages.error(request, 'Invalid API key. Please check and try again.')
                        
                except Exception as e:
                    cj_settings_obj.api_status = 'invalid'
                    cj_settings_obj.is_active = False
                    messages.error(request, f'API key validation failed: {str(e)}')

            # Update other settings
            cj_settings_obj.auto_fulfill = request.POST.get('auto_fulfill') == 'on'
            cj_settings_obj.auto_sync_prices = request.POST.get('auto_sync_prices') == 'on'
            cj_settings_obj.auto_sync_inventory = request.POST.get('auto_sync_inventory') == 'on'
            cj_settings_obj.default_profit_margin = request.POST.get('default_profit_margin', '30.00')
            cj_settings_obj.default_warehouse = request.POST.get('default_warehouse', 'CN')
            cj_settings_obj.currency = request.POST.get('currency', 'USD')
            cj_settings_obj.price_sync_interval = int(request.POST.get('price_sync_interval', 24))
            cj_settings_obj.inventory_sync_interval = int(request.POST.get('inventory_sync_interval', 6))
            
            cj_settings_obj.save()
            messages.success(request, 'Settings saved successfully!')

        elif action == 'test_connection' and cj_settings_obj:
            # Test connection with existing API key
            try:
                from .services.cj_service import CJService
                test_service = CJService(cj_settings_obj.api_key)
                response = test_service.get_warehouses()
                
                if response is not None:
                    cj_settings_obj.api_status = 'active'
                    cj_settings_obj.is_active = True
                    cj_settings_obj.save(update_fields=['api_status', 'is_active'])
                    messages.success(request, 'API connection test successful!')
                else:
                    cj_settings_obj.api_status = 'invalid'
                    cj_settings_obj.is_active = False
                    cj_settings_obj.save(update_fields=['api_status', 'is_active'])
                    messages.error(request, 'API test failed. Invalid API key.')
                    
            except Exception as e:
                messages.error(request, f'Connection test failed: {str(e)}')

        elif action == 'toggle_active' and cj_settings_obj:
            cj_settings_obj.is_active = not cj_settings_obj.is_active
            cj_settings_obj.save(update_fields=['is_active'])
            status = 'activated' if cj_settings_obj.is_active else 'deactivated'
            messages.success(request, f'CJ integration {status}')

        return redirect('cj_settings', subdomain=subdomain)

    # Calculate API usage for display
    api_usage = {
        'today': cj_settings_obj.daily_api_calls if cj_settings_obj else 0,
        'limit': cj_settings_obj.max_daily_calls if cj_settings_obj else 950,
        'percentage': 0
    }
    if cj_settings_obj and cj_settings_obj.max_daily_calls > 0:
        api_usage['percentage'] = (cj_settings_obj.daily_api_calls / cj_settings_obj.max_daily_calls) * 100

    context = {
        'page': page,
        'cj_settings': cj_settings_obj,
        'api_usage': api_usage,
        'currencies': [
            ('USD', 'US Dollar'),
            ('EUR', 'Euro'),
            ('GBP', 'British Pound'),
            ('CAD', 'Canadian Dollar'),
            ('AUD', 'Australian Dollar'),
        ],
        'warehouses': [
            ('CN', 'China Warehouse'),
            ('US', 'USA Warehouse'),
            ('EU', 'Europe Warehouse'),
            ('RU', 'Russia Warehouse'),
        ]
    }

    return render(request, 'builder/cj_settings.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def validate_cj_api_key(request):
    """
    Validate a CJ Dropshipping API key by testing the connection.
    """
    try:
        import json
        data = json.loads(request.body)
        api_key = data.get('api_key', '').strip()
        
        if not api_key:
            return JsonResponse({
                'success': False,
                'error': 'API key is required'
            }, status=400)
        
        # Test the API key by calling CJ's authentication endpoint
        auth_url = "https://developers.cjdropshipping.com/api2.0/v1/authentication/getAccessToken"
        
        response = requests.post(
            auth_url,
            json={"apiKey": api_key},
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                # Valid API key - we got a token
                return JsonResponse({
                    'success': True,
                    'message': 'API key validated successfully'
                })
            else:
                # API returned an error
                error_msg = result.get("msg", "Invalid API key")
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=400)
        else:
            return JsonResponse({
                'success': False,
                'error': f'API returned status {response.status_code}'
            }, status=400)
            
    except requests.exceptions.Timeout:
        return JsonResponse({
            'success': False,
            'error': 'Connection timed out. Please try again.'
        }, status=408)
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            'success': False,
            'error': 'Could not connect to CJ API. Please check your internet connection.'
        }, status=503)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Validation failed: {str(e)}'
        }, status=500)


def json_response(success: bool, data: Dict = None, error: str = None, 
                 status: int = 200) -> JsonResponse:
    """Standard JSON response"""
    response_data = {
        'success': success,
        'timestamp': timezone.now().isoformat(),
    }
    
    if success:
        response_data['data'] = data or {}
    else:
        response_data['error'] = error or 'Unknown error'
        
    return JsonResponse(response_data, status=status)


def validate_json_request(request):
    """Validate JSON request body"""
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        raise ValueError('Invalid JSON data')



# ============== PRODUCT SEARCH ==============
import requests
# Utility for CJ API Calls
def call_cj_api(settings, endpoint, method="GET", params=None, data=None):
    if not settings.can_make_api_call()[0]:
        return None, "Rate limit exceeded"
    
    url = f"https://developers.cjdropshipping.com/api2.0/v1{endpoint}"
    headers = {"CJ-Access-Token": settings.api_key}
    
    response = requests.request(method, url, headers=headers, params=params, json=data)
    settings.increment_api_calls()
    return response.json(), None
   

from .models import CJSettings
import requests
from django.core.cache import cache

from django.utils import timezone
from datetime import timedelta
import requests


def get_cj_access_token(settings_obj):
    """
    Get a valid CJ access token from settings or fetch a new one.
    """
    from builder.services.cj_service import CJService
    
    if settings_obj.access_token and settings_obj.token_expiry:
        # Check if token is still valid (with 1-day buffer)
        if settings_obj.token_expiry > timezone.now() + timedelta(days=1):
            return settings_obj.access_token
    
    # Fetch new token
    print("🔄 Fetching new CJ Access Token...")
    auth_url = "https://developers.cjdropshipping.com/api2.0/v1/authentication/getAccessToken"
    payload = {"apiKey": settings_obj.api_key}
    
    try:
        response = requests.post(auth_url, json=payload, timeout=10)
        data = response.json()
        
        if data.get("code") == 200:
            new_token = data["data"]["accessToken"]
            settings_obj.access_token = new_token
            settings_obj.token_expiry = timezone.now() + timedelta(days=14)
            settings_obj.api_status = 'active'
            settings_obj.save()
            print("✅ New CJ Access Token obtained")
            return new_token
        else:
            print(f"❌ CJ Auth Error: {data.get('message')}")
            settings_obj.api_status = 'invalid'
            settings_obj.save()
            return None
    except Exception as e:
        print(f"❌ Connection to CJ failed: {e}")
        return None


import requests
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import PublishedPage, CJSettings

import re
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import PublishedPage, CJSettings
from builder.services.cj_service import CJService

# builder/views.py

def cj_product_search(request, subdomain):
    """
    CJ Dropshipping product search - ALWAYS returns JSON for AJAX calls
    """
    
    # ============================================================
    # DETECT AJAX - Force JSON if request is AJAX
    # ============================================================
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Get page
    try:
        if request.user.is_authenticated:
            page = PublishedPage.objects.get(subdomain=subdomain, user=request.user)
        else:
            page = PublishedPage.objects.get(subdomain=subdomain, is_published=True)
    except PublishedPage.DoesNotExist:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Store not found'}, status=404)
        return render(request, 'builder/dashboard/cj_search.html', {'error': 'Store not found'})
    
    query = request.GET.get('q', '').strip()
    
    # ============================================================
    # IF NOT AJAX - Render HTML
    # ============================================================
    if not is_ajax:
        context = {'page': page, 'query': query, 'cj_products': []}
        return render(request, 'builder/dashboard/cj_search.html', context)
    
    # ============================================================
    # AJAX REQUEST - ALWAYS RETURN JSON
    # ============================================================
    
    # If not authenticated, return error
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'error': 'Please log in to search CJ products',
            'data': []
        }, status=401)
    
    # If no query, return empty
    if not query:
        return JsonResponse({
            'success': True,
            'data': [],
            'query': '',
            'count': 0,
            'error': None
        })
    
    # Get CJ settings
    try:
        cj_settings_obj = CJSettings.objects.get(page=page)
    except CJSettings.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'CJ Dropshipping is not configured for this store',
            'data': []
        })
    
    # Get token
    token = get_cj_access_token(cj_settings_obj)
    
    if not token:
        return JsonResponse({
            'success': False,
            'error': 'Failed to authenticate with CJ Dropshipping API',
            'data': []
        })
    
    try:
        import requests
        import re
        from builder.services.cj_service import CJService
        
        service = CJService(token)
        cj_products = []
        
        # Parse Query for PID
        uuid_pattern = r'p-([A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12})'
        numeric_pattern = r'-p-(\d+)'
        uuid_match = re.search(uuid_pattern, query)
        numeric_match = re.search(numeric_pattern, query)
        extracted_id = None
        
        if uuid_match:
            extracted_id = uuid_match.group(1)
        elif numeric_match:
            extracted_id = numeric_match.group(1)
        elif len(query) > 15:
            extracted_id = query
        
        if extracted_id:
            # DIRECT FETCH
            res = requests.get(
                f"{service.BASE_URL}/product/query",
                headers=service.headers,
                params={"pid": extracted_id},
                timeout=30
            )
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == 200:
                    product = data.get("data")
                    if product:
                        cj_products.append(product)
        else:
            # KEYWORD SEARCH
            res = requests.get(
                f"{service.BASE_URL}/product/list",
                headers=service.headers,
                params={"productName": query, "pageSize": 20, "sortType": "3"},
                timeout=30
            )
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == 200:
                    cj_products = data.get("data", {}).get("list", [])
        
        # Enrich with stock
        for item in cj_products:
            total_stock = 0
            variants = item.get('variants', [])
            for variant in variants:
                vid = variant.get('vid')
                if vid:
                    try:
                        stock_data = service.get_stock_by_vid(vid)
                        if stock_data:
                            for wh in stock_data:
                                total_stock += int(wh.get('stockNum', 0))
                    except:
                        pass
            if total_stock == 0:
                for variant in variants:
                    if variant.get('inventoryNum'):
                        total_stock += int(variant.get('inventoryNum', 0))
            
            item['total_stock'] = total_stock
            item['in_stock'] = total_stock > 0
            
            name_slug = item.get('productNameEn', 'product').lower().replace(' ', '-')
            name_slug = re.sub(r'[^a-z0-9-]', '', name_slug)
            item['cj_url_slug'] = name_slug
        
        cj_settings_obj.daily_api_calls += 1
        cj_settings_obj.save(update_fields=['daily_api_calls'])
        
        return JsonResponse({
            'success': True,
            'data': cj_products,
            'query': query,
            'count': len(cj_products),
            'error': None
        })
        
    except Exception as e:
        print(f"CJ search error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'data': []
        })
    
@login_required
@require_http_methods(["GET"])
def cj_search_page(request, subdomain):
    """Render the CJ product search page"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Check if CJ is configured
    try:
        cj_settings = page.cj_settings.get()
        if not cj_settings.is_active:
            messages.warning(request, 'CJ integration is not active. Please activate it in settings.')
            return redirect('cj_settings', subdomain=subdomain)
    except CJSettings.DoesNotExist:
        messages.warning(request, 'Please configure CJ integration first.')
        return redirect('cj_settings', subdomain=subdomain)
    
    context = {
        'page': page,
        'cj_settings': cj_settings,
        'query': request.GET.get('q', '')
    }
    
    return render(request, 'builder/cj_product_search.html', context)


@login_required
@require_http_methods(["GET"])
def cj_product_details(request, subdomain, product_id):
    """View detailed information about a CJ product"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    try:
        cj_settings_obj = page.cj_settings.get()
        if not cj_settings_obj.is_active:
            messages.warning(request, 'CJ integration is not active')
            return redirect('cj_settings', subdomain=subdomain)
    except CJSettings.DoesNotExist:
        messages.warning(request, 'Please configure CJ integration first')
        return redirect('cj_settings', subdomain=subdomain)
    
    token = get_cj_access_token(cj_settings_obj)
    if not token:
        messages.error(request, 'Failed to connect to CJ API')
        return redirect('cj_product_search', subdomain=subdomain)
    
    # Fetch product details
    detail_url = "https://developers.cjdropshipping.com/api2.0/v1/product/query"
    headers = {"CJ-Access-Token": token}
    
    try:
        response = requests.get(detail_url, headers=headers, params={"pid": product_id}, timeout=30)
        
        if response.status_code != 200:
            messages.error(request, f'Failed to fetch product details: {response.status_code}')
            return redirect('cj_product_search', subdomain=subdomain)
        
        api_data = response.json()
        if api_data.get("code") != 200:
            messages.error(request, api_data.get("msg", "Failed to fetch product"))
            return redirect('cj_product_search', subdomain=subdomain)
        
        product_data = api_data.get("data", {})
        
        # Parse JSON strings
        if isinstance(product_data.get('productName'), str) and product_data['productName'].startswith('['):
            try:
                product_data['productName_parsed'] = json.loads(product_data['productName'])
            except:
                product_data['productName_parsed'] = []
        
        if isinstance(product_data.get('productImage'), str) and product_data['productImage'].startswith('['):
            try:
                product_data['productImage_parsed'] = json.loads(product_data['productImage'])
            except:
                product_data['productImage_parsed'] = []
        
        # Parse other JSON fields
        json_fields = ['materialNameEn', 'packingNameEn', 'productProEn']
        for field in json_fields:
            if isinstance(product_data.get(field), str) and product_data[field].startswith('['):
                try:
                    product_data[f'{field}_parsed'] = json.loads(product_data[field])
                except:
                    product_data[f'{field}_parsed'] = []
        
        # Calculate selling price
        try:
            sell_price_str = product_data.get('sellPrice', '0')
            if isinstance(sell_price_str, str):
                sell_price_str = sell_price_str.replace(',', '').replace('$', '').strip()
            cj_price = Decimal(str(sell_price_str)) if sell_price_str else Decimal('0')
            # margin = cj_settings_obj.default_profit_margin
            selling_price = cj_price * (1 + margin / Decimal('100'))
            rounded = selling_price.quantize(Decimal('0.01'), rounding='ROUND_HALF_UP')
            if rounded % Decimal('1') < Decimal('0.95'):
                final_price = Decimal(str(int(rounded))) + Decimal('0.95')
            else:
                final_price = Decimal(str(int(rounded))) + Decimal('0.99')
        except:
            cj_price = Decimal('0')
            final_price = Decimal('0')
        
        # Get product name
        product_name = product_data.get('productNameEn', 'Unknown Product')
        if not product_name or product_name == '':
            if product_data.get('productName_parsed') and len(product_data['productName_parsed']) > 0:
                product_name = product_data['productName_parsed'][0]
            elif product_data.get('productName'):
                product_name = str(product_data['productName'])[:200]
        
        # Check if already imported
        is_imported = CJProduct.objects.filter(page=page, cj_product_id=product_id).exists()
        
        context = {
            'page': page,
            'product_id': product_id,
            'product': product_data,
            'product_name': product_name,
            'cj_price': cj_price,
            'selling_price': final_price,
            'profit_margin': 0,
            'is_imported': is_imported,
            'variants': product_data.get('variants', []),
            'supplier_name': product_data.get('supplierName', 'Unknown Supplier'),
            'supplier_id': product_data.get('supplierId'),
            'category_name': product_data.get('categoryName', ''),
            'estimated_delivery': product_data.get('estimatedDelivery', '7-15 days'),
            'stock': product_data.get('stock', 0),
            'moq': product_data.get('moq', 1),  # Minimum Order Quantity
        }
        
        return render(request, 'builder/cj_product_details.html', context)
        
    except Exception as e:
        logger.error(f"Error fetching product details: {str(e)}")
        messages.error(request, f'Error loading product details: {str(e)}')
        return redirect('cj_product_search', subdomain=subdomain)



@login_required
@require_http_methods(["GET"])
def cj_categories(request, subdomain):
    """Get CJ product categories"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    try:
        cj_settings_obj = page.cj_settings.get()
        if not cj_settings_obj.is_active:
            return JsonResponse({'success': False, 'error': 'CJ integration is not active'})
    except CJSettings.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'CJ integration not configured'})
    
    token = get_cj_access_token(cj_settings_obj)
    if not token:
        return JsonResponse({'success': False, 'error': 'Failed to get access token'})
    
    url = "https://developers.cjdropshipping.com/api2.0/v1/product/getCategory"
    headers = {"CJ-Access-Token": token}
    params = {"pageNum": 1, "pageSize": 100}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        data = response.json()
        
        if data.get("code") == 200:
            categories = data.get("data", {}).get("resultList", [])
            # Filter for English categories
            english_categories = [
                cat for cat in categories 
                if cat.get('categoryNameEn') and not cat['categoryNameEn'].startswith('[')
            ]
            return JsonResponse({'success': True, 'categories': english_categories})
        else:
            return JsonResponse({'success': False, 'error': data.get("msg", "Failed to fetch categories")})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    



import json
import requests
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.db import transaction
import os


# views.py - Complete Fixed Import View

import io
from PIL import Image
from django.core.files.base import ContentFile

import io
from PIL import Image
from django.core.files.base import ContentFile

def compress_image_for_upload(image_content, max_size_mb=8, target_format='JPEG'):
    """
    Compress an image to stay under Cloudinary's 10MB limit.
    
    Args:
        image_content: The image content as bytes
        max_size_mb: Target maximum size in MB
        target_format: Output format (JPEG, PNG, WEBP)
    
    Returns:
        tuple: (compressed_content, content_type)
    """
    max_bytes = max_size_mb * 1024 * 1024
    
    # If already small enough, return original
    if len(image_content) <= max_bytes:
        return image_content, 'image/jpeg'
    
    try:
        # Open image with PIL
        img = Image.open(io.BytesIO(image_content))
        
        # Handle different modes
        if target_format == 'JPEG':
            # Convert to RGB for JPEG
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            content_type = 'image/jpeg'
        elif target_format == 'WEBP':
            if img.mode == 'P':
                img = img.convert('RGBA')
            content_type = 'image/webp'
        else:  # PNG
            if img.mode == 'P':
                img = img.convert('RGBA')
            content_type = 'image/png'
        
        # Try different quality settings
        output = io.BytesIO()
        quality = 85
        img.save(output, format=target_format, quality=quality, optimize=True)
        compressed_size = len(output.getvalue())
        
        # Reduce quality until under limit
        while compressed_size > max_bytes and quality > 20:
            quality -= 10
            output = io.BytesIO()
            img.save(output, format=target_format, quality=quality, optimize=True)
            compressed_size = len(output.getvalue())
        
        # If still too large, resize
        if compressed_size > max_bytes:
            # Calculate scale factor
            scale = (max_bytes / compressed_size) ** 0.5 * 0.95
            new_width = int(img.width * scale)
            new_height = int(img.height * scale)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            img.save(output, format=target_format, quality=quality if quality > 20 else 85, optimize=True)
            compressed_size = len(output.getvalue())
            
            # If still too large, reduce quality further
            while compressed_size > max_bytes and quality > 10:
                quality -= 5
                output = io.BytesIO()
                img.save(output, format=target_format, quality=quality, optimize=True)
                compressed_size = len(output.getvalue())
        
        print(f"✅ Compressed image: {len(output.getvalue())/1024/1024:.1f}MB")
        return output.getvalue(), content_type
        
    except Exception as e:
        print(f"⚠️ Error compressing image: {e}")
        # Return original if compression fails
        return image_content, 'image/jpeg'

# views.py - Complete Fixed Import View



@login_required
@csrf_exempt
@require_http_methods(["POST"])
@transaction.atomic
def cj_import_product(request, subdomain, pid):
    """
    Import a CJ product with all variants properly synced.
    
    Handles:
    - Products with variants (color/size combinations)
    - Products without variants (simple products)
    - Image downloading and storage with compression
    - Variant images
    - Stock quantities (using storageNum from stock API)
    - Review importing
    - Stock synchronization
    """
    # ===== 1. GET PAGE AND SETTINGS =====
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    settings_obj = get_object_or_404(CJSettings, page=page)
    
    token = get_cj_access_token(settings_obj)
    if not token:
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to get CJ access token. Please check your API settings.'
        }, status=400)
    
    service = CJService(token)
    manager = CJManager(token)
    
    # ===== 2. GET PRODUCT DETAILS =====
    product_data = service.get_product_details(pid)
    
    if not product_data:
        return JsonResponse({
            'status': 'error',
            'message': f'Product not found on CJ (PID: {pid})'
        }, status=404)
    
    print(f"✅ Product found: {product_data.get('productNameEn', 'Unknown')}")
    
    # ===== 3. GET VARIANTS =====
    # Try primary method first
    variants_data = service.get_variants(pid)
    
    # If no variants found, try alternative method
    if not variants_data:
        print("⚠️ No variants found with primary method, trying alternative...")
        variants_data = service.get_variants_alternative(pid)
    
    # If still no variants, try to extract from product data directly
    if not variants_data and 'variants' in product_data:
        variants_data = product_data.get('variants', [])
        print(f"📦 Found {len(variants_data)} variants in product data")
    
    print(f"📊 Total variants found: {len(variants_data)}")
    
    # Log first few variants for debugging
    for i, v in enumerate(variants_data[:3]):
        print(f"  Variant {i+1}: vid={v.get('vid')}, key={v.get('variantKey')}, sku={v.get('variantSku')}")
    
    # ===== 4. FETCH STOCK FOR EACH VARIANT =====
    print("\n🔍 FETCHING STOCK FOR EACH VARIANT...")
    
    enriched_variants = []
    total_product_stock = 0
    
    for idx, variant in enumerate(variants_data):
        vid = variant.get('vid')
        if not vid:
            print(f"  ⚠️ Variant {idx+1}: No VID found, skipping")
            continue
        
        print(f"\n  📦 Processing Variant {idx+1}: VID={vid}")
        variant_stock = 0
        
        # ===== METHOD 1: Get stock from stock API endpoint =====
        try:
            stock_url = f"{service.BASE_URL}/product/stock/queryByVid"
            params = {"vid": vid}
            response = requests.get(stock_url, headers=service.headers, params=params, timeout=15)
            data = response.json()
            
            if data.get('code') == 200:
                stock_data = data.get('data', [])
                if stock_data:
                    for item in stock_data:
                        # CJ returns stock in these fields:
                        # - storageNum (primary)
                        # - totalInventoryNum (total inventory)
                        # - factoryInventoryNum (factory stock)
                        stock_num = item.get('storageNum') or item.get('totalInventoryNum') or item.get('factoryInventoryNum') or 0
                        try:
                            variant_stock += int(stock_num)
                        except (ValueError, TypeError):
                            pass
                    
                    if variant_stock > 0:
                        print(f"    ✅ Stock from API: {variant_stock}")
                    else:
                        print(f"    ⚠️ Stock API returned 0 for VID {vid}")
        except Exception as e:
            print(f"    ⚠️ Error getting stock from API for VID {vid}: {e}")
        
        # ===== METHOD 2: Check variant data for stock fields =====
        if variant_stock == 0:
            stock_fields = ['inventoryNum', 'stock', 'availableNum', 'quantity', 'listedNum']
            for field in stock_fields:
                value = variant.get(field)
                if value is not None:
                    try:
                        variant_stock = int(value)
                        if variant_stock > 0:
                            print(f"    ✅ Stock from variant.{field}: {variant_stock}")
                        break
                    except (ValueError, TypeError):
                        pass
        
        # ===== METHOD 3: Check product-level listedNum =====
        if variant_stock == 0:
            product_listed_num = product_data.get('listedNum', 0)
            if product_listed_num and product_listed_num > 0:
                variant_count = len(variants_data) or 1
                variant_stock = max(1, product_listed_num // variant_count)
                print(f"    ⚠️ Using product.listedNum ({product_listed_num}) distributed: {variant_stock}")
        
        # ===== METHOD 4: If product is active, use default stock =====
        if variant_stock == 0:
            product_status = product_data.get('status')
            if product_status == 3:  # Active/Available
                variant_stock = 10  # Default stock for active products
                print(f"    ⚠️ Product active, using default stock: {variant_stock}")
        
        print(f"    📊 FINAL STOCK for VID {vid}: {variant_stock}")
        
        # Add stock to variant data
        variant['_stock'] = variant_stock
        total_product_stock += variant_stock
        enriched_variants.append(variant)
    
    print(f"\n📊 TOTAL PRODUCT STOCK: {total_product_stock}")
    
    # ===== 5. CREATE OR GET CATEGORY =====
    raw_cat = product_data.get('categoryName', 'General')
    clean_cat_name = raw_cat.split('/')[-1].strip() if raw_cat else 'General'
    category_obj, _ = ProductCategory.objects.get_or_create(
        name=clean_cat_name[:100],
        page=page
    )
    
    # ===== 6. CREATE UNIQUE SLUG =====
    base_slug = slugify(product_data.get('productNameEn', 'product'))
    slug = base_slug
    counter = 1
    while Product.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # ===== 7. EXTRACT WEIGHT =====
    raw_weight = str(product_data.get('productWeight', '0'))
    if '-' in raw_weight:
        raw_weight = raw_weight.split('-')[-1].strip()
    try:
        weight = float(raw_weight) if raw_weight else 0.0
    except ValueError:
        weight = 0.0
    
    # ===== 8. PARSE PRICE =====
    price_str = product_data.get('sellPrice', '0')
    if '-' in str(price_str):
        price_str = str(price_str).split('-')[0].strip()
    try:
        cj_price = float(price_str) if price_str else 0.0
    except ValueError:
        cj_price = 0.0
    
    suggest_price_str = product_data.get('suggestSellPrice', '0')
    if '-' in str(suggest_price_str):
        suggest_price_str = str(suggest_price_str).split('-')[0].strip()
    try:
        suggest_price = float(suggest_price_str) if suggest_price_str else 0.0
    except ValueError:
        suggest_price = 0.0
    
    # ===== 9. CREATE THE PRODUCT =====
    product, created = Product.objects.update_or_create(
        cj_pid=pid,
        defaults={
            'page': page,
            'title': product_data.get('productNameEn', 'Unknown Product')[:200],
            'slug': slug,
            'description': product_data.get('description', '')[:10000],
            'short_description': product_data.get('productPro', '')[:500],
            'category': category_obj,
            'price': Decimal(str(cj_price)),
            'compare_at_price': Decimal(str(suggest_price)) if suggest_price > 0 else None,
            'status': 'active' if total_product_stock > 0 else 'out_of_stock',
            'weight': Decimal(str(weight)),
            'weight_unit': 'kg',
            'requires_shipping': True,
            'visible_on_store': True,
            'cj_vid': variants_data[0].get('vid') if variants_data else None,
            'has_variants': len(variants_data) > 1,
            'quantity': total_product_stock,
        }
    )
    
    print(f"✅ Product {'created' if created else 'updated'}: {product.title}")
    print(f"   Initial quantity set to: {total_product_stock}")
    
    # ===== 10. HANDLE IMAGES =====
    def process_image(url, max_size_mb=8, is_variant=False):
        """Download and compress an image to stay under Cloudinary's limit."""
        if not url:
            return None
        
        try:
            # Clean up URL
            if not url.startswith('http'):
                if url.startswith('//'):
                    url = 'https:' + url
                else:
                    url = 'https://' + url
            
            # Download with timeout
            response = requests.get(url, timeout=15, stream=True)
            
            if response.status_code != 200:
                print(f"⚠️ Failed to download image: HTTP {response.status_code}")
                return None
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                print(f"⚠️ Not an image: {content_type}")
                return None
            
            # Load image
            content = response.content
            
            # If image is too large, compress it
            max_bytes = max_size_mb * 1024 * 1024
            if len(content) > max_bytes:
                print(f"🔄 Compressing image ({len(content)/1024/1024:.1f}MB -> target {max_size_mb}MB)")
                
                try:
                    # Open image with PIL
                    from PIL import Image
                    img = Image.open(io.BytesIO(content))
                    
                    # Convert to RGB if necessary (for PNG with alpha)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Calculate new size to stay under limit
                    quality = 85
                    output = io.BytesIO()
                    img.save(output, format='JPEG', quality=quality, optimize=True)
                    compressed_size = len(output.getvalue())
                    
                    # If still too large, reduce quality further
                    while compressed_size > max_bytes and quality > 20:
                        quality -= 10
                        output = io.BytesIO()
                        img.save(output, format='JPEG', quality=quality, optimize=True)
                        compressed_size = len(output.getvalue())
                    
                    # If still too large, resize
                    if compressed_size > max_bytes:
                        print(f"🔄 Resizing image (still too large: {compressed_size/1024/1024:.1f}MB)")
                        scale = (max_bytes / compressed_size) ** 0.5
                        new_width = int(img.width * scale * 0.9)
                        new_height = int(img.height * scale * 0.9)
                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        
                        output = io.BytesIO()
                        img.save(output, format='JPEG', quality=85, optimize=True)
                        compressed_size = len(output.getvalue())
                    
                    # Generate filename
                    filename = url.split('/')[-1].split('?')[0]
                    if not filename or '.' not in filename:
                        filename = f"{'variant' if is_variant else 'product'}.jpg"
                    elif not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                        filename = filename.split('.')[0] + '.jpg'
                    
                    print(f"✅ Compressed image: {len(output.getvalue())/1024/1024:.1f}MB")
                    return ContentFile(output.getvalue(), name=filename)
                    
                except Exception as e:
                    print(f"⚠️ Error compressing image: {e}")
                    # Return original if compression fails
                    filename = url.split('/')[-1].split('?')[0] or 'image.jpg'
                    return ContentFile(content, name=filename)
            
            # Image is already small enough
            filename = url.split('/')[-1].split('?')[0] or 'image.jpg'
            return ContentFile(content, name=filename)
            
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout downloading image from {url[:50]}...")
            return None
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Request error downloading image: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Error downloading image: {e}")
            return None
    
    # Save main product image
    raw_images = product_data.get('productImageSet', [])
    if not raw_images:
        img_str = product_data.get('productImage', '[]')
        try:
            raw_images = json.loads(img_str) if img_str and img_str.startswith('[') else [img_str] if img_str else []
        except json.JSONDecodeError:
            raw_images = [img_str] if img_str else []
    
    # Filter out invalid URLs
    raw_images = [img for img in raw_images if img and img.startswith('http')]
    
    print(f"📸 Found {len(raw_images)} product images")
    
    # Save main image
    if raw_images:
        img_file = process_image(raw_images[0], max_size_mb=8)
        if img_file:
            try:
                product.main_image.save(f"{pid}_main.jpg", img_file, save=True)
                print(f"✅ Saved main image")
            except Exception as e:
                print(f"⚠️ Failed to save main image: {e}")
    
    # Save gallery images (up to 5)
    gallery_count = 0
    for img_url in raw_images[1:6]:
        if not img_url:
            continue
        
        img_file = process_image(img_url, max_size_mb=8)
        if img_file:
            try:
                file_name = img_url.split('/')[-1].split('?')[0] or f"{pid}_gallery_{gallery_count}.jpg"
                if not file_name or '.' not in file_name:
                    file_name = f"{pid}_gallery_{gallery_count}.jpg"
                
                if not ProductImages.objects.filter(product=product, image__icontains=file_name[:50]).exists():
                    pi = ProductImages(product=product)
                    pi.image.save(file_name, img_file, save=True)
                    gallery_count += 1
                    print(f"✅ Saved gallery image {gallery_count}")
            except Exception as e:
                print(f"⚠️ Failed to save gallery image: {e}")
    
    # ===== 11. SYNC VARIANTS WITH STOCK =====
    variant_stats = {'total': 0, 'created': 0, 'updated': 0, 'failed': 0, 'variants': []}
    
    if enriched_variants:
        print(f"\n🔄 Syncing {len(enriched_variants)} variants with stock data...")
        
        # Delete existing variants for this product to avoid duplicates
        ProductVariant.objects.filter(product=product).delete()
        
        colors = set()
        sizes = set()
        total_stock = 0
        
        for variant_data in enriched_variants:
            try:
                vid = variant_data.get('vid')
                if not vid:
                    variant_stats['failed'] += 1
                    continue
                
                # Get stock from enriched data
                variant_stock = variant_data.get('_stock', 0)
                
                # Extract color and size
                variant_key = variant_data.get('variantKey', '')
                color_value, size_value = manager._extract_color_size(variant_key)
                
                if color_value:
                    colors.add(color_value)
                if size_value:
                    sizes.add(size_value)
                
                # Parse price
                variant_price = variant_data.get('variantSellPrice')
                if variant_price is None:
                    variant_price = variant_data.get('variantPrice', 0)
                try:
                    variant_price = float(variant_price)
                except (ValueError, TypeError):
                    variant_price = 0.0
                
                # Get variant image
                variant_image_url = variant_data.get('variantImage', '')
                
                # Build options
                options = {}
                if color_value:
                    options['Color'] = color_value
                if size_value:
                    options['Size'] = size_value
                
                # Determine SKU
                sku = variant_data.get('variantSku', '')
                if not sku:
                    sku = f"VAR-{vid}"
                
                # ===== CREATE VARIANT WITH STOCK =====
                variant = ProductVariant.objects.create(
                    product=product,
                    cj_vid=vid,
                    options=options,
                    option1=size_value or '',
                    option2=color_value or '',
                    sku=sku,
                    price=Decimal(str(variant_price)) if variant_price else Decimal('0.00'),
                    compare_at_price=product.compare_at_price,
                    quantity=variant_stock,
                    track_quantity=True,
                    low_stock_threshold=5,
                    barcode=variant_data.get('barcode', ''),
                )
                
                total_stock += variant_stock
                variant_stats['created'] += 1
                variant_stats['total'] += 1
                
                variant_stats['variants'].append({
                    'vid': vid,
                    'created': True,
                    'color': color_value,
                    'size': size_value,
                    'sku': sku,
                    'price': variant_price,
                    'stock': variant_stock,
                    'has_image': bool(variant_image_url)
                })
                
                print(f"  ✅ Variant {vid}: Color={color_value}, Size={size_value}, Stock={variant_stock}")
                
                # ===== SAVE VARIANT IMAGE =====
                if variant_image_url:
                    try:
                        img_file = process_image(variant_image_url, max_size_mb=5, is_variant=True)
                        if img_file:
                            filename = f"variant_{vid}.jpg"
                            variant.image.save(filename, img_file, save=True)
                            print(f"    📸 Saved variant image for {vid}")
                    except Exception as e:
                        print(f"    ⚠️ Failed to save variant image for {vid}: {e}")
                
            except Exception as e:
                print(f"  ❌ Error syncing variant {variant_data.get('vid')}: {e}")
                variant_stats['failed'] += 1
        
        # Update product with color and size options
        if colors:
            product.colors = ', '.join(sorted(colors))
        if sizes:
            product.sizes = ', '.join(sorted(sizes))
        
        product.has_variants = len(enriched_variants) > 1
        product.quantity = total_stock
        
        if total_stock == 0:
            product.status = 'out_of_stock'
        else:
            product.status = 'active'
        
        product.save()
        
        print(f"\n📊 Variant sync complete:")
        print(f"   Total variants: {variant_stats['total']}")
        print(f"   Created: {variant_stats['created']}")
        print(f"   Failed: {variant_stats['failed']}")
        print(f"   Total stock: {total_stock}")
        print(f"   Colors: {', '.join(sorted(colors)) if colors else 'None'}")
        print(f"   Sizes: {', '.join(sorted(sizes)) if sizes else 'None'}")
        
    else:
        print("ℹ️ No variants to sync - creating simple product")
        product.has_variants = False
        product.quantity = 0
        product.status = 'out_of_stock'
        product.save()
    
    # ===== 12. IMPORT REVIEWS =====
    review_count = 0
    try:
        reviews_data = service.get_product_reviews(pid)
        for review in reviews_data[:20]:
            comment_text = review.get('comment', '')
            if not comment_text or len(comment_text) < 3:
                continue
            
            author_name = review.get('userName', 'Verified Buyer')
            rating = int(review.get('score', 5)) if review.get('score') else 5
            
            ProductReview.objects.get_or_create(
                product=product,
                comment=comment_text[:500],
                author_name=author_name[:100],
                defaults={
                    'rating': min(5, max(1, rating)),
                    'title': f"Customer Review"[:200],
                    'is_verified_purchase': True,
                    'is_approved': True,
                    'helpful_count': 0,
                }
            )
            review_count += 1
        print(f"⭐ Imported {review_count} reviews")
    except Exception as e:
        print(f"⚠️ Failed to import reviews: {e}")
    
    # ===== 13. CREATE CJ PRODUCT RECORD =====
    try:
        cj_product, cj_created = CJProduct.objects.update_or_create(
            page=page,
            cj_product_id=pid,
            defaults={
                'cj_pid': pid,
                'local_product': product,
                'cj_sku': enriched_variants[0].get('variantSku', '') if enriched_variants else '',
                'cj_variant_id': enriched_variants[0].get('vid', '') if enriched_variants else '',
                'cj_price_usd': Decimal(str(cj_price)),
                'local_selling_price': product.price,
                'cj_stock_quantity': product.quantity,
                'local_stock_quantity': product.quantity,
                'sync_status': 'synced' if enriched_variants else 'pending',
                'last_full_sync': timezone.now(),
                'cj_data': product_data,
            }
        )
        print(f"📦 CJ Product record {'created' if cj_created else 'updated'}")
    except Exception as e:
        print(f"⚠️ Failed to create CJ product record: {e}")
    
    # ===== 14. RETURN RESPONSE =====
    return JsonResponse({
        'status': 'success',
        'message': f'Successfully imported {product.title}',
        'product_id': product.id,
        'product_slug': product.slug,
        'created': created,
        'variant_stats': {
            'total': variant_stats.get('total', 0),
            'created': variant_stats.get('created', 0),
            'updated': variant_stats.get('updated', 0),
            'failed': variant_stats.get('failed', 0),
        },
        'has_variants': product.has_variants,
        'total_stock': product.quantity,
        'colors': product.colors,
        'sizes': product.sizes,
        'review_count': review_count,
        'image_count': len(raw_images),
        'variant_images': sum(1 for v in variant_stats.get('variants', []) if v.get('has_image', False))
    })


def download_image_to_field(url):
    """
    Download an image from URL and return as ContentFile.
    Handles various image formats and error cases.
    """
    if not url:
        return None
    
    try:
        # Clean up URL
        if not url.startswith('http'):
            if url.startswith('//'):
                url = 'https:' + url
            else:
                url = 'https://' + url
        
        # Download with timeout
        response = requests.get(url, timeout=15, stream=True)
        
        if response.status_code != 200:
            print(f"⚠️ Failed to download image: HTTP {response.status_code}")
            return None
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            print(f"⚠️ Not an image: {content_type}")
            return None
        
        # Generate filename
        content = response.content
        if len(content) < 100:  # Too small to be an image
            print(f"⚠️ Image too small: {len(content)} bytes")
            return None
        
        # Extract filename from URL or generate one
        filename = url.split('/')[-1].split('?')[0]
        if not filename or '.' not in filename:
            ext = content_type.split('/')[-1] if '/' in content_type else 'jpg'
            if ext in ['jpeg', 'jpg', 'png', 'gif', 'webp', 'bmp', 'svg+xml']:
                filename = f"image.{ext.replace('+xml', '')}"
            else:
                filename = f"image.jpg"
        
        # Create ContentFile
        from django.core.files.base import ContentFile
        return ContentFile(content, name=filename)
        
    except requests.exceptions.Timeout:
        print(f"⚠️ Timeout downloading image from {url[:50]}...")
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Request error downloading image: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Error downloading image: {e}")
        return None

# ============== OTHER VIEWS (simplified) ==============
# @login_required
# @require_http_methods(["GET"])
# def cj_products_list(request, subdomain):
#     """List all products imported from CJ for this store"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
#     products = CJProduct.objects.filter(page=page).select_related('local_product')
    
#     # Filter by status if provided
#     status = request.GET.get('status')
#     if status:
#         products = products.filter(sync_status=status)

#     return render(request, 'builder/cj_products_list.html', {
#         'page': page,
#         'products': products,
#         'synced_count': products.filter(sync_status='synced').count(),
#         'failed_count': products.filter(sync_status='failed').count()
#     })


# builder/views.py - Add this new view

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import Product, ProductDisplayMode, VariantGroup
from .services.variant_grouping import VariantGroupManager
import json


# builder/views.py - Updated views

from builder.services.variant_grouping import VariantGroupManager

@login_required
def product_grouping_view(request, subdomain, product_id):
    """View for managing variant grouping"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    product = get_object_or_404(Product, id=product_id, page=page)
    
    # Get or create display mode
    from builder.models import ProductDisplayMode
    display_mode, created = ProductDisplayMode.objects.get_or_create(
        product=product,
        defaults={'mode': 'single', 'group_by': 'image'}
    )
    
    # Get grouped products
    from builder.models import GroupedProduct
    grouped_products = GroupedProduct.objects.filter(
        original_product=product
    ).select_related('product')
    
    # Get all attributes
    all_attributes = {}
    for variant in product.variants.all():
        for key, value in variant.options.items():
            if key not in all_attributes:
                all_attributes[key] = []
            if value not in all_attributes[key]:
                all_attributes[key].append(value)
    
    context = {
        'page': page,
        'product': product,
        'variants': product.variants.all(),
        'display_mode': display_mode,
        'grouped_products': grouped_products,
        'has_grouped_products': grouped_products.exists(),
        'all_attributes': all_attributes,
    }
    
    return render(request, 'builder/product_grouping.html', context)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def apply_grouping(request, subdomain, product_id):
    """Apply grouping and create actual product records"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        product = get_object_or_404(Product, id=product_id, page=page)
        
        data = json.loads(request.body)
        mode = data.get('mode', 'single')
        group_by = data.get('group_by', 'image')
        primary_attribute = data.get('primary_attribute', '')
        
        manager = VariantGroupManager(product)
        
        # Update display mode
        display_mode = manager.get_display_mode()
        display_mode.mode = mode
        display_mode.group_by = group_by
        display_mode.primary_attribute = primary_attribute if mode == 'grouped' else ''
        display_mode.save()
        
        # Process groups and create products
        result = manager.process_groups_to_products()
        
        if result.get('success'):
            return JsonResponse({
                'success': True,
                'message': result.get('message'),
                'created_count': result.get('created_count', 0),
                'product_ids': result.get('product_ids', []),
                'mode': result.get('mode'),
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to process groups')
            }, status=400)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def restore_original_product(request, subdomain, product_id):
    """Restore the original product and remove grouped products"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        product = get_object_or_404(Product, id=product_id, page=page)
        
        manager = VariantGroupManager(product)
        restored = manager.restore_original()
        
        return JsonResponse({
            'success': True,
            'message': 'Original product restored successfully',
            'product_id': restored.id,
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    
@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_product_grouping(request, subdomain, product_id):
    """
    AJAX endpoint to update product grouping settings.
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        product = get_object_or_404(Product, id=product_id, page=page)
        
        data = json.loads(request.body)
        
        # Get or create display mode
        display_mode, created = ProductDisplayMode.objects.get_or_create(
            product=product
        )
        
        # Update mode
        mode = data.get('mode', 'single')
        display_mode.mode = mode
        
        if mode == 'grouped':
            group_by = data.get('group_by', 'image')
            primary_attribute = data.get('primary_attribute', '')
            display_mode.group_by = group_by
            display_mode.primary_attribute = primary_attribute
        else:
            display_mode.group_by = 'none'
            display_mode.primary_attribute = None
        
        display_mode.save()
        
        # Rebuild groups using the service
        manager = VariantGroupManager(product)
        manager.update_display_mode(mode, display_mode.group_by, display_mode.primary_attribute)
        
        # Get updated groups
        groups = product.variant_groups.all().prefetch_related('variants')
        groups_data = []
        for group in groups:
            groups_data.append({
                'id': group.id,
                'display_name': group.display_name,
                'group_key': group.group_key,
                'variant_count': group.variants.count(),
                'image_url': group.image.url if group.image else None,
            })
        
        return JsonResponse({
            'success': True,
            'message': 'Product grouping updated successfully',
            'display_mode': {
                'mode': display_mode.mode,
                'group_by': display_mode.group_by,
                'primary_attribute': display_mode.primary_attribute,
            },
            'groups': groups_data,
            'group_count': len(groups_data),
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def manual_group_variants(request, subdomain, product_id):
    """
    Manually group specific variants together.
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        product = get_object_or_404(Product, id=product_id, page=page)
        
        data = json.loads(request.body)
        group_name = data.get('group_name', 'Group')
        variant_ids = data.get('variant_ids', [])
        
        if not variant_ids:
            return JsonResponse({
                'success': False,
                'error': 'Please select at least one variant'
            }, status=400)
        
        # Get the variants
        variants = ProductVariant.objects.filter(id__in=variant_ids, product=product)
        
        if not variants.exists():
            return JsonResponse({
                'success': False,
                'error': 'No valid variants found'
            }, status=400)
        
        # Create the group
        group_key = f"manual_{hashlib.md5(str(variant_ids).encode()).hexdigest()[:10]}"
        
        group = VariantGroup.objects.create(
            product=product,
            group_key=group_key,
            display_name=group_name,
            display_order=product.variant_groups.count()
        )
        group.variants.set(variants)
        group.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Group "{group_name}" created with {variants.count()} variants',
            'group': {
                'id': group.id,
                'display_name': group.display_name,
                'variant_count': variants.count(),
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def delete_variant_group(request, subdomain, product_id, group_id):
    """
    Delete a variant group.
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        product = get_object_or_404(Product, id=product_id, page=page)
        group = get_object_or_404(VariantGroup, id=group_id, product=product)
        
        group_name = group.display_name
        group.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Group "{group_name}" deleted successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def auto_detect_groups(request, subdomain, product_id):
    """
    Auto-detect groups based on current mode.
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        product = get_object_or_404(Product, id=product_id, page=page)
        
        # Rebuild groups using the service
        manager = VariantGroupManager(product)
        manager.rebuild_groups()
        
        groups = product.variant_groups.all().prefetch_related('variants')
        groups_data = []
        for group in groups:
            groups_data.append({
                'id': group.id,
                'display_name': group.display_name,
                'group_key': group.group_key,
                'variant_count': group.variants.count(),
                'image_url': group.image.url if group.image else None,
            })
        
        return JsonResponse({
            'success': True,
            'message': f'Auto-detected {len(groups_data)} groups',
            'groups': groups_data,
            'group_count': len(groups_data),
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    

@login_required
@require_http_methods(["GET"])
def cj_products_list(request, subdomain):
    """List all imported CJ products"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get filter parameters
    sync_status = request.GET.get('sync_status')
    search_query = request.GET.get('q', '').strip()
    
    # Base queryset
    products = CJProduct.objects.filter(page=page).select_related('local_product')
    
    # Apply filters
    if sync_status:
        products = products.filter(sync_status=sync_status)
    
    if search_query:
        products = products.filter(
            Q(cj_product_id__icontains=search_query) |
            Q(local_product__title__icontains=search_query) |
            Q(cj_sku__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(products.order_by('-created_at'), 20)
    page_num = int(request.GET.get('page', 1))
    try:
        page_obj = paginator.page(page_num)
    except:
        page_obj = paginator.page(1)
    
    # Calculate stats
    total_products = products.count()
    synced_count = products.filter(sync_status='synced').count()
    failed_count = products.filter(sync_status='failed').count()
    pending_count = products.filter(sync_status='pending').count()
    
    context = {
        'page': page,
        'products': page_obj,
        'total_products': total_products,
        'synced_count': synced_count,
        'failed_count': failed_count,
        'pending_count': pending_count,
        'search_query': search_query,
        'current_sync_status': sync_status,
    }
    return render(request, 'builder/cj_products_list.html', context)


# Note: Remaining views (dashboard, orders, sync logs, etc.) would follow similar pattern
# but since you only asked for product-related views, I'll stop here
















# @login_required
# def cj_sync_product(request, subdomain, cj_product_id):
#     """Manually sync price and stock for a specific product"""
#     page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
#     cj_product = get_object_or_404(CJProduct, page=page, cj_product_id=cj_product_id)
    
#     settings = page.cj_settings.get()
#     cj_service = CJService(settings.api_key, page)
    
#     # Fetch fresh data from CJ API
#     result = cj_service.get_product_detail(cj_product_id)
#     if result['success']:
#         # Update price and stock
#         cj_product.cj_price_usd = result['product']['pricing']['price']
#         cj_product.cj_stock_quantity = result['product']['inventory']['stock']
#         cj_product.last_full_sync = timezone.now()
#         cj_product.sync_status = 'synced'
#         cj_product.save()
        
#         return JsonResponse({'status': 'success', 'price': str(cj_product.cj_price_usd)})
    
#     return JsonResponse({'status': 'error', 'message': result.get('error')}, status=400)


@login_required
@require_http_methods(["POST"])
def cj_sync_product(request, subdomain, product_id):
    """Sync a specific product"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    try:
        cj_product = CJProduct.objects.get(page=page, cj_product_id=product_id)
    except CJProduct.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)
    
    try:
        cj_settings_obj = page.cj_settings.get()
        if not cj_settings_obj.is_active:
            return JsonResponse({
                'success': False,
                'error': 'CJ integration is not active'
            }, status=400)
    except CJSettings.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'CJ integration not configured'
        }, status=400)
    
    sync_log = CJSyncLog.objects.create(
        page=page,
        sync_type='price_sync',
        status='started',
        request_data={'cj_product_id': product_id}
    )
    
    try:
        token = get_cj_access_token(cj_settings_obj)
        if not token:
            sync_log.status = 'failed'
            sync_log.error_message = 'Failed to get access token'
            sync_log.completed_at = timezone.now()
            sync_log.save()
            return JsonResponse({
                'success': False,
                'error': 'Failed to get access token'
            }, status=400)
        
        # Fetch latest product data
        detail_url = "https://developers.cjdropshipping.com/api2.0/v1/product/query"
        headers = {"CJ-Access-Token": token}
        response = requests.get(detail_url, headers=headers, params={"pid": product_id}, timeout=30)
        
        if response.status_code != 200:
            cj_product.sync_status = 'failed'
            cj_product.last_sync_error = f'API returned {response.status_code}'
            cj_product.retry_count += 1
            cj_product.save()
            
            sync_log.status = 'failed'
            sync_log.error_message = f'API returned {response.status_code}'
            sync_log.completed_at = timezone.now()
            sync_log.save()
            
            return JsonResponse({
                'success': False,
                'error': f'API returned {response.status_code}'
            }, status=400)
        
        api_data = response.json()
        if api_data.get("code") != 200:
            cj_product.sync_status = 'failed'
            cj_product.last_sync_error = api_data.get("msg", "API error")
            cj_product.retry_count += 1
            cj_product.save()
            
            sync_log.status = 'failed'
            sync_log.error_message = api_data.get("msg", "API error")
            sync_log.completed_at = timezone.now()
            sync_log.save()
            
            return JsonResponse({
                'success': False,
                'error': api_data.get("msg", "Failed to fetch product")
            }, status=400)
        
        product_data = api_data.get("data", {})
        cj_price = Decimal(str(product_data.get('sellPrice', 0)))
        
        # Update prices if changed
        if cj_price != cj_product.cj_price_usd:
            selling_price = cj_product.calculate_selling_price()
            if selling_price and cj_product.local_product:
                cj_product.local_product.price = selling_price
                cj_product.local_product.save()
        
        # Update CJ product record
        cj_product.cj_data = product_data
        cj_product.cj_price_usd = cj_price
        cj_product.last_price_sync = timezone.now()
        cj_product.last_full_sync = timezone.now()
        cj_product.sync_status = 'synced'
        cj_product.last_sync_error = ''
        cj_product.retry_count = 0
        cj_product.save()
        
        sync_log.status = 'success'
        sync_log.items_processed = 1
        sync_log.items_succeeded = 1
        sync_log.api_calls_made = 1
        sync_log.completed_at = timezone.now()
        sync_log.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Product synced successfully',
            'cj_price': float(cj_price),
            'last_sync': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error syncing CJ product: {str(e)}")
        cj_product.sync_status = 'failed'
        cj_product.last_sync_error = str(e)
        cj_product.retry_count += 1
        cj_product.save()
        
        sync_log.status = 'failed'
        sync_log.error_message = str(e)
        sync_log.completed_at = timezone.now()
        sync_log.save()
        
        return JsonResponse({
            'success': False,
            'error': f'Sync failed: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def cj_bulk_sync(request, subdomain):
    """Bulk sync all products that need syncing"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    try:
        cj_settings_obj = page.cj_settings.get()
        if not cj_settings_obj.is_active:
            return JsonResponse({
                'success': False,
                'error': 'CJ integration is not active'
            }, status=400)
    except CJSettings.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'CJ integration not configured'
        }, status=400)
    
    # Get products that need syncing
    products_to_sync = CJProduct.objects.filter(
        page=page,
        sync_status__in=['synced', 'out_of_sync', 'failed']
    )
    
    # Limit to 50 products per bulk sync to avoid timeouts
    products_to_sync = products_to_sync[:50]
    
    sync_log = CJSyncLog.objects.create(
        page=page,
        sync_type='price_sync',
        status='started',
        request_data={'bulk': True, 'product_count': len(products_to_sync)}
    )
    
    try:
        cj_service = CJService(cj_settings_obj.api_key, page)
        results = []
        successful = 0
        failed = 0
        
        for cj_product in products_to_sync:
            try:
                # Get latest product data
                result = cj_service.get_product_detail(cj_product.cj_product_id, include_variants=False)
                
                if result['success']:
                    product_data = result['product']
                    cj_price = product_data['pricing']['price']
                    stock = product_data['inventory']['stock']
                    
                    # Update prices if changed
                    if cj_price != cj_product.cj_price_usd:
                        selling_price = cj_product.calculate_selling_price()
                        
                        if selling_price and cj_product.local_product:
                            cj_product.local_product.price = selling_price
                            cj_product.local_product.save()
                    
                    # Update CJ product record
                    cj_product.cj_data = product_data
                    cj_product.cj_price_usd = cj_price
                    cj_product.cj_stock_quantity = stock
                    cj_product.local_stock_quantity = stock
                    cj_product.last_price_sync = timezone.now()
                    cj_product.last_inventory_sync = timezone.now()
                    cj_product.last_full_sync = timezone.now()
                    cj_product.sync_status = 'synced'
                    cj_product.last_sync_error = ''
                    cj_product.retry_count = 0
                    cj_product.save()
                    
                    successful += 1
                    results.append({
                        'product_id': cj_product.cj_product_id,
                        'status': 'success',
                        'new_price': float(cj_price) if cj_price else None
                    })
                else:
                    failed += 1
                    cj_product.sync_status = 'failed'
                    cj_product.last_sync_error = result.get('error', 'Sync failed')
                    cj_product.retry_count += 1
                    cj_product.save()
                    
                    results.append({
                        'product_id': cj_product.cj_product_id,
                        'status': 'failed',
                        'error': result.get('error')
                    })
                    
            except Exception as e:
                failed += 1
                cj_product.sync_status = 'failed'
                cj_product.last_sync_error = str(e)
                cj_product.retry_count += 1
                cj_product.save()
                
                results.append({
                    'product_id': cj_product.cj_product_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        sync_log.status = 'success' if successful > 0 else 'failed'
        sync_log.items_processed = len(products_to_sync)
        sync_log.items_succeeded = successful
        sync_log.items_failed = failed
        sync_log.api_calls_made = len(products_to_sync)
        sync_log.completed_at = timezone.now()
        sync_log.response_data = {'results': results}
        sync_log.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Bulk sync completed: {successful} successful, {failed} failed',
            'total': len(products_to_sync),
            'successful': successful,
            'failed': failed,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error in bulk sync: {str(e)}")
        
        sync_log.status = 'failed'
        sync_log.error_message = str(e)
        sync_log.completed_at = timezone.now()
        sync_log.save()
        
        return JsonResponse({
            'success': False,
            'error': f'Bulk sync failed: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def cj_create_order(request, subdomain):
    """Create a CJ order (manual fulfillment)"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    try:
        cj_settings_obj = page.cj_settings.get()
        if not cj_settings_obj.is_active:
            messages.error(request, 'CJ integration is not active')
            return redirect('cj_orders', subdomain=subdomain)
    except CJSettings.DoesNotExist:
        messages.error(request, 'CJ integration not configured')
        return redirect('cj_settings', subdomain=subdomain)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['order_number', 'products', 'shipping_country', 'customer_info']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }, status=400)
            
            # Create sync log
            sync_log = CJSyncLog.objects.create(
                page=page,
                sync_type='order_submit',
                status='started',
                request_data={'order_number': data['order_number']}
            )
            
            try:
                cj_service = CJService(cj_settings_obj.api_key, page)
                
                # Prepare order data for CJ
                order_data = {
                    'orderNo': data['order_number'],
                    'shippingCountryCode': data['shipping_country'],
                    'productList': [],
                    'warehouse': data.get('warehouse', cj_settings_obj.default_warehouse),
                    'buyerInfo': data['customer_info']
                }
                
                # Add shipping method if provided
                if 'shipping_method' in data:
                    order_data['shippingMethod'] = data['shipping_method']
                
                # Calculate total cost and prepare product list
                total_cost = 0
                for item in data['products']:
                    # Get CJ product details
                    try:
                        cj_product = CJProduct.objects.get(
                            page=page,
                            local_product_id=item.get('product_id')
                        )
                        
                        order_data['productList'].append({
                            'pid': cj_product.cj_product_id,
                            'quantity': item.get('quantity', 1),
                            'sellingPrice': float(cj_product.local_selling_price or cj_product.calculate_selling_price())
                        })
                        
                        total_cost += float(cj_product.cj_price_usd or 0) * item.get('quantity', 1)
                        
                    except CJProduct.DoesNotExist:
                        sync_log.status = 'failed'
                        sync_log.error_message = f"Product not found: {item.get('product_id')}"
                        sync_log.completed_at = timezone.now()
                        sync_log.save()
                        
                        return JsonResponse({
                            'success': False,
                            'error': f'Product not found: {item.get("product_id")}'
                        }, status=400)
                
                # Submit order to CJ
                result = cj_service.create_order(order_data)
                
                if result['success']:
                    # Create CJ order record
                    cj_order = CJOrder.objects.create(
                        page=page,
                        order_number=data['order_number'],
                        cj_order_id=result['order_id'],
                        local_order_reference=data.get('local_order_id', ''),
                        customer_name=data['customer_info'].get('name', ''),
                        customer_email=data['customer_info'].get('email', ''),
                        shipping_country=data['shipping_country'],
                        shipping_address=data['customer_info'].get('address', {}),
                        status='submitted',
                        total_amount=data.get('total_amount', 0),
                        cj_cost=total_cost,
                        profit=data.get('total_amount', 0) - total_cost,
                        currency=cj_settings_obj.currency,
                        shipping_method=data.get('shipping_method', ''),
                        products=data['products'],
                        cj_request_data=order_data,
                        cj_response_data=result,
                        submitted_at=timezone.now()
                    )
                    
                    sync_log.status = 'success'
                    sync_log.items_processed = len(data['products'])
                    sync_log.items_succeeded = len(data['products'])
                    sync_log.api_calls_made = 1
                    sync_log.completed_at = timezone.now()
                    sync_log.response_data = result
                    sync_log.save()
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Order submitted to CJ successfully',
                        'order_id': cj_order.id,
                        'cj_order_id': result['order_id'],
                        'total_cost': total_cost,
                        'profit': float(cj_order.profit)
                    })
                else:
                    sync_log.status = 'failed'
                    sync_log.error_message = result.get('error', 'Order submission failed')
                    sync_log.completed_at = timezone.now()
                    sync_log.save()
                    
                    return JsonResponse(result, status=400)
                    
            except Exception as e:
                logger.error(f"Error creating CJ order: {str(e)}")
                
                sync_log.status = 'failed'
                sync_log.error_message = str(e)
                sync_log.completed_at = timezone.now()
                sync_log.save()
                
                return JsonResponse({
                    'success': False,
                    'error': f'Order creation failed: {str(e)}'
                }, status=500)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
    
    # GET request - show order creation form
    # Get available products for dropdown
    cj_products = CJProduct.objects.filter(
        page=page,
        sync_status='synced',
        cj_stock_quantity__gt=0
    ).select_related('local_product')[:100]
    
    context = {
        'page': page,
        'cj_settings': cj_settings_obj,
        'cj_products': cj_products,
        'countries': [
            ('US', 'United States'),
            ('CA', 'Canada'),
            ('GB', 'United Kingdom'),
            ('AU', 'Australia'),
            ('DE', 'Germany'),
            ('FR', 'France'),
        ]
    }
    
    return render(request, 'builder/cj_create_order.html', context)


@login_required
def cj_orders_list(request, subdomain):
    """View status of all CJ-related orders"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    orders = CJOrder.objects.filter(page=page).order_by('-created_at')
    
    return render(request, 'builder/cj_orders.html', {
        'page': page,
        'orders': orders,
        'status_options': CJOrder._meta.get_field('status').choices
    })


@login_required
@require_http_methods(["GET"])
def cj_order_detail(request, subdomain, order_id):
    """View details of a specific CJ order"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    try:
        order = CJOrder.objects.get(page=page, id=order_id)
    except CJOrder.DoesNotExist:
        messages.error(request, 'Order not found')
        return redirect('cj_orders', subdomain=subdomain)
    
    context = {
        'page': page,
        'order': order,
    }
    
    return render(request, 'builder/cj_order_detail.html', context)


@login_required
def cj_check_order_status(request, subdomain, order_id):
    """Force an update of an order's status from CJ's API"""
    order = get_object_or_404(CJOrder, id=order_id, page__subdomain=subdomain)
    settings = order.page.cj_settings.get()
    cj_service = CJService(settings.api_key, order.page)
    
    result = cj_service.get_order_status(order.cj_order_id)
    if result['success']:
        order.status = result['order']['status'].lower()
        order.tracking_number = result['order'].get('tracking_number')
        order.save()
        return JsonResponse({'status': 'success', 'new_status': order.status})
    
    return JsonResponse({'status': 'error', 'message': result.get('error')}, status=400)



@login_required
@require_http_methods(["GET"])
def cj_sync_logs(request, subdomain):
    """View sync logs for monitoring"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get filter parameters
    sync_type = request.GET.get('sync_type')
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base queryset
    logs = CJSyncLog.objects.filter(page=page)
    
    # Apply filters
    if sync_type:
        logs = logs.filter(sync_type=sync_type)
    
    if status:
        logs = logs.filter(status=status)
    
    if date_from:
        logs = logs.filter(started_at__date__gte=date_from)
    
    if date_to:
        logs = logs.filter(started_at__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(logs.order_by('-started_at'), 50)
    page_num = int(request.GET.get('page', 1))
    
    try:
        page_obj = paginator.page(page_num)
    except:
        page_obj = paginator.page(1)
    
    # Calculate statistics
    total_logs = logs.count()
    success_rate = 0
    if total_logs > 0:
        success_count = logs.filter(status='success').count()
        success_rate = (success_count / total_logs) * 100
    
    # API usage
    api_calls = logs.aggregate(models.Sum('api_calls_made'))['api_calls_made__sum'] or 0
    
    context = {
        'page': page,
        'logs': page_obj,
        'total_logs': total_logs,
        'success_rate': round(success_rate, 1),
        'api_calls': api_calls,
        'sync_type_options': [
            ('', 'All Types'),
            ('product_search', 'Product Search'),
            ('product_import', 'Product Import'),
            ('price_sync', 'Price Sync'),
            ('inventory_sync', 'Inventory Sync'),
            ('order_submit', 'Order Submission'),
            ('order_status_check', 'Order Status Check'),
        ],
        'status_options': [
            ('', 'All Status'),
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('partial', 'Partial'),
            ('rate_limited', 'Rate Limited'),
        ],
        'current_sync_type': sync_type,
        'current_status': status,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'builder/cj_sync_logs.html', context)

# builder/views.py - Updated CJ Dashboard View

@login_required
def cj_dashboard(request, subdomain):
    """Enhanced CJ Dropshipping dashboard with all stats populated"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create CJ settings
    cj_settings, created = CJSettings.objects.get_or_create(
        page=page,
        defaults={
            'api_key': '',
            'is_active': False,
            'api_status': 'inactive',
        }
    )
    
    # ===== STATS CALCULATIONS =====
    
    # 1. Product Stats
    cj_products = CJProduct.objects.filter(page=page)
    total_products = cj_products.count()
    synced_products = cj_products.filter(sync_status='synced').count()
    failed_products = cj_products.filter(sync_status='failed').count()
    pending_products = cj_products.filter(sync_status='pending').count()
    
    sync_rate = 0
    if total_products > 0:
        sync_rate = round((synced_products / total_products) * 100)
    
    # 2. Order Stats
    cj_orders = CJOrder.objects.filter(page=page)
    total_orders = cj_orders.count()
    fulfilled_orders = cj_orders.filter(status__in=['shipped', 'delivered']).count()
    pending_orders = cj_orders.filter(status__in=['pending', 'submitted', 'processing']).count()
    
    order_completion = 0
    if total_orders > 0:
        order_completion = round((fulfilled_orders / total_orders) * 100)
    
    # 3. Revenue Stats
    monthly_revenue = 0
    monthly_profit = 0
    monthly_orders = cj_orders.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    )
    for order in monthly_orders:
        monthly_revenue += float(order.total_amount or 0)
        monthly_profit += float(order.profit or 0)
    
    profit_margin = 0
    if monthly_revenue > 0:
        profit_margin = round((monthly_profit / monthly_revenue) * 100, 1)
    
    # Revenue target (assuming $1000 target)
    revenue_target = 0
    if monthly_revenue > 0:
        revenue_target = min(100, round((monthly_revenue / 1000) * 100))
    
    # 4. Sync Health
    sync_logs = CJSyncLog.objects.filter(page=page)
    total_syncs = sync_logs.count()
    successful_syncs = sync_logs.filter(status='success').count()
    
    sync_success_rate = 0
    if total_syncs > 0:
        sync_success_rate = round((successful_syncs / total_syncs) * 100, 1)
    
    # 5. API Usage
    api_usage = {
        'today': cj_settings.daily_api_calls or 0,
        'limit': cj_settings.max_daily_calls or 950,
        'percentage': 0
    }
    if api_usage['limit'] > 0:
        api_usage['percentage'] = round((api_usage['today'] / api_usage['limit']) * 100)
    
    # ===== RECENT ACTIVITY =====
    recent_activity = CJSyncLog.objects.filter(page=page).order_by('-started_at')[:20]
    
    # ===== RECENT ORDERS =====
    recent_orders = CJOrder.objects.filter(page=page).order_by('-created_at')[:5]
    
    # ===== RECENT PRODUCTS =====
    recent_products = CJProduct.objects.filter(page=page).select_related('local_product').order_by('-created_at')[:5]
    
    # ===== API STATUS CHECKS =====
    api_status = {
        'is_connected': cj_settings.api_status == 'active' and cj_settings.is_active,
        'is_valid': cj_settings.api_status != 'invalid' and cj_settings.api_key,
        'has_token': bool(cj_settings.access_token),
        'token_expiry': cj_settings.token_expiry,
        'last_check': cj_settings.last_api_check,
    }
    
    # ===== STATS SUMMARY =====
    stats = {
        'total_products': total_products,
        'synced_products': synced_products,
        'failed_products': failed_products,
        'pending_products': pending_products,
        'sync_rate': sync_rate,
        
        'total_orders': total_orders,
        'fulfilled_orders': fulfilled_orders,
        'pending_orders': pending_orders,
        'order_completion': order_completion,
        
        'monthly_revenue': monthly_revenue,
        'monthly_profit': monthly_profit,
        'profit_margin': profit_margin,
        'revenue_target': revenue_target,
        
        'sync_success_rate': sync_success_rate,
        'total_syncs': total_syncs,
        'successful_syncs': successful_syncs,
        
        'api_usage': api_usage,
    }
    
    context = {
        'page': page,
        'cj_settings': cj_settings,
        'stats': stats,
        'recent_activity': recent_activity,
        'recent_orders': recent_orders,
        'recent_products': recent_products,
        'api_status': api_status,
        'is_configured': bool(cj_settings.api_key) and cj_settings.is_active,
        'has_products': total_products > 0,
        'has_orders': total_orders > 0,
    }
    
    return render(request, 'builder/cj_dashboard.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def cj_webhook(request, subdomain):
    """Receive webhooks from CJ for order updates"""
    # Get page from subdomain
    try:
        page = PublishedPage.objects.get(subdomain=subdomain)
    except PublishedPage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid subdomain'}, status=404)
    
    # Verify webhook secret
    try:
        cj_settings_obj = page.cj_settings.get()
    except CJSettings.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'CJ integration not configured'}, status=400)
    
    # Get webhook signature
    signature = request.headers.get('X-CJ-Signature')
    if not signature:
        return JsonResponse({'success': False, 'error': 'Missing signature'}, status=400)
    
    # Verify signature (CJ might send it, implement if they provide method)
    # For now, we'll trust the webhook
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    # Create sync log for webhook
    sync_log = CJSyncLog.objects.create(
        page=page,
        sync_type='webhook',
        status='started',
        request_data=data
    )
    
    try:
        event_type = data.get('event_type')
        
        if event_type == 'order_status_update':
            # Update order status
            cj_order_id = data.get('order_id')
            new_status = data.get('status')
            tracking_info = data.get('tracking', {})
            
            try:
                order = CJOrder.objects.get(page=page, cj_order_id=cj_order_id)
                
                old_status = order.status
                order.status = new_status
                
                if tracking_info:
                    order.tracking_number = tracking_info.get('number', '')
                    order.tracking_url = tracking_info.get('url', '')
                
                if new_status == 'shipped' and not order.shipped_at:
                    order.shipped_at = timezone.now()
                elif new_status == 'delivered' and not order.delivered_at:
                    order.delivered_at = timezone.now()
                
                order.save()
                
                sync_log.status = 'success'
                sync_log.completed_at = timezone.now()
                sync_log.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Order status updated from {old_status} to {new_status}'
                })
                
            except CJOrder.DoesNotExist:
                sync_log.status = 'failed'
                sync_log.error_message = f'Order not found: {cj_order_id}'
                sync_log.completed_at = timezone.now()
                sync_log.save()
                
                return JsonResponse({
                    'success': False,
                    'error': 'Order not found'
                }, status=404)
        
        elif event_type == 'product_update':
            # Product price or stock update
            product_id = data.get('product_id')
            updates = data.get('updates', {})
            
            try:
                cj_product = CJProduct.objects.get(page=page, cj_product_id=product_id)
                
                if 'price' in updates:
                    cj_product.cj_price_usd = float(updates['price'])
                
                if 'stock' in updates:
                    cj_product.cj_stock_quantity = int(updates['stock'])
                
                cj_product.last_full_sync = timezone.now()
                cj_product.save()
                
                sync_log.status = 'success'
                sync_log.completed_at = timezone.now()
                sync_log.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Product updated'
                })
                
            except CJProduct.DoesNotExist:
                sync_log.status = 'failed'
                sync_log.error_message = f'Product not found: {product_id}'
                sync_log.completed_at = timezone.now()
                sync_log.save()
                
                return JsonResponse({
                    'success': False,
                    'error': 'Product not found'
                }, status=404)
        
        else:
            sync_log.status = 'failed'
            sync_log.error_message = f'Unknown event type: {event_type}'
            sync_log.completed_at = timezone.now()
            sync_log.save()
            
            return JsonResponse({
                'success': False,
                'error': f'Unknown event type: {event_type}'
            }, status=400)
            
    except Exception as e:
        logger.error(f"Error processing CJ webhook: {str(e)}")
        
        sync_log.status = 'failed'
        sync_log.error_message = str(e)
        sync_log.completed_at = timezone.now()
        sync_log.save()
        
        return JsonResponse({
            'success': False,
            'error': f'Webhook processing failed: {str(e)}'
        }, status=500)
    






# builder/views.py - Add these color-related views

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
import json
from .models import ColorPalette, ColorPaletteColor, PageColorPalette, CustomColorOverride, PublishedPage


@csrf_exempt
def get_color_palettes(request):
    """
    API endpoint to get all available color palettes
    """
    try:
        # Get filter parameters
        category = request.GET.get('category')
        mood = request.GET.get('mood')
        search = request.GET.get('search')
        
        # Base queryset
        palettes = ColorPalette.objects.filter(is_active=True)
        
        # Apply filters
        if category and category != 'all':
            palettes = palettes.filter(category=category)
        if mood and mood != 'all':
            palettes = palettes.filter(mood=mood)
        if search:
            palettes = palettes.filter(name__icontains=search)
        
        # Order by popularity and display order
        palettes = palettes.order_by('-display_order', '-usage_count', 'name')
        
        # Get current active palette for the page if editing
        current_palette = None
        page_subdomain = request.GET.get('page_subdomain')
        if page_subdomain:
            try:
                page = PublishedPage.objects.get(subdomain=page_subdomain, user=request.user)
                active_palette = page.color_palettes.filter(is_active=True).first()
                if active_palette:
                    current_palette = {
                        'id': active_palette.palette.id,
                        'name': active_palette.palette.name,
                        'slug': active_palette.palette.slug,
                    }
            except PublishedPage.DoesNotExist:
                pass
        
        # Format response
        data = {
            'categories': [],
            'palettes': [],
            'current_palette': current_palette
        }
        
        # Get all unique categories with counts
        categories = []
        for cat_code, cat_name in ColorPalette._meta.get_field('category').choices:
            count = ColorPalette.objects.filter(category=cat_code, is_active=True).count()
            if count > 0:
                categories.append({
                    'code': cat_code,
                    'name': cat_name,
                    'count': count
                })
        data['categories'] = categories
        
        # Format palettes
        for palette in palettes:  # Limit to 50 for performance
            colors = []
            for color in palette.colors.all().order_by('display_order'):
                colors.append({
                    'variable': color.variable_name,
                    'hex': color.hex_value,
                    'rgb': color.rgb_value,
                    'name': color.name,
                    'type': color.color_type
                })
            
            data['palettes'].append({
                'id': palette.id,
                'name': palette.name,
                'slug': palette.slug,
                'category': palette.category,
                'category_display': palette.get_category_display(),
                'mood': palette.mood,
                'mood_display': palette.get_mood_display(),
                'description': palette.description,
                'is_premium': palette.is_premium,
                'usage_count': palette.usage_count,
                'colors': colors[:8],  # Limit to 8 colors for preview
            })
        
        return JsonResponse({'success': True, 'data': data})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_palette_detail(request, palette_id):
    """
    Get detailed information about a specific palette
    """
    try:
        palette = get_object_or_404(ColorPalette, id=palette_id, is_active=True)
        
        colors = []
        for color in palette.colors.all().order_by('display_order'):
            colors.append({
                'variable': color.variable_name,
                'hex': color.hex_value,
                'rgb': color.rgb_value,
                'name': color.name,
                'type': color.color_type,
                'display_order': color.display_order
            })
        
        data = {
            'id': palette.id,
            'name': palette.name,
            'slug': palette.slug,
            'description': palette.description,
            'category': palette.category,
            'category_display': palette.get_category_display(),
            'mood': palette.mood,
            'mood_display': palette.get_mood_display(),
            'is_premium': palette.is_premium,
            'usage_count': palette.usage_count,
            'colors': colors
        }
        
        return JsonResponse({'success': True, 'data': data})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# builder/views.py - Enhanced apply_color_palette with dynamic variable mapping
# builder/views.py - Fixed apply_color_palette with proper F() usage

# builder/views.py - Enhanced apply_color_palette


# builder/views.py - Fixed apply_color_palette

@csrf_exempt
@login_required
def apply_color_palette(request, subdomain):
    """
    Apply a color palette to a published page and save to database
    """
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            data = json.loads(request.body)
            
            palette_id = data.get('palette_id')
            palette = get_object_or_404(ColorPalette, id=palette_id)
            
            # ===== CRITICAL FIX: Properly deactivate existing active palette =====
            # Use a transaction to ensure data consistency
            from django.db import transaction
            
            with transaction.atomic():
                # 1. Deactivate ALL existing active palettes for this page
                #    This must be done BEFORE creating a new active palette
                deactivated_count = PageColorPalette.objects.filter(
                    page=page, 
                    is_active=True
                ).update(is_active=False)
                
                print(f"🔄 Deactivated {deactivated_count} existing active palettes")
                
                # 2. Also update the PublishedPage model
                page.active_palette = None
                page.active_palette_colors = {}
                page.save(update_fields=['active_palette', 'active_palette_colors', 'updated_at'])
                
                # 3. Get the template's color mapping
                template = page.template
                
                # Get or create color mapping
                color_mapping, _ = TemplateColorMapping.objects.get_or_create(
                    template=template,
                    defaults={
                        'variables': TemplateColorExtractor.generate_color_map(template.name)['variables'],
                        'suggested_mapping': TemplateColorExtractor.generate_color_map(template.name)['suggested_mapping']
                    }
                )
                
                # Get active mapping
                variable_mapping = color_mapping.get_active_mapping()
                
                # Get custom overrides
                custom_overrides = data.get('overrides', {})
                
                # Build the color application map
                applied_colors = {}
                template_variables = color_mapping.variables
                
                for var_name, var_data in template_variables.items():
                    # Check for override
                    if var_name in custom_overrides:
                        applied_colors[var_name] = {
                            'hex': custom_overrides[var_name],
                            'rgb': ColorPaletteColor.hex_to_rgb(custom_overrides[var_name]),
                            'source': 'override'
                        }
                        continue
                    
                    # Try to find matching palette color
                    matched_color = None
                    
                    if var_name in variable_mapping:
                        role = variable_mapping[var_name].get('role')
                        palette_color = palette.colors.filter(color_type=role).first()
                        if palette_color:
                            matched_color = palette_color
                    
                    if not matched_color:
                        matched_color = find_best_palette_match(var_name, palette)
                    
                    if not matched_color:
                        matched_color = palette.colors.filter(color_type='primary').first()
                    
                    if matched_color:
                        applied_colors[var_name] = {
                            'hex': matched_color.hex_value,
                            'rgb': matched_color.rgb_value,
                            'source': 'palette',
                            'palette_color_id': matched_color.id,
                            'color_name': matched_color.name,
                            'color_type': matched_color.color_type
                        }
                    else:
                        # Keep original
                        applied_colors[var_name] = {
                            'hex': var_data.get('value', '#000000'),
                            'rgb': var_data.get('rgb', '0,0,0'),
                            'source': 'original'
                        }
                
                # 4. NOW create the new active palette (no conflict since we deactivated others)
                page_palette = PageColorPalette.objects.create(
                    page=page,
                    palette=palette,
                    is_active=True,
                    applied_colors=applied_colors,
                    variable_mapping=variable_mapping
                )
                
                # 5. Update the PublishedPage model with the new palette
                page.active_palette = palette
                page.active_palette_colors = applied_colors
                page.save(update_fields=['active_palette', 'active_palette_colors', 'updated_at'])
                
                # 6. Save custom overrides
                if custom_overrides:
                    for var_name, hex_value in custom_overrides.items():
                        CustomColorOverride.objects.update_or_create(
                            page=page,
                            palette=palette,
                            variable_name=var_name,
                            defaults={
                                'hex_value': hex_value,
                                'rgb_value': ColorPaletteColor.hex_to_rgb(hex_value)
                            }
                        )
                
                # 7. Increment usage counts
                palette.usage_count =F('usage_count') + 1
                palette.save(update_fields=['usage_count'])
            
            return JsonResponse({
                'success': True,
                'message': f'Applied {palette.name} palette successfully!',
                'colors': applied_colors,
                'variable_count': len(applied_colors),
                'palette_id': palette.id,
                'palette_name': palette.name,
                'deactivated': deactivated_count
            })
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})



@login_required
def get_page_palette(request, subdomain):
    """
    Get the currently active palette for a page (from PublishedPage)
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        # Get from PublishedPage first (faster)
        if page.active_palette and page.active_palette_colors:
            # Get custom overrides
            overrides = {}
            for override in CustomColorOverride.objects.filter(page=page, palette=page.active_palette):
                overrides[override.variable_name] = override.hex_value
            
            data = {
                'palette_id': page.active_palette.id,
                'palette_name': page.active_palette.name,
                'applied_at': page.updated_at.isoformat(),
                'colors': page.active_palette_colors,
                'overrides': overrides
            }
            return JsonResponse({'success': True, 'data': data})
        
        # Fallback to PageColorPalette
        else:
            active_palette = page.color_palettes.filter(is_active=True).first()
            if active_palette:
                # Update PublishedPage cache
                page.active_palette = active_palette.palette
                page.active_palette_colors = active_palette.applied_colors
                page.save(update_fields=['active_palette', 'active_palette_colors'])
                
                data = {
                    'palette_id': active_palette.palette.id,
                    'palette_name': active_palette.palette.name,
                    'applied_at': active_palette.applied_at.isoformat(),
                    'colors': active_palette.applied_colors,
                    'overrides': {}
                }
                return JsonResponse({'success': True, 'data': data})
            
            # IMPORTANT: Return null data when no palette is active
            return JsonResponse({'success': True, 'data': None})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# builder/views.py - Fixed reset_page_palette

@login_required
def reset_page_palette(request, subdomain):
    """
    Reset page to default template colors
    """
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            
            from django.db import transaction
            
            with transaction.atomic():
                # 1. Deactivate ALL active palettes for this page
                deactivated = PageColorPalette.objects.filter(
                    page=page,
                    is_active=True
                ).update(is_active=False)
                
                # 2. Clear palette from PublishedPage model (this is critical!)
                page.active_palette = None
                page.active_palette_colors = {}
                
                # 3. Also remove palette from page_customizations JSON
                if page.page_customizations:
                    # Remove from all pages in the multi-page site
                    for page_name in page.page_customizations.keys():
                        if 'color_palette' in page.page_customizations.get(page_name, {}):
                            del page.page_customizations[page_name]['color_palette']
                
                # Save the page with all changes
                page.save(update_fields=['active_palette', 'active_palette_colors', 'page_customizations', 'updated_at'])
                
                # 4. Delete all custom color overrides for this page
                deleted_overrides = CustomColorOverride.objects.filter(page=page).delete()
                
                # 5. Optionally, clear any color-related data from component customizations
                # This ensures no color variables remain in components
                for comp_custom in ComponentCustomization.objects.filter(page=page):
                    if comp_custom.customizations and 'colors' in comp_custom.customizations:
                        customizations = comp_custom.customizations
                        if 'colors' in customizations:
                            del customizations['colors']
                            comp_custom.customizations = customizations
                            comp_custom.save(update_fields=['customizations'])
                
                print(f"🔄 Reset palette for page {page.subdomain}: Deactivated {deactivated} palettes")

            return JsonResponse({
                'success': True,
                'message': 'Reset to default template colors',
                'deactivated': deactivated,
                'overrides_deleted': deleted_overrides[0] if deleted_overrides else 0
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


def find_best_palette_match(var_name, palette):
    """
    Find the best matching palette color for a template variable name
    Using fuzzy matching and keyword analysis
    """
    from difflib import SequenceMatcher
    
    var_lower = var_name.lower()
    best_match = None
    best_score = 0
    
    for palette_color in palette.colors.all():
        # Check against color name
        color_name_lower = palette_color.name.lower()
        score = SequenceMatcher(None, var_lower, color_name_lower).ratio()
        
        # Check against color type
        color_type_lower = palette_color.color_type.lower()
        type_score = SequenceMatcher(None, var_lower, color_type_lower).ratio()
        
        # Take the better score
        score = max(score, type_score)
        
        # Bonus for keyword matches
        keywords = {
            'primary': ['primary', 'main', 'brand'],
            'secondary': ['secondary', 'second', 'alt'],
            'accent': ['accent', 'highlight', 'cta'],
            'background': ['background', 'bg', 'back'],
            'text': ['text', 'font', 'copy'],
            'heading': ['heading', 'title', 'header'],
        }
        
        for role, words in keywords.items():
            if palette_color.color_type == role:
                for word in words:
                    if word in var_lower:
                        score += 0.3
                        break
        
        if score > best_score and score > 0.4:  # Minimum threshold
            best_score = score
            best_match = palette_color
    
    return best_match

# builder/views.py - Add this view

@login_required
def get_template_color_variables(request, template_name):
    """
    Get all color variables discovered in a template
    Used by the frontend to show what can be customized
    """
    try:
        template = get_object_or_404(Template, name=template_name)
        
        # Get or create color mapping
        color_mapping, created = TemplateColorMapping.objects.get_or_create(
            template=template,
            defaults={
                'variables': TemplateColorExtractor.generate_color_map(template.name)['variables'],
                'suggested_mapping': TemplateColorExtractor.generate_color_map(template.name)['suggested_mapping']
            }
        )
        
        # Get active mapping
        active_mapping = color_mapping.get_active_mapping()
        
        # Format response
        variables = []
        for var_name, var_data in color_mapping.variables.items():
            var_info = {
                'name': var_name,
                'value': var_data.get('value', ''),
                'type': var_data.get('type', 'hex'),
                'source': var_data.get('source', 'unknown'),
                'suggested_role': active_mapping.get(var_name, {}).get('role', 'custom'),
                'confidence': active_mapping.get(var_name, {}).get('confidence', 0.3)
            }
            variables.append(var_info)
        
        return JsonResponse({
            'success': True,
            'template': template.name,
            'variable_count': len(variables),
            'variables': variables,
            'has_custom_mapping': bool(color_mapping.custom_mapping),
            'mapping': active_mapping
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

# builder/views.py - Fixed get_page_palette

@login_required
def get_page_palette(request, subdomain):
    """
    Get the currently active palette for a page (from PublishedPage)
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        # Get from PublishedPage first (faster)
        if page.active_palette and page.active_palette_colors:
            # Get custom overrides
            overrides = {}
            for override in CustomColorOverride.objects.filter(page=page, palette=page.active_palette):
                overrides[override.variable_name] = override.hex_value
            
            data = {
                'palette_id': page.active_palette.id,
                'palette_name': page.active_palette.name,
                'applied_at': page.updated_at.isoformat(),
                'colors': page.active_palette_colors,
                'overrides': overrides
            }
            return JsonResponse({'success': True, 'data': data})
        
        # Fallback to PageColorPalette
        else:
            active_palette = page.color_palettes.filter(is_active=True).first()
            if active_palette:
                # Update PublishedPage cache
                page.active_palette = active_palette.palette
                page.active_palette_colors = active_palette.applied_colors
                page.save(update_fields=['active_palette', 'active_palette_colors'])
                
                data = {
                    'palette_id': active_palette.palette.id,
                    'palette_name': active_palette.palette.name,
                    'applied_at': active_palette.applied_at.isoformat(),
                    'colors': active_palette.applied_colors,
                    'overrides': {}
                }
                return JsonResponse({'success': True, 'data': data})
        
        return JsonResponse({'success': True, 'data': None})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

@login_required
def reset_page_palette(request, subdomain):
    """
    Reset page to default template colors
    """
    if request.method == 'POST':
        try:
            page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
            
            from django.db import transaction
            
            with transaction.atomic():
                # 1. Deactivate ALL active palettes for this page
                deactivated = PageColorPalette.objects.filter(
                    page=page,
                    is_active=True
                ).update(is_active=False)
                
                # 2. Clear palette from PublishedPage model (this is critical!)
                page.active_palette = None
                page.active_palette_colors = {}
                
                # 3. Also remove palette from page_customizations JSON
                if page.page_customizations:
                    # Remove from all pages in the multi-page site
                    for page_name in list(page.page_customizations.keys()):
                        if 'color_palette' in page.page_customizations.get(page_name, {}):
                            del page.page_customizations[page_name]['color_palette']
                
                # Save the page with all changes
                page.save(update_fields=['active_palette', 'active_palette_colors', 'page_customizations', 'updated_at'])
                
                # 4. Delete all custom color overrides for this page
                CustomColorOverride.objects.filter(page=page).delete()
                
                # 5. Clear any color-related data from component customizations
                for comp_custom in ComponentCustomization.objects.filter(page=page):
                    if comp_custom.customizations:
                        customizations = comp_custom.customizations
                        modified = False
                        if 'colors' in customizations:
                            del customizations['colors']
                            modified = True
                        if modified:
                            comp_custom.customizations = customizations
                            comp_custom.save(update_fields=['customizations'])
                
                print(f"🔄 Reset palette for page {page.subdomain}: Deactivated {deactivated} palettes")

            return JsonResponse({
                'success': True,
                'message': 'Reset to default template colors',
                'deactivated': deactivated
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})

# Add these imports at the top
from django.db import transaction
from django.core.cache import cache
from .models import PaletteColorUsage, ColorPaletteColor
import logging

logger = logging.getLogger(__name__)

@login_required
@csrf_exempt
def update_palette_color(request, subdomain):
    """
    Update a palette color globally across all elements that use it
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        data = json.loads(request.body)
        
        variable_name = data.get('variable_name')
        new_hex_value = data.get('hex_value')
        palette_id = data.get('palette_id')
        
        if not all([variable_name, new_hex_value, palette_id]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        # Validate hex color
        if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', new_hex_value):
            return JsonResponse({'success': False, 'error': 'Invalid hex color format'})
        
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                return f"{rgb[0]}, {rgb[1]}, {rgb[2]}"
            return ""
        
        with transaction.atomic():
            palette = get_object_or_404(ColorPalette, id=palette_id)
            
            # Update the page's active palette colors
            if page.active_palette == palette and page.active_palette_colors:
                if variable_name in page.active_palette_colors:
                    if isinstance(page.active_palette_colors[variable_name], dict):
                        page.active_palette_colors[variable_name]['hex'] = new_hex_value
                        page.active_palette_colors[variable_name]['rgb'] = hex_to_rgb(new_hex_value)
                    else:
                        page.active_palette_colors[variable_name] = new_hex_value
                    
                    page.save(update_fields=['active_palette_colors', 'updated_at'])
            
            # Update or create palette color in database
            palette_color, created = ColorPaletteColor.objects.update_or_create(
                palette=palette,
                variable_name=variable_name,
                defaults={
                    'name': variable_name.replace('_', ' ').title(),
                    'hex_value': new_hex_value,
                    'color_type': 'custom',
                    'rgb_value': hex_to_rgb(new_hex_value)
                }
            )
            
            # NO REDIS - Just return success without any cache operations
            return JsonResponse({
                'success': True,
                'message': f'Color {variable_name} updated to {new_hex_value}',
                'variable_name': variable_name,
                'hex_value': new_hex_value,
                'rgb_value': palette_color.rgb_value,
                'palette_id': palette.id,
                'palette_name': palette.name,
                'updated_at': timezone.now().isoformat()
            })
            
    except ColorPalette.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Palette not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.exception(f"Error updating palette color: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    """
    Update a palette color globally across all elements that use it
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        data = json.loads(request.body)
        
        variable_name = data.get('variable_name')
        new_hex_value = data.get('hex_value')
        palette_id = data.get('palette_id')
        
        if not all([variable_name, new_hex_value, palette_id]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        # Validate hex color
        if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', new_hex_value):
            return JsonResponse({'success': False, 'error': 'Invalid hex color format'})
        
        # Helper function to convert hex to RGB
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                return f"{rgb[0]}, {rgb[1]}, {rgb[2]}"
            return ""
        
        with transaction.atomic():
            # Get the palette
            palette = get_object_or_404(ColorPalette, id=palette_id)
            
            # Update the page's active palette colors
            if page.active_palette == palette and page.active_palette_colors:
                if variable_name in page.active_palette_colors:
                    if isinstance(page.active_palette_colors[variable_name], dict):
                        page.active_palette_colors[variable_name]['hex'] = new_hex_value
                        page.active_palette_colors[variable_name]['rgb'] = hex_to_rgb(new_hex_value)
                    else:
                        page.active_palette_colors[variable_name] = new_hex_value
                    
                    page.save(update_fields=['active_palette_colors', 'updated_at'])
            
            # Update or create palette color in database
            palette_color, created = ColorPaletteColor.objects.update_or_create(
                palette=palette,
                variable_name=variable_name,
                defaults={
                    'name': variable_name.replace('_', ' ').title(),
                    'hex_value': new_hex_value,
                    'color_type': 'custom',
                    'rgb_value': hex_to_rgb(new_hex_value)
                }
            )
            
            # Try to clear cache, but don't fail if Redis is down
            try:
                from django.core.cache import cache
                cache_key = f'palette_css_{page.id}_{variable_name}'
                cache.delete(cache_key)
            except Exception as cache_error:
                # Log but don't fail - cache is not critical
                logger.warning(f"Cache deletion failed (non-critical): {cache_error}")
            
            return JsonResponse({
                'success': True,
                'message': f'Color {variable_name} updated to {new_hex_value}',
                'variable_name': variable_name,
                'hex_value': new_hex_value,
                'rgb_value': palette_color.rgb_value,
                'palette_id': palette.id,
                'palette_name': palette.name,
                'updated_at': timezone.now().isoformat()
            })
            
    except ColorPalette.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Palette not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.exception(f"Error updating palette color: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)




@staticmethod
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"{rgb[0]}, {rgb[1]}, {rgb[2]}"
    return ""


@login_required
def scan_page_color_usage(request, subdomain):
    """
    Scan the current page to count how many elements use each palette color
    This helps track usage statistics for global updates
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        if not page.active_palette:
            return JsonResponse({'success': False, 'error': 'No active palette'})
        
        # Clear existing usage records for this page/palette
        PaletteColorUsage.objects.filter(
            page=page,
            palette=page.active_palette
        ).update(element_count=0)
        
        # Get all palette colors for the active palette
        palette_colors = page.active_palette.colors.all()
        
        # For each color, we need to count elements in the template that use it
        # This would require loading the template HTML and counting elements with matching CSS variables
        
        # Simplified approach: Update usage counts to at least 1 if the color is in active_palette_colors
        if page.active_palette_colors:
            for var_name, color_data in page.active_palette_colors.items():
                try:
                    palette_color = ColorPaletteColor.objects.get(
                        palette=page.active_palette,
                        variable_name=var_name
                    )
                    
                    usage, created = PaletteColorUsage.objects.get_or_create(
                        page=page,
                        palette=page.active_palette,
                        palette_color=palette_color,
                        variable_name=var_name,
                        defaults={
                            'current_hex_value': color_data.get('hex') if isinstance(color_data, dict) else color_data,
                            'element_count': 1  # At least the color is defined
                        }
                    )
                    
                    if not created:
                        usage.current_hex_value = color_data.get('hex') if isinstance(color_data, dict) else color_data
                        usage.element_count = max(usage.element_count, 1)
                        usage.save()
                        
                except ColorPaletteColor.DoesNotExist:
                    # Create it on the fly
                    hex_value = color_data.get('hex') if isinstance(color_data, dict) else color_data
                    palette_color = ColorPaletteColor.objects.create(
                        palette=page.active_palette,
                        variable_name=var_name,
                        name=var_name.replace('_', ' ').title(),
                        hex_value=hex_value,
                        color_type='custom'
                    )
                    
                    PaletteColorUsage.objects.create(
                        page=page,
                        palette=page.active_palette,
                        palette_color=palette_color,
                        variable_name=var_name,
                        current_hex_value=hex_value,
                        element_count=1
                    )
        
        total_usages = PaletteColorUsage.objects.filter(
            page=page,
            palette=page.active_palette
        ).count()
        
        return JsonResponse({
            'success': True,
            'message': f'Scanned {total_usages} color usages',
            'total_colors': total_usages
        })
        
    except Exception as e:
        logger.exception(f"Error scanning color usage: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})




# payment selection

@login_required
def currency_settings(request, subdomain):
    """Manage currency settings for the store"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    if request.method == 'POST':
        # Update currency settings
        page.currency_code = request.POST.get('currency_code', 'USD')
        
        # Set symbol based on currency code
        # Set symbol based on currency code
        currency_symbols = {
            # Major World Currencies
            'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CNY': '¥',
            
            # Americas
            'CAD': 'C$', 'MXN': 'MX$', 'BRL': 'R$', 'ARS': '$', 'CLP': 'CLP$',
            'COP': 'COL$', 'PEN': 'S/', 'UYU': '$U', 'PYG': '₲', 'BOB': 'Bs',
            'VES': 'Bs.S', 'CRC': '₡', 'DOP': 'RD$', 'GTQ': 'Q', 'HNL': 'L',
            'NIO': 'C$', 'PAB': 'B/.', 'BSD': 'B$', 'BBD': 'Bds$', 'BZD': 'BZ$',
            'BMD': 'BD$', 'KYD': 'CI$', 'TTD': 'TT$', 'JMD': 'J$', 'HTG': 'G',
            'CUP': '₱', 'AWG': 'Afl', 'ANG': 'ƒ',
            
            # Europe
            'CHF': 'Fr', 'NOK': 'kr', 'SEK': 'kr', 'DKK': 'kr', 'ISK': 'kr',
            'RUB': '₽', 'TRY': '₺', 'PLN': 'zł', 'CZK': 'Kč', 'HUF': 'Ft',
            'RON': 'lei', 'BGN': 'лв', 'HRK': 'kn', 'RSD': 'дин', 'ALL': 'L',
            'MKD': 'ден', 'BAM': 'KM', 'MDL': 'lei', 'BYN': 'Br', 'UAH': '₴',
            'GEL': '₾', 'AMD': '֏', 'AZN': '₼',
            
            # Asia Pacific
            'AUD': 'A$', 'NZD': 'NZ$', 'SGD': 'S$', 'HKD': 'HK$', 'KRW': '₩',
            'INR': '₹', 'IDR': 'Rp', 'MYR': 'RM', 'PHP': '₱', 'THB': '฿',
            'VND': '₫', 'PKR': '₨', 'BDT': '৳', 'LKR': 'Rs', 'NPR': 'रू',
            'MMK': 'K', 'KHR': '៛', 'LAK': '₭', 'MNT': '₮', 'TWD': 'NT$',
            'MOP': 'MOP$', 'KZT': '₸', 'UZS': 'soʻm', 'TJS': 'SM', 'KGS': 'с',
            'ILS': '₪', 'JOD': 'د.ا', 'IQD': 'ع.د', 'IRR': '﷼', 'SAR': '﷼',
            'AED': 'د.إ', 'QAR': 'ر.ق', 'KWD': 'د.ك', 'BHD': 'د.ب', 'OMR': 'ر.ع',
            'YER': '﷼', 'LBP': 'ل.ل', 'SYP': '£S', 'AFN': '؋',
            
            # Africa
            'ZAR': 'R', 'EGP': '£E', 'NGN': '₦', 'KES': 'KSh', 'GHS': '₵',
            'MAD': 'د.م.', 'DZD': 'د.ج', 'TND': 'د.ت', 'LYD': 'ل.د', 'SDG': 'ج.س',
            'ETB': 'ብር', 'UGX': 'USh', 'TZS': 'TSh', 'RWF': 'FRw', 'BIF': 'FBu',
            'CDF': 'FC', 'GNF': 'FG', 'XOF': 'CFA', 'XAF': 'FCFA', 'MUR': '₨',
            'MGA': 'Ar', 'ZMW': 'ZK', 'MWK': 'MK', 'BWP': 'P', 'NAD': 'N$',
            'SZL': 'E', 'LSL': 'L', 'ZWL': 'Z$', 'MZN': 'MT', 'AOA': 'Kz',
            'MRO': 'UM', 'CVE': '$', 'SCR': 'SR', 'KMF': 'CF', 'DJF': 'Fdj',
            'ERN': 'Nfk', 'SOS': 'Sh', 'GMD': 'D', 'SLL': 'Le', 'LRD': 'L$',
            
            # Oceania
            'PGK': 'K', 'FJD': 'FJ$', 'SBD': 'SI$', 'VUV': 'Vt', 'TOP': 'T$',
            'WST': 'WS$', 'KID': '$', 'TVD': '$', 'XPF': '₣',
            
            # Precious Metals & Special
            'XAU': 'oz t', 'XAG': 'oz t', 'XPT': 'oz t', 'XPD': 'oz t',
            'XDR': 'SDR',
        }
        page.currency_symbol = currency_symbols.get(page.currency_code, '$')
        
        page.currency_position = request.POST.get('currency_position', 'before')
        page.thousand_separator = request.POST.get('thousand_separator', ',')
        page.decimal_separator = request.POST.get('decimal_separator', '.')
        page.decimal_places = int(request.POST.get('decimal_places', 2))
        
        # Payment gateway mappings
        payment_mapping = {}
        gateways = ['stripe', 'paypal', 'razorpay', 'square']
        for gateway in gateways:
            gateway_currency = request.POST.get(f'{gateway}_currency')
            if gateway_currency:
                payment_mapping[gateway] = gateway_currency
        
        page.payment_currency_mapping = payment_mapping
        page.save()
        
        messages.success(request, 'Currency settings updated successfully!')
        return redirect('currency_settings', subdomain=subdomain)
    
    # Common currency list for display
    currencies = [
        # Major World Currencies
        {'code': 'USD', 'name': 'US Dollar', 'symbol': '$'},
        {'code': 'EUR', 'name': 'Euro', 'symbol': '€'},
        {'code': 'GBP', 'name': 'British Pound', 'symbol': '£'},
        {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥'},
        {'code': 'CNY', 'name': 'Chinese Yuan', 'symbol': '¥'},
        
        # Americas
        {'code': 'CAD', 'name': 'Canadian Dollar', 'symbol': 'C$'},
        {'code': 'MXN', 'name': 'Mexican Peso', 'symbol': 'MX$'},
        {'code': 'BRL', 'name': 'Brazilian Real', 'symbol': 'R$'},
        {'code': 'ARS', 'name': 'Argentine Peso', 'symbol': '$'},
        {'code': 'CLP', 'name': 'Chilean Peso', 'symbol': 'CLP$'},
        {'code': 'COP', 'name': 'Colombian Peso', 'symbol': 'COL$'},
        {'code': 'PEN', 'name': 'Peruvian Sol', 'symbol': 'S/'},
        {'code': 'UYU', 'name': 'Uruguayan Peso', 'symbol': '$U'},
        {'code': 'PYG', 'name': 'Paraguayan Guarani', 'symbol': '₲'},
        {'code': 'BOB', 'name': 'Bolivian Boliviano', 'symbol': 'Bs'},
        {'code': 'VES', 'name': 'Venezuelan Bolívar', 'symbol': 'Bs.S'},
        {'code': 'CRC', 'name': 'Costa Rican Colón', 'symbol': '₡'},
        {'code': 'DOP', 'name': 'Dominican Peso', 'symbol': 'RD$'},
        {'code': 'GTQ', 'name': 'Guatemalan Quetzal', 'symbol': 'Q'},
        {'code': 'HNL', 'name': 'Honduran Lempira', 'symbol': 'L'},
        {'code': 'NIO', 'name': 'Nicaraguan Córdoba', 'symbol': 'C$'},
        {'code': 'PAB', 'name': 'Panamanian Balboa', 'symbol': 'B/.'},
        {'code': 'BSD', 'name': 'Bahamian Dollar', 'symbol': 'B$'},
        {'code': 'BBD', 'name': 'Barbadian Dollar', 'symbol': 'Bds$'},
        {'code': 'BZD', 'name': 'Belize Dollar', 'symbol': 'BZ$'},
        {'code': 'BMD', 'name': 'Bermudian Dollar', 'symbol': 'BD$'},
        {'code': 'KYD', 'name': 'Cayman Islands Dollar', 'symbol': 'CI$'},
        {'code': 'TTD', 'name': 'Trinidad & Tobago Dollar', 'symbol': 'TT$'},
        {'code': 'JMD', 'name': 'Jamaican Dollar', 'symbol': 'J$'},
        {'code': 'HTG', 'name': 'Haitian Gourde', 'symbol': 'G'},
        {'code': 'CUP', 'name': 'Cuban Peso', 'symbol': '₱'},
        {'code': 'AWG', 'name': 'Aruban Florin', 'symbol': 'Afl'},
        {'code': 'ANG', 'name': 'Netherlands Antillean Guilder', 'symbol': 'ƒ'},
        
        # Europe
        {'code': 'CHF', 'name': 'Swiss Franc', 'symbol': 'Fr'},
        {'code': 'NOK', 'name': 'Norwegian Krone', 'symbol': 'kr'},
        {'code': 'SEK', 'name': 'Swedish Krona', 'symbol': 'kr'},
        {'code': 'DKK', 'name': 'Danish Krone', 'symbol': 'kr'},
        {'code': 'ISK', 'name': 'Icelandic Króna', 'symbol': 'kr'},
        {'code': 'RUB', 'name': 'Russian Ruble', 'symbol': '₽'},
        {'code': 'TRY', 'name': 'Turkish Lira', 'symbol': '₺'},
        {'code': 'PLN', 'name': 'Polish Złoty', 'symbol': 'zł'},
        {'code': 'CZK', 'name': 'Czech Koruna', 'symbol': 'Kč'},
        {'code': 'HUF', 'name': 'Hungarian Forint', 'symbol': 'Ft'},
        {'code': 'RON', 'name': 'Romanian Leu', 'symbol': 'lei'},
        {'code': 'BGN', 'name': 'Bulgarian Lev', 'symbol': 'лв'},
        {'code': 'HRK', 'name': 'Croatian Kuna', 'symbol': 'kn'},
        {'code': 'RSD', 'name': 'Serbian Dinar', 'symbol': 'дин'},
        {'code': 'ALL', 'name': 'Albanian Lek', 'symbol': 'L'},
        {'code': 'MKD', 'name': 'Macedonian Denar', 'symbol': 'ден'},
        {'code': 'BAM', 'name': 'Bosnian Mark', 'symbol': 'KM'},
        {'code': 'MDL', 'name': 'Moldovan Leu', 'symbol': 'lei'},
        {'code': 'BYN', 'name': 'Belarusian Ruble', 'symbol': 'Br'},
        {'code': 'UAH', 'name': 'Ukrainian Hryvnia', 'symbol': '₴'},
        {'code': 'GEL', 'name': 'Georgian Lari', 'symbol': '₾'},
        {'code': 'AMD', 'name': 'Armenian Dram', 'symbol': '֏'},
        {'code': 'AZN', 'name': 'Azerbaijani Manat', 'symbol': '₼'},
        
        # Asia Pacific
        {'code': 'AUD', 'name': 'Australian Dollar', 'symbol': 'A$'},
        {'code': 'NZD', 'name': 'New Zealand Dollar', 'symbol': 'NZ$'},
        {'code': 'SGD', 'name': 'Singapore Dollar', 'symbol': 'S$'},
        {'code': 'HKD', 'name': 'Hong Kong Dollar', 'symbol': 'HK$'},
        {'code': 'KRW', 'name': 'South Korean Won', 'symbol': '₩'},
        {'code': 'INR', 'name': 'Indian Rupee', 'symbol': '₹'},
        {'code': 'IDR', 'name': 'Indonesian Rupiah', 'symbol': 'Rp'},
        {'code': 'MYR', 'name': 'Malaysian Ringgit', 'symbol': 'RM'},
        {'code': 'PHP', 'name': 'Philippine Peso', 'symbol': '₱'},
        {'code': 'THB', 'name': 'Thai Baht', 'symbol': '฿'},
        {'code': 'VND', 'name': 'Vietnamese Dong', 'symbol': '₫'},
        {'code': 'PKR', 'name': 'Pakistani Rupee', 'symbol': '₨'},
        {'code': 'BDT', 'name': 'Bangladeshi Taka', 'symbol': '৳'},
        {'code': 'LKR', 'name': 'Sri Lankan Rupee', 'symbol': 'Rs'},
        {'code': 'NPR', 'name': 'Nepalese Rupee', 'symbol': 'रू'},
        {'code': 'MMK', 'name': 'Myanmar Kyat', 'symbol': 'K'},
        {'code': 'KHR', 'name': 'Cambodian Riel', 'symbol': '៛'},
        {'code': 'LAK', 'name': 'Lao Kip', 'symbol': '₭'},
        {'code': 'MNT', 'name': 'Mongolian Tögrög', 'symbol': '₮'},
        {'code': 'TWD', 'name': 'New Taiwan Dollar', 'symbol': 'NT$'},
        {'code': 'MOP', 'name': 'Macanese Pataca', 'symbol': 'MOP$'},
        {'code': 'KZT', 'name': 'Kazakhstani Tenge', 'symbol': '₸'},
        {'code': 'UZS', 'name': 'Uzbekistani Som', 'symbol': 'soʻm'},
        {'code': 'TJS', 'name': 'Tajikistani Somoni', 'symbol': 'SM'},
        {'code': 'KGS', 'name': 'Kyrgyzstani Som', 'symbol': 'с'},
        {'code': 'ILS', 'name': 'Israeli Shekel', 'symbol': '₪'},
        {'code': 'JOD', 'name': 'Jordanian Dinar', 'symbol': 'د.ا'},
        {'code': 'IQD', 'name': 'Iraqi Dinar', 'symbol': 'ع.د'},
        {'code': 'IRR', 'name': 'Iranian Rial', 'symbol': '﷼'},
        {'code': 'SAR', 'name': 'Saudi Riyal', 'symbol': '﷼'},
        {'code': 'AED', 'name': 'UAE Dirham', 'symbol': 'د.إ'},
        {'code': 'QAR', 'name': 'Qatari Riyal', 'symbol': 'ر.ق'},
        {'code': 'KWD', 'name': 'Kuwaiti Dinar', 'symbol': 'د.ك'},
        {'code': 'BHD', 'name': 'Bahraini Dinar', 'symbol': 'د.ب'},
        {'code': 'OMR', 'name': 'Omani Rial', 'symbol': 'ر.ع'},
        {'code': 'YER', 'name': 'Yemeni Rial', 'symbol': '﷼'},
        {'code': 'LBP', 'name': 'Lebanese Pound', 'symbol': 'ل.ل'},
        {'code': 'SYP', 'name': 'Syrian Pound', 'symbol': '£S'},
        {'code': 'AFN', 'name': 'Afghan Afghani', 'symbol': '؋'},
        
        # Africa
        {'code': 'ZAR', 'name': 'South African Rand', 'symbol': 'R'},
        {'code': 'EGP', 'name': 'Egyptian Pound', 'symbol': '£E'},
        {'code': 'NGN', 'name': 'Nigerian Naira', 'symbol': '₦'},
        {'code': 'KES', 'name': 'Kenyan Shilling', 'symbol': 'KSh'},
        {'code': 'GHS', 'name': 'Ghanaian Cedi', 'symbol': '₵'},
        {'code': 'MAD', 'name': 'Moroccan Dirham', 'symbol': 'د.م.'},
        {'code': 'DZD', 'name': 'Algerian Dinar', 'symbol': 'د.ج'},
        {'code': 'TND', 'name': 'Tunisian Dinar', 'symbol': 'د.ت'},
        {'code': 'LYD', 'name': 'Libyan Dinar', 'symbol': 'ل.د'},
        {'code': 'SDG', 'name': 'Sudanese Pound', 'symbol': 'ج.س'},
        {'code': 'ETB', 'name': 'Ethiopian Birr', 'symbol': 'ብር'},
        {'code': 'UGX', 'name': 'Ugandan Shilling', 'symbol': 'USh'},
        {'code': 'TZS', 'name': 'Tanzanian Shilling', 'symbol': 'TSh'},
        {'code': 'RWF', 'name': 'Rwandan Franc', 'symbol': 'FRw'},
        {'code': 'BIF', 'name': 'Burundian Franc', 'symbol': 'FBu'},
        {'code': 'CDF', 'name': 'Congolese Franc', 'symbol': 'FC'},
        {'code': 'GNF', 'name': 'Guinean Franc', 'symbol': 'FG'},
        {'code': 'XOF', 'name': 'West African CFA Franc', 'symbol': 'CFA'},
        {'code': 'XAF', 'name': 'Central African CFA Franc', 'symbol': 'FCFA'},
        {'code': 'MUR', 'name': 'Mauritian Rupee', 'symbol': '₨'},
        {'code': 'MGA', 'name': 'Malagasy Ariary', 'symbol': 'Ar'},
        {'code': 'ZMW', 'name': 'Zambian Kwacha', 'symbol': 'ZK'},
        {'code': 'MWK', 'name': 'Malawian Kwacha', 'symbol': 'MK'},
        {'code': 'BWP', 'name': 'Botswana Pula', 'symbol': 'P'},
        {'code': 'NAD', 'name': 'Namibian Dollar', 'symbol': 'N$'},
        {'code': 'SZL', 'name': 'Eswatini Lilangeni', 'symbol': 'E'},
        {'code': 'LSL', 'name': 'Lesotho Loti', 'symbol': 'L'},
        {'code': 'ZWL', 'name': 'Zimbabwean Dollar', 'symbol': 'Z$'},
        {'code': 'MZN', 'name': 'Mozambican Metical', 'symbol': 'MT'},
        {'code': 'AOA', 'name': 'Angolan Kwanza', 'symbol': 'Kz'},
        {'code': 'MRO', 'name': 'Mauritanian Ouguiya', 'symbol': 'UM'},
        {'code': 'CVE', 'name': 'Cape Verdean Escudo', 'symbol': '$'},
        {'code': 'SCR', 'name': 'Seychellois Rupee', 'symbol': 'SR'},
        {'code': 'KMF', 'name': 'Comorian Franc', 'symbol': 'CF'},
        {'code': 'DJF', 'name': 'Djiboutian Franc', 'symbol': 'Fdj'},
        {'code': 'ERN', 'name': 'Eritrean Nakfa', 'symbol': 'Nfk'},
        {'code': 'SOS', 'name': 'Somali Shilling', 'symbol': 'Sh'},
        {'code': 'GMD', 'name': 'Gambian Dalasi', 'symbol': 'D'},
        {'code': 'SLL', 'name': 'Sierra Leonean Leone', 'symbol': 'Le'},
        {'code': 'LRD', 'name': 'Liberian Dollar', 'symbol': 'L$'},
        
        # Oceania
        {'code': 'PGK', 'name': 'Papua New Guinean Kina', 'symbol': 'K'},
        {'code': 'FJD', 'name': 'Fijian Dollar', 'symbol': 'FJ$'},
        {'code': 'SBD', 'name': 'Solomon Islands Dollar', 'symbol': 'SI$'},
        {'code': 'VUV', 'name': 'Vanuatu Vatu', 'symbol': 'Vt'},
        {'code': 'TOP', 'name': 'Tongan Paʻanga', 'symbol': 'T$'},
        {'code': 'WST', 'name': 'Samoan Tālā', 'symbol': 'WS$'},
        {'code': 'KID', 'name': 'Kiribati Dollar', 'symbol': '$'},
        {'code': 'TVD', 'name': 'Tuvaluan Dollar', 'symbol': '$'},
        {'code': 'XPF', 'name': 'CFP Franc', 'symbol': '₣'},
        
        # Precious Metals & Special
        {'code': 'XAU', 'name': 'Gold (troy ounce)', 'symbol': 'oz t'},
        {'code': 'XAG', 'name': 'Silver (troy ounce)', 'symbol': 'oz t'},
        {'code': 'XPT', 'name': 'Platinum (troy ounce)', 'symbol': 'oz t'},
        {'code': 'XPD', 'name': 'Palladium (troy ounce)', 'symbol': 'oz t'},
        {'code': 'XDR', 'name': 'Special Drawing Rights', 'symbol': 'SDR'},
    ]    
    context = {
        'page': page,
        'currencies': currencies,
    }
    return render(request, 'builder/currency_settings.html', context)



from django.views.decorators.http import require_http_methods

@login_required
def edit_shipping_policy(request, subdomain):
    """
    Edit shipping and returns policy for a store with AJAX auto-save support
    """
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create policy
    policy, created = ShippingPolicy.objects.get_or_create(page=page)
    
    # Handle AJAX auto-save
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            
            # Update policy fields
            policy.processing_time = data.get('processing_time', '1-3 business days')
            policy.shipping_methods = data.get('shipping_methods', '')
            policy.delivery_timeframe = data.get('delivery_timeframe', '5-10 business days')
            policy.free_shipping_threshold = data.get('free_shipping_threshold', 'Orders over $50')
            policy.return_window = data.get('return_window', '30 days')
            policy.return_conditions = data.get('return_conditions', '')
            policy.return_process = data.get('return_process', '')
            policy.refund_info = data.get('refund_info', '')
            policy.international_shipping = data.get('international_shipping', '')
            policy.support_contact = data.get('support_contact', '')
            policy.is_active = data.get('is_active') == 'on'
            policy.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Policy saved successfully',
                'updated_at': policy.updated_at.isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    # Handle regular form submission
    elif request.method == 'POST':
        try:
            # Update policy fields
            policy.processing_time = request.POST.get('processing_time', '1-3 business days')
            policy.shipping_methods = request.POST.get('shipping_methods', '')
            policy.delivery_timeframe = request.POST.get('delivery_timeframe', '5-10 business days')
            policy.free_shipping_threshold = request.POST.get('free_shipping_threshold', 'Orders over $50')
            policy.return_window = request.POST.get('return_window', '30 days')
            policy.return_conditions = request.POST.get('return_conditions', '')
            policy.return_process = request.POST.get('return_process', '')
            policy.refund_info = request.POST.get('refund_info', '')
            policy.international_shipping = request.POST.get('international_shipping', '')
            policy.support_contact = request.POST.get('support_contact', '')
            policy.is_active = request.POST.get('is_active') == 'on'
            policy.save()
            
            messages.success(request, 'Shipping policy updated successfully!')
            return redirect('edit_shipping_policy', subdomain=subdomain)
            
        except Exception as e:
            messages.error(request, f'Error saving policy: {str(e)}')
    
    elif request.method == 'DELETE':
        policy.delete()
        return JsonResponse({'success': True})
    
    context = {
        'page': page,
        'policy': policy,
    }
    return render(request, 'builder/shipping_policy_edit.html', context)


def public_shipping_policy(request, subdomain):
    """
    Public view for shipping policy page
    """
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
    try:
        policy = page.shipping_policy
        if not policy.is_active:
            policy = None
    except ShippingPolicy.DoesNotExist:
        policy = None
    
    context = {
        'page': page,
        'policy': policy,
    }
    return render(request, 'builder/public_templates/shipping_returns.html', context)

@login_required
def manage_social_media(request, subdomain):
    """
    Manage social media handles for a store - no validation
    """
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    social_media = page.social_media.all()
    
    # Handle AJAX requests
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            platform = request.POST.get('platform')
            raw_handle = request.POST.get('raw_handle', '').strip()
            display_name = request.POST.get('display_name', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            open_in_new_tab = request.POST.get('open_in_new_tab', 'on') == 'on'
            
            # Check if this is an update or create
            if request.POST.get('update'):
                social = get_object_or_404(SocialMedia, page=page, platform=platform)
            else:
                # Check if platform already exists
                if SocialMedia.objects.filter(page=page, platform=platform).exists():
                    return JsonResponse({
                        'success': False,
                        'error': f'{platform} is already connected'
                    }, status=400)
                
                social, created = SocialMedia.objects.get_or_create(
                    page=page,
                    platform=platform,
                    defaults={'display_order': page.social_media.count()}
                )
            
            # Update fields - no validation!
            social.raw_handle = raw_handle
            social.display_name = display_name
            social.is_active = is_active
            social.open_in_new_tab = open_in_new_tab
            social.save()
            
            return JsonResponse({
                'success': True,
                'message': f'{social.get_platform_display()} saved successfully',
                'url': social.get_url()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    # Handle DELETE requests
    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            platform = data.get('platform')
            social = get_object_or_404(SocialMedia, page=page, platform=platform)
            social.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'{social.get_platform_display()} removed successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    context = {
        'page': page,
        'social_media': social_media,
        'total_active': social_media.filter(is_active=True).count(),
    }
    return render(request, 'builder/social_media_edit.html', context)



@login_required
def edit_terms(request, subdomain):
    """
    Edit terms and conditions for a store
    """
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create terms
    terms, created = TermsAndConditions.objects.get_or_create(page=page)
    
    # Handle AJAX auto-save
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Update all fields
            terms.content = request.POST.get('content', '')
            terms.introduction = request.POST.get('introduction', '')
            terms.agreement_to_terms = request.POST.get('agreement_to_terms', '')
            terms.intellectual_property = request.POST.get('intellectual_property', '')
            terms.user_responsibilities = request.POST.get('user_responsibilities', '')
            terms.prohibited_activities = request.POST.get('prohibited_activities', '')
            terms.termination = request.POST.get('termination', '')
            terms.governing_law = request.POST.get('governing_law', '')
            terms.disputes = request.POST.get('disputes', '')
            terms.limitations = request.POST.get('limitations', '')
            terms.contact_info = request.POST.get('contact_info', '')
            terms.is_active = request.POST.get('is_active') == 'on'
            terms.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Terms saved successfully',
                'updated_at': terms.last_updated.isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    # Handle regular form submission
    elif request.method == 'POST':
        try:
            terms.content = request.POST.get('content', '')
            terms.introduction = request.POST.get('introduction', '')
            terms.agreement_to_terms = request.POST.get('agreement_to_terms', '')
            terms.intellectual_property = request.POST.get('intellectual_property', '')
            terms.user_responsibilities = request.POST.get('user_responsibilities', '')
            terms.prohibited_activities = request.POST.get('prohibited_activities', '')
            terms.termination = request.POST.get('termination', '')
            terms.governing_law = request.POST.get('governing_law', '')
            terms.disputes = request.POST.get('disputes', '')
            terms.limitations = request.POST.get('limitations', '')
            terms.contact_info = request.POST.get('contact_info', '')
            terms.is_active = request.POST.get('is_active') == 'on'
            terms.save()
            
            messages.success(request, 'Terms and conditions updated successfully!')
            return redirect('edit_terms', subdomain=subdomain)
            
        except Exception as e:
            messages.error(request, f'Error saving terms: {str(e)}')
    
    # Handle DELETE
    elif request.method == 'DELETE':
        terms.delete()
        return JsonResponse({'success': True})
    
    context = {
        'page': page,
        'terms': terms,
    }
    return render(request, 'builder/terms_edit.html', context)


@login_required
def edit_privacy(request, subdomain):
    """
    Edit privacy policy for a store
    """
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    # Get or create privacy policy
    privacy, created = PrivacyPolicy.objects.get_or_create(page=page)
    
    # Handle AJAX auto-save
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Update all fields
            privacy.content = request.POST.get('content', '')
            privacy.introduction = request.POST.get('introduction', '')
            privacy.information_collected = request.POST.get('information_collected', '')
            privacy.how_we_use = request.POST.get('how_we_use', '')
            privacy.cookies = request.POST.get('cookies', '')
            privacy.third_party = request.POST.get('third_party', '')
            privacy.data_security = request.POST.get('data_security', '')
            privacy.your_rights = request.POST.get('your_rights', '')
            privacy.children_privacy = request.POST.get('children_privacy', '')
            privacy.international_transfers = request.POST.get('international_transfers', '')
            privacy.policy_changes = request.POST.get('policy_changes', '')
            privacy.contact_info = request.POST.get('contact_info', '')
            privacy.gdpr_compliant = request.POST.get('gdpr_compliant') == 'on'
            privacy.ccpa_compliant = request.POST.get('ccpa_compliant') == 'on'
            privacy.is_active = request.POST.get('is_active') == 'on'
            privacy.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Privacy policy saved successfully',
                'updated_at': privacy.last_updated.isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    # Handle regular form submission
    elif request.method == 'POST':
        try:
            privacy.content = request.POST.get('content', '')
            privacy.introduction = request.POST.get('introduction', '')
            privacy.information_collected = request.POST.get('information_collected', '')
            privacy.how_we_use = request.POST.get('how_we_use', '')
            privacy.cookies = request.POST.get('cookies', '')
            privacy.third_party = request.POST.get('third_party', '')
            privacy.data_security = request.POST.get('data_security', '')
            privacy.your_rights = request.POST.get('your_rights', '')
            privacy.children_privacy = request.POST.get('children_privacy', '')
            privacy.international_transfers = request.POST.get('international_transfers', '')
            privacy.policy_changes = request.POST.get('policy_changes', '')
            privacy.contact_info = request.POST.get('contact_info', '')
            privacy.gdpr_compliant = request.POST.get('gdpr_compliant') == 'on'
            privacy.ccpa_compliant = request.POST.get('ccpa_compliant') == 'on'
            privacy.is_active = request.POST.get('is_active') == 'on'
            privacy.save()
            
            messages.success(request, 'Privacy policy updated successfully!')
            return redirect('edit_privacy', subdomain=subdomain)
            
        except Exception as e:
            messages.error(request, f'Error saving privacy policy: {str(e)}')
    
    # Handle DELETE
    elif request.method == 'DELETE':
        privacy.delete()
        return JsonResponse({'success': True})
    
    context = {
        'page': page,
        'privacy': privacy,
    }
    return render(request, 'builder/privacy_edit.html', context)


def public_terms(request, subdomain):
    """
    Public view for terms and conditions
    """
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
    try:
        terms = page.terms
        if not terms.is_active:
            terms = None
    except TermsAndConditions.DoesNotExist:
        terms = None
    
    context = {
        'page': page,
        'terms': terms,
    }
    return render(request, 'builder/public_templates/terms.html', context)


def public_privacy(request, subdomain):
    """
    Public view for privacy policy
    """
    page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
    
    try:
        privacy = page.privacy
        if not privacy.is_active:
            privacy = None
    except PrivacyPolicy.DoesNotExist:
        privacy = None
    
    context = {
        'page': page,
        'privacy': privacy,
    }
    return render(request, 'builder/public_templates/privacy.html', context)


# Add this to your views.py in the builder app

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .models import PublishedPage

@csrf_exempt
@require_http_methods(["GET", "POST"])
def check_subdomain_availability(request):
    """
    API endpoint to check if a subdomain is available
    GET: Check availability of a single subdomain
    POST: Bulk check multiple subdomains
    """
    try:
        if request.method == "GET":
            subdomain = request.GET.get('subdomain', '').strip().lower()
            
            if not subdomain:
                return JsonResponse({
                    'success': False,
                    'error': 'Subdomain is required'
                }, status=400)
            
            # Validate subdomain format
            import re
            if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', subdomain):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid subdomain format',
                    'is_available': False,
                    'suggestions': generate_subdomain_suggestions(subdomain)
                })
            
            if len(subdomain) < 2:
                return JsonResponse({
                    'success': False,
                    'error': 'Subdomain must be at least 2 characters',
                    'is_available': False,
                    'suggestions': generate_subdomain_suggestions(subdomain)
                })
            
            # Check if subdomain exists (excluding current user's pages if editing)
            existing = PublishedPage.objects.filter(subdomain=subdomain)
            
            # If editing, exclude the current page
            page_id = request.GET.get('page_id')
            if page_id:
                existing = existing.exclude(id=page_id)
            
            is_available = not existing.exists()
            
            # Generate suggestions if not available
            suggestions = []
            if not is_available:
                suggestions = generate_subdomain_suggestions(subdomain)
            
            return JsonResponse({
                'success': True,
                'subdomain': subdomain,
                'is_available': is_available,
                'suggestions': suggestions,
                'message': 'Subdomain is available!' if is_available else 'Subdomain is already taken'
            })
            
        elif request.method == "POST":
            # Bulk check multiple subdomains
            data = json.loads(request.body)
            subdomains = data.get('subdomains', [])
            
            if not subdomains:
                return JsonResponse({
                    'success': False,
                    'error': 'No subdomains provided'
                }, status=400)
            
            results = {}
            for subdomain in subdomains:
                # Basic validation
                import re
                is_valid = bool(re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', subdomain)) and len(subdomain) >= 2
                
                if not is_valid:
                    results[subdomain] = {
                        'is_available': False,
                        'is_valid': False,
                        'error': 'Invalid format'
                    }
                else:
                    existing = PublishedPage.objects.filter(subdomain=subdomain)
                    page_id = data.get('page_id')
                    if page_id:
                        existing = existing.exclude(id=page_id)
                    
                    results[subdomain] = {
                        'is_available': not existing.exists(),
                        'is_valid': True
                    }
            
            return JsonResponse({
                'success': True,
                'results': results
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def generate_subdomain_suggestions(subdomain):
    """Generate alternative subdomain suggestions"""
    suggestions = []
    base = subdomain.strip('-').lower()
    
    # Remove invalid characters for base
    import re
    base = re.sub(r'[^a-z0-9-]', '', base)
    base = base.strip('-')
    
    if not base:
        return []
    
    suggestions = [
        f"{base}-shop",
        f"{base}-store",
        f"{base}1",
        f"{base}-online",
        f"shop-{base}",
        f"{base}-app",
        f"{base}-site",
        f"my{base}"
    ]
    
    # Filter out any invalid suggestions and limit to 5
    valid_suggestions = []
    for s in suggestions:
        if re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', s) and len(s) >= 2:
            valid_suggestions.append(s)
        if len(valid_suggestions) >= 5:
            break
    
    return valid_suggestions




@login_required
def get_storage_info(request):
    """Simple API to get current storage usage"""
    used = get_user_storage_usage(request.user)
    limit = get_storage_limit(request.user)
    
    return JsonResponse({
        'used_bytes': used,
        'used_formatted': format_bytes(used),
        'limit_bytes': limit,
        'limit_formatted': format_bytes(limit),
        'percentage': (used / limit * 100) if limit else 0
    })

# builder/views.py - Add debugging to the API endpoint

# builder/views.py

@login_required
def api_storage_info(request):
    """API endpoint to get storage and limits info"""
    from payments.decorators import get_user_limits_status
    import json
    import traceback
    
    try:
        limits = get_user_limits_status(request.user)
        
        # Debug print
        print(f"API storage info for {request.user.email}: {limits}")
        
        return JsonResponse({
            'success': True,
            'data': limits
        })
        
    except Exception as e:
        print(f"API storage info ERROR: {str(e)}")
        traceback.print_exc()
        
        # Return a proper fallback response with full structure
        return JsonResponse({
            'success': False,
            'error': str(e),
            'data': {
                'tier': 'free',
                'plan_name': 'Free',
                'is_paid': False,
                'websites': {'used': 0, 'limit': 1},
                'products': {'used': 0, 'limit': 10},
                'forms_this_month': {'used': 0, 'limit': 10},
                'storage': {'used_mb': 0, 'limit_mb': 100, 'percentage': 0},
            }
        })


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from payments.decorators import get_user_plan, has_feature


def support_page(request):
    """Support page with dynamic options based on user's plan"""
    
    # Default values for anonymous users
    current_plan = 'free'
    plan_name = 'Free'
    email_available = True
    email_response_time = '48 hours'
    chat_available = False
    chat_response_time = None
    chat_hours = None
    phone_available = False
    priority_available = False
    priority_response_time = None
    
    if request.user.is_authenticated:
        plan = get_user_plan(request.user)
        current_plan = plan.tier if plan else 'free'
        plan_name = plan.name if plan else 'Free'
        
        # Set support options based on plan tier
        if current_plan == 'free':
            email_available = True
            email_response_time = '48 hours'
            chat_available = False
            phone_available = False
            priority_available = False
            
        elif current_plan == 'pro':
            email_available = True
            email_response_time = '24 hours'
            chat_available = False
            phone_available = False
            priority_available = True
            priority_response_time = '24 hours'
            
        elif current_plan == 'business':
            email_available = True
            email_response_time = '24 hours'
            chat_available = True
            chat_response_time = '4 hours'
            chat_hours = '9am - 9pm EST'
            phone_available = False
            priority_available = True
            priority_response_time = '4 hours'
            
        elif current_plan == 'agency':
            email_available = True
            email_response_time = '24 hours'
            chat_available = True
            chat_response_time = 'Immediate'
            chat_hours = '24/7'
            phone_available = True
            priority_available = True
            priority_response_time = 'Immediate'
    
    context = {
        'current_plan': current_plan,
        'plan_name': plan_name,
        'email_available': email_available,
        'email_response_time': email_response_time,
        'chat_available': chat_available,
        'chat_response_time': chat_response_time,
        'chat_hours': chat_hours,
        'phone_available': phone_available,
        'priority_available': priority_available,
        'priority_response_time': priority_response_time,
    }
    
    return render(request, 'builder/support.html', context)



# builder/views.py - Add this view

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

def contact_page(request):
    """Simple contact page"""
    return render(request, 'builder/contact.html')


@require_http_methods(["POST"])
def submit_contact(request):
    """Handle contact form submission"""
    try:
        # Log the request
        logger.info(f"Contact form submission from: {request.META.get('REMOTE_ADDR')}")
        
        # Parse JSON data
        data = json.loads(request.body)
        logger.info(f"Contact form data received: {data.get('email')} - {data.get('subject')}")
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()
        
        # Basic validation
        if not all([name, email, subject, message]):
            logger.warning("Contact form missing required fields")
            return JsonResponse({
                'success': False, 
                'error': 'All fields are required'
            })
        
        # Email validation
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return JsonResponse({
                'success': False,
                'error': 'Please enter a valid email address'
            })
        
        # Save to database (optional)
        try:
            from builder.models import ContactSubmission
            ContactSubmission.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message,
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            logger.info(f"Contact form saved to database")
        except Exception as e:
            logger.error(f"Failed to save contact form: {e}")
            # Continue even if database save fails
        
        # Send email notification (optional)
        try:
            send_contact_notification(name, email, subject, message)
        except Exception as e:
            logger.error(f"Failed to send contact email: {e}")
            # Continue even if email fails
        
        logger.info(f"Contact form processed successfully")
        
        return JsonResponse({'success': True})
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in contact form: {e}")
        return JsonResponse({
            'success': False, 
            'error': 'Invalid request format'
        })
    except Exception as e:
        logger.error(f"Contact form error: {e}", exc_info=True)
        return JsonResponse({
            'success': False, 
            'error': 'An unexpected error occurred. Please try again.'
        })


def send_contact_notification(name, email, subject, message):
    """Send email notification for contact form"""
    # You can implement email sending here
    # For now, just print to console
    print(f"""
    ========================================
    New Contact Form Submission
    ========================================
    Name: {name}
    Email: {email}
    Subject: {subject}
    Message: {message[:200]}...
    ========================================
    """)


def about_page(request):
    """About page"""
    return render(request, 'builder/about.html')

def privacy_policy(request):
    """Privacy policy page"""
    return render(request, 'builder/legal/privacy.html')


def terms_of_service(request):
    """Terms of service page"""
    return render(request, 'builder/legal/terms.html')

def demo_page(request):
    """Demo video page"""
    return render(request, 'builder/demo.html', {
        'year': datetime.now().year,
    })


# Add these imports at the top if not present
import hashlib
from itertools import product as cartesian_product
from decimal import Decimal

# Add after your existing views

@login_required
def manage_variants(request, subdomain, product_id):
    """Main variant management interface"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    product = get_object_or_404(Product, id=product_id, page=page)
    
    options = ProductOption.objects.filter(page=page, is_active=True)
    variants = product.variants.all()
    
    # Generate variant matrix (all possible combinations)
    variant_matrix = {'rows': [], 'headers': []}
    
    if options.exists():
        option_values = {}
        for option in options:
            values = list(option.values.filter(is_active=True).values_list('value', flat=True))
            if values:
                option_values[option.name] = values
                variant_matrix['headers'].append({'name': option.name, 'values': values})
        
        if option_values:
            # Generate all combinations
            combinations = list(cartesian_product(*option_values.values()))
            option_names = list(option_values.keys())
            
            for combo in combinations:
                combo_dict = dict(zip(option_names, combo))
                existing_variant = product.variants.filter(options=combo_dict).first()
                
                row = {
                    'options': combo_dict,
                    'variant': existing_variant,
                    'exists': bool(existing_variant),
                    'combo_key': hashlib.md5(str(combo_dict).encode()).hexdigest()[:10]
                }
                
                if existing_variant:
                    row.update({
                        'price': existing_variant.price,
                        'compare_at_price': existing_variant.compare_at_price,
                        'quantity': existing_variant.quantity,
                        'sku': existing_variant.sku,
                    })
                variant_matrix['rows'].append(row)
    
    context = {
        'page': page,
        'product': product,
        'options': options,
        'product_options': options,
        'variants': variants,
        'variant_matrix': variant_matrix,
        'has_variants': variants.exists(),
    }
    
    return render(request, 'builder/product_variants.html', context)


@login_required
@require_http_methods(["POST"])
def create_product_option(request, subdomain):
    """Create a new product option"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        data = json.loads(request.body)
        
        option = ProductOption.objects.create(
            page=page,
            name=data.get('name'),
            option_type=data.get('option_type', 'text'),
            display_order=ProductOption.objects.filter(page=page).count()
        )
        
        # Create option values
        values = data.get('values', [])
        for idx, val in enumerate(values):
            ProductOptionValue.objects.create(
                option=option,
                value=val.get('value'),
                color_code=val.get('color_code', ''),
                display_order=idx
            )
        
        return JsonResponse({
            'success': True,
            'option': {
                'id': option.id,
                'name': option.name,
                'option_type': option.option_type,
                'values': list(option.values.values('id', 'value', 'color_code'))
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def bulk_update_variants(request, subdomain, product_id):
    """Bulk update variants from the matrix grid"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        product = get_object_or_404(Product, id=product_id, page=page)
        data = json.loads(request.body)
        
        variants_data = data.get('variants', [])
        
        updated_count = 0
        created_count = 0
        
        with transaction.atomic():
            for variant_data in variants_data:
                options_dict = variant_data.get('options', {})
                
                # Find existing variant or create new
                variant = product.variants.filter(options=options_dict).first()
                
                if variant:
                    # Update existing
                    if variant_data.get('price'):
                        variant.price = Decimal(str(variant_data['price']))
                    if variant_data.get('compare_at_price'):
                        variant.compare_at_price = Decimal(str(variant_data['compare_at_price']))
                    if variant_data.get('quantity') is not None:
                        variant.quantity = int(variant_data['quantity'])
                    if variant_data.get('sku'):
                        variant.sku = variant_data['sku']
                    variant.save()
                    updated_count += 1
                else:
                    # Create new
                    variant = ProductVariant.objects.create(
                        product=product,
                        options=options_dict,
                        price=Decimal(str(variant_data['price'])) if variant_data.get('price') else None,
                        compare_at_price=Decimal(str(variant_data['compare_at_price'])) if variant_data.get('compare_at_price') else None,
                        quantity=int(variant_data.get('quantity', 0)),
                        sku=variant_data.get('sku', ''),
                    )
                    created_count += 1
            
            # Mark product as having variants
            if variants_data:
                product.has_variants = True
                product.save(update_fields=['has_variants'])
        
        return JsonResponse({
            'success': True,
            'message': f'Updated {updated_count}, created {created_count} variants',
            'updated': updated_count,
            'created': created_count
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_option(request, subdomain, option_id):
    """Delete a product option"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        option = get_object_or_404(ProductOption, id=option_id, page=page)
        option.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def quick_edit_variant(request, subdomain, variant_id):
    """Quick edit a single variant"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        variant = get_object_or_404(ProductVariant, id=variant_id, product__page=page)
        data = json.loads(request.body)
        
        if 'price' in data:
            variant.price = Decimal(str(data['price'])) if data['price'] else None
        if 'compare_at_price' in data:
            variant.compare_at_price = Decimal(str(data['compare_at_price'])) if data['compare_at_price'] else None
        if 'quantity' in data:
            variant.quantity = int(data['quantity'])
        if 'sku' in data:
            variant.sku = data['sku']
        if 'track_quantity' in data:
            variant.track_quantity = data['track_quantity']
        
        variant.save()
        return JsonResponse({'success': True, 'message': 'Variant updated'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_variant(request, subdomain, variant_id):
    """Delete a variant"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        variant = get_object_or_404(ProductVariant, id=variant_id, product__page=page)
        variant.delete()
        
        # Update product has_variants flag
        has_variants = ProductVariant.objects.filter(product=variant.product).exists()
        variant.product.has_variants = has_variants
        variant.product.save(update_fields=['has_variants'])
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def duplicate_variant(request, subdomain, variant_id):
    """Duplicate a variant"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        original = get_object_or_404(ProductVariant, id=variant_id, product__page=page)
        
        duplicate = ProductVariant.objects.create(
            product=original.product,
            options=original.options,
            price=original.price,
            compare_at_price=original.compare_at_price,
            quantity=original.quantity,
            track_quantity=original.track_quantity,
            weight=original.weight,
            is_active=original.is_active,
        )
        
        return JsonResponse({
            'success': True,
            'variant_id': duplicate.id,
            'message': 'Variant duplicated'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
def get_product_variant(request, subdomain, product_id):
    """API endpoint to get variant by selected options"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, is_published=True)
        product = get_object_or_404(Product, id=product_id, page=page)
        data = json.loads(request.body)
        selected_options = data.get('options', {})
        
        # Find matching variant
        variant = product.variants.filter(options=selected_options).first()
        
        if variant:
            return JsonResponse({
                'success': True,
                'variant': {
                    'id': variant.id,
                    'price': float(variant.price) if variant.price else float(product.price),
                    'compare_at_price': float(variant.compare_at_price) if variant.compare_at_price else None,
                    'quantity': variant.quantity,
                    'sku': variant.sku,
                    'in_stock': variant.quantity > 0 if variant.track_quantity else True,
                    'image_url': variant.image.url if variant.image else None,
                }
            })
        else:
            return JsonResponse({'success': True, 'variant': None})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})




# builder/views.py - Add these views

@login_required
def manage_variants_simple(request, subdomain, product_id):
    """Simplified variant management"""
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    product = get_object_or_404(Product, id=product_id, page=page)
    
    context = {
        'page': page,
        'product': product,
        'variants': product.variants.all(),
    }
    
    return render(request, 'builder/product_variants.html', context)


@login_required
@require_http_methods(["POST"])
def add_variant_simple(request, subdomain, product_id):
    """Add a variant via simple form"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        product = get_object_or_404(Product, id=product_id, page=page)
        
        option1_name = request.POST.get('option1_name', '').strip()
        option1_value = request.POST.get('option1_value', '').strip()
        option2_name = request.POST.get('option2_name', '').strip()
        option2_value = request.POST.get('option2_value', '').strip()
        price = request.POST.get('price')
        compare_price = request.POST.get('compare_price')
        quantity = request.POST.get('quantity', 0)
        sku = request.POST.get('sku', '').strip()
        
        options = {}
        if option1_name and option1_value:
            options[option1_name] = option1_value
        if option2_name and option2_value:
            options[option2_name] = option2_value
        
        if not options:
            return JsonResponse({'success': False, 'error': 'Please add at least one option'})
        
        # Check for duplicates
        if product.variants.filter(options=options).exists():
            return JsonResponse({
                'success': False, 
                'error': 'This variant already exists!'
            })
        
        variant = ProductVariant.objects.create(
            product=product,
            options=options,
            price=Decimal(price) if price else None,
            compare_at_price=Decimal(compare_price) if compare_price else None,
            quantity=int(quantity) if quantity else 0,
            sku=sku if sku else '',
        )
        
        if 'image' in request.FILES:
            variant.image = request.FILES['image']
            variant.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Variant added!',
            'variant': {
                'id': variant.id,
                'options': variant.options,
                'price': str(variant.price) if variant.price else '',
                'quantity': variant.quantity,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def upload_variant_image(request, subdomain, variant_id):
    """Upload image for a variant"""
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        variant = get_object_or_404(ProductVariant, id=variant_id, product__page=page)
        
        if 'image' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No image provided'})
        
        variant.image = request.FILES['image']
        variant.save()
        
        return JsonResponse({
            'success': True,
            'image_url': variant.image.url,
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def manage_product_tiers(request, subdomain, product_id):
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    product = get_object_or_404(Product, id=product_id, page=page)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'save':
            tier_id = request.POST.get('tier_id')
            quantity = int(request.POST.get('quantity', 1))
            price_per_unit = Decimal(request.POST.get('price_per_unit', 0))
            badge_text = request.POST.get('badge_text', '')
            is_default = request.POST.get('is_default') == 'on'
            is_active = request.POST.get('is_active') == 'on'
            
            if tier_id:
                tier = get_object_or_404(ProductTier, id=tier_id, product=product)
                tier.quantity = quantity
                tier.price_per_unit = price_per_unit
                tier.badge_text = badge_text
                tier.is_default = is_default
                tier.is_active = is_active
                tier.save()
                messages.success(request, 'Tier updated!')
            else:
                ProductTier.objects.create(
                    product=product,
                    page=page,
                    quantity=quantity,
                    price_per_unit=price_per_unit,
                    badge_text=badge_text,
                    is_default=is_default,
                    is_active=is_active,
                    display_order=quantity
                )
                messages.success(request, 'Tier added!')
            
            # Only one default
            if is_default:
                ProductTier.objects.filter(product=product, is_active=True).exclude(
                    id=tier_id if tier_id else None
                ).update(is_default=False)
        
        elif action == 'delete':
            tier_id = request.POST.get('tier_id')
            tier = get_object_or_404(ProductTier, id=tier_id, product=product)
            tier.delete()
            messages.success(request, 'Tier deleted!')
        
        return redirect('manage_product_tiers', subdomain=subdomain, product_id=product_id)
    
    tiers = product.tiers.filter(is_active=True).order_by('display_order', 'quantity')
    
    return render(request, 'builder/manage_product_tiers.html', {
        'page': page,
        'product': product,
        'tiers': tiers
    })

def onboarding_wizard(request):
    """Main onboarding wizard view - handles authentication state"""
    
    # If user is already logged in, we still show the wizard but skip account step
    context = {
        'steps': [
            {'label': 'Account'},
            {'label': 'Store'},
            {'label': 'Brand'},
            {'label': 'Template'},
            {'label': 'Launch'},
        ]
    }
    return render(request, 'builder/onboarding/wizard.html', context)


@csrf_exempt
def get_templates_api(request):
    templates = Template.objects.filter(is_active=True)
    
    data = []
    for template in templates:
        data.append({
            'id': template.id,
            'name': template.name,
            'title': template.title,
            'description': template.description,
            'preview_image': template.preview_image.url if template.preview_image else None,
            'is_responsive': template.is_responsive,
        })
    
    return JsonResponse({
        'success': True,
        'templates': data
    })

@csrf_exempt
@check_website_limit
def launch_editor(request):
    """
    Create store from onboarding data and redirect to editor.
    ✅ BRAND NAME AND SUBDOMAIN ARE SAVED SEPARATELY
    ✅ BRAND NAME IS NEVER MODIFIED
    """
    print("\n" + "="*60)
    print("🚀 [launch_editor] ===== REQUEST RECEIVED =====")
    print("="*60)
    
    if request.method != 'POST':
        print("❌ [launch_editor] Invalid method:", request.method)
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    try:
        # Log raw request body
        print("📥 [launch_editor] Raw request body:")
        print(f"   {request.body[:500]}...")  # First 500 chars
        
        data = json.loads(request.body)
        print("\n📥 [launch_editor] Parsed JSON data:")
        print(f"   brand_name: '{data.get('brand_name')}'")
        print(f"   subdomain: '{data.get('subdomain')}'")
        print(f"   template_name: '{data.get('template_name')}'")
        print(f"   palette_id: '{data.get('palette_id')}'")
        print(f"   country: '{data.get('country')}'")
        print(f"   currency: '{data.get('currency')}'")
        print(f"   contact_number: '{data.get('contact_number')}'")
        print(f"   heading_font: '{data.get('heading_font')}'")
        print(f"   body_font: '{data.get('body_font')}'")
        
        with transaction.atomic():
            print("\n🔐 [launch_editor] Starting database transaction...")
            
            # 1. Handle user
            user = None
            if request.user.is_authenticated:
                user = request.user
                print(f"👤 [launch_editor] User already authenticated: {user.username} (ID: {user.id})")
            else:
                print("👤 [launch_editor] Creating new user...")
                user_data = data.get('user_data', {})
                if not user_data.get('email') or not user_data.get('password'):
                    print("❌ [launch_editor] Missing email or password for new user")
                    return JsonResponse({
                        'success': False,
                        'error': 'Email and password are required'
                    }, status=400)
                
                email = user_data.get('email')
                username = email.split('@')[0] if email else 'user'
                
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                print(f"   Creating user: {username} ({email})")
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=user_data.get('password')
                )
                
                full_name = user_data.get('full_name', '')
                if full_name:
                    name_parts = full_name.split()
                    user.first_name = name_parts[0] if name_parts else ''
                    user.last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    user.save()
                    print(f"   User full name: {full_name}")
                
                UserProfile.objects.create(
                    user=user,
                    contact_number=data.get('contact_number', ''),
                    country=data.get('country', ''),
                )
                
                login(request, user)
                print(f"✅ [launch_editor] User created and logged in: {user.username}")
            

            
            # 2. Get or create template
            template_name = data.get('template_name', 'ecommerce_4')
            print(f"\n📄 [launch_editor] Getting/Creating template: {template_name}")
            template, created = Template.objects.get_or_create(
                name=template_name,
                defaults={
                    'title': data.get('brand_name', 'My Store'),
                    'is_active': True,
                    'template_type': 'multi',
                    'available_pages': ['home', 'products', 'about', 'contact'],
                }
            )
            print(f"   Template {'created' if created else 'found'}: {template.name} (ID: {template.id})")
            
            # 3. ✅ CRITICAL: Get brand_name and subdomain SEPARATELY
            brand_name = data.get('brand_name', 'My Store').strip()
            subdomain = data.get('subdomain', '').strip().lower()
            
            print(f"\n🔑 [launch_editor] === CRITICAL VALUES ===")
            print(f"   brand_name from request: '{brand_name}'")
            print(f"   subdomain from request: '{subdomain}'")
            
            # ✅ Ensure subdomain is unique
            original_subdomain = subdomain
            counter = 1
            while PublishedPage.objects.filter(subdomain=subdomain).exists():
                subdomain = f"{original_subdomain}{counter}"
                counter += 1
            
            print(f"   After uniqueness check - subdomain: '{subdomain}'")
            
            # ✅ If subdomain is empty, generate from brand name
            if not subdomain:
                subdomain = generate_subdomain_from_brand(brand_name)
                print(f"   Subdomain was empty, generated from brand: '{subdomain}'")
                # Ensure uniqueness
                original_subdomain = subdomain
                counter = 1
                while PublishedPage.objects.filter(subdomain=subdomain).exists():
                    subdomain = f"{original_subdomain}{counter}"
                    counter += 1
                print(f"   After uniqueness check - generated subdomain: '{subdomain}'")
            
            print(f"\n✅ [launch_editor] FINAL VALUES BEFORE SAVING:")
            print(f"   brand_name: '{brand_name}' (type: {type(brand_name)})")
            print(f"   subdomain: '{subdomain}' (type: {type(subdomain)})")
            
            # 4. ✅ Create published page with SEPARATE brand_name and subdomain
            print(f"\n📝 [launch_editor] Creating PublishedPage...")
            currency = data.get('currency', 'USD')
            currency_symbols = {
                # Major World Currencies
                'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CNY': '¥',
                # Americas
                'CAD': 'C$', 'MXN': 'MX$', 'BRL': 'R$', 'ARS': '$', 'CLP': 'CLP$',
                'COP': 'COL$', 'PEN': 'S/', 'UYU': '$U', 'PYG': '₲', 'BOB': 'Bs',
                'VES': 'Bs.S', 'CRC': '₡', 'DOP': 'RD$', 'GTQ': 'Q', 'HNL': 'L',
                'NIO': 'C$', 'PAB': 'B/.', 'BSD': 'B$', 'BBD': 'Bds$', 'BZD': 'BZ$',
                'BMD': 'BD$', 'KYD': 'CI$', 'TTD': 'TT$', 'JMD': 'J$', 'HTG': 'G',
                'CUP': '₱', 'AWG': 'Afl', 'ANG': 'ƒ',
                # Europe
                'CHF': 'Fr', 'NOK': 'kr', 'SEK': 'kr', 'DKK': 'kr', 'ISK': 'kr',
                'RUB': '₽', 'TRY': '₺', 'PLN': 'zł', 'CZK': 'Kč', 'HUF': 'Ft',
                'RON': 'lei', 'BGN': 'лв', 'HRK': 'kn', 'RSD': 'дин', 'ALL': 'L',
                'MKD': 'ден', 'BAM': 'KM', 'MDL': 'lei', 'BYN': 'Br', 'UAH': '₴',
                'GEL': '₾', 'AMD': '֏', 'AZN': '₼',
                # Asia Pacific
                'AUD': 'A$', 'NZD': 'NZ$', 'SGD': 'S$', 'HKD': 'HK$', 'KRW': '₩',
                'INR': '₹', 'IDR': 'Rp', 'MYR': 'RM', 'PHP': '₱', 'THB': '฿',
                'VND': '₫', 'PKR': '₨', 'BDT': '৳', 'LKR': 'Rs', 'NPR': 'रू',
                'MMK': 'K', 'KHR': '៛', 'LAK': '₭', 'MNT': '₮', 'TWD': 'NT$',
                'MOP': 'MOP$', 'KZT': '₸', 'UZS': 'soʻm', 'TJS': 'SM', 'KGS': 'с',
                'ILS': '₪', 'JOD': 'د.ا', 'IQD': 'ع.د', 'IRR': '﷼', 'SAR': '﷼',
                'AED': 'د.إ', 'QAR': 'ر.ق', 'KWD': 'د.ك', 'BHD': 'د.ب', 'OMR': 'ر.ع',
                'YER': '﷼', 'LBP': 'ل.ل', 'SYP': '£S', 'AFN': '؋',
                # Africa
                'ZAR': 'R', 'EGP': '£E', 'NGN': '₦', 'KES': 'KSh', 'GHS': '₵',
                'MAD': 'د.م.', 'DZD': 'د.ج', 'TND': 'د.ت', 'LYD': 'ل.د', 'SDG': 'ج.س',
                'ETB': 'ብር', 'UGX': 'USh', 'TZS': 'TSh', 'RWF': 'FRw', 'BIF': 'FBu',
                'CDF': 'FC', 'GNF': 'FG', 'XOF': 'CFA', 'XAF': 'FCFA', 'MUR': '₨',
                'MGA': 'Ar', 'ZMW': 'ZK', 'MWK': 'MK', 'BWP': 'P', 'NAD': 'N$',
                'SZL': 'E', 'LSL': 'L', 'ZWL': 'Z$', 'MZN': 'MT', 'AOA': 'Kz',
                'MRO': 'UM', 'CVE': '$', 'SCR': 'SR', 'KMF': 'CF', 'DJF': 'Fdj',
                'ERN': 'Nfk', 'SOS': 'Sh', 'GMD': 'D', 'SLL': 'Le', 'LRD': 'L$',
                # Oceania
                'PGK': 'K', 'FJD': 'FJ$', 'SBD': 'SI$', 'VUV': 'Vt', 'TOP': 'T$',
                'WST': 'WS$', 'XPF': '₣',
            }
            
            currency_symbol = currency_symbols.get(currency, '$')
            page = PublishedPage.objects.create(
                user=user,
                template=template,
                template_name=template_name,
                brand_name=brand_name,      # ✅ User's original brand name - NEVER CHANGED
                subdomain=subdomain,         # ✅ Generated subdomain - CAN CHANGE
                is_published=False,
                currency_code=currency,
                currency_symbol=currency_symbol,
                currency_position='before',  # Default
                thousand_separator=',',
                decimal_separator='.',
                page_customizations={},
            )
            
            print(f"\n✅ [launch_editor] Page created successfully!")
            print(f"   Page ID: {page.id}")
            print(f"   brand_name in DB: '{page.brand_name}'")
            print(f"   subdomain in DB: '{page.subdomain}'")
            print(f"   template: {page.template_name}")
            print(f"   user: {page.user.username}")

            # ===== ✅ FIXED: SAVE CJ API KEY IF PROVIDED =====
            store_type = data.get('store_type')
            # ✅ FIX: Handle None value safely
            cj_api_key = data.get('cj_api_key')
            
            # Only proceed if store_type is CJ-related AND we have a non-empty key
            if store_type in ['cj', 'both'] and cj_api_key and isinstance(cj_api_key, str):
                cj_api_key = cj_api_key.strip()
                if cj_api_key:
                    print(f"🔑 [launch_editor] Saving CJ API key for store type: {store_type}")
                    try:
                        # Check if CJ settings already exist
                        cj_settings, created = CJSettings.objects.get_or_create(
                            page=page,
                            defaults={
                                'api_key': cj_api_key,
                                'is_active': True,
                                'api_status': 'active',
                                'default_profit_margin': 30.00,
                                'default_warehouse': 'CN',
                                'currency': currency,
                            }
                        )
                        if not created:
                            # Update existing settings
                            cj_settings.api_key = cj_api_key
                            cj_settings.is_active = True
                            cj_settings.api_status = 'active'
                            cj_settings.currency = currency
                            cj_settings.save()
                        
                        # Try to get an access token to confirm it works
                        try:
                            from builder.services.cj_service import CJService
                            service = CJService(cj_api_key)
                            token = service.get_access_token()
                            if token:
                                cj_settings.access_token = token
                                cj_settings.token_expiry = timezone.now() + timedelta(days=14)
                                cj_settings.api_status = 'active'
                                cj_settings.save()
                                print(f"✅ [launch_editor] CJ API key validated and token obtained")
                        except Exception as e:
                            print(f"⚠️ [launch_editor] CJ token fetch failed: {e}")
                            # Still save the key even if token fetch fails
                            cj_settings.api_status = 'pending'
                            cj_settings.save()
                            
                    except Exception as e:
                        print(f"❌ [launch_editor] Error saving CJ settings: {e}")
                        # Continue even if CJ settings fail - user can set up later
                else:
                    print(f"⚠️ [launch_editor] CJ API key was empty string, skipping")
            else:
                print(f"ℹ️ [launch_editor] No CJ API key to save (store_type: {store_type})")
            
            # 5. Apply the palette
            palette_id = data.get('palette_id')
            if palette_id:
                print(f"\n🎨 [launch_editor] Applying palette: {palette_id}")
                try:
                    palette = ColorPalette.objects.get(id=palette_id)
                    print(f"   Palette found: {palette.name}")
                    
                    from builder.utils.color_extractor import TemplateColorExtractor
                    color_map = TemplateColorExtractor.generate_color_map(template_name)
                    variables = color_map.get('variables', {})
                    print(f"   Found {len(variables)} template variables")
                    
                    applied_colors = {}
                    palette_colors = list(palette.colors.all())
                    print(f"   Palette has {len(palette_colors)} colors")
                    
                    for var_name, var_data in variables.items():
                        var_lower = var_name.lower()
                        matched_color = None
                        
                        for pc in palette_colors:
                            if pc.color_type in var_lower or var_lower in pc.color_type:
                                matched_color = pc
                                break
                        
                        if not matched_color:
                            for pc in palette_colors:
                                if pc.name.lower() in var_lower or var_lower in pc.name.lower():
                                    matched_color = pc
                                    break
                        
                        if not matched_color:
                            primary = palette.colors.filter(color_type='primary').first()
                            if primary:
                                matched_color = primary
                            else:
                                matched_color = palette_colors[0] if palette_colors else None
                        
                        if matched_color:
                            applied_colors[var_name] = {
                                'hex': matched_color.hex_value,
                                'rgb': matched_color.rgb_value,
                                'source': 'palette',
                                'palette_color_id': matched_color.id,
                                'color_type': matched_color.color_type,
                            }
                    
                    page.active_palette = palette
                    page.active_palette_colors = applied_colors
                    page.save(update_fields=['active_palette', 'active_palette_colors'])
                    
                    PageColorPalette.objects.create(
                        page=page,
                        palette=palette,
                        is_active=True,
                        applied_colors=applied_colors,
                        variable_mapping={}
                    )
                    
                    print(f"✅ [launch_editor] Palette applied successfully: {palette.name}")
                    
                except ColorPalette.DoesNotExist:
                    print(f"⚠️ [launch_editor] Palette {palette_id} not found")
                except Exception as e:
                    print(f"⚠️ [launch_editor] Error applying palette: {e}")
                    import traceback
                    traceback.print_exc()
            
            # 6. Build editor URL
            editor_url = reverse('editor_with_page', kwargs={
                'template_name': template_name,
                'subdomain': subdomain
            })
            editor_url += f'?onboarding=true&brand={brand_name}'
            
            print(f"\n📤 [launch_editor] Returning response:")
            print(f"   success: True")
            print(f"   editor_url: {editor_url}")
            print(f"   subdomain: {subdomain}")
            print(f"   brand_name: {brand_name}")
            print(f"   page_id: {page.id}")
            print("="*60 + "\n")
            
            return JsonResponse({
                'success': True,
                'message': 'Store created, launching editor...',
                'editor_url': editor_url,
                'subdomain': subdomain,
                'brand_name': brand_name,
                'page_id': page.id,
                'template_name': template_name,
                'palette_applied': palette_id is not None,
            })
            
    except Exception as e:
        print(f"\n❌ [launch_editor] EXCEPTION CAUGHT:")
        print(f"   Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*60 + "\n")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def generate_subdomain_from_brand(brand_name):
    """
    Generate a subdomain from a brand name
    """
    if not brand_name:
        return 'my-store'
    
    subdomain = brand_name.lower()
    subdomain = re.sub(r'[^a-z0-9\s-]', '', subdomain)
    subdomain = re.sub(r'\s+', '-', subdomain)
    subdomain = re.sub(r'-+', '-', subdomain)
    subdomain = re.sub(r'^-|-$', '', subdomain)
    
    if not subdomain:
        subdomain = 'my-store'
    
    return subdomain
    

def apply_palette_directly(page, palette_id):
    """Fallback: Apply palette directly to page"""
    try:
        from builder.utils.color_extractor import TemplateColorExtractor
        palette = ColorPalette.objects.get(id=palette_id)
        
        color_map = TemplateColorExtractor.generate_color_map(page.template.name)
        variables = color_map.get('variables', {})
        
        applied_colors = {}
        palette_colors = list(palette.colors.all())
        
        for var_name, var_data in variables.items():
            var_lower = var_name.lower()
            matched_color = None
            
            for pc in palette_colors:
                if pc.color_type in var_lower or var_lower in pc.color_type:
                    matched_color = pc
                    break
            
            if not matched_color:
                for pc in palette_colors:
                    if pc.name.lower() in var_lower or var_lower in pc.name.lower():
                        matched_color = pc
                        break
            
            if not matched_color:
                primary = palette.colors.filter(color_type='primary').first()
                if primary:
                    matched_color = primary
                else:
                    matched_color = palette_colors[0] if palette_colors else None
            
            if matched_color:
                applied_colors[var_name] = {
                    'hex': matched_color.hex_value,
                    'rgb': matched_color.rgb_value,
                    'source': 'palette',
                }
            else:
                applied_colors[var_name] = {
                    'hex': var_data.get('value', '#4361ee'),
                    'rgb': var_data.get('rgb', '67, 97, 238'),
                    'source': 'original',
                }
        
        page.active_palette = palette
        page.active_palette_colors = applied_colors
        page.save(update_fields=['active_palette', 'active_palette_colors'])
        
        from builder.models import PageColorPalette
        PageColorPalette.objects.create(
            page=page,
            palette=palette,
            is_active=True,
            applied_colors=applied_colors,
            variable_mapping={}
        )
        
        print(f"✅ Fallback: Applied palette {palette.name} directly")
        
    except Exception as e:
        print(f"❌ Fallback failed: {e}")

    
def map_palette_to_template(palette, template_name):
    """Map palette colors to template variables"""
    from builder.utils.color_extractor import TemplateColorExtractor
    color_map = TemplateColorExtractor.generate_color_map(template_name)
    variables = color_map.get('variables', {})
    applied_colors = {}
    
    for var_name, var_data in variables.items():
        matched_color = None
        for palette_color in palette.colors.all():
            if palette_color.color_type in var_name.lower():
                matched_color = palette_color
                break
        
        if matched_color:
            applied_colors[var_name] = {
                'hex': matched_color.hex_value,
                'rgb': matched_color.rgb_value,
                'source': 'palette'
            }
        else:
            first_color = palette.colors.first()
            if first_color:
                applied_colors[var_name] = {
                    'hex': first_color.hex_value,
                    'rgb': first_color.rgb_value,
                    'source': 'palette'
                }
    
    return applied_colors


def generate_initial_content(brand_name, heading_font, body_font, description, palette):
    """Generate initial page content with fonts and colors"""
    primary_color = '#4361ee'
    if palette:
        primary = palette.colors.filter(color_type='primary').first()
        if primary:
            primary_color = primary.hex_value
    
    return {
        'home': {
            'text_contents': {
                '1': f"Welcome to {brand_name}",
                '2': description or "Your amazing store is ready to go",
                '3': "Why Choose Us",
                '4': "Fast Delivery",
                '5': "Get your products delivered quickly",
                '6': "Quality Guarantee",
                '7': "30-day money back guarantee",
            },
            'style_customizations': {
                '1': {
                    'font_family': heading_font,
                    'background_color': primary_color,
                },
                '3': {
                    'font_family': body_font,
                }
            }
        },
        'products': {
            'text_contents': {
                '9': "Our Products",
                '10': "Discover our amazing collection",
            }
        },
        'about': {
            'text_contents': {
                '1': "About Us",
                '2': f"Welcome to {brand_name}",
            }
        },
        'contact': {
            'text_contents': {
                '1': "Contact Us",
                '2': "We'd love to hear from you",
            }
        }
    }















# builder/views.py - Add these imports at the top with your existing imports

import json
import os
from pathlib import Path
from datetime import datetime
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, render
from django.conf import settings

from builder.models import PublishedPage, Template
from builder.copywriting.template_copy import TemplateCopyManager

# Initialize the copy manager
copy_manager = TemplateCopyManager()

# ============================================================
# COPYWRITING SYSTEM - Integrated Views
# ============================================================

@login_required
def get_template_copy(request, template_name):
    """
    API endpoint to get template copy data
    """
    try:
        data = copy_manager.load_template_copy(template_name)
        
        if not data:
            # Try to extract if not found
            template = get_object_or_404(Template, name=template_name)
            # Extract fresh copy from template files
            template_path = Path(settings.BASE_DIR) / 'builder' / 'public_templates' / template_name
            if template_path.exists():
                all_texts = []
                for html_file in template_path.glob('*.html'):
                    with open(html_file, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    page_texts = copy_manager.extract_template_text(template_name, html_content)
                    all_texts.append(page_texts)
                
                # Combine data
                combined_data = {
                    'template': template_name,
                    'pages': {},
                    'components': {},
                    'global_texts': []
                }
                for page_data in all_texts:
                    combined_data['pages'].update(page_data.get('pages', {}))
                    combined_data['global_texts'].extend(page_data.get('global_texts', []))
                
                copy_manager.save_template_copy(template_name, combined_data)
                data = combined_data
        
        return JsonResponse({
            'success': True,
            'data': data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def get_page_copy(request, subdomain, page_name):
    """
    Get copy for a specific page
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        template_name = page.template_name
        
        data = copy_manager.load_template_copy(template_name)
        
        if data and page_name in data.get('pages', {}):
            return JsonResponse({
                'success': True,
                'page': page_name,
                'copy': data['pages'][page_name]
            })
        
        return JsonResponse({
            'success': False,
            'error': f'Page "{page_name}" not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
def save_copy_changes(request, subdomain):
    """
    Save copy changes from the editor
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        template_name = page.template_name
        
        # Validate the data
        changes = data.get('changes', [])
        page_name = data.get('page', 'home')
        
        # Load existing copy
        copy_data = copy_manager.load_template_copy(template_name)
        
        if not copy_data:
            copy_data = {
                'template': template_name,
                'pages': {},
                'components': {},
                'global_texts': []
            }
        
        # Update the specific page
        if page_name not in copy_data['pages']:
            copy_data['pages'][page_name] = []
        
        # Apply changes
        for change in changes:
            element_id = change.get('id')
            new_text = change.get('text')
            
            # Find and update the element
            found = False
            for text_item in copy_data['pages'][page_name]:
                if text_item['id'] == element_id:
                    text_item['text'] = new_text
                    text_item['customized'] = True
                    text_item['customized_at'] = datetime.now().isoformat()
                    found = True
                    break
            
            if not found:
                # Add new element if not found
                copy_data['pages'][page_name].append({
                    'id': element_id,
                    'text': new_text,
                    'customized': True,
                    'customized_at': datetime.now().isoformat(),
                    'type': 'text'
                })
        
        # Save changes
        copy_manager.apply_custom_copy(template_name, copy_data)
        
        return JsonResponse({
            'success': True,
            'message': 'Copy saved successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def export_copy_json(request, subdomain):
    """
    Export copy as JSON
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        template_name = page.template_name
        
        data = copy_manager.load_template_copy(template_name)
        
        # If no data, try to extract first
        if not data:
            return get_template_copy(request, template_name)
        
        return JsonResponse({
            'success': True,
            'template': template_name,
            'copy_data': data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
def import_copy_json(request, subdomain):
    """
    Import copy from JSON
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        template_name = page.template_name
        
        copy_data = data.get('copy_data', {})
        
        # Validate
        if 'pages' not in copy_data:
            return JsonResponse({
                'success': False,
                'error': 'Invalid copy data: missing pages'
            }, status=400)
        
        # Apply the copy
        result = copy_manager.apply_custom_copy(template_name, copy_data)
        
        return JsonResponse({
            'success': True,
            'message': 'Copy imported successfully',
            'version': result.get('custom_version', 1)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
def generate_ai_prompt(request, subdomain):
    """
    Generate an AI prompt with context and JSON format instructions
    """
    try:
        print("=" * 60)
        print("📝 GENERATE AI PROMPT")
        print("=" * 60)
        
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        template_name = page.template_name
        
        # Get context from POST data
        context = ''
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                context = data.get('context', '')
                print(f"📝 Context received: {context[:200] if context else '(empty)'}...")
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
        else:
            print(f"⚠️ Request method is {request.method}, not POST")
        
        # Read the JSON file
        json_path = Path(settings.BASE_DIR) / 'builder' / 'copywriting' / 'templates' / f'{template_name}.json'
        
        if not json_path.exists():
            return JsonResponse({
                'success': False,
                'error': f'No copy data found for "{template_name}". Run: python manage.py extract_copy --template {template_name}'
            }, status=404)
        
        with open(json_path, 'r', encoding='utf-8') as f:
            copy_data = json.load(f)
        
        print(f"📄 Template: {template_name}")
        print(f"📄 Pages: {list(copy_data.get('pages', {}).keys())}")
        
        # Build the AI prompt with context
        prompt = build_ai_prompt_with_json(copy_data, page, context)
        
        print(f"✅ Prompt generated: {len(prompt)} characters")
        print("=" * 60)
        
        return JsonResponse({
            'success': True,
            'prompt': prompt
        })
    except Exception as e:
        print(f"❌ Generate prompt error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

        
def build_ai_prompt_with_json(data, page, context=None):
    """Build AI prompt with JSON format instructions and optional context"""
    template_name = data.get('template', 'unknown')
    brand_name = page.brand_name if page else 'My Store'
    
    # Build the prompt using simple string concatenation to avoid escape issues
    prompt = "# AI Copywriting Assistant - " + template_name + "\n\n"
    prompt += "## BRAND INFORMATION\n"
    prompt += "- Brand Name: " + brand_name + "\n"
    prompt += "- Template: " + template_name + "\n\n"
    
    # Add context if provided
    if context and context.strip():
        prompt += "## CONTEXT FROM USER\n"
        prompt += context + "\n\n"
    
    prompt += "## INSTRUCTIONS\n"
    prompt += "You are an expert copywriter. Rewrite the following text to be more engaging, professional, and persuasive.\n\n"
    
    # Add context-specific instructions if context is provided
    if context and context.strip():
        prompt += "### Using the Context Above\n"
        prompt += "Use the business information and product references provided in the CONTEXT FROM USER section to:\n"
        prompt += "1. Write copy that accurately describes the products/services\n"
        prompt += "2. Highlight the unique selling points mentioned\n"
        prompt += "3. Use language that matches the brand's tone\n"
        prompt += "4. Incorporate specific product details where relevant\n\n"
    
    prompt += "### CRITICAL: Response Format\n"
    prompt += "You MUST respond with a VALID JSON object in this EXACT format:\n\n"
    prompt += '{\n'
    prompt += '  "pages": {\n'
    prompt += '    "home": [\n'
    prompt += '      {"id": "1", "text": "YOUR NEW HEADLINE HERE", "type": "heading"},\n'
    prompt += '      {"id": "2", "text": "YOUR NEW PARAGRAPH HERE", "type": "paragraph"}\n'
    prompt += '    ]\n'
    prompt += '  }\n'
    prompt += '}\n\n'
    prompt += "## CURRENT CONTENT TO REWRITE\n\n"
    
    # Add all pages and their text
    for page_name, page_texts in data.get('pages', {}).items():
        prompt += "### Page: " + page_name + "\n\n"
        for text in page_texts:
            prompt += "ID: " + text['id'] + "\n"
            prompt += "Current: \"" + text['text'] + "\"\n"
            prompt += "Type: " + text['type'] + "\n\n"
    
    prompt += "## YOUR RESPONSE\n"
    prompt += "Copy this template and fill in your new text:\n\n"
    prompt += '{\n'
    prompt += '  "pages": {\n'
    
    # Generate the JSON template with placeholder text
    page_count = 0
    for page_name, page_texts in data.get('pages', {}).items():
        if page_count > 0:
            prompt += ",\n"
        prompt += '    "' + page_name + '": [\n'
        for i, text in enumerate(page_texts):
            line = '      {"id": "' + text['id'] + '", "text": "REWRITE THIS TEXT", "type": "' + text['type'] + '"}'
            if i < len(page_texts) - 1:
                line += ","
            prompt += line + "\n"
        prompt += "    ]"
        page_count += 1
    
    prompt += "\n  }\n}"
    
    return prompt


@login_required
@csrf_exempt
def apply_ai_copy(request, subdomain):
    """
    Apply AI-generated copy - uses the EXACT same logic as the editor and publish views
    """
    print("\n" + "=" * 80)
    print("🚀 APPLY AI COPY - Using Editor/Publish Logic")
    print("=" * 80)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        print("📥 Received data:", json.dumps(data, indent=2)[:500])
        
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        # Get the AI copy - same structure as editor's page_data
        ai_copy = data.get('copy', {})
        
        # Handle different JSON structures
        if 'pages' in ai_copy:
            pages_data = ai_copy['pages']
        else:
            pages_data = ai_copy
        
        if not pages_data:
            return JsonResponse({
                'success': False,
                'error': 'No copy data provided'
            }, status=400)
        
        updated_count = 0
        
        # ============================================================
        # EXACT SAME LOGIC AS THE EDITOR'S publish_page
        # The editor sends: all_page_data[page_name]['text_contents']
        # ============================================================
        
        for page_name, page_texts in pages_data.items():
            print(f"\n📄 Processing page: {page_name}")
            
            # Initialize page_customizations - SAME as editor
            if page_name not in page.page_customizations:
                page.page_customizations[page_name] = {}
            
            # Initialize text_contents - SAME as editor
            if 'text_contents' not in page.page_customizations[page_name]:
                page.page_customizations[page_name]['text_contents'] = {}
            
            # Apply each text - SAME as editor
            for text_item in page_texts:
                element_id = str(text_item.get('id'))
                new_text = text_item.get('text', '').strip()
                
                if element_id and new_text:
                    # Clean the text - remove extra whitespace like the editor does
                    cleaned_text = re.sub(r'\s+', ' ', new_text).strip()
                    
                    # Save to page_customizations - EXACT same as editor
                    page.page_customizations[page_name]['text_contents'][element_id] = cleaned_text
                    updated_count += 1
                    print(f"  ✅ text_contents['{element_id}'] = '{cleaned_text[:50]}...'")
        
        # ============================================================
        # SAVE THE PAGE - EXACT same as publish_page
        # ============================================================
        
        page.is_published = True
        page.save()
        
        print(f"\n💾 Page saved with {updated_count} updates")
        print(f"   is_published: {page.is_published}")
        print("=" * 80)
        
        return JsonResponse({
            'success': True,
            'message': f'AI copy applied to {updated_count} elements',
            'updated_count': updated_count,
            'pages_updated': list(pages_data.keys())
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def copy_editor_view(request, subdomain):
    """
    Main copy editor view
    """
    page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
    
    context = {
        'page': page,
        'template_name': page.template_name,
    }
    
    return render(request, 'builder/copy_editor.html', context)


@login_required
def extract_template_copy(request, template_name):
    """
    API endpoint to extract copy from a template
    """
    try:
        template = get_object_or_404(Template, name=template_name)
        
        # Extract fresh copy from template files
        template_path = Path(settings.BASE_DIR) / 'builder' / 'public_templates' / template_name
        
        if not template_path.exists():
            return JsonResponse({
                'success': False,
                'error': f'Template directory not found: {template_name}'
            }, status=404)
        
        all_texts = []
        for html_file in template_path.glob('*.html'):
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            page_texts = copy_manager.extract_template_text(template_name, html_content)
            all_texts.append(page_texts)
        
        # Combine data
        combined_data = {
            'template': template_name,
            'pages': {},
            'components': {},
            'global_texts': []
        }
        for page_data in all_texts:
            combined_data['pages'].update(page_data.get('pages', {}))
            combined_data['global_texts'].extend(page_data.get('global_texts', []))
        
        # Extract from components if available
        components_dir = Path(settings.BASE_DIR) / 'builder' / 'components'
        if components_dir.exists():
            for comp_file in components_dir.rglob('*.html'):
                try:
                    with open(comp_file, 'r', encoding='utf-8') as f:
                        comp_content = f.read()
                    comp_data = copy_manager.extract_template_text(comp_file.stem, comp_content)
                    combined_data['components'][comp_file.stem] = comp_data.get('global_texts', [])
                except Exception as e:
                    print(f"Error processing component {comp_file.name}: {e}")
        
        # Save the copy
        copy_manager.save_template_copy(template_name, combined_data)
        
        return JsonResponse({
            'success': True,
            'message': f'Copy extracted for {template_name}',
            'element_count': len(combined_data.get('global_texts', [])),
            'pages': list(combined_data.get('pages', {}).keys())
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def list_templates_copy(request):
    """
    List all templates with copy status
    """
    try:
        templates_path = Path(settings.BASE_DIR) / 'builder' / 'public_templates'
        
        templates = []
        for template_dir in templates_path.iterdir():
            if template_dir.is_dir():
                has_copy = copy_manager.get_template_copy_path(template_dir.name).exists()
                templates.append({
                    'name': template_dir.name,
                    'has_copy': has_copy,
                    'pages': [f.stem for f in template_dir.glob('*.html')]
                })
        
        return JsonResponse({
            'success': True,
            'templates': templates
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
def bulk_import_copy(request, subdomain):
    """
    Bulk import copy from JSON for multiple pages
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        template_name = page.template_name
        
        copy_data = data.get('copy_data', {})
        
        # Validate
        if 'pages' not in copy_data:
            return JsonResponse({
                'success': False,
                'error': 'Invalid copy data: missing pages'
            }, status=400)
        
        # Apply the copy
        result = copy_manager.apply_custom_copy(template_name, copy_data)
        
        # Also update the page customizations
        for page_name, page_copy in copy_data.get('pages', {}).items():
            if page_name not in page.page_customizations:
                page.page_customizations[page_name] = {}
            
            if 'text_contents' not in page.page_customizations[page_name]:
                page.page_customizations[page_name]['text_contents'] = {}
            
            for item in page_copy:
                element_id = item.get('id')
                text = item.get('text')
                if element_id and text:
                    page.page_customizations[page_name]['text_contents'][element_id] = text
        
        page.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Bulk import successful',
            'pages_updated': list(copy_data.get('pages', {}).keys())
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def get_copy_stats(request, subdomain):
    """
    Get copy statistics for a page
    """
    try:
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        template_name = page.template_name
        
        data = copy_manager.load_template_copy(template_name)
        
        if not data:
            return JsonResponse({
                'success': True,
                'stats': {
                    'total_elements': 0,
                    'customized_elements': 0,
                    'total_words': 0,
                    'pages': []
                }
            })
        
        total_elements = 0
        customized_elements = 0
        total_words = 0
        pages_stats = []
        
        for page_name, page_data in data.get('pages', {}).items():
            page_total = len(page_data)
            page_customized = sum(1 for item in page_data if item.get('customized', False))
            page_words = sum(len(item.get('text', '').split()) for item in page_data)
            
            total_elements += page_total
            customized_elements += page_customized
            total_words += page_words
            
            pages_stats.append({
                'name': page_name,
                'total': page_total,
                'customized': page_customized,
                'words': page_words
            })
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_elements': total_elements,
                'customized_elements': customized_elements,
                'total_words': total_words,
                'pages': pages_stats
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)    



# builder/views.py

import os
import sys
import time
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from builder.models import PublishedPage, Product

def get_memory_mb():
    """Get current memory usage in MB"""
    try:
        import psutil
        pid = os.getpid()
        process = psutil.Process(pid)
        return process.memory_info().rss / 1024 / 1024
    except:
        return 0

def memory_status(request):
    """Check current memory usage"""
    try:
        import psutil
        pid = os.getpid()
        process = psutil.Process(pid)
        memory_info = {
            'rss': process.memory_info().rss / 1024 / 1024,
            'vms': process.memory_info().vms / 1024 / 1024,
        }
        return JsonResponse({
            'pid': pid,
            'memory': memory_info,
            'cpu': process.cpu_percent(interval=0.1),
            'threads': process.num_threads(),
        })
    except Exception as e:
        return JsonResponse({'error': str(e), 'python_version': sys.version})

def memory_test_public(request):
    """Test public memory usage"""
    print("\n" + "="*60)
    print("🟢 PUBLIC VIEW TEST")
    print("="*60)
    
    start_memory = get_memory_mb()
    start_time = time.time()
    print(f"📊 Starting memory: {start_memory:.2f} MB")
    
    # Simulate some work
    time.sleep(0.1)
    
    end_memory = get_memory_mb()
    elapsed = time.time() - start_time
    
    print(f"📊 Ending memory: {end_memory:.2f} MB")
    print(f"📊 Memory increased: {end_memory - start_memory:+.2f} MB")
    print(f"⏱️  Time: {elapsed:.2f}s")
    print("="*60)
    
    return JsonResponse({
        'authenticated': False,
        'start_memory': round(start_memory, 2),
        'end_memory': round(end_memory, 2),
        'diff': round(end_memory - start_memory, 2),
        'time': round(elapsed, 2),
        'message': 'This is a public view'
    })

@login_required
def memory_test_auth(request):
    """Test authenticated memory usage"""
    print("\n" + "="*60)
    print("🔴 AUTHENTICATED VIEW TEST")
    print("="*60)
    
    start_memory = get_memory_mb()
    start_time = time.time()
    print(f"📊 Starting memory: {start_memory:.2f} MB")
    
    # Load user data
    user = request.user
    print(f"👤 User: {user.username} (ID: {user.id})")
    
    # Load pages
    pages = PublishedPage.objects.filter(user=user)
    page_count = pages.count()
    print(f"📄 Pages: {page_count}")
    
    # Load first page data
    page_data = []
    for page in pages[:3]:
        page_data.append({
            'id': page.id,
            'brand_name': page.brand_name,
            'subdomain': page.subdomain,
            'template_name': page.template_name,
        })
    
    # Load products
    products = Product.objects.filter(page__user=user)
    product_count = products.count()
    print(f"🛒 Products: {product_count}")
    
    # Simulate work
    time.sleep(0.1)
    
    end_memory = get_memory_mb()
    elapsed = time.time() - start_time
    
    print(f"📊 Ending memory: {end_memory:.2f} MB")
    print(f"📊 Memory increased: {end_memory - start_memory:+.2f} MB")
    print(f"⏱️  Time: {elapsed:.2f}s")
    print("="*60)
    
    return JsonResponse({
        'authenticated': True,
        'user': user.username,
        'page_count': page_count,
        'product_count': product_count,
        'pages': page_data,
        'start_memory': round(start_memory, 2),
        'end_memory': round(end_memory, 2),
        'diff': round(end_memory - start_memory, 2),
        'time': round(elapsed, 2),
        'message': 'This is an authenticated view'
    })



@login_required
@csrf_exempt
@check_storage_before_upload('video')
def upload_video(request):
    """
    Upload video file and poster image for editable elements
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        subdomain = request.POST.get('subdomain')
        element_id = request.POST.get('element_id')
        page_name = request.POST.get('page_name', 'home')
        video_file = request.FILES.get('video')
        poster_file = request.FILES.get('poster')
        alt_text = request.POST.get('alt_text', '')
        autoplay = request.POST.get('autoplay', 'false') == 'true'
        loop = request.POST.get('loop', 'false') == 'true'
        muted = request.POST.get('muted', 'true') == 'true'
        controls = request.POST.get('controls', 'true') == 'true'
        # ===== ADD THIS =====
        show_play_button = request.POST.get('show_play_button', 'true') == 'true'
        
        if not all([subdomain, element_id, video_file]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        # Delete existing video if any
        VideoCustomization.objects.filter(
            page=page,
            element_id=element_id,
            page_name=page_name
        ).delete()
        
        # Create video customization
        video_customization = VideoCustomization.objects.create(
            page=page,
            element_id=element_id,
            page_name=page_name,
            video_file=video_file,
            alt_text=alt_text,
            autoplay=autoplay,
            loop=loop,
            muted=muted,
            controls=controls,
            show_play_button=show_play_button  # ===== ADD THIS =====
        )
        
        # Handle poster image
        poster_url = None
        if poster_file:
            video_customization.poster_image = poster_file
            video_customization.save()
            poster_url = video_customization.poster_image.url
        
        return JsonResponse({
            'success': True,
            'video_url': video_customization.video_file.url,
            'poster_url': poster_url,
            'element_id': element_id,
            'show_play_button': show_play_button,  # ===== ADD THIS =====
            'message': 'Video uploaded successfully'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@csrf_exempt
def save_video_url(request):
    """
    Save video URL for editable elements (YouTube, Vimeo, etc.)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body)
        subdomain = data.get('subdomain')
        element_id = data.get('element_id')
        page_name = data.get('page_name', 'home')
        video_url = data.get('video_url', '').strip()
        alt_text = data.get('alt_text', '')
        autoplay = data.get('autoplay', False)
        loop = data.get('loop', False)
        muted = data.get('muted', True)
        controls = data.get('controls', True)
        # ===== ADD THIS =====
        show_play_button = data.get('show_play_button', True)
        
        if not all([subdomain, element_id, video_url]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        # Delete existing video
        VideoCustomization.objects.filter(
            page=page,
            element_id=element_id,
            page_name=page_name
        ).delete()
        
        # Create video customization
        video_customization = VideoCustomization.objects.create(
            page=page,
            element_id=element_id,
            page_name=page_name,
            video_url=video_url,
            alt_text=alt_text,
            autoplay=autoplay,
            loop=loop,
            muted=muted,
            controls=controls,
            show_play_button=show_play_button  # ===== ADD THIS =====
        )
        
        return JsonResponse({
            'success': True,
            'video_url': video_url,
            'element_id': element_id,
            'show_play_button': show_play_button,  # ===== ADD THIS =====
            'message': 'Video URL saved successfully'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
def remove_video(request, subdomain):
    """
    Remove video from an element
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body)
        element_id = data.get('element_id')
        page_name = data.get('page_name', 'home')
        
        if not element_id:
            return JsonResponse({'success': False, 'error': 'Element ID required'})
        
        page = get_object_or_404(PublishedPage, subdomain=subdomain, user=request.user)
        
        deleted_count, _ = VideoCustomization.objects.filter(
            page=page,
            element_id=element_id,
            page_name=page_name
        ).delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Video removed successfully',
            'deleted': deleted_count
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================
# DOMAIN SEARCH & REQUEST VIEWS
# ============================================================

from builder.utils.rdap import (
    check_domain_availability,
    check_multiple_domains,
    get_supported_tlds,
    is_tld_supported,
)
from builder.models import DomainRequest, PurchasedDomain
from payments.decorators import (
    check_domain_eligibility,
    get_user_domain_summary,
    get_user_limits_status,
)
import json as _json
import re as _re


@login_required
def search_domain(request, subdomain):
    """
    AJAX endpoint: search for a domain name across one or more TLDs.

    Accepts either:
      - A base name (e.g. "jerase") → searches across the plan's free TLDs
        plus a small set of popular TLDs.
      - A full domain (e.g. "jerase.store") → searches only that specific TLD.

    GET params:
      q (required): the name or full domain to search
      tlds (optional): comma-separated TLDs, overrides defaults

    Response:
      {
        "success": True,
        "query": "jerase",
        "forced_tld": "store" | null,
        "results": [
           {"domain_name": "jerase.store", "tld": "store",
            "available": True/False/None, "reason": "...",
            "is_free_on_plan": True/False, "is_supported": True},
           ...
        ]
      }
    """
    page = get_object_or_404(
        PublishedPage, subdomain=subdomain, user=request.user
    )

    query = (request.GET.get('q') or '').strip().lower()
    tlds_param = (request.GET.get('tlds') or '').strip()

    if not query:
        return JsonResponse({
            'success': False,
            'error': 'Search query is required',
        }, status=400)

    # ---- Smart parsing: detect a full domain in the input ----
    raw_query = query
    raw_query = _re.sub(r'^https?://', '', raw_query)
    raw_query = _re.sub(r'^www\.', '', raw_query)
    raw_query = raw_query.split('/')[0]
    raw_query = raw_query.split('?')[0]

    forced_tld = None
    if '.' in raw_query:
        parts = raw_query.split('.')
        last = parts[-1]
        # Only treat the last segment as a TLD if it looks real:
        # alphabetic, 2-15 characters long
        if last.isalpha() and 2 <= len(last) <= 15:
            forced_tld = last
            base_name = '.'.join(parts[:-1])
        else:
            base_name = raw_query
    else:
        base_name = raw_query

    # Sanitize the base name
    base_name = _re.sub(r'[^a-z0-9-]', '', base_name)
    base_name = _re.sub(r'-+', '-', base_name).strip('-')

    if not base_name or len(base_name) < 2:
        return JsonResponse({
            'success': False,
            'error': 'Please enter at least 2 valid characters',
        }, status=400)

    # ---- Decide which TLDs to search ----
    if forced_tld:
        # User pasted a full domain — search only that TLD
        tlds = [forced_tld]
    elif tlds_param:
        tlds = [t.strip().lstrip('.').lower() for t in tlds_param.split(',') if t.strip()]
    else:
        # Default: plan's free TLDs + a small set of popular paid TLDs
        limits = get_user_limits_status(request.user)
        free_tlds = limits['domains']['free_tlds'] or []

        default_paid = ['com', 'store', 'org', 'net', 'shop', 'online', 'site', 'co']
        seen = set()
        tlds = []
        for t in free_tlds + default_paid:
            t = t.lower().lstrip('.')
            if t and t not in seen:
                seen.add(t)
                tlds.append(t)

    # Limit total queries (protection)
    tlds = tlds[:10]

    # ---- Run availability checks ----
    raw_results = check_multiple_domains([base_name], tlds)

    # Enrich with plan context
    limits = get_user_limits_status(request.user)
    free_tlds_set = set(limits['domains']['free_tlds'] or [])

    results = []
    for domain_name, data in raw_results.items():
        tld = data.get('tld', '')
        results.append({
            'domain_name': domain_name,
            'tld': tld,
            'available': data.get('available'),  # True / False / None
            'reason': data.get('reason', ''),
            'is_supported': data.get('supported', False),
            'is_free_on_plan': tld in free_tlds_set,
            'cached': data.get('cached', False),
        })

    # Sort: available free-TLD first, then available paid, then unknown, then taken
    def sort_key(r):
        if r['available'] is True and r['is_free_on_plan']:
            return (0, r['tld'])
        if r['available'] is True:
            return (1, r['tld'])
        if r['available'] is None:
            return (2, r['tld'])
        return (3, r['tld'])

    results.sort(key=sort_key)

    return JsonResponse({
        'success': True,
        'query': base_name,
        'forced_tld': forced_tld,
        'results': results,
    })


@login_required
@check_domain_eligibility
def request_domain(request, subdomain):
    """
    AJAX POST: create a DomainRequest for the user.

    Runs all eligibility checks via @check_domain_eligibility.
    Expects POST/JSON body with:
      domain_name (str, full domain e.g. "mystore.store")
      tld (str, e.g. "store")

    On success returns the created request with status.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'POST required',
        }, status=405)

    page = get_object_or_404(
        PublishedPage, subdomain=subdomain, user=request.user
    )

    domain_name = request.domain_name
    tld = request.domain_tld
    is_free_tier = request.domain_is_free_tier

    # Guard: prevent duplicate pending requests for the same domain
    existing = DomainRequest.objects.filter(
        user=request.user,
        domain_name=domain_name,
    ).exclude(
        status__in=DomainRequest.TERMINAL_STATUSES
    ).first()

    if existing:
        return JsonResponse({
            'success': False,
            'error': 'duplicate_request',
            'message': (
                f"You already have a pending request for {domain_name}. "
                f"Please wait for it to be processed."
            ),
        }, status=400)

    # Guard: ensure it's still actually available at request time.
    # (We checked during search, but availability can change in seconds.
    #  Also, users could POST directly to this endpoint.)
    availability = check_domain_availability(domain_name)
    if availability.get('available') is False:
        return JsonResponse({
            'success': False,
            'error': 'domain_taken',
            'message': (
                f"{domain_name} has just been registered. "
                f"Please try a different name."
            ),
        }, status=400)

    # If availability is None, we allow the request but flag it for manual
    # review — the admin will verify before purchasing.
    # (This handles RDAP being temporarily down or rate-limited.)

    # Create the request
    domain_request = DomainRequest.objects.create(
        user=request.user,
        page=page,
        domain_name=domain_name,
        tld=tld,
        is_free_tier=is_free_tier,
        status='pending_review',
    )

    # Log to console (replace with proper logging in production)
    print(
        f"📥 [request_domain] New domain request: {domain_name} "
        f"(user={request.user.username}, free={is_free_tier})"
    )

    return JsonResponse({
        'success': True,
        'message': (
            f"{domain_name} has been added to your account. "
            f"We're finalizing the setup and will notify you once it's live."       
              ),
        'request': {
            'id': domain_request.id,
            'domain_name': domain_request.domain_name,
            'tld': domain_request.tld,
            'status': domain_request.status,
            'status_display': domain_request.get_status_display(),
            'is_free_tier': domain_request.is_free_tier,
            'created_at': domain_request.created_at.isoformat(),
        }
    })


@login_required
def list_domain_requests(request, subdomain):
    """
    AJAX GET: list the user's domain requests for this page.
    Used to render the "Your Domains" section of the dashboard.
    """
    page = get_object_or_404(
        PublishedPage, subdomain=subdomain, user=request.user
    )

    requests_qs = DomainRequest.objects.filter(
        user=request.user
    ).order_by('-created_at')

    # Optional filter by page
    if request.GET.get('page_only') == '1':
        requests_qs = requests_qs.filter(page=page)

    data = []
    for req in requests_qs[:50]:
        data.append({
            'id': req.id,
            'domain_name': req.domain_name,
            'tld': req.tld,
            'status': req.status,
            'status_display': req.get_status_display(),
            'is_free_tier': req.is_free_tier,
            'created_at': req.created_at.isoformat(),
            'activated_at': req.activated_at.isoformat() if req.activated_at else None,
            'is_terminal': req.is_terminal,
        })

    return JsonResponse({
        'success': True,
        'requests': data,
        'summary': get_user_domain_summary(request.user),
    })


"""
Staff-only admin views for the domain fulfillment system.

These views are staff-gated and handle:
  - The review queue (pending requests)
  - In-progress requests (approved → purchasing → purchased → configuring_dns)
  - History (terminal states)
  - Status transition actions (approve, reject, mark purchased, mark DNS, mark active, mark failed)
"""

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from builder.models import DomainRequest, PurchasedDomain, PublishedPage
from payments.decorators import get_user_domain_summary


# ============================================================
# STAFF ACCESS DECORATOR
# ============================================================

def staff_required(view_func):
    """
    Require request.user.is_staff == True.
    Returns 404 (not 403) to non-staff, so the admin panel is not discoverable.
    """
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_staff:
            from django.http import Http404
            raise Http404("Not found")
        return view_func(request, *args, **kwargs)
    return wrapped


# ============================================================
# QUEUE VIEW
# ============================================================

@login_required
@staff_required
def admin_domain_queue(request):
    """
    Show all pending_review domain requests, oldest first.
    """
    pending = DomainRequest.objects.filter(
        status='pending_review'
    ).select_related('user', 'page').order_by('created_at')

    # Attach per-user context for the template (limit remaining, etc.)
    enriched = []
    for req in pending:
        summary = get_user_domain_summary(req.user)
        enriched.append({
            'request': req,
            'user_plan': summary,
        })

    context = {
        'pending': enriched,
        'pending_count': len(enriched),
    }
    return render(request, 'builder/admin/domains/queue.html', context)


# ============================================================
# IN-PROGRESS VIEW
# ============================================================

@login_required
@staff_required
def admin_domain_in_progress(request):
    """
    Show requests currently being worked on:
    approved, purchasing, purchased, configuring_dns.
    """
    in_progress_statuses = ['approved', 'purchasing', 'purchased', 'configuring_dns']

    requests_qs = DomainRequest.objects.filter(
        status__in=in_progress_statuses
    ).select_related('user', 'page').order_by('updated_at')

    context = {
        'requests': requests_qs,
        'in_progress_count': requests_qs.count(),
        'namecheap_url': 'https://www.namecheap.com/domains/registration/results/?domain=',
    }
    return render(request, 'builder/admin/domains/in_progress.html', context)


# ============================================================
# HISTORY VIEW
# ============================================================

@login_required
@staff_required
def admin_domain_history(request):
    """
    Show terminal requests: active, failed, rejected, cancelled.
    Filterable by status and searchable by domain or user.
    """
    status_filter = request.GET.get('status', '')
    search = (request.GET.get('q') or '').strip()

    history_qs = DomainRequest.objects.filter(
        status__in=DomainRequest.TERMINAL_STATUSES
    ).select_related('user', 'page', 'reviewed_by').order_by('-updated_at')

    if status_filter:
        history_qs = history_qs.filter(status=status_filter)

    if search:
        from django.db.models import Q
        history_qs = history_qs.filter(
            Q(domain_name__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__email__icontains=search)
        )

    # Stats for the header
    total = DomainRequest.objects.filter(
        status__in=DomainRequest.TERMINAL_STATUSES
    ).count()
    active_count = DomainRequest.objects.filter(status='active').count()
    failed_count = DomainRequest.objects.filter(status='failed').count()
    rejected_count = DomainRequest.objects.filter(status='rejected').count()

    context = {
        'requests': history_qs[:200],
        'total_count': total,
        'active_count': active_count,
        'failed_count': failed_count,
        'rejected_count': rejected_count,
        'current_status': status_filter,
        'search': search,
        'status_options': [
            ('active', 'Active'),
            ('failed', 'Failed'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
    }
    return render(request, 'builder/admin/domains/history.html', context)


# ============================================================
# STATUS TRANSITION ACTIONS
# ============================================================

@login_required
@staff_required
@require_http_methods(["POST"])
def admin_domain_action(request, request_id):
    """
    POST handler for all status transitions.
    Expected POST field: 'action' with one of:
      approve, reject, mark_purchasing, mark_purchased,
      mark_dns_configured, mark_active, mark_failed, cancel
    """
    domain_request = get_object_or_404(DomainRequest, id=request_id)
    action = (request.POST.get('action') or '').strip()
    notes = (request.POST.get('admin_notes') or '').strip()

    # Redirect target preserves the current page
    return_to = request.POST.get('return_to') or reverse('admin_domain_queue')

    try:
        with transaction.atomic():
            if action == 'approve':
                _action_approve(domain_request, request.user, notes)
            elif action == 'reject':
                _action_reject(domain_request, request.user, notes)
            elif action == 'mark_purchasing':
                _action_mark_purchasing(domain_request, request.user, notes)
            elif action == 'mark_purchased':
                _action_mark_purchased(domain_request, request.user, notes, request.POST)
            elif action == 'mark_dns_configured':
                _action_mark_dns_configured(domain_request, request.user, notes)
            elif action == 'mark_active':
                _action_mark_active(domain_request, request.user, notes)
            elif action == 'mark_failed':
                _action_mark_failed(domain_request, request.user, notes)
            elif action == 'cancel':
                _action_cancel(domain_request, request.user, notes)
            else:
                messages.error(request, f"Unknown action: {action}")
                return redirect(return_to)

        messages.success(
            request,
            f"Request for {domain_request.domain_name} updated to "
            f"{domain_request.get_status_display()}."
        )
    except Exception as exc:
        messages.error(request, f"Action failed: {exc}")
        # Log this properly in production
        print(f"❌ [admin_domain_action] Error: {exc}")
        import traceback
        traceback.print_exc()

    return redirect(return_to)


# ============================================================
# INDIVIDUAL ACTIONS
# ============================================================

def _log_note(domain_request, actor, note):
    """Append a timestamped note to admin_notes."""
    if not note:
        return
    stamp = timezone.now().strftime('%Y-%m-%d %H:%M')
    prefix = f"[{stamp} by {actor.username}] "
    domain_request.admin_notes = (
        (domain_request.admin_notes + "\n" if domain_request.admin_notes else "")
        + prefix + note
    )


def _action_approve(domain_request, actor, notes):
    if domain_request.status != 'pending_review':
        raise ValueError(f"Cannot approve from status '{domain_request.status}'")
    domain_request.status = 'approved'
    domain_request.reviewed_by = actor
    domain_request.reviewed_at = timezone.now()
    _log_note(domain_request, actor, notes or "Approved")
    domain_request.save()
    print(f"✅ Approved: {domain_request.domain_name}")


def _action_reject(domain_request, actor, notes):
    if domain_request.status in DomainRequest.TERMINAL_STATUSES:
        raise ValueError(f"Cannot reject terminal request '{domain_request.status}'")
    domain_request.status = 'rejected'
    domain_request.reviewed_by = actor
    domain_request.reviewed_at = timezone.now()
    _log_note(domain_request, actor, notes or "Rejected")
    domain_request.save()

    # Notify user (non-blocking; failure to send email does not roll back)
    _send_rejection_email(domain_request, notes)

    print(f"❌ Rejected: {domain_request.domain_name}")


def _action_mark_purchasing(domain_request, actor, notes):
    domain_request.status = 'purchasing'
    _log_note(domain_request, actor, notes or "Purchase started")
    domain_request.save()


def _action_mark_purchased(domain_request, actor, notes, post_data):
    domain_request.status = 'purchased'
    domain_request.registrar = (post_data.get('registrar') or 'namecheap').strip()
    domain_request.registrar_order_id = (
        post_data.get('registrar_order_id') or ''
    ).strip()

    cost = (post_data.get('purchase_cost') or '').strip()
    if cost:
        try:
            from decimal import Decimal
            domain_request.purchase_cost = Decimal(cost)
        except Exception:
            pass

    domain_request.purchase_currency = (
        post_data.get('purchase_currency') or 'USD'
    ).strip()

    domain_request.purchase_date = timezone.now()

    expiry = (post_data.get('expiry_date') or '').strip()
    if expiry:
        try:
            from datetime import datetime
            domain_request.expiry_date = timezone.make_aware(
                datetime.strptime(expiry, '%Y-%m-%d')
            )
        except Exception:
            pass

    _log_note(domain_request, actor, notes or "Domain purchased")
    domain_request.save()

    print(f"💳 Purchased: {domain_request.domain_name}")


def _action_mark_dns_configured(domain_request, actor, notes):
    domain_request.status = 'configuring_dns'
    domain_request.dns_configured = True
    domain_request.dns_verified_at = timezone.now()
    _log_note(domain_request, actor, notes or "DNS configured")
    domain_request.save()


def _action_mark_active(domain_request, actor, notes):
    """
    The critical action. Sets the domain live on the user's page.
    Side effects:
      1. Set status to 'active'
      2. Update PublishedPage.custom_domain / is_custom_domain_active
      3. Create PurchasedDomain record
      4. Set UserProfile.has_received_free_domain if applicable
      5. Send activation email to the user
    """
    if not domain_request.page:
        raise ValueError("Cannot activate a domain without a linked page")

    page = domain_request.page

    # 1. Set status
    domain_request.status = 'active'
    domain_request.activated_at = timezone.now()
    _log_note(domain_request, actor, notes or "Activated")
    domain_request.save()

    # 2. Activate on the page
    # Note: PublishedPage.custom_domain has unique=True. If the same domain
    # is somehow already assigned to another page, this will raise an
    # IntegrityError and the transaction will roll back.
    page.custom_domain = domain_request.domain_name
    page.is_custom_domain_active = True
    page.save(update_fields=['custom_domain', 'is_custom_domain_active', 'updated_at'])

    # 3. Create PurchasedDomain record (idempotent — skip if it exists)
    purchased, created = PurchasedDomain.objects.update_or_create(
        domain_name=domain_request.domain_name,
        defaults={
            'registrar': domain_request.registrar or 'namecheap',
            'purchase_date': domain_request.purchase_date or timezone.now(),
            'expiry_date': domain_request.expiry_date,
            'purchase_cost': domain_request.purchase_cost or 0,
            'currency': domain_request.purchase_currency or 'USD',
            'assigned_page': page,
            'source_request': domain_request,
            'is_active': True,
        }
    )

    # 4. Free domain flag
    if domain_request.is_free_tier:
        profile = getattr(domain_request.user, 'profile', None)
        if profile and not profile.has_received_free_domain:
            profile.has_received_free_domain = True
            profile.save(update_fields=['has_received_free_domain'])

    # 5. Activation email (non-blocking — we already saved; if it fails, log only)
    _send_activation_email(domain_request)

    print(
        f"🎉 Activated: {domain_request.domain_name} → "
        f"{page.subdomain} ({'created' if created else 'updated'} PurchasedDomain)"
    )


def _action_mark_failed(domain_request, actor, notes):
    domain_request.status = 'failed'
    _log_note(domain_request, actor, notes or "Marked as failed")
    domain_request.save()
    _send_failure_email(domain_request, notes)


def _action_cancel(domain_request, actor, notes):
    if domain_request.status == 'active':
        raise ValueError("Cannot cancel an already-active domain")
    domain_request.status = 'cancelled'
    _log_note(domain_request, actor, notes or "Cancelled")
    domain_request.save()


# ============================================================
# EMAIL NOTIFICATIONS
# ============================================================

def _send_activation_email(domain_request):
    """Send the 'your domain is live' email."""
    try:
        user = domain_request.user
        recipient = user.email
        if not recipient:
            return

        domain = domain_request.domain_name
        site_url = f"https://{domain}"

        subject = f"🎉 Your domain {domain} is live!"
        body = f"""Hi {user.first_name or user.username},

Great news — your domain {domain} is now live!

You can visit your store here:
{site_url}

It may take a few minutes for the change to be visible everywhere,
but from our side everything is configured and ready to go.

Thanks for using bynUp!
— The bynUp Team
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@bynup.store'),
            recipient_list=[recipient],
            fail_silently=True,
        )
        print(f"📧 Activation email sent to {recipient}")
    except Exception as exc:
        print(f"⚠️ Activation email failed: {exc}")


def _send_rejection_email(domain_request, notes):
    try:
        user = domain_request.user
        if not user.email:
            return
        domain = domain_request.domain_name
        subject = f"Update on your domain request: {domain}"
        body = f"""Hi {user.first_name or user.username},

Unfortunately we're unable to register {domain} for you at this time.

{f'Reason: {notes}' if notes else ''}

You can search for another domain from your dashboard. If you have
questions, please reply to this email.

— The bynUp Team
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@bynup.store'),
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as exc:
        print(f"⚠️ Rejection email failed: {exc}")


def _send_failure_email(domain_request, notes):
    try:
        user = domain_request.user
        if not user.email:
            return
        domain = domain_request.domain_name
        subject = f"⚠️ Issue with your domain request: {domain}"
        body = f"""Hi {user.first_name or user.username},

There was a problem setting up {domain}.

{f'Details: {notes}' if notes else ''}

We'll look into it and reach out. You can also contact support
if you'd like to try a different domain.

— The bynUp Team
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@bynup.store'),
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as exc:
        print(f"⚠️ Failure email failed: {exc}")



@login_required
def manage_website(request, subdomain):
    """
    Store management page.
    Shows a four-step setup checklist and a compact set of quick actions.
    """
    page = get_object_or_404(
        PublishedPage, subdomain=subdomain, user=request.user
    )

    from builder.models import Product , DomainRequest
    from payments.models import PaymentGateway

    # --- Step 1: Add your first product ---
    has_product = Product.objects.filter(
        page=page, is_active=True
    ).exists()

    # --- Step 2: Set up a payment method ---
    has_payment = PaymentGateway.objects.filter(
        page=page, is_active=True
    ).exists()

    # --- Step 3: Connect a custom domain ---
    has_domain = bool(page.custom_domain and page.is_custom_domain_active)

    has_pending_domain = False
    if not has_domain:
        has_pending_domain = DomainRequest.objects.filter(
            user=page.user,
            status__in=[
                'pending_review', 'approved', 'purchasing',
                'purchased', 'configuring_dns',
            ]
        ).exists()

    # --- Step 4: Publish your store ---
    is_published = bool(page.is_published)

    # --- Build the checklist ---
    steps = [
        {
            'id': 'add_product',
            'title': 'Add your first product',
            'description': 'Products appear on your storefront and can be added to cart.',
            'completed': has_product,
            'in_progress': False,
            'action_label': 'Add product',
            'action_url': reverse('manage_products', kwargs={'subdomain': subdomain}),
            'weight': 25,
        },
        {
            'id': 'payment_method',
            'title': 'Set up a payment method',
            'description': 'Accept payments from customers at checkout.',
            'completed': has_payment,
            'in_progress': False,
            'action_label': 'Set up payments',
            'action_url': reverse('payments:manage_gateways', kwargs={'subdomain': subdomain}),            'weight': 25,
        },
        {
            'id': 'custom_domain',
            'title': 'Connect a custom domain',
            'description': 'Give your store a professional, memorable web address.',
            'completed': has_domain,
            'in_progress': has_pending_domain,
            'action_label': 'View status' if has_pending_domain else 'Connect',
            'action_url': reverse('domains_page', kwargs={'subdomain': subdomain}),
            'weight': 25,
        },
        {
            'id': 'publish_store',
            'title': 'Publish your store',
            'description': 'Make your store visible to the world.',
            'completed': is_published,
            'in_progress': False,
            'action_label': 'Go to editor',
            'action_url': reverse(
                'editor_with_page',
                kwargs={
                    'template_name': page.template_name,
                    'subdomain': subdomain,
                }
            ),
            'weight': 25,
        },
    ]

    completed_count = sum(1 for s in steps if s['completed'])
    total_weight = sum(s['weight'] for s in steps)
    earned = sum(s['weight'] for s in steps if s['completed'])
    percentage = int(round((earned / total_weight) * 100)) if total_weight else 0

    checklist = {
        'percentage': percentage,
        'completed_count': completed_count,
        'total_count': len(steps),
        'is_complete': completed_count == len(steps),
        'steps': steps,
    }

    context = {
        'page': page,
        'checklist': checklist,
    }
    return render(request, 'builder/manage_website.html', context)

