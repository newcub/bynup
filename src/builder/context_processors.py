# builder/context_processors.py
from accounts.models import WebsiteUser
from django.conf import settings
from builder.models import *

def website_auth_context(request):
    """Add website authentication context to all templates"""
    context = {}
    
    if hasattr(request, 'published_page') and request.published_page:
        page = request.published_page
        
        # Check if user is a member of this website
        is_website_member = False
        website_user_data = {}
        
        if request.user.is_authenticated:
            try:
                website_user = WebsiteUser.objects.get(
                    user=request.user,
                    website=page,
                    is_active=True
                )
                is_website_member = True
                website_user_data = {
                    'role': website_user.role,
                    'joined_date': website_user.registered_at,
                    'is_verified': website_user.is_verified,
                }
            except WebsiteUser.DoesNotExist:
                pass
        
        # Generate URLs
        from django.urls import reverse
        from accounts.helpers import get_website_homepage_url
        homepage_url = get_website_homepage_url(page)
        login_url = reverse('accounts:universal_login') + f'?website_id={page.id}&next={homepage_url}'
        logout_url = reverse('accounts:logout') + f'?website_id={page.id}&next={homepage_url}'
        # logout_url = reverse('accounts:logout') + f'?website_id={page.id}'

        register_url = reverse('accounts:website_register', args=[page.subdomain])
        
        context.update({
            'is_website_member': is_website_member,
            'website_user_data': website_user_data,
            'website_login_url': login_url,
            'website_register_url': register_url,
            'website_logout_url': logout_url,
            'website_homepage_url':homepage_url,
            'show_auth_links': True,  # Flag to show auth widgets
        })
    
    return context

# Add to settings.py TEMPLATES context_processors:
# 'builder.context_processors.website_auth_context',



from .models import RecentlyViewedProduct

def recently_viewed_products(request):
    """Add recently viewed products to template context"""
    context = {}
    
    if hasattr(request, 'published_page') and request.published_page:
        page = request.published_page
        
        # Get session key
        session_key = request.session.session_key
        
        if session_key or request.user.is_authenticated:
            # Get recently viewed products
            if request.user.is_authenticated:
                recently_viewed = RecentlyViewedProduct.objects.filter(
                    page=page,
                    user=request.user
                ).select_related('product')[:10]
            else:
                recently_viewed = RecentlyViewedProduct.objects.filter(
                    page=page,
                    session_key=session_key
                ).select_related('product')[:10]
            
            context['recently_viewed_products'] = recently_viewed
    
    return context


def domain_listing(request):
    site_domain = settings.SITE_DOMAIN
    # Ensure the domain has a protocol
    if site_domain and not site_domain.startswith(('http://', 'https://')):
        # In production, use https
        if settings.DEBUG:
            site_domain = f"http://{site_domain}"
        else:
            site_domain = f"https://{site_domain}"
    
    return {
        'SITE_DOMAIN': site_domain
    }


# builder/context_processors.py

from payments.decorators import get_user_subscription


def branding_context(request):
    """
    Check if user is on a paid plan and determine if branding should be shown.
    Returns context for footer branding.
    """
    show_branding = True
    user_plan = 'free'
    
    # Check if we have a published page and its owner
    if hasattr(request, 'published_page') and request.published_page:
        page_owner = request.published_page.user
        
        try:
            subscription = get_user_subscription(page_owner)
            if subscription and subscription.is_active and subscription.plan:
                # Hide branding if user has remove_branding feature
                if subscription.plan.remove_branding:
                    show_branding = False
                user_plan = subscription.plan.tier
        except:
            pass
    
    # Also check if the current user is authenticated (for preview/editor)
    elif request.user.is_authenticated:
        try:
            subscription = get_user_subscription(request.user)
            if subscription and subscription.is_active and subscription.plan:
                if subscription.plan.remove_branding:
                    show_branding = False
                user_plan = subscription.plan.tier
        except:
            pass
    
    return {
        'show_bynup_branding': show_branding,
        'bynup_plan': user_plan,
        'bynup_url': 'https://bynup.store',
    }


# builder/context_processors.py

def currency_context(request):
    """
    Makes currency information available in all templates.
    """
    # Check if we have a published page from middleware
    if hasattr(request, 'published_page') and request.published_page:
        page = request.published_page
        return {
            'store_currency': {
                'code': page.currency_code,
                'symbol': page.currency_symbol,
                'position': page.currency_position,
                'thousand_separator': page.thousand_separator,
                'decimal_separator': page.decimal_separator,
                'decimal_places': page.decimal_places,
                # Helper for formatting prices
                'format_price': page.format_price,
            }
        }
    
    # Default fallback
    return {
        'store_currency': {
            'code': 'USD',
            'symbol': '$',
            'position': 'before',
            'thousand_separator': ',',
            'decimal_separator': '.',
            'decimal_places': 2,
        }
    }


# builder/context_processors.py

def subscription_tiers(request):
    """Context processor for subscription tiers and published pages"""
    from django.contrib.auth.models import AnonymousUser
    
    # Default values for all users
    pages = []
    limits = {
        'tier': 'free',
        'plan_name': 'Free',
        'is_paid': False,
        'websites': {'used': 0, 'limit': 1},
        'products': {'used': 0, 'limit': 10},
        'forms_this_month': {'used': 0, 'limit': 10},
        'storage': {'used_mb': 0, 'limit_mb': 100, 'percentage': 0},
    }
    
    # Only fetch user-specific data if authenticated
    if hasattr(request, 'user') and request.user.is_authenticated:
        # Safe to use request.user now
        if not isinstance(request.user, AnonymousUser):
            try:
                from payments.decorators import get_user_limits_status
                
                pages = PublishedPage.objects.filter(
                    user_id=request.user.id  # Using user_id is safer
                ).exclude(
                    subdomain__isnull=True
                ).exclude(
                    subdomain=''
                ).order_by('-created_at')
                
                try:
                    user_limits = get_user_limits_status(request.user)
                    if user_limits:
                        limits = user_limits
                except Exception as e:
                    print(f"Error getting limits: {e}")
                    
            except Exception as e:
                print(f"Error in subscription_tiers: {e}")
    
    return {
        'published_pages': pages,
        'limits': limits,
    }




def brand_context(request):
    """
    Add brand_name to all template contexts.
    """
    context = {
        'brand_name': 'My Store',  # Default fallback
        'page': None,
    }
    
    # Check if we have a published_page in the request (set by middleware)
    if hasattr(request, 'published_page') and request.published_page:
        page = request.published_page
        context['brand_name'] = page.brand_name or 'My Store'
        context['page'] = page
    
    # For editor, check if page is in request
    elif hasattr(request, 'page'):
        context['brand_name'] = getattr(request.page, 'brand_name', 'My Store')
        context['page'] = request.page
    
    # Check session for brand_name (for onboarding)
    elif request.session.get('brand_name'):
        context['brand_name'] = request.session.get('brand_name')
    
    return context


def pending_domain_requests(request):
    """
    Make the pending domain request count available to all templates
    for staff users. Non-staff users get 0 (never causes a query for them).
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return {'pending_domain_requests_count': 0}

    try:
        from builder.models import DomainRequest
        count = DomainRequest.objects.filter(status='pending_review').count()
        return {'pending_domain_requests_count': count}
    except Exception:
        return {'pending_domain_requests_count': 0}

