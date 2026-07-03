"""
Core models for the Django Permissions Demo.

Models implement a multi-tenant delivery platform:
- Tenant: a business/organization using the platform
- Account: a customer account within a tenant
- Driver: delivery personnel, can service multiple tenants
- Order: placed by accounts, delivered by drivers
- UserProfile: extends Django's User with role and tenant affiliation
"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone


class Tenant(models.Model):
    """
    A Tenant is a business/organization on the platform.

    Django Permissions at work:
    - Each tenant gets its own Django Group (created via post_save signal)
    - Tenant-level permissions are assigned to this group
    - Users with tenant_admin role get these permissions
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # The Django Group that holds this tenant's permissions
    group = models.OneToOneField(
        Group, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tenant',
        help_text="Django Group for tenant-level permission assignment"
    )

    class Meta:
        ordering = ['name']
        # Custom permission: who can manage a tenant?
        permissions = [
            ("manage_tenant", "Can manage tenant settings and users"),
            ("view_tenant_analytics", "Can view tenant analytics"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('tenant_detail', kwargs={'slug': self.slug})

    @property
    def order_count(self):
        return self.accounts.aggregate(
            total=Count('orders')
        )['total'] or 0

    @property
    def active_drivers(self):
        return self.home_drivers.filter(is_active=True).count()


class Account(models.Model):
    """
    An Account belongs to exactly one Tenant (strict hierarchy).

    Django Permissions at work:
    - account_manager role gets CRUD permissions for their own accounts
    - Object-level permissions (via custom backend) restrict to own tenant
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name='accounts'
    )
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tenant', 'name']
        permissions = [
            ("manage_account", "Can manage account details"),
            ("create_order_for_account", "Can create orders for this account"),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"

    def get_absolute_url(self):
        return reverse('account_detail', kwargs={'pk': self.pk})

    @property
    def order_count(self):
        return self.orders.count()

    @property
    def pending_orders(self):
        return self.orders.filter(status__in=['pending', 'confirmed']).count()


class Driver(models.Model):
    """
    A Driver delivers orders. Drivers have a home tenant but can be shared
    across multiple tenants (M2M).

    Django Permissions at work:
    - driver role: can view assigned orders, update delivery status
    - Cross-tenant visibility controlled via shared_tenants M2M
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='driver_profile'
    )
    home_tenant = models.ForeignKey(
        Tenant, on_delete=models.PROTECT, related_name='home_drivers',
        help_text="Primary tenant this driver belongs to"
    )
    shared_tenants = models.ManyToManyField(
        Tenant, blank=True, related_name='shared_drivers',
        help_text="Additional tenants this driver can deliver for"
    )
    license_number = models.CharField(max_length=50, blank=True)
    vehicle_type = models.CharField(
        max_length=50, blank=True,
        help_text="e.g., Motorcycle, Van, Truck"
    )
    is_active = models.BooleanField(default=True)
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("manage_drivers", "Can manage driver assignments"),
            ("assign_delivery", "Can be assigned to deliveries"),
            ("update_delivery_status", "Can update order delivery status"),
        ]

    def __str__(self):
        username = self.user.username if self.user else "No User"
        return f"{username} ({self.home_tenant.name})"

    def get_absolute_url(self):
        return reverse('driver_detail', kwargs={'pk': self.pk})

    def all_tenants(self):
        """Returns all tenants this driver can work with."""
        return Tenant.objects.filter(
            Q(pk=self.home_tenant_id) | Q(shared_drivers=self)
        ).distinct()

    @property
    def delivery_count(self):
        return self.deliveries.count()

    @property
    def completed_deliveries(self):
        return self.deliveries.filter(status='delivered').count()

    @property
    def active_deliveries(self):
        return self.deliveries.filter(
            status__in=['confirmed', 'picked_up', 'in_transit']
        ).count()


class Order(models.Model):
    """
    An Order is placed by an Account and delivered by a Driver.

    Django Permissions at work:
    - create_order_for_account: account managers can create orders
    - update_delivery_status: drivers can update status
    - Object-level: users only see orders in their tenant/account scope
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='orders'
    )
    driver = models.ForeignKey(
        Driver, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deliveries'
    )
    description = models.TextField()
    pickup_address = models.TextField()
    delivery_address = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Order value in local currency"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [
            ("view_all_orders", "Can view all orders across tenants"),
            ("assign_order", "Can assign orders to drivers"),
            ("cancel_order", "Can cancel orders"),
        ]

    def __str__(self):
        return f"Order #{self.pk} - {self.account.name}"

    def get_absolute_url(self):
        return reverse('order_detail', kwargs={'pk': self.pk})

    @property
    def tenant(self):
        return self.account.tenant

    @property
    def delivery_time(self):
        """Calculate delivery time in hours, if delivered."""
        if self.delivered_at and self.created_at:
            delta = self.delivered_at - self.created_at
            return round(delta.total_seconds() / 3600, 1)
        return None

    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)


class UserProfile(models.Model):
    """
    Extends Django's User with role and tenant affiliation.

    This is NOT a custom User model — it's a profile linked via OneToOne.
    Using a profile keeps the auth system standard while adding our domain fields.

    Django Permissions at work:
    - role determines which Django Groups the user belongs to
    - tenant + accounts determine object-level access scope
    - is_super_admin bypasses all checks (Django's is_superuser)
    """
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('tenant_admin', 'Tenant Admin'),
        ('account_manager', 'Account Manager'),
        ('driver', 'Driver'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='profile'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='users',
        help_text="Primary tenant for tenant_admins, account_managers"
    )
    managed_accounts = models.ManyToManyField(
        Account, blank=True, related_name='managers',
        help_text="Accounts this user manages (for account_manager role)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("manage_permissions", "Can manage user permissions and roles"),
        ]

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    def has_tenant_access(self, tenant):
        """Check if user has access to a specific tenant."""
        if self.role == 'super_admin':
            return True
        if self.role == 'driver':
            driver = getattr(self.user, 'driver_profile', None)
            if driver:
                return driver.all_tenants().filter(pk=tenant.pk).exists()
            return False
        return self.tenant_id == tenant.pk

    def get_accessible_tenants(self):
        """Get all tenants this user can access."""
        if self.role == 'super_admin':
            return Tenant.objects.all()
        if self.role == 'driver':
            driver = getattr(self.user, 'driver_profile', None)
            if driver:
                return driver.all_tenants()
            return Tenant.objects.none()
        if self.tenant:
            return Tenant.objects.filter(pk=self.tenant_id)
        return Tenant.objects.none()
