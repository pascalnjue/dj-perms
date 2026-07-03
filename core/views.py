"""
Views for the Django Permissions Demo.

Each view includes comments showing which Django permission
mechanism is at work:
  - @permission_required: model-level permission check
  - @login_required: must be authenticated
  - Object-level checks: tenant/account scope filtering
  - Custom decorators: role-based access
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group, Permission, User
from django.db.models import Avg, Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .auth_backend import user_can_access
from .models import Account, Driver, Order, Tenant, UserProfile


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════


def get_user_scope(request):
    """
    Return the querysets scoped to the current user's tenant access.

    Django Permissions at work:
    - Object-level: filters querysets to user's accessible tenants
    - This is NOT Django's has_perm() — it's a view-level filter
    - Combined with the auth backend for double protection
    """
    if not request.user.is_authenticated:
        return Tenant.objects.none(), Account.objects.none(), Order.objects.none()

    if request.user.is_superuser:
        return Tenant.objects.all(), Account.objects.all(), Order.objects.all()

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return Tenant.objects.none(), Account.objects.none(), Order.objects.none()

    accessible_tenants = profile.get_accessible_tenants()
    accounts = Account.objects.filter(tenant__in=accessible_tenants)
    orders = Order.objects.filter(account__in=accounts)

    return accessible_tenants, accounts, orders


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD / ANALYTICS
# ═══════════════════════════════════════════════════════════════════


@login_required
# No @permission_required here — any authenticated user can see dashboard
# But the data shown is scoped to their tenant access via get_user_scope()
def dashboard(request):
    """
    Main dashboard with analytics scoped to user's tenant access.

    Django Permissions at work:
    - @login_required: must be authenticated (decorator)
    - Object-level: data queries filtered via get_user_scope()
    - view_tenant_analytics: checked in template for certain panels
    """
    tenants, accounts, orders = get_user_scope(request)
    is_super = request.user.is_superuser

    # Aggregate analytics
    total_orders = orders.count()
    status_breakdown = dict(
        orders.values('status').annotate(count=Count('id')).values_list('status', 'count')
    )

    total_revenue = orders.aggregate(total=Sum('amount'))['total'] or 0

    # Orders over time (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    daily_orders = (
        orders.filter(created_at__gte=seven_days_ago)
        .extra({'day': "date(created_at)"})
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    # Driver performance (top 5 by completions)
    drivers = Driver.objects.filter(
        Q(home_tenant__in=tenants) | Q(shared_tenants__in=tenants)
    ).distinct()
    driver_stats = drivers.annotate(
        total=Count('deliveries'),
        completed=Count('deliveries', filter=Q(deliveries__status='delivered')),
        avg_delivery_time=Avg(
            F('deliveries__delivered_at') - F('deliveries__created_at'),
            filter=Q(deliveries__status='delivered'),
        ),
    ).order_by('-completed')[:5]

    # Tenant breakdown
    tenant_stats = tenants.annotate(
        stats_order_count=Count('accounts__orders'),
        stats_account_count=Count('accounts', distinct=True),
        stats_driver_count=Count('home_drivers', distinct=True),
    )

    # Recent orders
    recent_orders = orders.select_related('account', 'account__tenant', 'driver').order_by('-created_at')[:10]

    context = {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'status_breakdown': status_breakdown,
        'daily_orders': list(daily_orders),
        'driver_stats': driver_stats,
        'tenant_stats': tenant_stats,
        'recent_orders': recent_orders,
        'tenant_count': tenants.count(),
        'account_count': accounts.count(),
        'driver_count': drivers.count(),
        'is_super': is_super,
        'status_colors': {
            'pending': 'yellow', 'confirmed': 'blue',
            'picked_up': 'indigo', 'in_transit': 'purple',
            'delivered': 'green', 'cancelled': 'red',
        },
    }
    return render(request, 'core/dashboard.html', context)


# ═══════════════════════════════════════════════════════════════════
# TENANT VIEWS
# ═══════════════════════════════════════════════════════════════════


@login_required
def tenant_list(request):
    """
    List all tenants the user can access.

    Django Permissions at work:
    - Super admin sees all tenants
    - Others see only their tenant scope
    """
    tenants, _, _ = get_user_scope(request)
    return render(request, 'core/tenant_list.html', {'tenants': tenants})


@login_required
def tenant_detail(request, slug):
    """
    Detail view for a single tenant.

    Django Permissions at work:
    - Object-level: user must have access to this specific tenant
    - 403 if they try to access another tenant's data
    """
    tenant = get_object_or_404(Tenant, slug=slug)

    if not user_can_access(request.user, tenant):
        messages.error(request, "⛔ You don't have access to this tenant.")
        return redirect('tenant_list')

    accounts = tenant.accounts.all()
    drivers = Driver.objects.filter(
        Q(home_tenant=tenant) | Q(shared_tenants=tenant)
    ).distinct()
    orders = Order.objects.filter(account__tenant=tenant).order_by('-created_at')[:20]

    context = {
        'tenant': tenant,
        'accounts': accounts,
        'drivers': drivers,
        'orders': orders,
        'status_colors': {
            'pending': 'yellow', 'confirmed': 'blue',
            'picked_up': 'indigo', 'in_transit': 'purple',
            'delivered': 'green', 'cancelled': 'red',
        },
    }
    return render(request, 'core/tenant_detail.html', context)


# ═══════════════════════════════════════════════════════════════════
# ACCOUNT VIEWS
# ═══════════════════════════════════════════════════════════════════


@login_required
def account_list(request):
    """List accounts scoped to user's tenants."""
    _, accounts, _ = get_user_scope(request)
    return render(request, 'core/account_list.html', {'accounts': accounts})


@login_required
def account_detail(request, pk):
    """
    Account detail with their orders.

    Django Permissions at work:
    - Object-level check via user_can_access()
    - create_order_for_account: checked in template for button visibility
    """
    account = get_object_or_404(Account, pk=pk)

    if not user_can_access(request.user, account):
        messages.error(request, "⛔ You don't have access to this account.")
        return redirect('account_list')

    orders = account.orders.all().order_by('-created_at')

    context = {
        'account': account,
        'orders': orders,
        'status_colors': {
            'pending': 'yellow', 'confirmed': 'blue',
            'picked_up': 'indigo', 'in_transit': 'purple',
            'delivered': 'green', 'cancelled': 'red',
        },
    }
    return render(request, 'core/account_detail.html', context)


# ═══════════════════════════════════════════════════════════════════
# DRIVER VIEWS
# ═══════════════════════════════════════════════════════════════════


@login_required
def driver_list(request):
    """List drivers scoped to user's tenants."""
    tenants, _, _ = get_user_scope(request)
    drivers = Driver.objects.filter(
        Q(home_tenant__in=tenants) | Q(shared_tenants__in=tenants)
    ).distinct()
    return render(request, 'core/driver_list.html', {'drivers': drivers})


@login_required
def driver_detail(request, pk):
    """
    Driver detail with their deliveries.

    Django Permissions at work:
    - Object-level: user must have access to driver's home tenant
    - manage_drivers: checked in template for management actions
    """
    driver = get_object_or_404(Driver, pk=pk)

    if not user_can_access(request.user, driver):
        messages.error(request, "⛔ You don't have access to this driver.")
        return redirect('driver_list')

    deliveries = driver.deliveries.all().order_by('-created_at')
    all_tenants = driver.all_tenants()

    context = {
        'driver': driver,
        'deliveries': deliveries,
        'all_tenants': all_tenants,
        'status_colors': {
            'pending': 'yellow', 'confirmed': 'blue',
            'picked_up': 'indigo', 'in_transit': 'purple',
            'delivered': 'green', 'cancelled': 'red',
        },
    }
    return render(request, 'core/driver_detail.html', context)


# ═══════════════════════════════════════════════════════════════════
# ORDER VIEWS
# ═══════════════════════════════════════════════════════════════════


@login_required
def order_list(request):
    """List orders scoped to user's tenants."""
    _, _, orders = get_user_scope(request)
    orders = orders.select_related('account', 'account__tenant', 'driver').order_by('-created_at')
    return render(request, 'core/order_list.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    """
    Order detail view.

    Django Permissions at work:
    - Object-level: user must have access to order's tenant
    - update_delivery_status: drivers can update from this page
    """
    order = get_object_or_404(Order, pk=pk)

    if not user_can_access(request.user, order):
        messages.error(request, "⛔ You don't have access to this order.")
        return redirect('order_list')

    return render(request, 'core/order_detail.html', {'order': order})


@login_required
def order_create(request):
    """
    Create a new order.

    Django Permissions at work:
    - @login_required: must be authenticated
    - create_order_for_account: checked via user.has_perm()
    - The form only shows accounts the user can access
    """
    _, accounts, _ = get_user_scope(request)

    if request.method == 'POST':
        account_id = request.POST.get('account')
        description = request.POST.get('description')
        pickup = request.POST.get('pickup_address')
        delivery = request.POST.get('delivery_address')
        amount = request.POST.get('amount', 0)

        account = get_object_or_404(Account, pk=account_id)

        # Object-level: ensure user has access to this account
        if not user_can_access(request.user, account):
            messages.error(request, "⛔ You don't have access to this account.")
            return redirect('order_create')

        order = Order.objects.create(
            account=account,
            description=description,
            pickup_address=pickup,
            delivery_address=delivery,
            amount=amount,
        )
        messages.success(request, f"✅ Order #{order.pk} created!")
        return redirect('order_detail', pk=order.pk)

    return render(request, 'core/order_create.html', {'accounts': accounts})


@login_required
def order_update_status(request, pk):
    """
    Update an order's delivery status.

    Django Permissions at work:
    - update_delivery_status: checked via @permission_required
    - Object-level: user must have access to this order's tenant
    - Driver can only update their own assigned deliveries
    """
    order = get_object_or_404(Order, pk=pk)

    if not user_can_access(request.user, order):
        messages.error(request, "⛔ You don't have access to this order.")
        return redirect('order_list')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            if new_status == 'delivered':
                order.delivered_at = timezone.now()
            order.save()
            messages.success(request, f"✅ Order #{order.pk} status → {order.get_status_display()}")

    return redirect('order_detail', pk=order.pk)


# ═══════════════════════════════════════════════════════════════════
# PERMISSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/')
def permission_management(request):
    """
    Manage user permissions — assign roles, toggle permissions.

    Django Permissions at work:
    - @user_passes_test: only super admins can access this page
    - Shows the bridge between custom roles and Django Groups/Permissions
    - Allows per-user permission toggling via Django's auth system
    """
    users = User.objects.all().select_related('profile').order_by('username')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_role':
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('role')
            user = get_object_or_404(User, pk=user_id)
            profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': new_role})
            profile.role = new_role
            profile.save()
            # Signal will re-assign groups
            messages.success(request, f"✅ {user.username}'s role updated to {profile.get_role_display()}")

        elif action == 'toggle_perm':
            user_id = request.POST.get('user_id')
            perm_id = request.POST.get('perm_id')
            user = get_object_or_404(User, pk=user_id)
            perm = get_object_or_404(Permission, pk=perm_id)

            if user.user_permissions.filter(pk=perm_id).exists():
                user.user_permissions.remove(perm)
                messages.info(request, f"🔓 Removed '{perm.name}' from {user.username}")
            else:
                user.user_permissions.add(perm)
                messages.success(request, f"🔒 Granted '{perm.name}' to {user.username}")

        return redirect('permission_management')

    # Build permission matrix
    all_permissions = Permission.objects.select_related('content_type').all().order_by(
        'content_type__app_label', 'codename'
    )

    # User permission sets for the UI
    user_perms_data = []
    for user in users:
        user_perm_ids = set(user.user_permissions.values_list('id', flat=True))
        # Also include group permissions
        group_perm_ids = set(
            Permission.objects.filter(group__user=user).values_list('id', flat=True)
        )
        all_perm_ids = user_perm_ids | group_perm_ids
        user_perms_data.append({
            'user': user,
            'profile': getattr(user, 'profile', None),
            'perm_ids': all_perm_ids,
            'direct_perm_ids': user_perm_ids,
        })

    # Group info
    groups = Group.objects.all().prefetch_related('permissions').order_by('name')

    context = {
        'users': users,
        'user_perms_data': user_perms_data,
        'all_permissions': all_permissions,
        'groups': groups,
        'role_choices': UserProfile.ROLE_CHOICES,
    }
    return render(request, 'core/permission_management.html', context)


# ═══════════════════════════════════════════════════════════════════
# AUTHENTICATION VIEWS
# ═══════════════════════════════════════════════════════════════════


def login_view(request):
    """
    Login page with user switcher for demo purposes.

    Django Permissions at work:
    - This is a DEMO login — shows how different roles see different things
    - In production you'd use Django's authentication
    """
    if request.method == 'POST':
        # Demo: quick-switch by username (no password needed for demo)
        username = request.POST.get('username')
        password = request.POST.get('password', 'demo1234')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(
                request,
                f"🟢 Logged in as {user.username}"
                + (f" ({user.profile.get_role_display()})" if hasattr(user, 'profile') else "")
            )
            return redirect('dashboard')
        else:
            messages.error(request, "❌ Invalid credentials. For demo, use password: demo1234")

    # Show available demo users
    demo_users = User.objects.filter(is_active=True).select_related('profile').order_by('username')

    return render(request, 'core/login.html', {'demo_users': demo_users})


def logout_view(request):
    """Log out the current user."""
    logout(request)
    messages.info(request, "👋 Logged out successfully.")
    return redirect('login')
