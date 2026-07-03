"""
Signals for auto-creating tenant groups and assigning default permissions.

Django Permissions at work:
- post_save on Tenant creates a matching Django Group
- post_save on UserProfile assigns the user to the correct groups
- This shows how signals automate permission setup (vs manual admin UI)
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Account, Driver, Order, Tenant, UserProfile


def _get_or_create_perm(codename, name, model_class):
    """Helper to get or create a custom permission on a model's content type."""
    ct = ContentType.objects.get_for_model(model_class)
    perm, _ = Permission.objects.get_or_create(
        codename=codename,
        content_type=ct,
        defaults={'name': name},
    )
    return perm


TENANT_ADMIN_PERMS = [
    # Tenant-level
    ('manage_tenant', Tenant),
    ('view_tenant_analytics', Tenant),
    # Account management
    ('manage_account', Account),
    ('create_order_for_account', Account),
    # Driver management
    ('manage_drivers', Driver),
    ('assign_delivery', Driver),
    # Order management
    ('view_all_orders', Order),
    ('assign_order', Order),
    ('cancel_order', Order),
]

ACCOUNT_MANAGER_PERMS = [
    ('create_order_for_account', Account),
    # Can view their own orders (object-level, not model-level)
]

DRIVER_PERMS = [
    ('assign_delivery', Driver),
    ('update_delivery_status', Order),
]


@receiver(post_save, sender=Tenant)
def create_tenant_group(sender, instance, created, **kwargs):
    """
    When a new Tenant is created, automatically create a Django Group
    and assign tenant-level permissions.

    This demonstrates how you can use Django's Group model as a
    tenant-level permission container.
    """
    if created:
        group_name = f"tenant_{instance.slug}"
        group, _ = Group.objects.get_or_create(name=group_name)

        # Assign all tenant-admin permissions to this group
        for codename, model_class in TENANT_ADMIN_PERMS:
            perm = _get_or_create_perm(
                codename, codename.replace('_', ' ').title(), model_class
            )
            group.permissions.add(perm)

        instance.group = group
        instance.save(update_fields=['group'])


@receiver(post_save, sender=UserProfile)
def assign_user_to_groups(sender, instance, created, **kwargs):
    """
    When a UserProfile is saved, assign the user to the correct
    Django Groups based on their role.

    This shows the bridge between our custom role system
    and Django's built-in Group/Permission framework.
    """
    user = instance.user

    # Clear existing group memberships (except for super admins who keep all)
    if instance.role != 'super_admin':
        user.groups.clear()

    if instance.role == 'super_admin':
        # Super admins get all tenant groups + super admin status
        user.is_superuser = True
        user.is_staff = True
        user.save(update_fields=['is_superuser', 'is_staff'])
        # Add to all tenant groups
        for tenant in Tenant.objects.all():
            if tenant.group:
                user.groups.add(tenant.group)

    elif instance.role == 'tenant_admin':
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        if instance.tenant and instance.tenant.group:
            user.groups.add(instance.tenant.group)

    elif instance.role == 'account_manager':
        # Account managers get basic permissions
        if instance.tenant and instance.tenant.group:
            user.groups.add(instance.tenant.group)

    elif instance.role == 'driver':
        # Drivers get tenant group membership for their home + shared tenants
        driver = getattr(user, 'driver_profile', None)
        if driver:
            for tenant in driver.all_tenants():
                if tenant.group:
                    user.groups.add(tenant.group)


# Ensure the global role groups exist
def ensure_role_groups():
    """Create the standard role groups if they don't exist."""
    for role_code, role_name in UserProfile.ROLE_CHOICES:
        group_name = f"role_{role_code}"
        group, created = Group.objects.get_or_create(name=group_name)
        if created:
            # Assign role-specific permissions
            if role_code == 'tenant_admin':
                for codename, model_class in TENANT_ADMIN_PERMS:
                    perm = _get_or_create_perm(
                        codename, codename.replace('_', ' ').title(), model_class
                    )
                    group.permissions.add(perm)
            elif role_code == 'account_manager':
                for codename, model_class in ACCOUNT_MANAGER_PERMS:
                    perm = _get_or_create_perm(
                        codename, codename.replace('_', ' ').title(), model_class
                    )
                    group.permissions.add(perm)
            elif role_code == 'driver':
                for codename, model_class in DRIVER_PERMS:
                    perm = _get_or_create_perm(
                        codename, codename.replace('_', ' ').title(), model_class
                    )
                    group.permissions.add(perm)
