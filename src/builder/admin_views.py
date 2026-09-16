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