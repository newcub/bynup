# payments/decorators.py

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum


# ============ HELPER FUNCTIONS ============

def get_user_subscription(user):
    """Get or create user's subscription"""
    from payments.models import Subscription, Plan
    
    try:
        return user.subscription
    except:
        free_plan = Plan.objects.filter(tier='free').first()
        if not free_plan:
            free_plan = Plan.objects.create(
                name='Starter',
                tier='free',
                max_websites=1,
                max_products=10,
                max_storage_mb=100,
                max_visitors=1000,
                max_form_submissions=10,
            )
        return Subscription.objects.create(user=user, plan=free_plan, status='free')


def get_user_plan(user):
    """Get user's current plan"""
    subscription = get_user_subscription(user)
    
    if not subscription.is_active or not subscription.plan:
        # Return free plan defaults
        from payments.models import Plan
        free_plan = Plan.objects.filter(tier='free').first()
        if free_plan:
            return free_plan
        
        # Fallback defaults
        class FreePlan:
            tier = 'free'
            name = 'Starter'
            max_websites = 1
            max_products = 10
            max_storage_mb = 100
            max_visitors = 1000
            max_form_submissions = 10
            max_emails = 0
            # NEW:
            max_domains = 0
            free_domain_tlds = []
            # Existing features
            custom_domain = False
            remove_branding = False
            advanced_seo = False
            priority_support = False
            email_marketing = False
            abandoned_cart = False
            discount_codes = False
            white_label = False
            custom_templates = False
        return FreePlan()
        
    return subscription.plan


def get_tier_level(user):
    """Get numeric tier level: free=0, pro=1, business=2, agency=3"""
    plan = get_user_plan(user)
    tier_map = {'free': 0, 'pro': 1, 'business': 2, 'agency': 3}
    return tier_map.get(plan.tier, 0)


# ============ USAGE COUNTING (Direct Database Queries) ============

def count_user_websites(user):
    """Count websites created by user"""
    from builder.models import PublishedPage
    return PublishedPage.objects.filter(user=user).count()


def count_user_products(user):
    """Count products created by user"""
    from builder.models import Product
    return Product.objects.filter(page__user=user).count()


def count_user_form_submissions_this_month(user):
    """Count form submissions this month"""
    from builder.models import FormSubmission
    now = timezone.now()
    return FormSubmission.objects.filter(
        page__user=user,
        submitted_at__year=now.year,
        submitted_at__month=now.month
    ).count()

def count_user_domains(user):
    """
    Count non-terminal domain requests across all of the user's pages.
    Terminal statuses (active/failed/rejected/cancelled) don't count toward the limit.
    """
    from builder.models import DomainRequest
    return DomainRequest.objects.filter(
        user=user
    ).exclude(
        status__in=DomainRequest.TERMINAL_STATUSES
    ).count()


def count_user_active_domains(user):
    """
    Count of currently active domains for the user.
    Useful for displaying on the dashboard ("You have 2 active domains").
    """
    from builder.models import DomainRequest
    return DomainRequest.objects.filter(
        user=user,
        status='active'
    ).count()


def get_user_domain_summary(user):
    """
    Full summary of a user's domain status.
    Returns a dict for use in views and the limits API.
    """
    plan = get_user_plan(user)
    active_count = count_user_active_domains(user)
    pending_count = count_user_domains(user) - active_count

    return {
        'active': active_count,
        'pending': pending_count,
        'total_used': active_count + pending_count,
        'limit': plan.max_domains,
        'free_tlds': plan.free_domain_tlds or [],
        'has_received_free_domain': getattr(
            getattr(user, 'profile', None),
            'has_received_free_domain',
            False
        ),
    }


def get_user_storage_usage_bytes(user):
    """Calculate total storage used by summing all file sizes"""
    from builder.models import BackgroundImage, ImageCustomization, Product, ProductImages
    import os
    
    total_bytes = 0
    
    # Background images
    for bg in BackgroundImage.objects.filter(page__user=user):
        if bg.image:
            try:
                total_bytes += bg.image.size
            except:
                pass
    
    # Custom images
    for img in ImageCustomization.objects.filter(page__user=user):
        if img.image:
            try:
                total_bytes += img.image.size
            except:
                pass
    
    # Product main images
    for product in Product.objects.filter(page__user=user):
        if product.main_image:
            try:
                total_bytes += product.main_image.size
            except:
                pass
    
    # Product gallery images
    for img in ProductImages.objects.filter(product__page__user=user):
        if img.image:
            try:
                total_bytes += img.image.size
            except:
                pass
    
    return total_bytes


def format_bytes(bytes_val):
    """Format bytes to human readable"""
    if bytes_val is None:
        return "Unlimited"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


# ============ LIMIT CHECKERS ============

def can_create_website(user):
    """Check if user can create another website"""
    plan = get_user_plan(user)
    current_count = count_user_websites(user)
    
    if plan.max_websites == -1:  # Unlimited
        return True, None
    
    if current_count >= plan.max_websites:
        return False, 0
    
    return True, plan.max_websites - current_count


def can_add_products(user, count=1):
    """Check if user can add products"""
    plan = get_user_plan(user)
    current_count = count_user_products(user)
    
    if plan.max_products == -1:  # Unlimited
        return True, None
    
    if current_count + count > plan.max_products:
        remaining = plan.max_products - current_count
        return False, max(0, remaining)
    
    return True, plan.max_products - (current_count + count)


def can_submit_form(user):
    """Check if user can submit another form this month"""
    plan = get_user_plan(user)
    current_count = count_user_form_submissions_this_month(user)
    
    if plan.max_form_submissions == -1:  # Unlimited
        return True, None
    
    if current_count >= plan.max_form_submissions:
        return False, 0
    
    return True, plan.max_form_submissions - current_count


def can_upload_file(user, file_size_bytes):
    """Check if user has enough storage for a file"""
    plan = get_user_plan(user)
    
    if plan.max_storage_mb == -1:  # Unlimited
        return True, None
    
    limit_bytes = plan.max_storage_mb * 1024 * 1024
    current_bytes = get_user_storage_usage_bytes(user)
    new_total = current_bytes + file_size_bytes
    
    if new_total > limit_bytes:
        remaining = limit_bytes - current_bytes
        return False, remaining
    
    return True, limit_bytes - new_total

def can_add_domain(user):
    """
    Check if user can request another domain.
    Returns (bool, remaining_or_none, reason_str_or_none).
    """
    plan = get_user_plan(user)

    # Unlimited domains (future-proofing; not used by current plans)
    if plan.max_domains == -1:
        return True, None, None

    # Plan doesn't include domains at all
    if plan.max_domains == 0:
        return False, 0, "Your plan does not include custom domains."

    current_count = count_user_domains(user)

    if current_count >= plan.max_domains:
        return False, 0, (
            f"You've reached your plan's domain limit "
            f"({current_count}/{plan.max_domains})."
        )

    return True, plan.max_domains - current_count, None


def has_feature(user, feature_name):
    """Check if user's plan has a specific feature"""
    plan = get_user_plan(user)
    
    features = {
        'custom_domain': plan.custom_domain,
        'remove_branding': plan.remove_branding,
        'advanced_seo': plan.advanced_seo,
        'priority_support': plan.priority_support,
        'email_marketing': plan.email_marketing,
        'abandoned_cart': plan.abandoned_cart,
        'discount_codes': plan.discount_codes,
        'white_label': plan.white_label,
        'custom_templates': plan.custom_templates,
    }
    
    return features.get(feature_name, False)


# ============ DECORATORS ============

def pro_required(view_func):
    """Require Pro plan or higher"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if get_tier_level(request.user) < 1:
            msg = "This feature requires a Pro plan or higher."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def business_required(view_func):
    """Require Business plan or higher"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if get_tier_level(request.user) < 2:
            msg = "This feature requires a Business plan or higher."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def agency_required(view_func):
    """Require Agency plan"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if get_tier_level(request.user) < 3:
            msg = "This feature requires an Agency plan."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def paid_plan_required(view_func):
    """Require any paid plan (Pro, Business, or Agency)"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if get_tier_level(request.user) < 1:
            msg = "This feature requires a paid subscription."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


# payments/decorators.py - Enhanced detection

def check_website_limit(view_func):
    """
    Smart decorator that:
    - Only checks limits when CREATING new websites
    - Automatically detects edit operations and allows them
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        # ============ AGGRESSIVE EDIT DETECTION ============
        is_edit_operation = False
        
        # 1. Check URL kwargs for subdomain
        if kwargs.get('subdomain'):
            is_edit_operation = True
            print(f"✅ Edit detected via kwargs['subdomain']: {kwargs.get('subdomain')}")
        
        # 2. Check URL path for editor pattern
        if '/editor/' in request.path and kwargs.get('subdomain'):
            is_edit_operation = True
            print(f"✅ Edit detected via /editor/ path pattern")
        
        # 3. Check GET parameters
        if request.GET.get('edit') or request.GET.get('page_subdomain') or request.GET.get('page'):
            is_edit_operation = True
            print(f"✅ Edit detected via GET parameters")
        
        # 4. Check if the subdomain exists and belongs to user
        subdomain = kwargs.get('subdomain')
        if subdomain:
            from builder.models import PublishedPage
            existing_page = PublishedPage.objects.filter(
                subdomain=subdomain, 
                user=request.user
            ).first()
            if existing_page:
                is_edit_operation = True
                print(f"✅ Edit detected - existing page found: {subdomain}")
        
        # 5. Check POST data
        if request.method == 'POST':
            try:
                import json
                if request.body:
                    data = json.loads(request.body)
                    if data.get('page_subdomain') or data.get('is_editing') or data.get('subdomain'):
                        is_edit_operation = True
                        print(f"✅ Edit detected via POST data")
            except:
                pass
        
        # 6. Check view name
        view_name = view_func.__name__
        if view_name in ['editor', 'edit_page', 'publish_page'] and kwargs.get('subdomain'):
            is_edit_operation = True
            print(f"✅ Edit detected via view name: {view_name}")
        
        # If ANY edit indicator is found, skip limit check
        if is_edit_operation:
            print(f"🟢 ALLOWING: Edit operation for {request.user.email}")
            return view_func(request, *args, **kwargs)
        
        # ============ CREATE OPERATION - CHECK LIMITS ============
        print(f"🔴 CHECKING: Create operation for {request.user.email}")
        
        can_create, remaining = can_create_website(request.user)
        
        if not can_create:
            plan = get_user_plan(request.user)
            current = count_user_websites(request.user)
            msg = f"You've reached your website limit ({current}/{plan.max_websites}). Upgrade to create more."
            
            print(f"❌ BLOCKED: {request.user.email} - {msg}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False, 
                    'error': 'limit_exceeded', 
                    'message': msg,
                    'current': current,
                    'limit': plan.max_websites
                })
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        print(f"🟢 ALLOWING: Create operation for {request.user.email} ({current}/{plan.max_websites})")
        return view_func(request, *args, **kwargs)
    
    return wrapped_view

    

def check_product_limit(count=1):
    """Check if user can add products"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            can_add, remaining = can_add_products(request.user, count)
            
            if not can_add:
                plan = get_user_plan(request.user)
                current = count_user_products(request.user)
                msg = f"Product limit reached ({current}/{plan.max_products}). You can add {remaining} more. Upgrade to add more."
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'limit_exceeded',
                        'current': current,
                        'limit': plan.max_products,
                        'remaining': remaining,
                        'message': msg
                    })
                
                messages.error(request, msg)
                return redirect('payments:pricing')
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def check_form_submission_limit(view_func):
    """Check if user can submit another form this month"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # Get the page owner from the subdomain
        subdomain = kwargs.get('subdomain')
        
        if subdomain:
            from builder.models import PublishedPage
            page = PublishedPage.objects.filter(subdomain=subdomain).first()
            if page:
                user = page.user
                
                can_submit, remaining = can_submit_form(user)
                
                if not can_submit:
                    plan = get_user_plan(user)
                    current = count_user_form_submissions_this_month(user)
                    msg = f"Monthly form submission limit reached ({current}/{plan.max_form_submissions})."
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'limit_exceeded',
                            'current': current,
                            'limit': plan.max_form_submissions,
                            'message': msg
                        })
                    
                    messages.error(request, msg)
                    return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def check_storage_before_upload(file_field='image'):
    """Check storage before file upload"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            uploaded_file = request.FILES.get(file_field)
            if not uploaded_file and request.FILES:
                uploaded_file = list(request.FILES.values())[0]
            
            if uploaded_file:
                can_upload, remaining = can_upload_file(request.user, uploaded_file.size)
                
                if not can_upload:
                    plan = get_user_plan(request.user)
                    current_bytes = get_user_storage_usage_bytes(request.user)
                    current_mb = current_bytes / (1024 * 1024)
                    limit_mb = plan.max_storage_mb
                    remaining_str = format_bytes(remaining) if remaining else "0 B"
                    
                    msg = f"Storage full! Used: {current_mb:.1f}MB / {limit_mb}MB. Remaining: {remaining_str}"
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'storage_full',
                            'current_mb': round(current_mb, 2),
                            'limit_mb': limit_mb,
                            'remaining_bytes': remaining,
                            'message': msg
                        })
                    
                    messages.error(request, msg)
                    return redirect('payments:pricing')
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def check_domain_eligibility(view_func):
    """
    Runs all eligibility checks before allowing a domain request.

    Checks (in order):
      1. User is authenticated
      2. Subscription is active
      3. Plan has domains available (max_domains > 0)
      4. User hasn't hit their domain count limit
      5. Requested TLD is in the plan's free_domain_tlds
      6. User hasn't already received a free domain

    On success, attaches to request:
      - request.domain_plan
      - request.domain_free_tlds
      - request.domain_is_free_tier
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        import json as _json

        if not request.user.is_authenticated:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'not_authenticated'})
            return redirect('accounts:login')

        def _error(msg, code='ineligible'):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': code, 'message': msg})
            messages.error(request, msg)
            return redirect('payments:pricing')

        # --- Extract domain + tld from request (POST or JSON body) ---
        domain_name = ''
        tld = ''

        if request.method == 'POST':
            # Try form POST first
            domain_name = (request.POST.get('domain_name') or '').strip().lower()
            tld = (request.POST.get('tld') or '').strip().lower()

            # Fall back to JSON body
            if not domain_name:
                try:
                    data = _json.loads(request.body or b'{}')
                    domain_name = (data.get('domain_name') or '').strip().lower()
                    tld = (data.get('tld') or '').strip().lower()
                except Exception:
                    pass

        if not domain_name or not tld:
            return _error("Domain name and TLD are required.", 'invalid_input')

        # --- 1. Subscription must be active ---
        subscription = get_user_subscription(request.user)
        if not subscription.is_active:
            return _error(
                "Your subscription is not active. Please renew to add domains.",
                'subscription_inactive'
            )

        plan = subscription.plan or get_user_plan(request.user)

        # --- 2. Plan must include domains ---
        if not plan.max_domains or plan.max_domains == 0:
            return _error(
                "Upgrade to a paid plan to add a custom domain.",
                'upgrade_required'
            )

        # --- 3. Domain count check ---
        can_add, remaining, reason = can_add_domain(request.user)
        if not can_add:
            return _error(reason or "Domain limit reached.", 'limit_exceeded')

        # --- 4. TLD eligibility ---
        free_tlds = plan.free_domain_tlds or []
        is_free_tier = tld in free_tlds

        if not is_free_tier:
            return _error(
                f"'.{tld}' is not included in your plan. "
                f"Please contact us for pricing.",
                'tld_not_included'
            )

        # --- 5. Free domain history check ---
        profile = getattr(request.user, 'profile', None)
        if is_free_tier and profile and profile.has_received_free_domain:
            return _error(
                "You've already received a free domain on your account. "
                "Contact support if you need additional domains.",
                'free_domain_used'
            )

        # --- Attach validated context for the view ---
        request.domain_plan = plan
        request.domain_free_tlds = free_tlds
        request.domain_is_free_tier = is_free_tier
        request.domain_name = domain_name
        request.domain_tld = tld

        return view_func(request, *args, **kwargs)
    return wrapped_view


def custom_domain_required(view_func):
    """Require custom domain feature"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not has_feature(request.user, 'custom_domain'):
            msg = "Custom domain requires a Pro plan or higher."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def remove_branding_required(view_func):
    """Require remove branding feature"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not has_feature(request.user, 'remove_branding'):
            msg = "Removing platform branding requires a Pro plan or higher."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def email_marketing_required(view_func):
    """Require email marketing feature"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not has_feature(request.user, 'email_marketing'):
            msg = "Email marketing requires a Pro plan or higher."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def abandoned_cart_required(view_func):
    """Require abandoned cart feature"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not has_feature(request.user, 'abandoned_cart'):
            msg = "Abandoned cart recovery requires a Business plan or higher."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def discount_codes_required(view_func):
    """Require discount codes feature"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not has_feature(request.user, 'discount_codes'):
            msg = "Discount codes require a Business plan or higher."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def advanced_seo_required(view_func):
    """Require advanced SEO feature"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not has_feature(request.user, 'advanced_seo'):
            msg = "Advanced SEO requires a Pro plan or higher."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def white_label_required(view_func):
    """Require white label feature"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not has_feature(request.user, 'white_label'):
            msg = "White label requires an Agency plan."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def custom_templates_required(view_func):
    """Require custom templates feature"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not has_feature(request.user, 'custom_templates'):
            msg = "Custom template creation requires an Agency plan."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'upgrade_required', 'message': msg})
            
            messages.error(request, msg)
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


# ============ API HELPER ============

def get_user_limits_status(user):
    """Get complete limits status for API responses"""
    plan = get_user_plan(user)

    websites_current = count_user_websites(user)
    products_current = count_user_products(user)
    forms_current = count_user_form_submissions_this_month(user)
    storage_bytes = get_user_storage_usage_bytes(user)
    domain_summary = get_user_domain_summary(user)

    return {
        'tier': plan.tier,
        'plan_name': plan.name if hasattr(plan, 'name') else 'Free',
        'is_paid': get_tier_level(user) >= 1,

        'websites': {
            'used': websites_current,
            'limit': plan.max_websites if plan.max_websites != -1 else 'Unlimited',
            'remaining': None if plan.max_websites == -1 else max(0, plan.max_websites - websites_current),
        },
        'products': {
            'used': products_current,
            'limit': plan.max_products if plan.max_products != -1 else 'Unlimited',
            'remaining': None if plan.max_products == -1 else max(0, plan.max_products - products_current),
        },
        'forms_this_month': {
            'used': forms_current,
            'limit': plan.max_form_submissions if plan.max_form_submissions != -1 else 'Unlimited',
            'remaining': None if plan.max_form_submissions == -1 else max(0, plan.max_form_submissions - forms_current),
        },
        'storage': {
            'used_bytes': storage_bytes,
            'used_mb': round(storage_bytes / (1024 * 1024), 2),
            'limit_mb': plan.max_storage_mb if plan.max_storage_mb != -1 else 'Unlimited',
            'remaining_bytes': None if plan.max_storage_mb == -1 else max(0, (plan.max_storage_mb * 1024 * 1024) - storage_bytes),
            'percentage': 0 if plan.max_storage_mb == -1 else round((storage_bytes / (plan.max_storage_mb * 1024 * 1024)) * 100, 1),
        },

        # NEW: Domains block
        'domains': {
            'active': domain_summary['active'],
            'pending': domain_summary['pending'],
            'used': domain_summary['total_used'],
            'limit': domain_summary['limit'] if domain_summary['limit'] != -1 else 'Unlimited',
            'remaining': None if domain_summary['limit'] == -1 else max(
                0, domain_summary['limit'] - domain_summary['total_used']
            ),
            'free_tlds': domain_summary['free_tlds'],
            'has_received_free_domain': domain_summary['has_received_free_domain'],
        },

        'features': {
            'custom_domain': plan.custom_domain,
            'remove_branding': plan.remove_branding,
            'advanced_seo': plan.advanced_seo,
            'priority_support': plan.priority_support,
            'email_marketing': plan.email_marketing,
            'abandoned_cart': plan.abandoned_cart,
            'discount_codes': plan.discount_codes,
            'white_label': plan.white_label,
            'custom_templates': plan.custom_templates,
        }
    }